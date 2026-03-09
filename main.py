import time
from machine import Pin, PWM, I2C, RTC
from lcd1602 import LCD
import network
import urequests
import ujson
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
# NTP Time Synchronization
# -----------------------------
def sync_time():
    """Get current time from NTP server"""
    try:
        # NTP server and port
        NTP_SERVER = "pool.ntp.org"
        NTP_PORT = 123
        NTP_DELTA = 2208988800  # Seconds between 1900 and 1970
        
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        
        # Send NTP request
        ntp_query = bytearray(48)
        ntp_query[0] = 0x1B
        sock.sendto(ntp_query, (NTP_SERVER, NTP_PORT))
        
        # Receive response
        msg, _ = sock.recvfrom(48)
        sock.close()
        
        # Extract time
        import struct
        t = struct.unpack("!12I", msg)[10]
        t -= NTP_DELTA
        
        # Convert to local time (UTC+0 for now - adjust for your timezone)
        tm = time.gmtime(t)
        
        # Set RTC (year, month, day, weekday, hour, minute, second, subsecond)
        # weekday: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
        rtc.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
        
        print(f"Time synchronized: {tm[3]:02d}:{tm[4]:02d}:{tm[5]:02d}")
        return True
    except Exception as e:
        print("NTP sync failed:", e)
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

# Reference date: March 9, 2026 (Monday) was Idrees' Day
# March 10, 2026 (Tuesday) is Issa's Day
REFERENCE_DATE = (2026, 3, 9)  # Year, Month, Day
REFERENCE_DAY_NAME = "Idrees' Day"  # This date was Idrees' Day

def get_day_assignment(year, month, day):
    """Calculate whose day it is based on days since reference date"""
    # Simple day counter (approximate but works for our needs)
    def days_since_ref(y, m, d):
        # Months days (non-leap year approximation)
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        # Adjust for leap year (simplified)
        if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0):
            month_days[1] = 29
        
        # Calculate days since reference
        days = 0
        # Add years
        for yr in range(REFERENCE_DATE[0], y):
            days += 366 if (yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)) else 365
        # Add months
        for mo in range(REFERENCE_DATE[1] - 1, m - 1):
            days += month_days[mo]
        # Add days
        days += d - REFERENCE_DATE[2]
        
        return days
    
    days_diff = days_since_ref(year, month, day)
    
    # If days_diff is even, it's Issa's Day, if odd, it's Idrees' Day
    if days_diff % 2 == 0:
        return "Issa's Day"
    else:
        return "Idrees' Day"

# -----------------------------
# Weather function using wttr.in
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
    
    # Sync time from NTP
    time_synced = sync_time()
    
    if time_synced:
        lcd.clear()
        lcd.puts("Time Synced!")
        now = time.localtime()
        lcd.goto(0, 1)
        lcd.puts(f"{now[3]:02d}:{now[4]:02d}:{now[5]:02d}")
    else:
        lcd.clear()
        lcd.puts("Time sync failed")
        lcd.goto(0, 1)
        lcd.puts("Using default")
else:
    lcd.clear()
    lcd.puts("WiFi Failed!")
    lcd.goto(0, 1)
    lcd.puts("Check credentials")

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

print(f"Ready - wave hand to activate (screen will stay on for {SCREEN_TIMEOUT} seconds)")

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
            lcd.puts(SCREENS[1]()[:16])  # Show next screen on line 2
            print("Screen ON - showing Time screen")
        
        time.sleep(0.05)
        motion_led.off()
    
    # Screen management
    if screen_active:
        # Check if screen should turn off after 45 seconds
        if current_time - screen_timeout_start > SCREEN_TIMEOUT:
            screen_active = False
            lcd.clear()
            lcd.backlight(False)
            print("Screen OFF - timeout")
        
        else:
            # Update content every second (for time updates)
            if current_time - last_time_update >= TIME_UPDATE_INTERVAL:
                # Only refresh screen 1 (time) every second, others stay the same
                if current_screen_index == 0:  # If showing time screen
                    lcd.goto(0, 0)
                    lcd.puts(SCREENS[0]()[:16])
                last_time_update = current_time
            
            # Cycle to next screen every SCREEN_CYCLE_TIME seconds
            if current_time - last_screen_cycle >= SCREEN_CYCLE_TIME:
                # Move to next screen
                current_screen_index = (current_screen_index + 1) % len(SCREENS)
                last_screen_cycle = current_time
                
                # Update display with new screen on line 1, next screen on line 2
                lcd.clear()
                
                # Show current screen on line 1
                line1 = SCREENS[current_screen_index]()
                lcd.puts(line1[:16])
                
                # Show next screen on line 2
                next_index = (current_screen_index + 1) % len(SCREENS)
                line2 = SCREENS[next_index]()
                lcd.goto(0, 1)
                lcd.puts(line2[:16])
                
                print(f"Screen cycled to {SCREEN_NAMES[current_screen_index]}")
    
    # OTA update check (every 2 minutes)
    if current_time - last_update_check >= UPDATE_INTERVAL:
        led17.on()
        print("Checking for OTA updates...")
        
        # Briefly show OTA status on LCD if screen is active
        if screen_active:
            # Save current screen info to restore later
            temp_line1 = line1 if 'line1' in locals() else SCREENS[current_screen_index]()
            temp_line2 = line2 if 'line2' in locals() else SCREENS[(current_screen_index + 1) % len(SCREENS)]()
            
            lcd.goto(0, 0)
            lcd.puts("OTA checking...")
            lcd.goto(0, 1)
            lcd.puts("Please wait")
        
        # Perform OTA update check
        ota.check_for_update()
        
        led17.off()
        last_update_check = current_time
        
        # Restore LCD display if screen is still active
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
