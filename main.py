import time
from machine import Pin, PWM, I2C, RTC
from lcd1602 import LCD
import network
import urequests
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
# LED setup - ALL OFF BY DEFAULT
# -----------------------------
led14 = Pin(14, Pin.OUT)
led14.off()  # Start off

led16 = PWM(Pin(16))
led16.freq(1000)
led16.duty_u16(0)  # Start off (0 duty cycle)

led17 = Pin(17, Pin.OUT)
led17.off()  # Start off

motion_led = Pin(19, Pin.OUT)
motion_led.off()  # Start off

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
    rtc = RTC()
    
    # List of time servers to try
    time_servers = [
        "http://worldtimeapi.org/api/timezone/Europe/London",
        "http://timeapi.org/utc/now",
    ]
    
    ntp_servers = ["pool.ntp.org", "time.google.com", "time.nist.gov"]
    
    # Check WiFi
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print("WiFi not connected, cannot sync time")
        return False
    
    print("Attempting time sync...")
    
    # Try HTTP APIs first
    for server in time_servers:
        try:
            print(f"Trying {server}...")
            response = urequests.get(server, timeout=5)
            if response.status_code == 200:
                data = response.json()
                response.close()
                
                # Parse based on API
                if "worldtimeapi" in server:
                    datetime_str = data['datetime']
                elif "timeapi" in server:
                    datetime_str = data
                else:
                    continue
                
                if 'T' in str(datetime_str):
                    date_part = datetime_str.split('T')[0]
                    time_part = datetime_str.split('T')[1].split('.')[0].split('+')[0].split('-')[0]
                    
                    year, month, day = map(int, date_part.split('-'))
                    hour, minute, second = map(int, time_part.split(':'))
                    
                    # Simple weekday calculation for March 2026
                    # March 9, 2026 is Monday (0)
                    weekday = 0  # Default to Monday
                    
                    rtc.datetime((year, month, day, weekday, hour, minute, second, 0))
                    print(f"Time synced: {hour:02d}:{minute:02d}:{second:02d}")
                    return True
        except Exception as e:
            print(f"HTTP sync failed: {e}")
            continue
    
    # Try NTP as fallback
    for ntp_server in ntp_servers:
        try:
            print(f"Trying NTP: {ntp_server}...")
            import ntptime
            ntptime.host = ntp_server
            ntptime.settime()
            
            now = time.localtime()
            year, month, day, hour, minute, second = now[0:6]
            weekday = now[6]
            
            rtc.datetime((year, month, day, weekday, hour, minute, second, 0))
            print(f"NTP sync successful")
            return True
        except Exception as e:
            print(f"NTP failed: {e}")
            continue
    
    # Default time
    print("Using default time")
    rtc.datetime((2026, 3, 9, 0, 1, 28, 0, 0))
    return False

# -----------------------------
# OTA update settings
# -----------------------------
UPDATE_INTERVAL = 120
last_update_check = time.time()

# -----------------------------
# Day names and assignment
# -----------------------------
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# March 9, 2026 (Monday) is Idrees' Day
REFERENCE_DATE = (2026, 3, 9)
REFERENCE_DAY_NAME = "Idrees' Day"

def get_day_assignment(year, month, day):
    """Calculate whose day it is"""
    def days_since_ref(y, m, d):
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0):
            month_days[1] = 29
        
        days = 0
        for yr in range(REFERENCE_DATE[0], y):
            days += 366 if (yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)) else 365
        
        start_month = REFERENCE_DATE[1] if y == REFERENCE_DATE[0] else 1
        for mo in range(start_month - 1, m - 1):
            days += month_days[mo]
        
        days += d - REFERENCE_DATE[2]
        return days
    
    days_diff = days_since_ref(year, month, day)
    
    # Even = Idrees' Day, Odd = Issa's Day
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
WEATHER_UPDATE_INTERVAL = 1800

def get_cached_weather():
    """Get weather, updating cache every 30 minutes"""
    global weather_cache, weather_cache_time
    current_time = time.time()
    
    if current_time - weather_cache_time > WEATHER_UPDATE_INTERVAL or not weather_cache:
        # Briefly turn on LED17 during weather fetch
        led17.on()
        weather_cache = get_weather()
        led17.off()
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
        
        # LED14 on during connection attempt
        led14.on()
        
        wlan.connect(SSID, PASSWORD)
        
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(f"Waiting... {timeout}")
        
        led14.off()  # Turn off after connection attempt
    
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
    
    if total_minutes < 1 * 60 + 1:
        return "Good morning"
    elif total_minutes < 12 * 60:
        return "Good morning"
    elif total_minutes < 17 * 60:
        return "Good afternoon"
    elif total_minutes < 19 * 60 + 45:
        return "Good evening"
    else:
        return "Goodnight"

def format_time(hour, minute):
    """Format time in 12-hour format"""
    period = "AM" if hour < 12 else "PM"
    hour_12 = hour if hour <= 12 else hour - 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{hour_12:02d}:{minute:02d}{period}"

# Screen 1: Greeting and Time
def get_screen1():
    """Screen 1: Greeting with time"""
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    
    greeting = get_greeting(hour, minute)
    time_str = format_time(hour, minute)
    
    return f"{greeting} {time_str}"

# Screen 2: Day and Assignment
def get_screen2():
    """Screen 2: Day, date, and whose day"""
    now = time.localtime()
    year = now[0]
    month = now[1]
    day = now[2]
    weekday = now[6]
    
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

# Connect to WiFi (LED14 on during connection)
wifi_ok = connect_wifi()

if wifi_ok:
    lcd.clear()
    lcd.puts("WiFi Connected!")
    lcd.goto(0, 1)
    lcd.puts("Syncing time...")
    
    # LED17 on during time sync
    led17.on()
    time_synced = sync_time()
    led17.off()
    
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

# Brief LED test at startup (all off afterward)
led14.on()
led17.on()
time.sleep(0.5)
led14.off()
led17.off()

# Get initial weather (LED17 on during fetch)
print("Getting initial weather...")
led17.on()
initial_weather = get_weather()
led17.off()
print("Weather:", initial_weather)

# Show current date and assignment
now = time.localtime()
print(f"Date: {now[0]}-{now[1]:02d}-{now[2]:02d}")
print(f"Day: {DAY_NAMES[now[6]]}")
whose_day = get_day_assignment(now[0], now[1], now[2])
print(f"Today: {whose_day}")

# -----------------------------
# Screen control variables
# -----------------------------
screen_active = False
screen_timeout_start = 0
SCREEN_TIMEOUT = 45
motion_cooldown = 1
last_motion_time = 0

# Screen cycling
current_screen_index = 0
last_screen_cycle = 0
SCREEN_CYCLE_TIME = 4

# Breathing LED - starts at 0 (off)
breath_direction = 1
breath_value = 0
BREATH_STEP = 500
BREATH_DELAY = 0.02
led16.duty_u16(0)  # Ensure off

# Timing
last_time_update = 0
TIME_UPDATE_INTERVAL = 1

print(f"Ready - wave hand to activate")

# -----------------------------
# Main loop
# -----------------------------
while True:
    current_time = time.time()
    current_ms = time.ticks_ms()
    
    # Motion detection
    if pir.value() == 1 and (current_time - last_motion_time > motion_cooldown):
        motion_led.on()  # Flash briefly
        last_motion_time = current_time
        
        if not screen_active:
            screen_active = True
            screen_timeout_start = current_time
            current_screen_index = 0
            last_screen_cycle = current_time
            lcd.backlight(True)
            lcd.clear()
            
            # Show first screen
            lcd.puts(SCREENS[0]()[:16])
            lcd.goto(0, 1)
            lcd.puts(SCREENS[1]()[:16])
            print("Screen ON")
        
        time.sleep(0.1)
        motion_led.off()  # Turn off after flash
    
    # Screen management
    if screen_active:
        if current_time - screen_timeout_start > SCREEN_TIMEOUT:
            screen_active = False
            lcd.clear()
            lcd.backlight(False)
            print("Screen OFF")
        
        else:
            # Update time every second
            if current_time - last_time_update >= TIME_UPDATE_INTERVAL:
                if current_screen_index == 0:
                    lcd.goto(0, 0)
                    lcd.puts(SCREENS[0]()[:16])
                last_time_update = current_time
            
            # Cycle screens
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
                
                print(f"Screen: {SCREEN_NAMES[current_screen_index]}")
    
    # OTA update check
    if current_time - last_update_check >= UPDATE_INTERVAL:
        led17.on()  # On during OTA
        print("Checking for OTA updates...")
        
        if screen_active:
            temp_line1 = line1 if 'line1' in locals() else SCREENS[current_screen_index]()
            temp_line2 = line2 if 'line2' in locals() else SCREENS[(current_screen_index + 1) % len(SCREENS)]()
            
            lcd.goto(0, 0)
            lcd.puts("OTA checking...")
            lcd.goto(0, 1)
            lcd.puts("Please wait")
        
        ota.check_for_update()
        
        led17.off()  # Off after OTA
        last_update_check = current_time
        
        if screen_active:
            lcd.clear()
            lcd.puts(temp_line1[:16])
            lcd.goto(0, 1)
            lcd.puts(temp_line2[:16])
        
        print("OTA check complete")
    
    # Breathing LED - only runs when screen is active
    if screen_active:
        breath_value += breath_direction * BREATH_STEP
        
        if breath_value >= 65535:
            breath_value = 65535
            breath_direction = -1
        elif breath_value <= 0:
            breath_value = 0
            breath_direction = 1
        
        led16.duty_u16(breath_value)
    else:
        # Ensure breathing LED is off when screen is inactive
        led16.duty_u16(0)
        breath_value = 0
        breath_direction = 1  # Reset direction for next activation
    
    time.sleep(BREATH_DELAY)
