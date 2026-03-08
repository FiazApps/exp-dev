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

# GP17 - OTA update indicator
led17 = Pin(17, Pin.OUT)

# GP19 - motion detected LED
motion_led = Pin(19, Pin.OUT)

# PIR motion sensor input
pir = Pin(18, Pin.IN)

print("Runtime started")

# Flash GP14 5 times at startup
for i in range(5):
    led14.on()
    time.sleep(0.3)
    led14.off()
    time.sleep(0.3)

led14.on()
print("Service running")

# -----------------------------
# OTA update settings
# -----------------------------
UPDATE_INTERVAL = 600
last_update_check = time.time()

# -----------------------------
# breathing settings
# -----------------------------
fade_step = 2000
fade_delay = 0.02

# -----------------------------
# Main loop
# -----------------------------
while True:

    # Motion detection
    if pir.value() == 1:
        motion_led.on()
        print("Motion detected")
    else:
        motion_led.off()

    # Breathing LED
    for duty in range(0, 65535, fade_step):
        led16.duty_u16(duty)
        time.sleep(fade_delay)

    for duty in range(65535, 0, -fade_step):
        led16.duty_u16(duty)
        time.sleep(fade_delay)

    # OTA update check
    current_time = time.time()
    if current_time - last_update_check >= UPDATE_INTERVAL:

        led17.on()
        print("Checking for updates")

        ota.check_for_update()

        led17.off()

        last_update_check = current_time
