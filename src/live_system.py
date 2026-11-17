"""
live_system.py (v2 — Cloud Integrated)
---------------------------------------
النظام الحي لمراقبة مواقف السيارات مع:
  - كشف الإشغال بـ YOLO
  - إرسال حالة المواقف للـ ESP32 عبر Serial
  - رفع البيانات لـ ThingSpeak عبر HTTPS (TLS)
  - تخزين محلي SQLite عند انقطاع الإنترنت
"""

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import sys
import time
import logging

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT_DIR)

import cv2
import serial
from ultralytics import YOLO

from config.parking_spots import PARKING_SPOTS
from src.cloud_uploader import CloudUploader

try:
    from run_dashboard import start_dashboard_server
except ImportError:
    start_dashboard_server = None

# ====== إعداد Logging ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(ROOT_DIR, "parking_system.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
# Fix Windows terminal encoding
import sys
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logger = logging.getLogger(__name__)

# ====== إعداد Serial (ESP32) ======
esp = None
esp_port = None
ports_to_try = ["COM5", "COM13"]

import serial.tools.list_ports
for p in serial.tools.list_ports.comports():
    if p.device not in ports_to_try:
        ports_to_try.append(p.device)

for port in ports_to_try:
    try:
        esp = serial.Serial(port, 115200, timeout=1)
        time.sleep(2)
        esp_port = port
        logger.info(f"✅ تم الاتصال مع ESP32 بنجاح على المنفذ {port}")
        break
    except Exception:
        continue

if esp is None:
    logger.warning("⚠️ لم يتم الاتصال مع ESP على أي منفذ (وضع اختبار)")

# ====== تحميل نموذج YOLO ======
MODEL_PATH = os.path.join(ROOT_DIR, "runs", "classify", "train", "weights", "best.pt")
model = YOLO(MODEL_PATH)
logger.info(f"✅ النموذج محمّل: {MODEL_PATH}")

CONF_THRESHOLD = 0.7

# ====== إعداد Cloud Uploader ======
uploader = CloudUploader()
uploader.start()
logger.info("☁️  Cloud Uploader يعمل في الخلفية")

# ====== تشغيل الداش بورد تلقائياً في المتصفح ======
if start_dashboard_server:
    try:
        dash_url = start_dashboard_server()
        logger.info(f"🌐 تم تشغيل الداش بورد وفتحه في المتصفح: {dash_url}")
    except Exception as e:
        logger.warning(f"⚠️ يتعذر فتح الداش بورد آلياً: {e}")

# ====== فتح الكاميرا ======
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    logger.warning("⚠️ الكاميرا رقم 1 لم تفتح، جاري تجربة الكاميرا 0...")
    cap = cv2.VideoCapture(0)

if not cap.isOpened():
    logger.error("❌ تعذر فتح أي كاميرا!")
    uploader.stop()
    sys.exit(1)

logger.info("🎥 الكاميرا تعمل | اضغط ESC للخروج")

# ====== الحلقة الرئيسية ======
while True:
    ret, frame = cap.read()
    if not ret:
        logger.warning("⚠️ لم يتم قراءة إطار من الكاميرا")
        break

    parking_states = []

    for i, (x1, y1, x2, y2) in enumerate(PARKING_SPOTS):
        crop = frame[y1:y2, x1:x2]

        if crop.size == 0:
            parking_states.append(1)
            continue

        results = model(crop, verbose=False)[0]
        probs   = results.probs.data.cpu().numpy()

        class_id   = probs.argmax()
        confidence = probs[class_id]
        label      = model.names[class_id]

        occupied = 1 if (label == "occupied" and confidence >= CONF_THRESHOLD) else 0
        parking_states.append(occupied)

        color = (0, 0, 255) if occupied else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            f"P{i+1}:{label[:3].upper()} {confidence:.0%}",
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1
        )

    # ====== إرسال للـ ESP32 ======
    msg = ",".join(map(str, parking_states)) + "\n"
    logger.info(f"Serial -> {msg.strip()}")

    if esp:
        try:
            esp.write(msg.encode())
        except Exception as e:
            logger.warning(f"⚠️ خطأ في الإرسال للـ ESP: {e}")

    # ====== رفع للسحابة (ThingSpeak) ======
    uploader.send(parking_states)

    # ====== عرض حالة الاتصال والبوابة على الشاشة ======
    cloud_status = uploader.get_status()
    occupied_count = sum(parking_states)
    total_spots    = len(parking_states)
    available_spots = total_spots - occupied_count

    if occupied_count == total_spots:
        gate_text = "Gate: CLOSED (PARKING FULL)"
        gate_color = (0, 0, 255) # أحمر
    else:
        gate_text = f"Gate: OPEN ({available_spots} Spot{'s' if available_spots > 1 else ''} Free)"
        gate_color = (0, 255, 0) # أخضر

    cv2.putText(frame, cloud_status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    cv2.putText(frame, f"Occupied: {occupied_count}/{total_spots}", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, gate_text, (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.65, gate_color, 2)

    cv2.imshow("Smart Parking — Cloud Connected", frame)

    if cv2.waitKey(1) == 27:  # ESC
        break

# ====== تنظيف ======
logger.info("🛑 إيقاف النظام...")
uploader.stop()
cap.release()
cv2.destroyAllWindows()
logger.info("✅ النظام أوقف بشكل نظيف.")
