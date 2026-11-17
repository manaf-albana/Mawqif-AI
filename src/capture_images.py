import cv2
import os
from datetime import datetime

# إعداد الكاميرا
cap = cv2.VideoCapture(1)

# مجلدات الحفظ
empty_dir = "data/raw_images/empty"
occupied_dir = "data/raw_images/occupied"

os.makedirs(empty_dir, exist_ok=True)
os.makedirs(occupied_dir, exist_ok=True)

print("e : حفظ صورة موقف فاضي")
print("o : حفظ صورة موقف ممتلئ")
print("q : خروج")

img_counter = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    cv2.imshow("Capture Data", frame)
    key = cv2.waitKey(1) & 0xFF

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if key == ord('e'):
        filename = f"{empty_dir}/empty_{timestamp}_{img_counter}.jpg"
        cv2.imwrite(filename, frame)
        print(f"✔ حفظ: {filename}")
        img_counter += 1

    elif key == ord('o'):
        filename = f"{occupied_dir}/occupied_{timestamp}_{img_counter}.jpg"
        cv2.imwrite(filename, frame)
        print(f"✔ حفظ: {filename}")
        img_counter += 1

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
