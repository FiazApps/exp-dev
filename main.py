import time
from machine import Pin, PWM

# GP14 - startup LED
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

# Turn GP14 on permanently when service is running
led14.on()

print("Service running")

# --- Main loop with GP16 breathing ---
while True:
    # Fade in
    for duty in range(0, 65535, 2000):
        led16.duty_u16(duty)
        time.sleep(0.02)
    # Fade out
    for duty in range(65535, 0, -2000):
        led16.duty_u16(duty)
        time.sleep(0.02)
