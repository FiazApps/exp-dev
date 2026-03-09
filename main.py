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
        # Format: temperature, weather code, wind speed
        # Using ?m for metric units (Celsius, km/h)
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
    period = "AM" if hour < 12 else "PM"
    hour_12 = hour if hour <= 12 else hour - 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{hour_12:02d}:{minute:02d}{period}"

def get_top_line():
    """Top line with greeting, time, and real weather"""
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    
    greeting = get_greeting(hour, minute)
    time_str = format_time(hour, minute)
    weather = get_cached_weather()
    
    return f"{greeting} {time_str} {weather} "

def get_bottom_line():
    """Bottom line with day, date, and assignment"""
    now = time.localtime()
    year = now[0]
    month = now[1]
    day = now[2]
    weekday = now[6]
    
    day_name = DAY_NAMES[weekday]
    whose_day = get_day_assignment(year, month, day)
    
    return f"{day_name} {month:02d}/{day:02d} {whose_day}"

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
SCREEN_TIMEOUT = 10
motion_cooldown = 1
last_motion_time = 0

# Breathing LED
breath_direction = 1
breath_value = 0
BREATH_STEP = 500
BREATH_DELAY = 0.02

# Scrolling
scroll_pos = 0
last_scroll_time = 0
SCROLL_SPEED = 0.3

# Timing
last_time_update = 0
TIME_UPDATE_INTERVAL = 1

print("Ready - wave hand to activate")

# Store current content
current_top = get_top_line()
current_bottom = get_bottom_line()

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
            lcd.backlight(True)
            lcd.clear()
            scroll_pos = 0
            print("Screen ON")
        
        time.sleep(0.05)
        motion_led.off()
    
    # Screen management
    if screen_active:
        if current_time - screen_timeout_start > SCREEN_TIMEOUT:
            screen_active = False
            lcd.clear()
            lcd.backlight(False)
            print("Screen OFF")
        
        else:
            # Update content every second
            if current_time - last_time_update >= TIME_UPDATE_INTERVAL:
                current_top = get_top_line()
                current_bottom = get_bottom_line()
                last_time_update = current_time
            
            # Scroll top line
            if time.ticks_diff(current_ms, last_scroll_time) > SCROLL_SPEED * 1000:
                display_top = current_top + "   "
                if scroll_pos >= len(display_top) - 16:
                    scroll_pos = 0
                
                visible_top = display_top[scroll_pos:scroll_pos+16]
                
                lcd.goto(0, 0)
                lcd.puts(visible_top)
                lcd.goto(0, 1)
                lcd.puts(current_bottom[:16])
                
                scroll_pos += 1
                last_scroll_time = current_ms
    
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
