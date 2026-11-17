import cv2

parking_spots = []
drawing = False
x_start, y_start = -1, -1
frozen_frame = None  # الصورة المثبتة

def normalize_box(x1, y1, x2, y2):
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

def draw_rectangle(event, x, y, flags, param):
    global x_start, y_start, drawing, parking_spots, frozen_frame

    # لا ترسم قبل تثبيت الصورة
    if frozen_frame is None:
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        x_start, y_start = x, y

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        temp = frozen_frame.copy()
        x1, y1, x2, y2 = normalize_box(x_start, y_start, x, y)
        cv2.rectangle(temp, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.imshow("Frame", temp)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x1, y1, x2, y2 = normalize_box(x_start, y_start, x, y)
        parking_spots.append((x1, y1, x2, y2))
        print(f"Spot {len(parking_spots)}: {(x1, y1, x2, y2)}")

cap = cv2.VideoCapture(1)
cv2.namedWindow("Frame")
cv2.setMouseCallback("Frame", draw_rectangle)

print("اضغط s لالتقاط وتثبيت صورة واحدة")
print("بعدها ارسم 6 مربعات (كل موقف مربع)")
print("اضغط q للخروج")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # قبل التثبيت: فيديو مباشر
    if frozen_frame is None:
        cv2.imshow("Frame", frame)
    else:
        display = frozen_frame.copy()
        for (x1, y1, x2, y2) in parking_spots:
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.imshow("Frame", display)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('s') and frozen_frame is None:
        frozen_frame = frame.copy()
        print("✔ تم تثبيت الصورة، ابدأ بتحديد المواقف")

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

print("\nانسخ هذا إلى config/parking_spots.py:\n")
print("PARKING_SPOTS = [")
for spot in parking_spots:
    print(f"    {spot},")
print("]")
