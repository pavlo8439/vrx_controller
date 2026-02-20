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
        i2c = board.I2C()
        i2c_display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
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

esp32 = setup_uart()

# ========== НОВЫЕ ЧАСТОТНЫЕ СЕТКИ ==========
# VRX1 (5.8 ГГц) – 12 бандов по 8 каналов (96 каналов)
VRX1_BANDS = ['A', 'B', 'E', 'F', 'R', 'P', 'L', 'U', 'O', 'H', 'T', 'N']
VRX1_CHANNELS = [
    [5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600],  # A
    [5362, 5399, 5436, 5473, 5500, 5547, 5584, 5621],  # B
    [5300, 5348, 5366, 5384, 5400, 5420, 5438, 5456],  # E
    [5129, 5159, 5189, 5219, 5249, 5279, 5309, 5339],  # F
    [4990, 5020, 5050, 5080, 5110, 5150, 5170, 5200],  # R
    [5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613],  # P
    [4875, 4884, 4900, 4858, 4995, 5032, 5069, 5099],  # L
    [5960, 5980, 6000, 6020, 6030, 6040, 6050, 6060],  # U
    [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5735],  # O
    [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866],  # H
    [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945],  # T
    [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880]   # N
]

# VRX4 (3.3 ГГц) – 8 бандов по 8 каналов (64 канала)
VRX4_BANDS = ['FR1', 'FR2', 'FR3', 'FR4', 'FR5', 'FR6', 'FR7', 'FR8']
# Значения S для каждого банда (одинаковые для всех каналов в банде)
VRX4_BAND_S = [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111]
# Частоты и CS биты для каждого банда
VRX4_FREQS = [
    [3360, 3380, 3400, 3420, 3440, 3460, 3480, 3500],  # FR1
    [3200, 3220, 3240, 3260, 3280, 3300, 3320, 3340],  # FR2
    [3330, 3350, 3370, 3390, 3410, 3430, 3450, 3470],  # FR3
    [3170, 3190, 3210, 3230, 3250, 3270, 3290, 3310],  # FR4
    [3320, 3345, 3370, 3395, 3420, 3445, 3470, 3495],  # FR5
    [3310, 3330, 3355, 3380, 3405, 3430, 3455, 3480],  # FR6
    [3220, 3240, 3260, 3280, 3300, 3320, 3340, 3360],  # FR7
    [3060, 3080, 3100, 3120, 3140, 3160, 3180, 3200]   # FR8
]
VRX4_CS_BITS = [  # для каждого канала в банде свои CS биты (от 0 до 7)
    [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],
    [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],
    [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],
    [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],
    [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],
    [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],
    [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],
    [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111]
]

# ========== КОНФИГУРАЦИЯ VRX ==========
VRX_CONFIG = {
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 2,
        'spi_cs_pin': 6,          # CS для SPI (RX5808)
        'bands': VRX1_BANDS,
        'channels': VRX1_CHANNELS  # 2D список частот
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
        'cs_pins': [7, 8, 9],      # пины для CS0, CS1, CS2
        's_pins': [10, 11, 12],     # пины для S0, S1, S2
        'bands': VRX4_BANDS,
        'band_s': VRX4_BAND_S,      # значения S для каждого банда
        'freqs': VRX4_FREQS,
        'cs_bits': VRX4_CS_BITS
    }
}

# Кнопки управления
BTN_SELECT = 27
BTN_UP = 22
BTN_DOWN = 23

# Текущее состояние
current_vrx = 'VRX1'
channel_states = {
    'VRX1': {'band': 0, 'channel': 0},
    'VRX2': {'channel': 0},
    'VRX3': {'channel': 0},
    'VRX4': {'band': 0, 'channel': 0},
}
app_state = "vrx_select"
VERSION = "2.0"  # обновлена версия
rssi_value = 0
autosearch_active = False
active_vrx = None

# Для обработки долгих нажатий
up_press_time = 0
down_press_time = 0
LONG_PRESS_TIME = 1.0  # секунд

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ДИСПЛЕЕМ (без изменений) ==========
def get_display_dimensions():
    if disp.rotation % 180 == 90:
        return disp.height, disp.width
    else:
        return disp.width, disp.height

def create_display_image():
    width, height = get_display_dimensions()
    return Image.new("RGB", (width, height)), width, height

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
            band = state['band']
            ch = state['channel']
            freq = config['channels'][band][ch]
            draw.text((0, 0), f"VRX1 ({config['bands'][band]})", font=font, fill=255)
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

# ========== УПРАВЛЕНИЕ ПИТАНИЕМ (инвертированная логика) ==========
def set_vrx_power(vrx, power_on):
    config = VRX_CONFIG[vrx]
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)
    status = "ВКЛ" if power_on else "ВЫКЛ"
    print(f"{vrx} питание: {status} (пин: {config['power_pin']}, состояние: {'LOW' if power_on else 'HIGH'})")

def reset_vrx_channels(vrx):
    if vrx in ['VRX1', 'VRX4']:
        channel_states[vrx]['band'] = 0
        channel_states[vrx]['channel'] = 0
    else:
        channel_states[vrx]['channel'] = 0
    print(f"{vrx}: сброс на начальный канал")

# ========== ПРЯМОЕ УПРАВЛЕНИЕ ЧАСТОТОЙ ==========
def set_vrx1_frequency(freq_mhz):
    """Установка частоты для VRX1 (RX5808) через SPI"""
    config = VRX_CONFIG['VRX1']
    cs_pin = config['spi_cs_pin']
    # Формула из 5.8.ino
    N = (freq_mhz - 479) // 2
    Nhigh = N >> 5
    Nlow = N & 0x1F
    data0 = Nlow * 32 + 17
    data1 = Nhigh * 16 + (Nlow // 8)
    data2 = Nhigh // 16
    data3 = 0
    # Отправка по SPI
    GPIO.output(cs_pin, GPIO.LOW)
    spi.write(bytes([data0, data1, data2, data3]))
    GPIO.output(cs_pin, GPIO.HIGH)
    print(f"VRX1: установлена частота {freq_mhz} МГц")

def set_vrx4_frequency(band, channel):
    """Установка частоты для VRX4 через пины CS и S"""
    config = VRX_CONFIG['VRX4']
    s_val = config['band_s'][band]
    cs_val = config['cs_bits'][band][channel]
    # Установка S пинов (общие для банда)
    for i, pin in enumerate(config['s_pins']):
        bit = (s_val >> i) & 1
        GPIO.output(pin, GPIO.HIGH if bit else GPIO.LOW)
    # Установка CS пинов (зависят от канала)
    for i, pin in enumerate(config['cs_pins']):
        bit = (cs_val >> i) & 1
        GPIO.output(pin, GPIO.HIGH if bit else GPIO.LOW)
    freq = config['freqs'][band][channel]
    print(f"VRX4: банда {config['bands'][band]}, канал {channel+1}, частота {freq} МГц")

# ========== ОБНОВЛЕНИЕ ТЕКУЩЕГО КАНАЛА ==========
def apply_current_channel(vrx):
    """Применить текущие настройки канала к оборудованию"""
    if vrx == 'VRX1':
        config = VRX_CONFIG[vrx]
        state = channel_states[vrx]
        freq = config['channels'][state['band']][state['channel']]
        set_vrx1_frequency(freq)
    elif vrx == 'VRX4':
        state = channel_states[vrx]
        set_vrx4_frequency(state['band'], state['channel'])
    else:
        # Для остальных VRX используем старый метод (кнопки) – но при прямом включении мы не можем
        # установить конкретную частоту, только переключать. Они уже должны быть на нужном канале.
        pass

# ========== ПЕРЕКЛЮЧЕНИЕ КАНАЛОВ И БАНДОВ ==========
def change_channel(direction):
    """Короткое нажатие: переключение канала в текущем банде"""
    state = channel_states[current_vrx]
    config = VRX_CONFIG[current_vrx]
    
    if current_vrx in ['VRX1', 'VRX4']:
        # Для VRX1 и VRX4 есть банды
        max_channel = len(config['channels'][state['band']]) if current_vrx == 'VRX1' else len(config['freqs'][state['band']])
        if direction == 'UP':
            state['channel'] = (state['channel'] + 1) % max_channel
        else:
            state['channel'] = (state['channel'] - 1) % max_channel
        apply_current_channel(current_vrx)
        freq = (config['channels'][state['band']][state['channel']] if current_vrx == 'VRX1' 
                else config['freqs'][state['band']][state['channel']])
        band_name = config['bands'][state['band']]
        print(f"{current_vrx}: Банда {band_name}, Канал {state['channel']+1}, Частота {freq} МГц")
    else:
        # Старые VRX без бандов
        if direction == 'UP':
            state['channel'] = (state['channel'] + 1) % len(config['channels'])
            press_button(config['control_pins']['CH_UP'])
        else:
            state['channel'] = (state['channel'] - 1) % len(config['channels'])
            press_button(config['control_pins']['CH_DOWN'])
        freq = config['channels'][state['channel']]
        print(f"{current_vrx}: Канал {state['channel']+1}, Частота {freq} МГц")
    
    update_display()
    send_state_to_esp32()

def change_band(direction):
    """Долгое нажатие: переключение банда (только для VRX1 и VRX4)"""
    if current_vrx not in ['VRX1', 'VRX4']:
        return
    state = channel_states[current_vrx]
    config = VRX_CONFIG[current_vrx]
    max_band = len(config['bands'])
    if direction == 'UP':
        state['band'] = (state['band'] + 1) % max_band
    else:
        state['band'] = (state['band'] - 1) % max_band
    # Сбрасываем канал на первый в новом банде
    state['channel'] = 0
    apply_current_channel(current_vrx)
    freq = (config['channels'][state['band']][0] if current_vrx == 'VRX1' 
            else config['freqs'][state['band']][0])
    band_name = config['bands'][state['band']]
    print(f"{current_vrx}: Переключена банда {band_name}, частота {freq} МГц")
    update_display()
    send_state_to_esp32()

# Эмуляция нажатия кнопки (для старых VRX)
def press_button(pin, duration=0.1):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

# ========== АВТОПОИСК ==========
def autosearch():
    global autosearch_active, rssi_value
    if current_vrx not in ['VRX1', 'VRX4']:
        return
    
    autosearch_active = True
    update_display()
    
    config = VRX_CONFIG[current_vrx]
    state = channel_states[current_vrx]
    original_band = state['band']
    original_channel = state['channel']
    
    best_rssi = 0
    best_band = 0
    best_channel = 0
    
    # Определяем количество бандов и каналов
    if current_vrx == 'VRX1':
        bands = config['channels']
        total_bands = len(bands)
        total_channels_per_band = len(bands[0])
    else:  # VRX4
        bands = config['freqs']
        total_bands = len(bands)
        total_channels_per_band = len(bands[0])
    
    try:
        for b in range(total_bands):
            for c in range(total_channels_per_band):
                # Устанавливаем канал
                if current_vrx == 'VRX1':
                    freq = config['channels'][b][c]
                    set_vrx1_frequency(freq)
                else:
                    set_vrx4_frequency(b, c)
                time.sleep(0.5)  # ждем стабилизации
                
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
                    best_band = b
                    best_channel = c
    except Exception as e:
        print(f"Ошибка в автопоиске: {e}")
        print(traceback.format_exc())
    finally:
        autosearch_active = False
    
    # Возвращаемся к лучшему каналу
    if best_rssi > 0:
        if current_vrx == 'VRX1':
            set_vrx1_frequency(config['channels'][best_band][best_channel])
        else:
            set_vrx4_frequency(best_band, best_channel)
        state['band'] = best_band
        state['channel'] = best_channel
    else:
        # Возвращаем исходный канал
        if current_vrx == 'VRX1':
            set_vrx1_frequency(config['channels'][original_band][original_channel])
        else:
            set_vrx4_frequency(original_band, original_channel)
        state['band'] = original_band
        state['channel'] = original_channel
    
    update_display()
    print(f"Автопоиск завершен. Лучший: банда {best_band+1}, канал {best_channel+1}, RSSI {best_rssi}")

# ========== ОТПРАВКА СОСТОЯНИЯ НА ESP32 ==========
def send_state_to_esp32():
    if not esp32:
        return
    vrx = current_vrx
    state = channel_states[vrx]
    config = VRX_CONFIG[vrx]
    
    try:
        if vrx == 'VRX1':
            band = state['band']
            ch = state['channel']
            freq = config['channels'][band][ch]
            message = f"VRX:{vrx}:{band}:{ch}:{freq}:{rssi_value}\n"
        elif vrx == 'VRX4':
            band = state['band']
            ch = state['channel']
            freq = config['freqs'][band][ch]
            message = f"VRX:{vrx}:{band}:{ch}:{freq}:{rssi_value}\n"
        else:
            ch = state['channel']
            freq = config['channels'][ch]
            message = f"VRX:{vrx}:0:{ch}:{freq}:{rssi_value}\n"  # band=0 для совместимости
        esp32.write(message.encode())
        print(f"Отправлено на ESP32: {message.strip()}")
    except Exception as e:
        print(f"Ошибка отправки на ESP32: {e}")
        print(traceback.format_exc())

# ========== ОБРАБОТКА КОМАНД ОТ ESP32 ==========
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
                        apply_current_channel(current_vrx)  # установить частоту
                        app_state = "main"
                        update_display()
                        send_state_to_esp32()
                elif command == "CH_UP":
                    if app_state == "main":
                        change_channel('UP')
                elif command == "CH_DOWN":
                    if app_state == "main":
                        change_channel('DOWN')
                elif command == "BAND_UP":   # новая команда для переключения банда
                    if app_state == "main" and current_vrx in ['VRX1','VRX4']:
                        change_band('UP')
                elif command == "BAND_DOWN":
                    if app_state == "main" and current_vrx in ['VRX1','VRX4']:
                        change_band('DOWN')
                elif command == "AUTO_SEARCH":
                    if app_state == "main" and current_vrx in ['VRX1','VRX4']:
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

# ========== ЭКРАНЫ ДИСПЛЕЯ ==========
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
        
        config = VRX_CONFIG[current_vrx]
        state = channel_states[current_vrx]
        
        # Заголовок
        title = f"{current_vrx} ({config['type']})"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))
        
        # Частота и банд
        if current_vrx == 'VRX1':
            band = state['band']
            ch = state['channel']
            freq = config['channels'][band][ch]
            band_name = config['bands'][band]
            band_text = f"Банда: {band_name}  Канал: {ch+1}"
        elif current_vrx == 'VRX4':
            band = state['band']
            ch = state['channel']
            freq = config['freqs'][band][ch]
            band_name = config['bands'][band]
            band_text = f"Банда: {band_name}  Канал: {ch+1}"
        else:
            ch = state['channel']
            freq = config['channels'][ch]
            band_text = f"Канал: {ch+1}/{len(config['channels'])}"
        
        freq_text = f"Частота: {freq} МГц"
        freq_width = draw.textlength(freq_text, font=font_medium)
        draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))
        
        band_width = draw.textlength(band_text, font=font_small)
        draw.text((width//2 - band_width//2, 90), band_text, font=font_small, fill=(255, 255, 255))
        
        # RSSI для VRX1
        if current_vrx == 'VRX1':
            rssi_text = f"RSSI: {rssi_value}"
            rssi_width = draw.textlength(rssi_text, font=font_small)
            draw.text((width//2 - rssi_width//2, 120), rssi_text, font=font_small, fill=(255, 255, 255))
            if autosearch_active:
                search_text = "АВТОПОИСК АКТИВЕН"
                search_width = draw.textlength(search_text, font=font_small)
                draw.text((width//2 - search_width//2, 140), search_text, font=font_small, fill=(255, 0, 0))
        
        # Версия
        version_text = f"Ver: {VERSION}"
        version_width = draw.textlength(version_text, font=font_small)
        draw.text((width - version_width - 10, height - 20), version_text, font=font_small, fill=(150, 150, 150))
        
        # Инструкция
        if current_vrx in ['VRX1', 'VRX4']:
            instruction = "UP/DOWN: канал  HOLD UP/DOWN: банда  HOLD SELECT: автопоиск"
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

# ========== ИНИЦИАЛИЗАЦИЯ GPIO ==========
def setup_gpio():
    # Пины питания
    for vrx, config in VRX_CONFIG.items():
        GPIO.setup(config['power_pin'], GPIO.OUT)
        GPIO.output(config['power_pin'], GPIO.HIGH)
        print(f"{vrx} питание инициализировано (пин {config['power_pin']}: HIGH)")
    
    # Пины управления для старых VRX (VRX2, VRX3)
    for vrx in ['VRX2', 'VRX3']:
        config = VRX_CONFIG[vrx]
        for pin in config['control_pins'].values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
    
    # Пины SPI для VRX1
    GPIO.setup(VRX_CONFIG['VRX1']['spi_cs_pin'], GPIO.OUT)
    GPIO.output(VRX_CONFIG['VRX1']['spi_cs_pin'], GPIO.HIGH)
    
    # Пины CS и S для VRX4
    for pin in VRX_CONFIG['VRX4']['cs_pins'] + VRX_CONFIG['VRX4']['s_pins']:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)  # начальное состояние
    
    # Кнопки
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ========== ПЕРЕКЛЮЧЕНИЕ VRX В МЕНЮ ==========
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

# ========== ОСНОВНОЙ ЦИКЛ ==========
def main():
    global app_state, current_vrx, active_vrx, up_press_time, down_press_time
    
    print("Запуск системы управления VRX...")
    
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
    up_press_time = 0
    down_press_time = 0
    
    print("Система готова к работе")
    
    try:
        while True:
            current_time = time.time()
            
            # SELECT
            select_btn = GPIO.input(BTN_SELECT)
            if select_btn != last_select:
                if select_btn == GPIO.LOW:
                    select_press_time = current_time
                else:
                    press_duration = current_time - select_press_time
                    if press_duration > 2.0 and app_state == "main" and current_vrx in ['VRX1', 'VRX4']:
                        autosearch()
                    elif press_duration > 0.1:
                        if app_state == "vrx_select":
                            set_vrx_power(current_vrx, True)
                            active_vrx = current_vrx
                            apply_current_channel(current_vrx)  # установить начальную частоту
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
            
            # UP
            up_btn = GPIO.input(BTN_UP)
            if up_btn != last_up:
                if up_btn == GPIO.LOW:
                    up_press_time = current_time
                else:
                    press_duration = current_time - up_press_time
                    if press_duration > LONG_PRESS_TIME and app_state == "main" and current_vrx in ['VRX1', 'VRX4']:
                        change_band('UP')
                    elif press_duration > 0.1:
                        if app_state == "vrx_select":
                            change_vrx('UP')
                        elif app_state == "main":
                            change_channel('UP')
                last_up = up_btn
            
            # DOWN
            down_btn = GPIO.input(BTN_DOWN)
            if down_btn != last_down:
                if down_btn == GPIO.LOW:
                    down_press_time = current_time
                else:
                    press_duration = current_time - down_press_time
                    if press_duration > LONG_PRESS_TIME and app_state == "main" and current_vrx in ['VRX1', 'VRX4']:
                        change_band('DOWN')
                    elif press_duration > 0.1:
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
