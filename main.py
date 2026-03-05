import time
from machine import Pin

# Setup LED on GP14
led = Pin(14, Pin.OUT)

print("Runtime started")

# Flash LED 5 times to indicate startup
for i in range(5):
    led.on()
    time.sleep(0.3)
    led.off()
    time.sleep(0.3)

# Turn LED on permanently when service is running
led.on()

while True:
    print("Service running")
    time.sleep(5)
