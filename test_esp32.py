import serial
import time
import sys

import serial.tools.list_ports

ports_to_try = ["COM5", "COM13"]
for p in serial.tools.list_ports.comports():
    if p.device not in ports_to_try:
        ports_to_try.append(p.device)

BAUD = 115200
esp = None
PORT = None

for port in ports_to_try:
    print(f"Trying to connect to ESP32 on {port}...")
    try:
        esp = serial.Serial(port, BAUD, timeout=2)
        time.sleep(2)
        PORT = port
        print(f"SUCCESS: Connected to ESP32 on {port}!\n")
        break
    except Exception as e:
        print(f"Failed on {port}: {e}")

if esp is None:
    print("FAILED: Could not connect to ESP32 on any COM port.")
    sys.exit(1)

initial = esp.read_all().decode(errors='ignore')
if initial:
    print(f"ESP32 says: {initial.strip()}")

def test(cmd, desc):
    print(f"\n--- {desc} ---")
    print(f"Sending: {cmd}")
    esp.write((cmd + "\n").encode())
    time.sleep(1)
    ans = esp.read_all().decode(errors='ignore').strip()
    if ans:
        print(f"ESP32 response: {ans}")
    time.sleep(2)

test("0,0,0,0", "All EMPTY -> All Green LEDs ON, Servo OPEN")
test("1,0,0,0", "Spot 1 OCCUPIED -> Red LED 1 ON, Others Green")
test("1,1,1,1", "All OCCUPIED -> All Red LEDs ON, Servo CLOSING")
test("0,0,0,0", "All EMPTY again -> All Green LEDs ON, Servo OPENING")

esp.close()
print("\nDone testing.")
