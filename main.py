import time
from machine import Pin, PWM, I2C, RTC
import ota
from lcd1602 import LCD
import network
import urequests
import ujson

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
# RTC and time settings
# -----------------------------
rtc = RTC()
# Set time if needed (year, month, day, weekday, hour, minute, second, microsecond)
# weekday: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
# For example, if today is Monday:
# rtc.datetime((2026, 3, 9, 0, 14, 30, 0, 0))  # 2026-03-09 Monday 14:30:00

# Day names
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Alternating day assignment (starting with Issa's Day for today)
# This will be set based on a reference date
REFERENCE_DATE = (2026, 3, 9)  # Year, Month, Day - today (Monday)
REFERENCE_DAY_NAME = "Idrees' Day"  # Today is Issa's Day

def get_day_assignment(current_year, current_month, current_day):
    """Calculate whose day it is based on days since reference date"""
    # Convert dates to days since epoch (simplified calculation)
    def days_since_epoch(year, month, day):
        # A simple day counter (not accounting for leap years perfectly, but close enough)
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        # Adjust for leap year (simplified)
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            month_days[1] = 29
        
        days = 0
        for y in range(1970, year):
            days += 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
        for m in range(month - 1):
            days += month_days[m]
        days += day - 1
        return days
    
    ref_days = days_since_epoch(*REFERENCE_DATE)
    current_days = days_since_epoch(current_year, current_month, current_day)
    days_diff = current_days - ref_days
    
    # If days_diff is even, it's Issa's Day, if odd, it's Idrees' Day
    if days_diff % 2 == 0:
        return "Issa's Day"
    else:
        return "Idrees' Day"

# -----------------------------
# Weather settings (free API)
# -----------------------------
# You'll need to sign up for a free API key at https://openweathermap.org/api
# or use wttr.in which doesn't require an API key
WEATHER_LOCATION = "Bolton"  # Change to your city
weather_cache = ""
weather_cache_time = 0
WEATHER_UPDATE_INTERVAL = 1800  # Update weather every 30 minutes

def get_weather():
    """Get weather from wttr.in (no API key required)"""
    global weather_cache, weather_cache_time
    
    current_time = time.time()
    if current_time - weather_cache_time < WEATHER_UPDATE_INTERVAL and weather_cache:
        return weather_cache
    
    try:
        # Connect to WiFi (you'll need your credentials)
        # This assumes you have WiFi credentials stored elsewhere
        # For now, we'll return a placeholder
        url = f"http://wttr.in/{WEATHER_LOCATION}?format=%t+%c+%w"
        response = urequests.get(url)
        if response.status_code == 200:
            weather_cache = response.text.strip()
        else:
            weather_cache = "Weather N/A"
        response.close()
        weather_cache_time = current_time
        return weather_cache
    except:
        return "Weather unavailable"

# -----------------------------
# Message screens
# -----------------------------
def get_greeting(hour, minute):
    """Get greeting based on time of day"""
    total_minutes = hour * 60 + minute
    
    if total_minutes < 1 * 60 + 1:  # 00:01 AM
        return "Good morning"
    elif total_minutes < 12 * 60:  # Before 12:00 PM
        return "Good morning"
    elif total_minutes < 17 * 60:  # 12:00 PM - 5:00 PM
        return "Good afternoon"
    elif total_minutes < 19 * 60 + 45:  # 5:00 PM - 7:45 PM
        return "Good evening"
    else:  # 7:45 PM - 12:00 AM
        return "Goodnight"

def format_time(hour, minute):
    """Format time in 12-hour format with AM/PM"""
    period = "AM" if hour < 12 else "PM"
    hour_12 = hour if hour <= 12 else hour - 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{hour_12:02d}:{minute:02d} {period}"

def get_time_based_message():
    """Get the full time-based message"""
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    
    greeting = get_greeting(hour, minute)
    time_str = format_time(hour, minute)
    
    return f"{greeting} {time_str}"

def get_date_message():
    """Get date and day assignment message"""
    now = time.localtime()
    year = now[0]
    month = now[1]
    day = now[2]
    weekday = now[6]  # 0=Monday, 6=Sunday
    
    day_name = DAY_NAMES[weekday]
    day_full = DAY_FULL[weekday]
    
    # Get whose day it is
    whose_day = get_day_assignment(year, month, day)
    
    return f"{day_name} {month:02d}/{day:02d} - {whose_day}"

def get_weather_message():
    """Get weather report"""
    weather = get_weather()
    return f"Weather: {weather}"

# -----------------------------
# Screen management
# -----------------------------
MESSAGE_SCREENS = [
    get_time_based_message,
    get_date_message,
    get_weather_message
]

SCREEN_DISPLAY_TIME = 3  # seconds per screen
SCREEN_ACTIVE_TIME = 15  # seconds before turning off LCD backlight

# -----------------------------
# Startup sequence
# -----------------------------
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

# Initial screen
lcd.clear()
lcd.puts(get_time_based_message())
lcd.goto(0, 1)
lcd.puts(get_date_message()[:16])  # Truncate if needed

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
# Screen control variables
# -----------------------------
screen_active = False
screen_start_time = 0
current_screen_index = 0
last_screen_change = 0
last_motion_time = 0
motion_cooldown = 1  # seconds to ignore repeated motion triggers

# -----------------------------
# Main loop
# -----------------------------
while True:
    current_time = time.time()
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    second = now[5]
    
    # Motion detection with cooldown
    motion_detected = pir.value() == 1
    
    if motion_detected and (current_time - last_motion_time > motion_cooldown):
        motion_led.on()
        last_motion_time = current_time
        
        # Activate screen
        if not screen_active:
            screen_active = True
            screen_start_time = current_time
            current_screen_index = 0
            last_screen_change = current_time
            
            # Turn on backlight and show first screen
            lcd.backlight(True)
            lcd.clear()
            lcd.puts(MESSAGE_SCREENS[0]()[:16])
            lcd.goto(0, 1)
            next_screen = MESSAGE_SCREENS[1]()[:16]
            lcd.puts(next_screen)
            print("Motion detected - screen activated")
        
        # Brief flash on motion LED
        time.sleep(0.1)
        motion_led.off()
    else:
        motion_led.off()
    
    # Screen management
    if screen_active:
        # Check if screen should turn off
        if current_time - screen_start_time > SCREEN_ACTIVE_TIME:
            screen_active = False
            lcd.clear()
            lcd.backlight(False)
            print("Screen deactivated")
        
        # Cycle through screens
        if current_time - last_screen_change > SCREEN_DISPLAY_TIME:
            current_screen_index = (current_screen_index + 1) % len(MESSAGE_SCREENS)
            last_screen_change = current_time
            
            # Update display with current and next screen
            lcd.clear()
            lcd.puts(MESSAGE_SCREENS[current_screen_index]()[:16])
            lcd.goto(0, 1)
            next_index = (current_screen_index + 1) % len(MESSAGE_SCREENS)
            lcd.puts(MESSAGE_SCREENS[next_index]()[:16])
    
    # Breathing LED (continues regardless of screen state)
    for duty in range(0, 65535, fade_step):
        led16.duty_u16(duty)
        time.sleep(fade_delay)
        
        # Quick motion check during breathing
        if pir.value() == 1 and (time.time() - last_motion_time > motion_cooldown):
            motion_led.on()
            last_motion_time = time.time()
            if not screen_active:
                screen_active = True
                screen_start_time = time.time()
                current_screen_index = 0
                last_screen_change = time.time()
                lcd.backlight(True)
                lcd.clear()
                lcd.puts(MESSAGE_SCREENS[0]()[:16])
                lcd.goto(0, 1)
                lcd.puts(MESSAGE_SCREENS[1]()[:16])
            time.sleep(0.1)
            motion_led.off()

    for duty in range(65535, 0, -fade_step):
        led16.duty_u16(duty)
        time.sleep(fade_delay)
        
        # Quick motion check during breathing
        if pir.value() == 1 and (time.time() - last_motion_time > motion_cooldown):
            motion_led.on()
            last_motion_time = time.time()
            if not screen_active:
                screen_active = True
                screen_start_time = time.time()
                current_screen_index = 0
                last_screen_change = time.time()
                lcd.backlight(True)
                lcd.clear()
                lcd.puts(MESSAGE_SCREENS[0]()[:16])
                lcd.goto(0, 1)
                lcd.puts(MESSAGE_SCREENS[1]()[:16])
            time.sleep(0.1)
            motion_led.off()

    # OTA update check
    if current_time - last_update_check >= UPDATE_INTERVAL:
        led17.on()
        print("Checking for updates")
        
        # Briefly show OTA status on LCD if active
        if screen_active:
            lcd.goto(0, 1)
            lcd.puts("OTA checking...")
        
        ota.check_for_update()
        
        led17.off()
        last_update_check = current_time
        
        # Restore LCD display if active
        if screen_active:
            lcd.goto(0, 1)
            lcd.puts(MESSAGE_SCREENS[(current_screen_index + 1) % len(MESSAGE_SCREENS)]()[:16])
