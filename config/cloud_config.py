"""
cloud_config.py
---------------
تحميل إعدادات الاتصال السحابي (ThingSpeak) من ملف .env
يضمن عدم تضمين أي أسرار مباشرة في الكود.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# تحميل ملف .env من جذر المشروع
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _require(key: str) -> str:
    """يقرأ متغير البيئة أو يرفع خطأ واضح إذا كان مفقوداً."""
    value = os.getenv(key, "").strip()
    if not value or value.startswith("YOUR_"):
        raise EnvironmentError(
            f"\n[!] المتغير '{key}' غير مضبوط في ملف .env\n"
            f"    افتح ملف .env وضع قيمة حقيقية بدلاً من 'YOUR_..._HERE'"
        )
    return value


# ====== إعدادات ThingSpeak ======
THINGSPEAK_BASE_URL  = "https://api.thingspeak.com"
THINGSPEAK_WRITE_URL = f"{THINGSPEAK_BASE_URL}/update"

# يتم قراءتها عند الاستدعاء الفعلي، ليس عند الاستيراد
def get_write_api_key() -> str:
    return _require("THINGSPEAK_WRITE_API_KEY")

def get_channel_id() -> str:
    return _require("THINGSPEAK_CHANNEL_ID")

def get_read_api_key() -> str:
    return os.getenv("THINGSPEAK_READ_API_KEY", "")


# ====== إعدادات النظام ======
UPDATE_INTERVAL: int = int(os.getenv("UPDATE_INTERVAL_SECONDS", "15"))
MAX_RETRY_QUEUE: int = int(os.getenv("MAX_RETRY_QUEUE_SIZE", "500"))

# ====== TLS Verification ======
# True = التحقق من شهادة SSL (موصى به في الإنتاج)
TLS_VERIFY: bool = True
