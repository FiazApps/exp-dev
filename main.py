import time
from machine import Pin, PWM, I2C
import ota
from lcd1602 import LCD  # Make sure lcd1602.py is on your Pico

# -----------------------------
# LCD setup (I2C)
# -----------------------------
# Initialize I2C for LCD (using GP20/SDA and GP21/SCL)
i2c = I2C(0, sda=Pin(20), scl=Pin(21), freq=100000)

# Initialize LCD at address 0x27 with backlight on
lcd = LCD(i2c, addr=0x27, bl=1)

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
lcd.clear()
lcd.puts("System starting...")
lcd.goto(0, 1)
lcd.puts("Pico W ready")

# Flash GP14 5 times at startup
for i in range(5):
    led14.on()
    time.sleep(0.3)
    led14.off()
    time.sleep(0.3)

led14.on()
print("Service running")
lcd.clear()
lcd.puts("Service running")
lcd.goto(0, 1)
lcd.puts("No motion")

# -----------------------------
# OTA update settings
# -----------------------------
UPDATE_INTERVAL = 120
last_update_check = time.time()

# -----------------------------
# breathing settings
# -----------------------------
fade_step = 2000
fade_delay = 0.02

# -----------------------------
# LCD update tracking
# -----------------------------
last_motion_state = 0
motion_count = 0
last_lcd_update = time.time()
LCD_UPDATE_INTERVAL = 0.5  # Update LCD display every 0.5 seconds

# -----------------------------
# Main loop
# -----------------------------
while True:
    current_time = time.time()
    
    # Motion detection
    motion_detected = pir.value() == 1
    
    if motion_detected:
        motion_led.on()
        if last_motion_state == 0:  # Motion just started
            motion_count += 1
            print(f"Motion detected! Count: {motion_count}")
        last_motion_state = 1
    else:
        motion_led.off()
        last_motion_state = 0

    # Breathing LED (non-blocking approach - runs continuously)
    for duty in range(0, 65535, fade_step):
        led16.duty_u16(duty)
        time.sleep(fade_delay)
        
        # Check motion during breathing cycle
        if pir.value() == 1:
            motion_led.on()
            if last_motion_state == 0:
                motion_count += 1
                print(f"Motion detected! Count: {motion_count}")
            last_motion_state = 1
        else:
            motion_led.off()
            last_motion_state = 0
            
        # Update LCD periodically (non-blocking)
        if current_time - last_lcd_update >= LCD_UPDATE_INTERVAL:
            lcd.goto(0, 0)
            lcd.puts(f"Motion:{motion_count}")
            lcd.goto(8, 0)
            lcd.puts(" " * 8)  # Clear rest of line
            lcd.goto(8, 0)
            
            if motion_detected:
                lcd.puts("ACTIVE ")
            else:
                lcd.puts("IDLE   ")
                
            lcd.goto(0, 1)
            # Show time since last update or OTA status
            mins = int(current_time / 60) % 60
            secs = int(current_time % 60)
            lcd.puts(f"Uptime:{mins:02d}:{secs:02d}")
            
            last_lcd_update = current_time

    for duty in range(65535, 0, -fade_step):
        led16.duty_u16(duty)
        time.sleep(fade_delay)
        
        # Check motion during breathing cycle
        if pir.value() == 1:
            motion_led.on()
            if last_motion_state == 0:
                motion_count += 1
                print(f"Motion detected! Count: {motion_count}")
            last_motion_state = 1
        else:
            motion_led.off()
            last_motion_state = 0
            
        # Update LCD periodically
        if current_time - last_lcd_update >= LCD_UPDATE_INTERVAL:
            lcd.goto(0, 0)
            lcd.puts(f"Motion:{motion_count}")
            lcd.goto(8, 0)
            lcd.puts(" " * 8)
            lcd.goto(8, 0)
            
            if motion_detected:
                lcd.puts("ACTIVE ")
            else:
                lcd.puts("IDLE   ")
                
            lcd.goto(0, 1)
            mins = int(current_time / 60) % 60
            secs = int(current_time % 60)
            lcd.puts(f"Uptime:{mins:02d}:{secs:02d}")
            
            last_lcd_update = current_time

    # OTA update check (outside breathing loop to run less frequently)
    if current_time - last_update_check >= UPDATE_INTERVAL:
        led17.on()
        print("Checking for updates")
        
        # Show OTA status on LCD
        lcd.goto(0, 1)
        lcd.puts("OTA checking...")
        
        ota.check_for_update()
        
        led17.off()
        last_update_check = current_time
        
        # Restore LCD display
        lcd.goto(0, 1)
        mins = int(current_time / 60) % 60
        secs = int(current_time % 60)
        lcd.puts(f"Uptime:{mins:02d}:{secs:02d}")
