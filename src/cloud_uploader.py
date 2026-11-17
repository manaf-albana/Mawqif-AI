"""
cloud_uploader.py
-----------------
وحدة الرفع السحابي إلى ThingSpeak عبر HTTPS (TLS مضمون).

المميزات:
    - إرسال فوري عند توفر الإنترنت
    - تخزين محلي (SQLite) عند الانقطاع
    - خيط خلفي (Background Thread) يعيد الإرسال تلقائياً
    - Exponential Backoff لتجنب إغراق الشبكة
    - حد أدنى 15 ثانية بين الإرسالات (ThingSpeak Free limit)

الاستخدام:
    from src.cloud_uploader import CloudUploader
    uploader = CloudUploader()
    uploader.start()
    uploader.send(states=[1, 0, 1, 0])
    uploader.stop()
"""

import os
import sys
import time
import logging
import threading
import requests
from typing import List, Optional

# إضافة مسار جذر المشروع
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT_DIR)

from config.cloud_config import (
    THINGSPEAK_WRITE_URL,
    get_write_api_key,
    UPDATE_INTERVAL,
    MAX_RETRY_QUEUE,
    TLS_VERIFY,
)
from src.local_cache import init_db, save_reading, get_unsynced, mark_synced, get_stats

logger = logging.getLogger(__name__)


class CloudUploader:
    """
    مُرسل سحابي متكامل مع دعم الاستمرارية وإعادة المحاولة.
    """

    def __init__(self):
        init_db()                        # تأكد من وجود قاعدة البيانات
        self._api_key: Optional[str] = None
        self._last_send_time: float = 0.0
        self._connected: bool = False
        self._stop_event = threading.Event()
        self._retry_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # محاولة تحميل API Key مبكراً (لكشف الخطأ قبل التشغيل)
        try:
            self._api_key = get_write_api_key()
            logger.info("🔑 API Key محمّل بنجاح من .env")
        except EnvironmentError as e:
            logger.warning(str(e))
            logger.warning("⚠️  سيعمل النظام في وضع 'محلي فقط' (لا إرسال سحابي)")

    # ──────────────────────────────────────────────
    # واجهة عامة
    # ──────────────────────────────────────────────

    def start(self) -> None:
        """تشغيل خيط إعادة الإرسال في الخلفية."""
        if not self._api_key:
            return
        self._stop_event.clear()
        self._retry_thread = threading.Thread(
            target=self._retry_loop,
            daemon=True,
            name="CloudRetryThread"
        )
        self._retry_thread.start()
        logger.info("🚀 خيط إعادة الإرسال يعمل في الخلفية")

    def stop(self) -> None:
        """إيقاف الخيط الخلفي بشكل نظيف."""
        self._stop_event.set()
        if self._retry_thread and self._retry_thread.is_alive():
            self._retry_thread.join(timeout=5)
        logger.info("⛔ CloudUploader أوقف.")

    def send(self, states: List[int]) -> bool:
        """
        إرسال حالة المواقف للسحابة بنظام Store-and-Forward:
        - التحقق من انقضاء مهلة UPDATE_INTERVAL لتفادي إغراق قاعدة البيانات والشبكة
        - حفظ القراءة محلياً في SQLite كـ (synced=0)
        - إرسال البيانات لـ ThingSpeak
        - في حال النجاح، يُعلّم هذا السجل تحديداً كـ (synced=1)
        - في حال الفشل، يبقى السجل (synced=0) ليتولى الخيط الخلفي إعادة إرساله

        Args:
            states: قائمة [0/1] لكل موقف

        Returns:
            True إذا نجح الإرسال الفوري، False إذا خُزّن في قائمة الانتظار المحلية
        """
        # 1. تحقق من انقضاء المدة الدنيا بين الإرسالات السحابية
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._last_send_time
            if elapsed < UPDATE_INTERVAL:
                return False
            self._last_send_time = now

        # 2. حفظ القراءة الدورية في SQLite
        row_id = save_reading(states)

        # 3. إذا لم يتوفر مفتاح API، تبقى القراءة محفوظة محلياً
        if not self._api_key:
            return False

        # 4. إرسال فوري وتحديث حالة المزامنة بدقة
        ok = self._upload_to_thingspeak(states)
        if ok:
            mark_synced([row_id])
            return True
        return False

    @property
    def is_connected(self) -> bool:
        """حالة الاتصال الأخيرة (للعرض في OpenCV)."""
        return self._connected

    def get_status(self) -> str:
        """نص حالة للعرض على الشاشة."""
        if not self._api_key:
            return "Cloud: OFF (no API key)"
        stats = get_stats()
        pending = stats.get("pending", 0)
        icon = "🟢" if self._connected else "🔴"
        return f"{icon} Cloud | Pending: {pending}"

    # ──────────────────────────────────────────────
    # منطق داخلي
    # ──────────────────────────────────────────────

    def _build_payload(self, states: List[int]) -> dict:
        """بناء payload لـ ThingSpeak من حالات المواقف."""
        padded   = (states + [1, 1, 1, 1])[:4]
        occupied  = sum(padded)
        occupancy = round((occupied / 4) * 100, 1)
        return {
            "api_key":  self._api_key,
            "field1":   padded[0],
            "field2":   padded[1],
            "field3":   padded[2],
            "field4":   padded[3],
            "field5":   occupied,
            "field6":   occupancy,
        }

    def _upload_to_thingspeak(self, states: List[int]) -> bool:
        """
        إرسال HTTP POST واحد إلى ThingSpeak.

        يستخدم requests مع verify=TLS_VERIFY للتحقق من شهادة TLS.
        """
        payload = self._build_payload(states)
        try:
            resp = requests.post(
                THINGSPEAK_WRITE_URL,
                params=payload,
                timeout=10,
                verify=TLS_VERIFY     # ← TLS verification
            )
            if resp.status_code == 200 and resp.text.strip() != "0":
                self._connected = True
                logger.info(f"☁️  ThingSpeak ← entry_id={resp.text.strip()}")
                return True
            else:
                logger.warning(f"⚠️  ThingSpeak رفض الإرسال: {resp.status_code} | {resp.text}")
                self._connected = False
                return False
        except requests.exceptions.SSLError as e:
            logger.error(f"❌ خطأ TLS: {e}")
            self._connected = False
            return False
        except requests.exceptions.ConnectionError:
            self._connected = False
            logger.warning("🔌 انقطاع الإنترنت — البيانات محفوظة محلياً")
            return False
        except requests.exceptions.Timeout:
            self._connected = False
            logger.warning("⏱️  انتهت مهلة الاتصال — البيانات محفوظة محلياً")
            return False

    def _retry_loop(self) -> None:
        """
        خيط خلفي: يفحص كل 60 ثانية ويرسل السجلات المعلّقة.
        يستخدم Exponential Backoff عند فشل متكرر.
        """
        backoff = 60        # ثانية
        max_backoff = 900   # 15 دقيقة
        logger.info(f"🔁 خيط الإعادة بدأ (فحص كل {backoff}s)")

        while not self._stop_event.wait(backoff):
            pending = get_unsynced(limit=50)
            if not pending:
                backoff = 60  # إعادة الضبط
                continue

            logger.info(f"🔁 محاولة إرسال {len(pending)} سجل معلّق...")
            success_ids = []

            for record in pending:
                states = [
                    record["spot1"], record["spot2"],
                    record["spot3"], record["spot4"]
                ]
                ok = self._upload_to_thingspeak(states)
                if ok:
                    success_ids.append(record["id"])
                else:
                    break  # فشل → توقف عن باقي الدفعة
                time.sleep(UPDATE_INTERVAL)  # احترام حد ThingSpeak

            if success_ids:
                mark_synced(success_ids)
                logger.info(f"✅ أُرسل {len(success_ids)} سجل معلّق")
                backoff = 60
            else:
                # Exponential Backoff
                backoff = min(backoff * 2, max_backoff)
                logger.warning(f"⚠️  فشل الإعادة — التالي بعد {backoff}s")

        logger.info("⛔ خيط الإعادة أوقف.")


# ──────────────────────────────────────────────
# اختبار مباشر (python src/cloud_uploader.py --test)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="اختبار CloudUploader")
    parser.add_argument("--test", action="store_true",
                        help="اختبار الاتصال بـ ThingSpeak")
    args = parser.parse_args()

    uploader = CloudUploader()

    if args.test:
        print("\n=== اختبار الاتصال بـ ThingSpeak ===")
        test_states = [1, 0, 1, 0]   # موقفان مشغولان
        uploader.start()
        result = uploader._upload_to_thingspeak(test_states)
        print(f"النتيجة: {'✅ نجح الإرسال' if result else '❌ فشل (تحقق من API Key في .env)'}")
        stats = get_stats()
        print(f"إحصائيات قاعدة البيانات: {stats}")
        uploader.stop()
    else:
        print("استخدم: python src/cloud_uploader.py --test")
