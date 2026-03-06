import time
from machine import Pin, PWM
import ota

# -----------------------------
# LED setup
# -----------------------------

# GP14 - startup/service LED
led14 = Pin(14, Pin.OUT)

# GP16 - breathing LED
led16 = PWM(Pin(16))
led16.freq(1000)

print("Runtime started")

# Flash GP14 5 times to indicate startup
for i in range(5):
    led14.on()
    time.sleep(0.3)
    led14.off()
    time.sleep(0.3)

# Turn GP14 solid ON when service is running
led14.on()
print("Service running")

# -----------------------------
# Periodic OTA update settings
# -----------------------------
UPDATE_INTERVAL = 60 * 2  # seconds (2 minutes)
last_update_check = time.time()  # track last update check

# -----------------------------
# Main loop
# -----------------------------
while True:
    # Breathing LED on GP16
    for duty in range(0, 65535, 2000):
        led16.duty_u16(duty)
        time.sleep(0.02)
    for duty in range(65535, 0, -2000):
        led16.duty_u16(duty)
        time.sleep(0.02)

    # Check if it's time to run the OTA update check
    current_time = time.time()
    if current_time - last_update_check >= UPDATE_INTERVAL:
        ota.check_for_update()  # GP15 will flash if update activity occurs
        last_update_check = current_time
