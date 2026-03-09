import time
from machine import Pin, PWM, I2C, RTC
import ota
from lcd1602 import LCD
import urequests

# -----------------------------
# LCD setup (I2C)
# -----------------------------
i2c = I2C(0, sda=Pin(20), scl=Pin(21), freq=100000)
lcd = LCD(i2c, addr=0x27, bl=1)

# -----------------------------
# LED setup
# -----------------------------
led14 = Pin(14, Pin.OUT)  # startup/service LED
led16 = PWM(Pin(16))       # breathing LED
led16.freq(1000)
led17 = Pin(17, Pin.OUT)   # OTA update indicator
motion_led = Pin(19, Pin.OUT)  # motion detected LED
pir = Pin(18, Pin.IN)      # PIR motion sensor

# -----------------------------
# Day names and assignment
# -----------------------------
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
REFERENCE_DATE = (2026, 3, 9)  # Today (Monday)

def get_day_assignment(year, month, day):
    """Simple alternating day calculation"""
    # Count days since reference (simplified)
    total_days = (year - REFERENCE_DATE[0]) * 365 + (month - REFERENCE_DATE[1]) * 30 + (day - REFERENCE_DATE[2])
    if total_days % 2 == 0:
        return "Issa's Day"
    else:
        return "Idrees' Day"

# -----------------------------
# Message generation
# -----------------------------
def get_greeting(hour, minute):
    """Get greeting based on time"""
    total_minutes = hour * 60 + minute
    
    if total_minutes < 1 * 60 + 1:  # 00:01
        return "Good morning"
    elif total_minutes < 12 * 60:   # Before 12 PM
        return "Good morning"
    elif total_minutes < 17 * 60:   # 12 PM - 5 PM
        return "Good afternoon"
    elif total_minutes < 19 * 60 + 45:  # 5 PM - 7:45 PM
        return "Good evening"
    else:                            # 7:45 PM - midnight
        return "Goodnight"

def format_time(hour, minute):
    """Format time in 12-hour format"""
    period = "AM" if hour < 12 else "PM"
    hour_12 = hour if hour <= 12 else hour - 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{hour_12:02d}:{minute:02d}{period}"

def get_top_line():
    """Get the scrolling top line (time + greeting + weather)"""
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    
    greeting = get_greeting(hour, minute)
    time_str = format_time(hour, minute)
    

# Then modify get_top_line():
def get_top_line():
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    
    greeting = get_greeting(hour, minute)
    time_str = format_time(hour, minute)
    
    # Get real weather (cache to avoid too many requests)
    global last_weather, last_weather_time
    if time.time() - last_weather_time > 1800:  # Update every 30 min
        try:
            response = urequests.get("http://wttr.in/London?format=%t+%c")
            last_weather = response.text.strip()
            response.close()
            last_weather_time = time.time()
        except:
            pass  # Keep old weather on failure
    
    return f"{greeting} {time_str} | {last_weather} | "
    
    return f"{greeting} {time_str} | {weather} | "

def get_bottom_line():
    """Get the static bottom line (day + date + assignment)"""
    now = time.localtime()
    year = now[0]
    month = now[1]
    day = now[2]
    weekday = now[6]
    
    day_name = DAY_NAMES[weekday]
    whose_day = get_day_assignment(year, month, day)
    
    return f"{day_name} {month:02d}/{day:02d} {whose_day}"

# -----------------------------
# Scrolling function
# -----------------------------
def scroll_text(lcd, text, line, start_pos=0):
    """Display a scrolling line of text"""
    # Pad with spaces to make scrolling smooth
    display_text = text + "   "  # Add padding
    if len(display_text) > 16:
        # Show a 16-character window
        if start_pos >= len(display_text) - 16:
            start_pos = 0
        visible = display_text[start_pos:start_pos+16]
    else:
        visible = display_text[:16]
    
    lcd.goto(0, line)
    lcd.puts(visible)
    return start_pos + 1  # Move scroll position

# -----------------------------
# Startup sequence
# -----------------------------
print("Runtime started")
lcd.clear()
lcd.puts("System starting...")
lcd.goto(0, 1)
lcd.puts("Pico W ready")

# Flash LED 5 times
for i in range(5):
    led14.on()
    time.sleep(0.3)
    led14.off()
    time.sleep(0.3)
led14.on()

# -----------------------------
# Screen control variables
# -----------------------------
screen_active = False
screen_off_time = 0
SCREEN_TIMEOUT = 15  # seconds
motion_cooldown = 0.5
last_motion_time = 0
scroll_position = 0
last_scroll_time = 0
SCROLL_SPEED = 0.3  # seconds per scroll step

# Get initial bottom line (doesn't change often)
current_bottom = get_bottom_line()

print("Ready - waiting for motion")

# -----------------------------
# Main loop
# -----------------------------
while True:
    current_time = time.time()
    
    # Check motion
    motion_detected = pir.value() == 1
    
    if motion_detected and (current_time - last_motion_time > motion_cooldown):
        motion_led.on()
        last_motion_time = current_time
        
        if not screen_active:
            screen_active = True
            screen_off_time = current_time + SCREEN_TIMEOUT
            lcd.backlight(True)
            lcd.clear()
            print("Screen activated")
        
        time.sleep(0.1)
        motion_led.off()
    
    # Screen management
    if screen_active:
        # Check if screen should turn off
        if current_time >= screen_off_time:
            screen_active = False
            lcd.clear()
            lcd.backlight(False)
            print("Screen deactivated")
        else:
            # Update scrolling text
            if current_time - last_scroll_time > SCROLL_SPEED:
                # Get fresh top line (updates time and greeting each scroll)
                current_top = get_top_line()
                # Update bottom line (in case day changed at midnight)
                current_bottom = get_bottom_line()
                
                # Scroll top line
                scroll_position = scroll_text(lcd, current_top, 0, scroll_position)
                
                # Show static bottom line
                lcd.goto(0, 1)
                lcd.puts(current_bottom[:16])
                
                last_scroll_time = current_time
    
    # Breathing LED (non-blocking with time checks)
    for duty in range(0, 65535, 2000):
        led16.duty_u16(duty)
        time.sleep(0.02)
        
        # Quick motion check during breathing
        if pir.value() == 1 and (time.time() - last_motion_time > motion_cooldown):
            break
    
    for duty in range(65535, 0, -2000):
        led16.duty_u16(duty)
        time.sleep(0.02)
        
        # Quick motion check during breathing
        if pir.value() == 1 and (time.time() - last_motion_time > motion_cooldown):
            break
    
    # OTA update (every 2 minutes)
    if current_time % 120 < 1:  # Simple timer
        led17.on()
        print("OTA check")
        # ota.check_for_update()  # Uncomment when ready
        led17.off()
