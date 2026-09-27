import serial
import time

PORT = "COM12"
BAUD = 115200

print("====================================")
print("     KISANNETRA SERIAL TEST")
print("====================================")
print(f"Opening {PORT}...")

ser = serial.Serial(PORT, BAUD, timeout=2)

# Arduino resets when serial connection opens
time.sleep(2)

print("Connected!")
print("Waiting for Arduino data...\n")

try:
    while True:
        line = ser.readline().decode("utf-8", errors="replace").strip()

        if line:
            print(f"Arduino → {line}")

except KeyboardInterrupt:
    print("\nTest stopped.")

finally:
    ser.close()
    print("Serial connection closed.")