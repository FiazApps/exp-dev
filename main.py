import time
from machine import Pin, PWM, I2C
from lcd1602 import LCD
import network
import urequests

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
motion_led = Pin(19, Pin.OUT)
pir = Pin(18, Pin.IN)

# -----------------------------
# Day names and assignment
# -----------------------------
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def get_day_assignment(year, month, day):
    """Simple alternating day calculation"""
    if day % 2 == 0:
        return "Idrees' Day"
    else:
        return "Issa's Day"

# -----------------------------
# Weather function using wttr.in
# -----------------------------
def get_weather():
    """Get real weather from wttr.in (no API key needed)"""
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

# Cache weather to avoid too many requests
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
        lcd.clear()
        lcd.puts("WiFi Connected!")
        lcd.goto(0, 1)
        lcd.puts(wlan.ifconfig()[0][:16])
        time.sleep(2)
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
    """Format time in 12-hour format"""
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

# Connect to WiFi
wifi_ok = connect_wifi()

if not wifi_ok:
    lcd.clear()
    lcd.puts("WiFi Failed!")
    lcd.goto(0, 1)
    lcd.puts("Check credentials")
    time.sleep(3)

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

# -----------------------------
# Screen control variables
# -----------------------------
screen_active = False
screen_timeout_start = 0
SCREEN_TIMEOUT = 45  # 45 seconds of screen-on time (updated!)
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

# Store current screen content
current_screen1 = get_screen1()
current_screen2 = get_screen2()
current_screen3 = get_screen3()

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
