#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import math
import board
import digitalio
import serial
import threading
import traceback
import subprocess
from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import ili9341

# Попробуем импортировать библиотеку для I2C дисплея
try:
    import adafruit_ssd1306
    I2C_DISPLAY_AVAILABLE = True
    print("Библиотека для I2C дисплея доступна")
except ImportError:
    I2C_DISPLAY_AVAILABLE = False
    print("Библиотека для I2C дисплея недоступна")

# Настройка GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Настройка дисплея ILI9341
cs_pin = digitalio.DigitalInOut(board.CE0)
dc_pin = digitalio.DigitalInOut(board.D24)
reset_pin = digitalio.DigitalInOut(board.D25)
BAUDRATE = 24000000

# Инициализация SPI
spi = board.SPI()

# Инициализация дисплея
try:
    disp = ili9341.ILI9341(
        spi,
        rotation=90,
        cs=cs_pin,
        dc=dc_pin,
        rst=reset_pin,
        baudrate=BAUDRATE,
        width=240,
        height=320,
    )
    print("Дисплей инициализирован успешно")
except Exception as e:
    print(f"Ошибка инициализации дисплея: {e}")
    print(traceback.format_exc())
    exit(1)

# Инициализация I2C дисплея (если доступен)
i2c_display = None
if I2C_DISPLAY_AVAILABLE:
    try:
        # Создаем I2C интерфейс
        i2c = board.I2C()
        
        # Создаем дисплей SSD1306 I2C (128x64)
        i2c_display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
        
        # Очищаем дисплей
        i2c_display.fill(0)
        i2c_display.show()
        
        print("I2C дисплей инициализирован успешно")
    except Exception as e:
        print(f"Ошибка инициализации I2C дисплея: {e}")
        print(traceback.format_exc())
        i2c_display = None

# Настройка UART для ESP32
def setup_uart():
    uart_ports = ['/dev/serial0', '/dev/ttyAMA0', '/dev/ttyS0']
    esp32 = None
    
    for port in uart_ports:
        try:
            esp32 = serial.Serial(port, 9600, timeout=0.1)
            print(f"UART для ESP32 инициализирован на порту {port}")
            return esp32
        except Exception as e:
            print(f"Не удалось открыть порт {port}: {e}")
            continue
    
    print("Не удалось найти подходящий UART порт для ESP32")
    return None

# Инициализация UART
esp32 = setup_uart()

# --- НОВЫЕ ПИНЫ ДЛЯ VRX1 (SPI) ---
VRX1_SPI_CS = 6      # бывший CH_UP VRX1
VRX1_SPI_MOSI = 7    # свободный
VRX1_SPI_SCLK = 16   # свободный

# --- НОВЫЕ ПИНЫ ДЛЯ VRX4 (параллельные) ---
VRX4_CS_PINS = [5, 12, 13]   # 5,12 бывшие кнопки VRX4, 13 бывший CH_DOWN VRX1
VRX4_S_PINS = [18, 0, 1]     # свободные

# Полная частотная сетка для VRX1 (5.8GHz, 96 каналов) из 5.8.ino
VRX1_CHANNELS = [
    # A
    5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600,
    # B
    5362, 5399, 5436, 5473, 5500, 5547, 5584, 5621,
    # E
    5300, 5348, 5366, 5384, 5400, 5420, 5438, 5456,
    # F
    5129, 5159, 5189, 5219, 5249, 5279, 5309, 5339,
    # R
    4990, 5020, 5050, 5080, 5110, 5150, 5170, 5200,
    # P
    5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613,
    # L
    4875, 4884, 4900, 4858, 4995, 5032, 5069, 5099,
    # U
    5960, 5980, 6000, 6020, 6030, 6040, 6050, 6060,
    # O
    5865, 5845, 5825, 5805, 5785, 5765, 5745, 5735,
    # H
    5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866,
    # T
    5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945,
    # N
    5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880
]

# Полная частотная сетка для VRX4 (3.3GHz, 64 канала) из 3.3.ino
VRX4_CHANNELS = [
    # FR1
    3360, 3380, 3400, 3420, 3440, 3460, 3480, 3500,
    # FR2
    3200, 3220, 3240, 3260, 3280, 3300, 3320, 3340,
    # FR3
    3330, 3350, 3370, 3390, 3410, 3430, 3450, 3470,
    # FR4
    3170, 3190, 3210, 3230, 3250, 3270, 3290, 3310,
    # FR5
    3320, 3345, 3370, 3395, 3420, 3445, 3470, 3495,
    # FR6
    3310, 3330, 3355, 3380, 3405, 3430, 3455, 3480,
    # FR7
    3220, 3240, 3260, 3280, 3300, 3320, 3340, 3360,
    # FR8
    3060, 3080, 3100, 3120, 3140, 3160, 3180, 3200
]

# Конфигурация VRX с обновлёнными параметрами для VRX1 и VRX4
VRX_CONFIG = {
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 2,
        # Больше нет control_pins, вместо них SPI параметры
        'spi_cs': VRX1_SPI_CS,
        'spi_mosi': VRX1_SPI_MOSI,
        'spi_sclk': VRX1_SPI_SCLK,
        'channels': VRX1_CHANNELS
    },
    'VRX2': {
        'type': '1.2GHz',
        'power_pin': 3,
        'control_pins': {'CH_UP': 19, 'CH_DOWN': 26},
        'channels': [
            1010, 1040, 1080, 1120, 1160, 1200, 1240,
            1280, 1320, 1360, 1258, 1100, 1140
        ]
    },
    'VRX3': {
        'type': '1.5GHz',
        'power_pin': 4,
        'control_pins': {'CH_UP': 21, 'CH_DOWN': 20},
        'channels': [
            1405, 1430, 1455, 1480, 1505, 1530, 1555,
            1580, 1605, 1630, 1655, 1680
        ]
    },
    'VRX4': {
        'type': '3.3GHz',
        'power_pin': 17,
        # Вместо control_pins используем параллельные шины
        'cs_pins': VRX4_CS_PINS,
        's_pins': VRX4_S_PINS,
        'channels': VRX4_CHANNELS
    }
}

# Кнопки управления
BTN_SELECT = 27     # Выбор VRX/подтверждение
BTN_UP = 22         # Переключение канала вверх
BTN_DOWN = 23       # Переключение канала вниз

# Текущее состояние
current_vrx = 'VRX1'
channel_states = {
    'VRX1': {'channel': 0},
    'VRX2': {'channel': 0},
    'VRX3': {'channel': 0},
    'VRX4': {'channel': 0},
}
app_state = "vrx_select"  # Начинаем с выбора VRX
VERSION = "2.0"
rssi_value = 0
autosearch_active = False
active_vrx = None  # Текущий активный VRX

# Функция для получения размеров дисплея
def get_display_dimensions():
    if disp.rotation % 180 == 90:
        return disp.height, disp.width
    else:
        return disp.width, disp.height

# Функция для создания изображения
def create_display_image():
    width, height = get_display_dimensions()
    return Image.new("RGB", (width, height)), width, height

# Функция для обновления I2C дисплея (без изменений)
def update_i2c_display():
    if not i2c_display:
        return
    
    try:
        image = Image.new("1", (i2c_display.width, i2c_display.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, i2c_display.width, i2c_display.height), outline=0, fill=0)
        font = ImageFont.load_default()
        
        if app_state == "main" and current_vrx == "VRX1":
            config = VRX_CONFIG[current_vrx]
            state = channel_states[current_vrx]
            freq = config['channels'][state['channel']]
            draw.text((0, 0), "VRX1 (5.8GHz)", font=font, fill=255)
            draw.text((0, 16), f"Freq: {freq} MHz", font=font, fill=255)
            draw.text((0, 32), f"RSSI: {rssi_value}", font=font, fill=255)
            if autosearch_active:
                draw.text((0, 48), "Auto Search", font=font, fill=255)
        else:
            draw.text((0, 0), "VRX System", font=font, fill=255)
            draw.text((0, 16), "Select VRX1", font=font, fill=255)
            draw.text((0, 32), "for I2C display", font=font, fill=255)
        
        i2c_display.image(image)
        i2c_display.show()
        
    except Exception as e:
        print(f"Ошибка обновления I2C дисплея: {e}")
        print(traceback.format_exc())

# Функция для управления питанием VRX (инвертированная логика)
def set_vrx_power(vrx, power_on):
    config = VRX_CONFIG[vrx]
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)
    status = "ВКЛ" if power_on else "ВЫКЛ"
    print(f"{vrx} питание: {status} (пин: {config['power_pin']}, состояние: {'LOW' if power_on else 'HIGH'})")
    
    # При выключении сбрасываем управляющие линии для VRX1 и VRX4
    if not power_on:
        if vrx == 'VRX1':
            GPIO.output(config['spi_cs'], GPIO.HIGH)
            GPIO.output(config['spi_mosi'], GPIO.LOW)
            GPIO.output(config['spi_sclk'], GPIO.LOW)
        elif vrx == 'VRX4':
            for pin in config['cs_pins'] + config['s_pins']:
                GPIO.output(pin, GPIO.LOW)

# Функция для сброса каналов VRX
def reset_vrx_channels(vrx):
    channel_states[vrx]['channel'] = 0
    print(f"{vrx}: канал сброшен на 0")

# Функции прямого управления VRX1 и VRX4
def software_spi_write(data, cs_pin, mosi_pin, sclk_pin):
    """Отправка данных через программный SPI (LSB first, mode 0)"""
    GPIO.output(cs_pin, GPIO.LOW)
    for byte in data:
        for bit in range(8):  # LSB first
            val = (byte >> bit) & 1
            GPIO.output(mosi_pin, val)
            GPIO.output(sclk_pin, GPIO.HIGH)
            time.sleep(0.000001)
            GPIO.output(sclk_pin, GPIO.LOW)
            time.sleep(0.000001)
    GPIO.output(cs_pin, GPIO.HIGH)

def set_vrx1_channel(channel_index):
    """Установка частоты VRX1 через SPI (RX5808)"""
    config = VRX_CONFIG['VRX1']
    freq = config['channels'][channel_index]
    # Формула из 5.8.ino
    N = (freq - 479) // 2
    Nhigh = N >> 5
    Nlow = N & 0x1F
    data0 = Nlow * 32 + 17
    data1 = Nhigh * 16 + Nlow // 8
    data2 = Nhigh // 16
    data3 = 0
    data = [data0, data1, data2, data3]
    software_spi_write(data, config['spi_cs'], config['spi_mosi'], config['spi_sclk'])
    print(f"VRX1 установлена частота {freq} МГц (канал {channel_index+1})")

def set_vrx4_channel(channel_index):
    """Установка канала VRX4 через параллельные пины CS и S"""
    config = VRX_CONFIG['VRX4']
    band = channel_index // 8
    ch_in_band = channel_index % 8
    cs_pins = config['cs_pins']
    s_pins = config['s_pins']
    
    # Устанавливаем CS (биты номера канала в бэнде)
    for i in range(3):
        bit = (ch_in_band >> i) & 1
        GPIO.output(cs_pins[i], GPIO.HIGH if bit else GPIO.LOW)
    # Устанавливаем S (биты номера бэнда)
    for i in range(3):
        bit = (band >> i) & 1
        GPIO.output(s_pins[i], GPIO.HIGH if bit else GPIO.LOW)
    
    freq = config['channels'][channel_index]
    print(f"VRX4 установлен канал {channel_index+1} (band {band+1}, ch {ch_in_band+1}) частота {freq} МГц")

def apply_current_channel(vrx):
    """Применить текущий сохранённый канал к VRX (после включения питания)"""
    state = channel_states[vrx]
    if vrx == 'VRX1':
        set_vrx1_channel(state['channel'])
    elif vrx == 'VRX4':
        set_vrx4_channel(state['channel'])
    # Для VRX2, VRX3 канал остаётся аппаратно запомненным, ничего не делаем

# Функция для отображения экрана выбора VRX (без изменений)
def show_vrx_selection():
    try:
        image, width, height = create_display_image()
        draw = ImageDraw.Draw(image)
        
        draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
        
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        title = "ВЫБОР VRX"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))
        
        vrx_list = list(VRX_CONFIG.keys())
        y_pos = 60
        for i, vrx in enumerate(vrx_list):
            config = VRX_CONFIG[vrx]
            color = (0, 255, 0) if vrx == current_vrx else (255, 255, 255)
            text = f"{vrx} ({config['type']})"
            draw.text((width//2 - 100, y_pos), text, font=font_medium, fill=color)
            y_pos += 30
        
        instruction = "SELECT: выбрать  UP/DOWN: переключение"
        instr_width = draw.textlength(instruction, font=font_small)
        draw.text((width//2 - instr_width//2, height - 30), instruction, font=font_small, fill=(200, 200, 200))
        
        disp.image(image)
        
    except Exception as e:
        print(f"Ошибка отображения выбора VRX: {e}")
        print(traceback.format_exc())
    
    update_i2c_display()

# Функция для отображения основного экрана (без изменений)
def show_main_screen():
    try:
        image, width, height = create_display_image()
        draw = ImageDraw.Draw(image)
        
        draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
        
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        vrx_type = VRX_CONFIG[current_vrx]['type']
        title = f"{current_vrx} ({vrx_type})"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))
        
        config = VRX_CONFIG[current_vrx]
        state = channel_states[current_vrx]
        
        if state['channel'] >= len(config['channels']):
            state['channel'] = len(config['channels']) - 1
        if state['channel'] < 0:
            state['channel'] = 0
            
        freq = config['channels'][state['channel']]
        
        freq_text = f"Частота: {freq} МГц"
        freq_width = draw.textlength(freq_text, font=font_medium)
        draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))
        
        channel_text = f"Канал: {state['channel'] + 1}/{len(config['channels'])}"
        channel_width = draw.textlength(channel_text, font=font_small)
        draw.text((width//2 - channel_width//2, 90), channel_text, font=font_small, fill=(255, 255, 255))
        
        if current_vrx == 'VRX1':
            rssi_text = f"RSSI: {rssi_value}"
            rssi_width = draw.textlength(rssi_text, font=font_small)
            draw.text((width//2 - rssi_width//2, 120), rssi_text, font=font_small, fill=(255, 255, 255))
            
            if autosearch_active:
                search_text = "АВТОПОИСК АКТИВЕН"
                search_width = draw.textlength(search_text, font=font_small)
                draw.text((width//2 - search_width//2, 140), search_text, font=font_small, fill=(255, 0, 0))
        
        version_text = f"Ver: {VERSION}"
        version_width = draw.textlength(version_text, font=font_small)
        draw.text((width - version_width - 10, height - 20), version_text, font=font_small, fill=(150, 150, 150))
        
        if current_vrx == 'VRX1':
            instruction = "UP: канал+  DOWN: канал-  HOLD SELECT: автопоиск"
        else:
            instruction = "UP: канал+  DOWN: канал-  SELECT: меню"
            
        instr_width = draw.textlength(instruction, font=font_small)
        draw.text((width//2 - instr_width//2, height - 40), instruction, font=font_small, fill=(200, 200, 200))
        
        disp.image(image)
        
    except Exception as e:
        print(f"Ошибка обновления дисплея: {e}")
        print(traceback.format_exc())
        try:
            image, width, height = create_display_image()
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
            disp.image(image)
        except:
            pass
    
    update_i2c_display()

def update_display():
    if app_state == "vrx_select":
        show_vrx_selection()
    elif app_state == "main":
        show_main_screen()

# Инициализация GPIO
def setup_gpio():
    # Настройка пинов питания VRX (инвертированная логика)
    for vrx, config in VRX_CONFIG.items():
        GPIO.setup(config['power_pin'], GPIO.OUT)
        GPIO.output(config['power_pin'], GPIO.HIGH)  # изначально выключены
        print(f"{vrx} питание инициализировано (пин {config['power_pin']}: HIGH)")
    
    # Настройка управляющих пинов в зависимости от типа VRX
    for vrx, config in VRX_CONFIG.items():
        if 'control_pins' in config:  # VRX2, VRX3 (кнопки)
            for pin in config['control_pins'].values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)
        elif 'spi_cs' in config:      # VRX1 (SPI)
            GPIO.setup(config['spi_cs'], GPIO.OUT)
            GPIO.setup(config['spi_mosi'], GPIO.OUT)
            GPIO.setup(config['spi_sclk'], GPIO.OUT)
            GPIO.output(config['spi_cs'], GPIO.HIGH)
            GPIO.output(config['spi_mosi'], GPIO.LOW)
            GPIO.output(config['spi_sclk'], GPIO.LOW)
            print(f"VRX1 SPI пины настроены: CS={config['spi_cs']}, MOSI={config['spi_mosi']}, SCLK={config['spi_sclk']}")
        elif 'cs_pins' in config:      # VRX4 (параллельные)
            for pin in config['cs_pins'] + config['s_pins']:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            print(f"VRX4 параллельные пины настроены: CS={config['cs_pins']}, S={config['s_pins']}")
    
    # Настройка кнопок
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Эмуляция нажатия кнопки на VRX (только для VRX2/3)
def press_button(pin, duration=0.1):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

# Переключение каналов с учётом новых методов
def change_channel(direction):
    try:
        state = channel_states[current_vrx]
        config = VRX_CONFIG[current_vrx]
        
        if direction == 'UP':
            state['channel'] = (state['channel'] + 1) % len(config['channels'])
        else:
            state['channel'] = (state['channel'] - 1) % len(config['channels'])
        
        if state['channel'] < 0:
            state['channel'] = 0
        if state['channel'] >= len(config['channels']):
            state['channel'] = len(config['channels']) - 1
        
        # Применяем изменение в зависимости от типа VRX
        if current_vrx == 'VRX1':
            set_vrx1_channel(state['channel'])
        elif current_vrx == 'VRX4':
            set_vrx4_channel(state['channel'])
        else:
            # Для VRX2/3 используем эмуляцию кнопок
            if direction == 'UP':
                press_button(config['control_pins']['CH_UP'])
            else:
                press_button(config['control_pins']['CH_DOWN'])
        
        freq = config['channels'][state['channel']]
        print(f"{current_vrx}: Канал {state['channel']+1}, Частота {freq} МГц")
        
        update_display()
        send_state_to_esp32()
    except Exception as e:
        print(f"Ошибка переключения канала: {e}")
        print(traceback.format_exc())

# Функция автопоиска для VRX1 (адаптирована под прямой метод)
def autosearch():
    global autosearch_active, rssi_value
    
    if current_vrx != 'VRX1':
        return
    
    autosearch_active = True
    update_display()
    
    best_rssi = 0
    best_channel = 0
    
    config = VRX_CONFIG['VRX1']
    state = channel_states['VRX1']
    original_channel = state['channel']
    
    try:
        for channel in range(len(config['channels'])):
            # Устанавливаем канал напрямую
            set_vrx1_channel(channel)
            state['channel'] = channel
            time.sleep(0.5)  # ждём стабилизации
            
            # Получаем RSSI от ESP32
            if esp32:
                try:
                    esp32.write(b'GET_RSSI\n')
                    time.sleep(0.1)
                    response = esp32.readline().decode().strip()
                    if response:
                        rssi_value = int(response)
                    else:
                        rssi_value = 0
                except:
                    rssi_value = 0
            
            update_display()
            
            if rssi_value > best_rssi:
                best_rssi = rssi_value
                best_channel = channel
    except Exception as e:
        print(f"Ошибка в автопоиске: {e}")
        print(traceback.format_exc())
    finally:
        autosearch_active = False
    
    # Возвращаемся к лучшему каналу
    try:
        set_vrx1_channel(best_channel)
        state['channel'] = best_channel
    except Exception as e:
        print(f"Ошибка возврата к лучшему каналу: {e}")
        print(traceback.format_exc())
    
    update_display()
    print(f"Автопоиск завершен. Лучший канал: {best_channel+1}, RSSI: {best_rssi}")

# Отправка состояния на ESP32 (без изменений)
def send_state_to_esp32():
    if not esp32:
        return
    
    vrx = current_vrx
    state = channel_states[vrx]
    config = VRX_CONFIG[vrx]
    
    try:
        if state['channel'] >= len(config['channels']):
            state['channel'] = len(config['channels']) - 1
        if state['channel'] < 0:
            state['channel'] = 0
            
        freq = config['channels'][state['channel']]
        message = f"VRX:{vrx}:{state['channel']}:{freq}:{rssi_value}\n"
        
        esp32.write(message.encode())
        print(f"Отправлено на ESP32: {message.strip()}")
    except Exception as e:
        print(f"Ошибка отправки на ESP32: {e}")
        print(traceback.format_exc())

# Обработка команд от ESP32 (без изменений, кроме вызова apply_current_channel при включении)
def handle_esp32_commands():
    global current_vrx, app_state, active_vrx
    
    if not esp32:
        return
    
    while True:
        try:
            if esp32.in_waiting > 0:
                command = esp32.readline().decode().strip()
                print(f"Получена команда от ESP32: {command}")
                
                if command.startswith("SELECT_"):
                    vrx = command.split("_")[1]
                    if vrx in VRX_CONFIG:
                        if active_vrx:
                            set_vrx_power(active_vrx, False)
                            reset_vrx_channels(active_vrx)
                        
                        current_vrx = vrx
                        set_vrx_power(current_vrx, True)
                        active_vrx = current_vrx
                        # Применить текущий канал после включения
                        apply_current_channel(current_vrx)
                        
                        app_state = "main"
                        update_display()
                        send_state_to_esp32()
                
                elif command == "CH_UP":
                    if app_state == "main":
                        change_channel('UP')
                
                elif command == "CH_DOWN":
                    if app_state == "main":
                        change_channel('DOWN')
                
                elif command == "AUTO_SEARCH":
                    if app_state == "main" and current_vrx == "VRX1":
                        autosearch()
                
                elif command == "MENU":
                    if app_state == "main":
                        if active_vrx:
                            set_vrx_power(active_vrx, False)
                            reset_vrx_channels(active_vrx)
                            active_vrx = None
                        app_state = "vrx_select"
                    else:
                        app_state = "main"
                    update_display()
        
        except Exception as e:
            print(f"Ошибка обработки команды от ESP32: {e}")
            print(traceback.format_exc())
        
        time.sleep(0.1)

def change_vrx(direction):
    global current_vrx
    vrx_list = list(VRX_CONFIG.keys())
    current_index = vrx_list.index(current_vrx)
    
    if direction == 'UP':
        current_index = (current_index + 1) % len(vrx_list)
    else:
        current_index = (current_index - 1) % len(vrx_list)
    
    current_vrx = vrx_list[current_index]
    update_display()

# Основная функция
def main():
    global app_state, current_vrx, active_vrx
    
    print("Запуск системы управления VRX (v2.0 с прямым управлением VRX1/VRX4)...")
    
    try:
        setup_gpio()
        print("GPIO инициализированы успешно")
    except Exception as e:
        print(f"Ошибка инициализации GPIO: {e}")
        print(traceback.format_exc())
        return
    
    if esp32:
        esp32_thread = threading.Thread(target=handle_esp32_commands, daemon=True)
        esp32_thread.start()
        print("Поток обработки команд ESP32 запущен")
    
    app_state = "vrx_select"
    try:
        update_display()
        print("Дисплей обновлен")
    except Exception as e:
        print(f"Ошибка обновления дисплея: {e}")
        print(traceback.format_exc())
        return
    
    last_select = 1
    last_up = 1
    last_down = 1
    select_press_time = 0
    
    print("Система готова к работе")
    
    try:
        while True:
            current_time = time.time()
            
            select_btn = GPIO.input(BTN_SELECT)
            if select_btn != last_select:
                if select_btn == GPIO.LOW:
                    select_press_time = current_time
                else:
                    press_duration = current_time - select_press_time
                    
                    if press_duration > 2.0 and app_state == "main" and current_vrx == "VRX1":
                        autosearch()
                    elif press_duration > 0.1:
                        if app_state == "vrx_select":
                            set_vrx_power(current_vrx, True)
                            active_vrx = current_vrx
                            apply_current_channel(current_vrx)  # применить канал
                            app_state = "main"
                            update_display()
                        elif app_state == "main":
                            if active_vrx:
                                set_vrx_power(active_vrx, False)
                                reset_vrx_channels(active_vrx)
                                active_vrx = None
                            app_state = "vrx_select"
                            update_display()
                
                last_select = select_btn
            
            up_btn = GPIO.input(BTN_UP)
            if up_btn != last_up:
                if up_btn == GPIO.LOW:
                    if app_state == "vrx_select":
                        change_vrx('UP')
                    elif app_state == "main":
                        change_channel('UP')
                last_up = up_btn
            
            down_btn = GPIO.input(BTN_DOWN)
            if down_btn != last_down:
                if down_btn == GPIO.LOW:
                    if app_state == "vrx_select":
                        change_vrx('DOWN')
                    elif app_state == "main":
                        change_channel('DOWN')
                last_down = down_btn
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("Программа завершена по запросу пользователя")
    except Exception as e:
        print(f"Критическая ошибка в основном цикле: {e}")
        print(traceback.format_exc())
    finally:
        for vrx in VRX_CONFIG:
            set_vrx_power(vrx, False)
            reset_vrx_channels(vrx)
        
        GPIO.cleanup()
        if esp32:
            esp32.close()
        print("Ресурсы освобождены")

if __name__ == "__main__":
    main()
