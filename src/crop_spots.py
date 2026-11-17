import cv2
import os
import random
from config.parking_spots import PARKING_SPOTS

# مسارات الإدخال
RAW_EMPTY = "data/raw_images/empty"
RAW_OCCUPIED = "data/raw_images/occupied"

# مسارات الإخراج
TRAIN_EMPTY = "data/dataset/train/empty"
TRAIN_OCCUPIED = "data/dataset/train/occupied"
VAL_EMPTY = "data/dataset/val/empty"
VAL_OCCUPIED = "data/dataset/val/occupied"

# إنشاء المجلدات
for path in [TRAIN_EMPTY, TRAIN_OCCUPIED, VAL_EMPTY, VAL_OCCUPIED]:
    os.makedirs(path, exist_ok=True)

def process_images(input_dir, train_dir, val_dir, label):
    images = os.listdir(input_dir)
    random.shuffle(images)

    split_idx = int(0.8 * len(images))
    train_imgs = images[:split_idx]
    val_imgs = images[split_idx:]

    def crop_and_save(img_list, out_dir):
        for img_name in img_list:
            img_path = os.path.join(input_dir, img_name)
            img = cv2.imread(img_path)
            if img is None:
                continue

            h, w = img.shape[:2]

            for i, (x1, y1, x2, y2) in enumerate(PARKING_SPOTS):

                # ✅ حماية الإحداثيات داخل حدود الصورة
                x1_c = max(0, min(x1, w - 1))
                y1_c = max(0, min(y1, h - 1))
                x2_c = max(0, min(x2, w))
                y2_c = max(0, min(y2, h))

                # تجاهل القص الخاطئ
                if x2_c <= x1_c or y2_c <= y1_c:
                    continue

                crop = img[y1_c:y2_c, x1_c:x2_c]

                if crop.size == 0:
                    continue

                out_name = f"{label}_spot{i}_{img_name}"
                cv2.imwrite(os.path.join(out_dir, out_name), crop)

    crop_and_save(train_imgs, train_dir)
    crop_and_save(val_imgs, val_dir)

# تنفيذ القصّ
process_images(RAW_EMPTY, TRAIN_EMPTY, VAL_EMPTY, "empty")
process_images(RAW_OCCUPIED, TRAIN_OCCUPIED, VAL_OCCUPIED, "occupied")

print("✔ تم قصّ وفصل المواقف بنجاح (مع حماية الحدود)")
