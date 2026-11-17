from ultralytics import YOLO

# تحميل مودل تصنيف جاهز
model = YOLO("models/yolov8n-cls.pt")

# التدريب (Fine-tuning)
model.train(
    data="data/dataset",
    epochs=20,
    imgsz=224,
    batch=16,
    device="cpu"  # غيّرها إلى 0 إذا عندك GPU
)
