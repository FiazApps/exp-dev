import time
from machine import Pin, PWM, I2C, RTC
from lcd1602 import LCD
import network
import urequests
import json
import socket
import ota

# -----------------------------
# WiFi Configuration
# -----------------------------
SSID = "YourWiFiSSID"
PASSWORD = "YourWiFiPassword"

# -----------------------------
# LCD setup
# -----------------------------
i2c = I2C(0, sda=Pin(20), scl=Pin(21), freq=100000)
lcd = LCD(i2c, addr=0x27, bl=1)

# -----------------------------
# LED setup
# -----------------------------
led14 = Pin(14, Pin.OUT)
led16 = PWM(Pin(16))
led16.freq(1000)
led17 = Pin(17, Pin.OUT)  # OTA update indicator
motion_led = Pin(19, Pin.OUT)
pir = Pin(18, Pin.IN)

# -----------------------------
# RTC setup
# -----------------------------
rtc = RTC()

# -----------------------------
# Reliable Time Synchronization
# -----------------------------
def sync_time():
    """Get current time from multiple sources"""
    
    # Method 1: Try wttr.in time (they return date header)
    try:
        print("Trying time from wttr.in...")
        response = urequests.get("http://wttr.in/London?format=%t")
        if response.status_code == 200:
            # Get the date from headers
            if 'Date' in response.headers:
                date_str = response.headers['Date']
                print(f"Date header: {date_str}")
                # Parse HTTP date format: "Wed, 09 Mar 2026 01:28:45 GMT"
                # This is complex to parse, so we'll use method 2 instead
        response.close()
    except:
        pass
    
    # Method 2: Use worldtimeapi.org (very reliable)
    try:
        print("Trying worldtimeapi.org...")
        response = urequests.get("http://worldtimeapi.org/api/timezone/Europe/London")
        if response.status_code == 200:
            data = response.json()
            datetime_str = data['datetime']
            # Format: 2026-03-09T01:28:45.123456+00:00
            date_part = datetime_str.split('T')[0]
            time_part = datetime_str.split('T')[1].split('.')[0]
            
            year, month, day = map(int, date_part.split('-'))
            hour, minute, second = map(int, time_part.split(':'))
            
            # Calculate weekday (0=Monday, 6=Sunday)
            # This is a simplified calculation - worldtimeapi also provides day_of_week
            if 'day_of_week' in data:
                weekday = data['day_of_week']  # 1=Monday, 7=Sunday in their API
                weekday = weekday - 1  # Convert to 0=Monday
            else:
                # Rough calculation - for March 9, 2026 it's Monday (0)
                weekday = 0  # Default to Monday
            
            rtc.datetime((year, month, day, weekday, hour, minute, second, 0))
            print(f"Time synchronized: {hour:02d}:{minute:02d}:{second:02d}")
            return True
        response.close()
    except Exception as e:
        print("worldtimeapi failed:", e)
    
    # Method 3: Use timeapi.org (backup)
    try:
        print("Trying timeapi.org...")
        response = urequests.get("http://timeapi.org/utc/now")
        if response.status_code == 200:
            time_str = response.text.strip()
            # Format: 2026-03-09T01:28:45Z
            date_part = time_str.split('T')[0]
            time_part = time_str.split('T')[1].replace('Z', '')
            
            year, month, day = map(int, date_part.split('-'))
            hour, minute, second = map(int, time_part.split(':'))
            
            # For March 9, 2026 it's Monday (0)
            weekday = 0
            
            rtc.datetime((year, month, day, weekday, hour, minute, second, 0))
            print(f"Time synchronized via backup: {hour:02d}:{minute:02d}")
            return True
        response.close()
    except Exception as e:
        print("timeapi.org failed:", e)
    
    # Method 4: Manual set for March 9, 2026 (Idrees' Day)
    print("Using manual time for March 9, 2026")
    # March 9, 2026 is Monday (weekday 0), 1:28 AM
    rtc.datetime((2026, 3, 9, 0, 1, 28, 0, 0))  # Monday, 1:28 AM
    return False

# -----------------------------
# OTA update settings
# -----------------------------
UPDATE_INTERVAL = 120  # Check for updates every 2 minutes
last_update_check = time.time()

# -----------------------------
# Day names and assignment
# -----------------------------
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Reference date: March 9, 2026 (Monday) is Idrees' Day
# March 10, 2026 (Tuesday) is Issa's Day
REFERENCE_DATE = (2026, 3, 9)  # Year, Month, Day
REFERENCE_DAY_NAME = "Idrees' Day"  # This date is Idrees' Day

def get_day_assignment(year, month, day):
    """Calculate whose day it is based on days since reference date"""
    # Simple day counter
    def days_since_ref(y, m, d):
        # Month days
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        # Adjust for leap year
        if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0):
            month_days[1] = 29
        
        # Calculate days since reference
        days = 0
        # Add years
        for yr in range(REFERENCE_DATE[0], y):
            days += 366 if (yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)) else 365
        # Add months
        if y == REFERENCE_DATE[0]:
            start_month = REFERENCE_DATE[1]
        else:
            start_month = 1
            
        for mo in range(start_month - 1, m - 1):
            days += month_days[mo]
        # Add days
        days += d - REFERENCE_DATE[2]
        
        return days
    
    days_diff = days_since_ref(year, month, day)
    
    # If days_diff is even, it's Idrees' Day, if odd, it's Issa's Day
    if days_diff % 2 == 0:
        return "Idrees' Day"
    else:
        return "Issa's Day"

# -----------------------------
# Weather function
# -----------------------------
def get_weather():
    """Get real weather from wttr.in"""
    try:
        url = "http://wttr.in/London?format=%t+%c+%w&m"
        response = urequests.get(url)
        if response.status_code == 200:
            weather = response.text.strip()
            response.close()
            return weather
        else:
            response.close()
            return "Weather N/A"
    except Exception as e:
        print("Weather error:", e)
        return "Weather N/A"

# Cache weather
weather_cache = ""
weather_cache_time = 0
WEATHER_UPDATE_INTERVAL = 1800  # 30 minutes

def get_cached_weather():
    """Get weather, updating cache every 30 minutes"""
    global weather_cache, weather_cache_time
    current_time = time.time()
    
    if current_time - weather_cache_time > WEATHER_UPDATE_INTERVAL or not weather_cache:
        weather_cache = get_weather()
        weather_cache_time = current_time
    
    return weather_cache

# -----------------------------
# WiFi connection
# -----------------------------
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        lcd.clear()
        lcd.puts("Connecting WiFi")
        lcd.goto(0, 1)
        lcd.puts(SSID[:16])
        
        wlan.connect(SSID, PASSWORD)
        
        # Wait for connection with timeout
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(f"Waiting... {timeout}")
    
    if wlan.isconnected():
        print("WiFi connected:", wlan.ifconfig())
        return True
    else:
        print("WiFi failed")
        return False

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
    """Format time in 12-hour format with leading zeros"""
    period = "AM" if hour < 12 else "PM"
    hour_12 = hour if hour <= 12 else hour - 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{hour_12:02d}:{minute:02d}{period}"

# Screen 1: Greeting and Time
def get_screen1():
    """Screen 1: Good morning/afternoon/evening/night with time"""
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    
    greeting = get_greeting(hour, minute)
    time_str = format_time(hour, minute)
    
    return f"{greeting} {time_str}"

# Screen 2: Day and Assignment
def get_screen2():
    """Screen 2: Day of week, date, and Issa/Idrees day"""
    now = time.localtime()
    year = now[0]
    month = now[1]
    day = now[2]
    weekday = now[6]  # 0=Monday, 6=Sunday
    
    day_name = DAY_NAMES[weekday]
    whose_day = get_day_assignment(year, month, day)
    
    return f"{day_name} {month:02d}/{day:02d} {whose_day}"

# Screen 3: Weather
def get_screen3():
    """Screen 3: Current weather"""
    weather = get_cached_weather()
    return f"Weather:{weather}"

# List of screen functions
SCREENS = [get_screen1, get_screen2, get_screen3]
SCREEN_NAMES = ["Time", "Date", "Weather"]

# -----------------------------
# Startup
# -----------------------------
print("Starting up...")
lcd.clear()
lcd.puts("Starting...")
lcd.goto(0, 1)
lcd.puts("Connecting WiFi")

# Connect to WiFi
wifi_ok = connect_wifi()

if wifi_ok:
    lcd.clear()
    lcd.puts("WiFi Connected!")
    lcd.goto(0, 1)
    lcd.puts("Syncing time...")
    
    # Sync time
    time_synced = sync_time()
    
    if time_synced:
        lcd.clear()
        lcd.puts("Time Synced!")
        now = time.localtime()
        lcd.goto(0, 1)
        lcd.puts(f"{now[3]:02d}:{now[4]:02d}:{now[5]:02d}")
    else:
        lcd.clear()
        lcd.puts("Using default time")
        lcd.goto(0, 1)
        lcd.puts("Mar 9 2026 01:28")
else:
    lcd.clear()
    lcd.puts("WiFi Failed!")
    lcd.goto(0, 1)
    lcd.puts("Using default time")

time.sleep(2)

# Flash LED
for i in range(3):
    led14.on()
    time.sleep(0.2)
    led14.off()
    time.sleep(0.2)
led14.on()

# Get initial weather
print("Getting initial weather...")
initial_weather = get_cached_weather()
print("Weather:", initial_weather)

# Show current date and assignment for verification
now = time.localtime()
print(f"Current date: {now[0]}-{now[1]:02d}-{now[2]:02d}")
print(f"Day of week: {DAY_NAMES[now[6]]}")
whose_day = get_day_assignment(now[0], now[1], now[2])
print(f"Today is: {whose_day}")

# -----------------------------
# Screen control variables
# -----------------------------
screen_active = False
screen_timeout_start = 0
SCREEN_TIMEOUT = 45  # 45 seconds of screen-on time
motion_cooldown = 1
last_motion_time = 0

# Screen cycling variables
current_screen_index = 0
last_screen_cycle = 0
SCREEN_CYCLE_TIME = 4  # seconds per screen

# Breathing LED
breath_direction = 1
breath_value = 0
BREATH_STEP = 500
BREATH_DELAY = 0.02

# Timing
last_time_update = 0
TIME_UPDATE_INTERVAL = 1  # update time every second

print(f"Ready - wave hand to activate")

# -----------------------------
# Main loop
# -----------------------------
while True:
    current_time = time.time()
    current_ms = time.ticks_ms()
    
    # Motion detection
    if pir.value() == 1 and (current_time - last_motion_time > motion_cooldown):
        motion_led.on()
        last_motion_time = current_time
        
        if not screen_active:
            screen_active = True
            screen_timeout_start = current_time
            current_screen_index = 0
            last_screen_cycle = current_time
            lcd.backlight(True)
            lcd.clear()
            
            # Show first screen immediately
            lcd.puts(SCREENS[0]()[:16])
            lcd.goto(0, 1)
            lcd.puts(SCREENS[1]()[:16])
            print("Screen ON")
        
        time.sleep(0.05)
        motion_led.off()
    
    # Screen management
    if screen_active:
        # Check if screen should turn off after 45 seconds
        if current_time - screen_timeout_start > SCREEN_TIMEOUT:
            screen_active = False
            lcd.clear()
            lcd.backlight(False)
            print("Screen OFF")
        
        else:
            # Update content every second (for time updates)
            if current_time - last_time_update >= TIME_UPDATE_INTERVAL:
                # Only refresh screen 1 (time) every second
                if current_screen_index == 0:
                    lcd.goto(0, 0)
                    lcd.puts(SCREENS[0]()[:16])
                last_time_update = current_time
            
            # Cycle to next screen every SCREEN_CYCLE_TIME seconds
            if current_time - last_screen_cycle >= SCREEN_CYCLE_TIME:
                current_screen_index = (current_screen_index + 1) % len(SCREENS)
                last_screen_cycle = current_time
                
                lcd.clear()
                line1 = SCREENS[current_screen_index]()
                lcd.puts(line1[:16])
                
                next_index = (current_screen_index + 1) % len(SCREENS)
                line2 = SCREENS[next_index]()
                lcd.goto(0, 1)
                lcd.puts(line2[:16])
                
                print(f"Screen cycled to {SCREEN_NAMES[current_screen_index]}")
    
    # OTA update check
    if current_time - last_update_check >= UPDATE_INTERVAL:
        led17.on()
        print("Checking for OTA updates...")
        
        if screen_active:
            temp_line1 = line1 if 'line1' in locals() else SCREENS[current_screen_index]()
            temp_line2 = line2 if 'line2' in locals() else SCREENS[(current_screen_index + 1) % len(SCREENS)]()
            
            lcd.goto(0, 0)
            lcd.puts("OTA checking...")
            lcd.goto(0, 1)
            lcd.puts("Please wait")
        
        ota.check_for_update()
        
        led17.off()
        last_update_check = current_time
        
        if screen_active:
            lcd.clear()
            lcd.puts(temp_line1[:16])
            lcd.goto(0, 1)
            lcd.puts(temp_line2[:16])
        
        print("OTA check complete")
    
    # Breathing LED
    breath_value += breath_direction * BREATH_STEP
    
    if breath_value >= 65535:
        breath_value = 65535
        breath_direction = -1
    elif breath_value <= 0:
        breath_value = 0
        breath_direction = 1
    
    led16.duty_u16(breath_value)
    time.sleep(BREATH_DELAY)
