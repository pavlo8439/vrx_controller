#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time
import math
import board
import digitalio
import spidev
import traceback
from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import ili9341

# ==================== НАСТРОЙКА GPIO ====================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ==================== ДИСПЛЕЙ ILI9341 ====================
cs_pin = digitalio.DigitalInOut(board.CE0)
dc_pin = digitalio.DigitalInOut(board.D24)
reset_pin = digitalio.DigitalInOut(board.D25)
BAUDRATE = 24000000

spi_display = board.SPI()  # SPI для дисплея (использует CE0)

try:
    disp = ili9341.ILI9341(
        spi_display,
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

# ==================== КОНФИГУРАЦИЯ VRX ====================
# Новые частотные сетки взяты из Arduino скетчей 5.8.ino и 3.3.ino

VRX_CONFIG = {
    # ---------- VRX1 (5.8 ГГц, RX5808, SPI) ----------
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 2,                 # пин управления питанием
        # Частотная сетка: 12 диапазонов (буквы) по 8 каналов
        'bands': {
            'A': [5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600],
            'B': [5362, 5399, 5436, 5473, 5500, 5547, 5584, 5621],
            'E': [5300, 5348, 5366, 5384, 5400, 5420, 5438, 5456],
            'F': [5129, 5159, 5189, 5219, 5249, 5279, 5309, 5339],
            'R': [4990, 5020, 5050, 5080, 5110, 5150, 5170, 5200],
            'P': [5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613],
            'L': [4875, 4884, 4900, 4858, 4995, 5032, 5069, 5099],
            'U': [5960, 5980, 6000, 6020, 6030, 6040, 6050, 6060],
            'O': [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5735],
            'H': [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866],
            'T': [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945],
            'N': [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880]
        }
    },
    # ---------- VRX2 (1.2 ГГц) ----------
    'VRX2': {
        'type': '1.2GHz',
        'power_pin': 3,
        'control_pins': {'CH_UP': 19, 'CH_DOWN': 26},
        'channels': [
            1010, 1040, 1080, 1120, 1160, 1200, 1240,
            1280, 1320, 1360, 1258, 1100, 1140
        ]
    },
    # ---------- VRX3 (1.5 ГГц) ----------
    'VRX3': {
        'type': '1.5GHz',
        'power_pin': 4,
        'control_pins': {'CH_UP': 21, 'CH_DOWN': 20},
        'channels': [
            1405, 1430, 1455, 1480, 1505, 1530, 1555,
            1580, 1605, 1630, 1655, 1680
        ]
    },
    # ---------- VRX4 (3.3 ГГц, прямое управление 6 бит) ----------
    'VRX4': {
        'type': '3.3GHz',
        'power_pin': 17,
        'control_pins': {            # пины для прямого управления
            'CS1': 12,
            'CS2': 16,
            'CS3': 20,
            'S1': 21,
            'S2': 26,
            'S3': 19
        },
        # Частотная сетка из скетча 3.3.ino: 8 диапазонов FR1..FR8 по 8 каналов
        'bands': {
            'FR1': [
                {'freq': 3360, 'cs': 0b000, 's': 0b000},
                {'freq': 3380, 'cs': 0b001, 's': 0b000},
                {'freq': 3400, 'cs': 0b010, 's': 0b000},
                {'freq': 3420, 'cs': 0b011, 's': 0b000},
                {'freq': 3440, 'cs': 0b100, 's': 0b000},
                {'freq': 3460, 'cs': 0b101, 's': 0b000},
                {'freq': 3480, 'cs': 0b110, 's': 0b000},
                {'freq': 3500, 'cs': 0b111, 's': 0b000}
            ],
            'FR2': [
                {'freq': 3200, 'cs': 0b000, 's': 0b001},
                {'freq': 3220, 'cs': 0b001, 's': 0b001},
                {'freq': 3240, 'cs': 0b010, 's': 0b001},
                {'freq': 3260, 'cs': 0b011, 's': 0b001},
                {'freq': 3280, 'cs': 0b100, 's': 0b001},
                {'freq': 3300, 'cs': 0b101, 's': 0b001},
                {'freq': 3320, 'cs': 0b110, 's': 0b001},
                {'freq': 3340, 'cs': 0b111, 's': 0b001}
            ],
            'FR3': [
                {'freq': 3330, 'cs': 0b000, 's': 0b010},
                {'freq': 3350, 'cs': 0b001, 's': 0b010},
                {'freq': 3370, 'cs': 0b010, 's': 0b010},
                {'freq': 3390, 'cs': 0b011, 's': 0b010},
                {'freq': 3410, 'cs': 0b100, 's': 0b010},
                {'freq': 3430, 'cs': 0b101, 's': 0b010},
                {'freq': 3450, 'cs': 0b110, 's': 0b010},
                {'freq': 3470, 'cs': 0b111, 's': 0b010}
            ],
            'FR4': [
                {'freq': 3170, 'cs': 0b000, 's': 0b011},
                {'freq': 3190, 'cs': 0b001, 's': 0b011},
                {'freq': 3210, 'cs': 0b010, 's': 0b011},
                {'freq': 3230, 'cs': 0b011, 's': 0b011},
                {'freq': 3250, 'cs': 0b100, 's': 0b011},
                {'freq': 3270, 'cs': 0b101, 's': 0b011},
                {'freq': 3290, 'cs': 0b110, 's': 0b011},
                {'freq': 3310, 'cs': 0b111, 's': 0b011}
            ],
            'FR5': [
                {'freq': 3320, 'cs': 0b000, 's': 0b100},
                {'freq': 3345, 'cs': 0b001, 's': 0b100},
                {'freq': 3370, 'cs': 0b010, 's': 0b100},
                {'freq': 3395, 'cs': 0b011, 's': 0b100},
                {'freq': 3420, 'cs': 0b100, 's': 0b100},
                {'freq': 3445, 'cs': 0b101, 's': 0b100},
                {'freq': 3470, 'cs': 0b110, 's': 0b100},
                {'freq': 3495, 'cs': 0b111, 's': 0b100}
            ],
            'FR6': [
                {'freq': 3310, 'cs': 0b000, 's': 0b101},
                {'freq': 3330, 'cs': 0b001, 's': 0b101},
                {'freq': 3355, 'cs': 0b010, 's': 0b101},
                {'freq': 3380, 'cs': 0b011, 's': 0b101},
                {'freq': 3405, 'cs': 0b100, 's': 0b101},
                {'freq': 3430, 'cs': 0b101, 's': 0b101},
                {'freq': 3455, 'cs': 0b110, 's': 0b101},
                {'freq': 3480, 'cs': 0b111, 's': 0b101}
            ],
            'FR7': [
                {'freq': 3220, 'cs': 0b000, 's': 0b110},
                {'freq': 3240, 'cs': 0b001, 's': 0b110},
                {'freq': 3260, 'cs': 0b010, 's': 0b110},
                {'freq': 3280, 'cs': 0b011, 's': 0b110},
                {'freq': 3300, 'cs': 0b100, 's': 0b110},
                {'freq': 3320, 'cs': 0b101, 's': 0b110},
                {'freq': 3340, 'cs': 0b110, 's': 0b110},
                {'freq': 3360, 'cs': 0b111, 's': 0b110}
            ],
            'FR8': [
                {'freq': 3060, 'cs': 0b000, 's': 0b111},
                {'freq': 3080, 'cs': 0b001, 's': 0b111},
                {'freq': 3100, 'cs': 0b010, 's': 0b111},
                {'freq': 3120, 'cs': 0b011, 's': 0b111},
                {'freq': 3140, 'cs': 0b100, 's': 0b111},
                {'freq': 3160, 'cs': 0b101, 's': 0b111},
                {'freq': 3180, 'cs': 0b110, 's': 0b111},
                {'freq': 3200, 'cs': 0b111, 's': 0b111}
            ]
        }
    }
}

# ==================== КНОПКИ УПРАВЛЕНИЯ ====================
BTN_SELECT = 27     # выбор VRX / подтверждение
BTN_UP = 22         # канал вверх / следующий VRX
BTN_DOWN = 23       # канал вниз / предыдущий VRX
BTN_BAND_UP = 5     # группа вверх (для VRX1 и VRX4)
BTN_BAND_DOWN = 18  # группа вниз (для VRX1 и VRX4)

# ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
current_vrx = 'VRX1'
channel_states = {
    'VRX1': {'band': 'A', 'channel': 0},
    'VRX2': {'channel': 0},
    'VRX3': {'channel': 0},
    'VRX4': {'band': 'FR1', 'channel': 0},
}
app_state = "vrx_select"        # vrx_select / main
VERSION = "3.0"                  # обновленная версия
active_vrx = None                # какой VRX сейчас включен

# SPI для VRX1 (RX5808) – используется отдельный канал, CS на CE1 (GPIO7)
vrx1_spi = None

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_display_dimensions():
    """Возвращает (ширина, высота) с учётом поворота 90°"""
    if disp.rotation % 180 == 90:
        return disp.height, disp.width
    else:
        return disp.width, disp.height

def create_display_image():
    width, height = get_display_dimensions()
    return Image.new("RGB", (width, height)), width, height

# -------------------- УПРАВЛЕНИЕ ПИТАНИЕМ (инвертированная логика) --------------------
def set_vrx_power(vrx, power_on):
    config = VRX_CONFIG[vrx]
    # LOW = включено, HIGH = выключено
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)
    status = "ВКЛ" if power_on else "ВЫКЛ"
    print(f"{vrx} питание: {status} (пин {config['power_pin']})")
    
    # При включении устанавливаем начальный канал
    if power_on:
        state = channel_states[vrx]
        if vrx == 'VRX1':
            freq = config['bands'][state['band']][state['channel']]
            set_vrx1_frequency(freq)
        elif vrx == 'VRX4':
            set_vrx4_channel(state['band'], state['channel'])

# -------------------- УПРАВЛЕНИЕ VRX1 (SPI, RX5808) --------------------
def init_vrx1_spi():
    global vrx1_spi
    vrx1_spi = spidev.SpiDev()
    vrx1_spi.open(0, 1)        # SPI0, CS1 (CE1, GPIO7)
    vrx1_spi.max_speed_hz = 1000000
    vrx1_spi.mode = 0
    vrx1_spi.lsbfirst = True   # как в Arduino скетче (LSB first)
    # Убедимся, что CS высокий (не активен)
    GPIO.setup(7, GPIO.OUT)    # пин CE1 как выход, если нужно
    GPIO.output(7, GPIO.HIGH)

def set_vrx1_frequency(freq_mhz):
    """Устанавливает частоту для VRX1 через SPI по алгоритму из 5.8.ino"""
    if freq_mhz < 479:
        print(f"Ошибка: частота {freq_mhz} МГц слишком мала")
        return
    N = (freq_mhz - 479) // 2
    Nhigh = (N >> 5) & 0xFF
    Nlow = N & 0x1F
    data0 = (Nlow << 5) + 17
    data1 = (Nhigh << 4) + (Nlow >> 3)   # Nlow >> 3 = Nlow // 8
    data2 = (Nhigh >> 4) & 0xFF
    data3 = 0
    # Отправка 4 байт
    vrx1_spi.xfer2([data0, data1, data2, data3])
    print(f"VRX1: установлена частота {freq_mhz} МГц, данные: {[hex(d) for d in [data0, data1, data2, data3]]}")

# -------------------- УПРАВЛЕНИЕ VRX4 (прямые GPIO) --------------------
def set_vrx4_channel(band, channel):
    config = VRX_CONFIG['VRX4']
    channel_data = config['bands'][band][channel]
    cs_bits = channel_data['cs']
    s_bits = channel_data['s']
    
    # CS1, CS2, CS3
    GPIO.output(config['control_pins']['CS1'], (cs_bits >> 0) & 1)
    GPIO.output(config['control_pins']['CS2'], (cs_bits >> 1) & 1)
    GPIO.output(config['control_pins']['CS3'], (cs_bits >> 2) & 1)
    # S1, S2, S3
    GPIO.output(config['control_pins']['S1'], (s_bits >> 0) & 1)
    GPIO.output(config['control_pins']['S2'], (s_bits >> 1) & 1)
    GPIO.output(config['control_pins']['S3'], (s_bits >> 2) & 1)
    
    freq = channel_data['freq']
    print(f"VRX4: Band:{band}, Channel:{channel+1}, Частота:{freq} МГц")
    print(f"  CS: {cs_bits:03b}, S: {s_bits:03b}")

# -------------------- УПРАВЛЕНИЕ ДРУГИМИ VRX (через эмуляцию нажатий) --------------------
def press_button(pin, duration=0.1):
    """Эмулирует нажатие кнопки на VRX (активный низкий уровень)"""
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

# ==================== ОТОБРАЖЕНИЕ НА ДИСПЛЕЕ ====================
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
        
        # Заголовок
        title = "ВЫБОР VRX"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))
        
        # Список VRX
        vrx_list = list(VRX_CONFIG.keys())
        y_pos = 60
        for i, vrx in enumerate(vrx_list):
            config = VRX_CONFIG[vrx]
            color = (0, 255, 0) if vrx == current_vrx else (255, 255, 255)
            text = f"{vrx} ({config['type']})"
            draw.text((width//2 - 100, y_pos), text, font=font_medium, fill=color)
            y_pos += 30
        
        # Инструкция
        instruction = "SELECT: выбрать  UP/DOWN: переключение"
        instr_width = draw.textlength(instruction, font=font_small)
        draw.text((width//2 - instr_width//2, height - 30), instruction, font=font_small, fill=(200, 200, 200))
        
        disp.image(image)
    except Exception as e:
        print(f"Ошибка отображения выбора VRX: {e}")
        print(traceback.format_exc())

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
        
        # Заголовок
        vrx_type = VRX_CONFIG[current_vrx]['type']
        title = f"{current_vrx} ({vrx_type})"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))
        
        # Получение текущей частоты
        config = VRX_CONFIG[current_vrx]
        state = channel_states[current_vrx]
        
        if current_vrx in ['VRX1', 'VRX4']:
            band = state['band']
            channel = state['channel']
            # Проверка границ
            if channel >= len(config['bands'][band]):
                channel = len(config['bands'][band]) - 1
                state['channel'] = channel
            if channel < 0:
                channel = 0
                state['channel'] = 0
            
            if current_vrx == 'VRX4':
                freq = config['bands'][band][channel]['freq']
            else:  # VRX1
                freq = config['bands'][band][channel]
            
            # Текущая частота
            freq_text = f"Частота: {freq} МГц"
            freq_width = draw.textlength(freq_text, font=font_medium)
            draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))
            
            # Группа и канал
            band_text = f"Группа: {band}"
            band_width = draw.textlength(band_text, font=font_small)
            draw.text((width//2 - band_width//2, 90), band_text, font=font_small, fill=(255, 255, 255))
            
            channel_text = f"Канал: {channel + 1}/{len(config['bands'][band])}"
            channel_width = draw.textlength(channel_text, font=font_small)
            draw.text((width//2 - channel_width//2, 110), channel_text, font=font_small, fill=(255, 255, 255))
            
            instruction = "UP: канал+  DOWN: канал-  B1/B2: группа  SELECT: меню"
        else:
            channel = state['channel']
            if channel >= len(config['channels']):
                channel = len(config['channels']) - 1
                state['channel'] = channel
            if channel < 0:
                channel = 0
                state['channel'] = 0
            freq = config['channels'][channel]
            
            freq_text = f"Частота: {freq} МГц"
            freq_width = draw.textlength(freq_text, font=font_medium)
            draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))
            
            channel_text = f"Канал: {channel + 1}/{len(config['channels'])}"
            channel_width = draw.textlength(channel_text, font=font_small)
            draw.text((width//2 - channel_width//2, 90), channel_text, font=font_small, fill=(255, 255, 255))
            
            instruction = "UP: канал+  DOWN: канал-  SELECT: меню"
        
        # Версия
        version_text = f"Ver: {VERSION}"
        version_width = draw.textlength(version_text, font=font_small)
        draw.text((width - version_width - 10, height - 20), version_text, font=font_small, fill=(150, 150, 150))
        
        # Инструкция внизу
        instr_width = draw.textlength(instruction, font=font_small)
        draw.text((width//2 - instr_width//2, height - 40), instruction, font=font_small, fill=(200, 200, 200))
        
        disp.image(image)
    except Exception as e:
        print(f"Ошибка обновления дисплея: {e}")
        print(traceback.format_exc())
        # Показать чёрный экран в случае ошибки
        try:
            image, width, height = create_display_image()
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
            disp.image(image)
        except:
            pass

def update_display():
    if app_state == "vrx_select":
        show_vrx_selection()
    elif app_state == "main":
        show_main_screen()

# ==================== ИНИЦИАЛИЗАЦИЯ GPIO ====================
def setup_gpio():
    # Пины питания VRX (все как выходы, изначально выключены - HIGH)
    for vrx, config in VRX_CONFIG.items():
        GPIO.setup(config['power_pin'], GPIO.OUT)
        GPIO.output(config['power_pin'], GPIO.HIGH)
        print(f"{vrx} питание: пин {config['power_pin']} HIGH (выкл)")
    
    # Пины управления для VRX2, VRX3, VRX4 (у VRX1 больше нет control_pins)
    for vrx, config in VRX_CONFIG.items():
        if 'control_pins' in config:
            for pin_name, pin in config['control_pins'].items():
                GPIO.setup(pin, GPIO.OUT)
                # Для VRX4 начальное состояние LOW (как в setup_gpio исходного кода)
                if vrx == 'VRX4':
                    GPIO.output(pin, GPIO.LOW)
                else:
                    GPIO.output(pin, GPIO.HIGH)  # для VRX2,VRX3 - неактивный уровень (HIGH)
    
    # Кнопки (все с подтяжкой вверх)
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_BAND_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_BAND_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ==================== ОБРАБОТКА ДЕЙСТВИЙ ====================
def change_channel(direction):
    """Переключение канала (вверх/вниз) для текущего VRX"""
    try:
        state = channel_states[current_vrx]
        config = VRX_CONFIG[current_vrx]
        
        if current_vrx in ['VRX1', 'VRX4']:
            band = state['band']
            max_chan = len(config['bands'][band])
            if direction == 'UP':
                state['channel'] = (state['channel'] + 1) % max_chan
            else:
                state['channel'] = (state['channel'] - 1) % max_chan
            
            if current_vrx == 'VRX1':
                freq = config['bands'][band][state['channel']]
                set_vrx1_frequency(freq)
            else:  # VRX4
                set_vrx4_channel(band, state['channel'])
        else:
            # VRX2, VRX3
            max_chan = len(config['channels'])
            if direction == 'UP':
                state['channel'] = (state['channel'] + 1) % max_chan
                press_button(config['control_pins']['CH_UP'])
            else:
                state['channel'] = (state['channel'] - 1) % max_chan
                press_button(config['control_pins']['CH_DOWN'])
        
        update_display()
        print(f"{current_vrx}: канал {state['channel']+1}")
    except Exception as e:
        print(f"Ошибка change_channel: {e}")
        print(traceback.format_exc())

def change_band(direction):
    """Переключение группы (только для VRX1 и VRX4)"""
    if current_vrx not in ['VRX1', 'VRX4']:
        return
    
    state = channel_states[current_vrx]
    config = VRX_CONFIG[current_vrx]
    bands = list(config['bands'].keys())
    current_idx = bands.index(state['band'])
    
    if direction == 'UP':
        new_idx = (current_idx + 1) % len(bands)
    else:
        new_idx = (current_idx - 1) % len(bands)
    
    state['band'] = bands[new_idx]
    state['channel'] = 0   # сброс на первый канал в новой группе
    
    if current_vrx == 'VRX1':
        freq = config['bands'][state['band']][0]
        set_vrx1_frequency(freq)
    else:  # VRX4
        set_vrx4_channel(state['band'], 0)
    
    update_display()
    print(f"{current_vrx}: группа {state['band']}")

def change_vrx(direction):
    """Переключение между VRX в режиме выбора"""
    global current_vrx
    vrx_list = list(VRX_CONFIG.keys())
    idx = vrx_list.index(current_vrx)
    if direction == 'UP':
        idx = (idx + 1) % len(vrx_list)
    else:
        idx = (idx - 1) % len(vrx_list)
    current_vrx = vrx_list[idx]
    update_display()

# ==================== ОСНОВНОЙ ЦИКЛ ====================
def main():
    global app_state, current_vrx, active_vrx
    
    print("Запуск системы управления VRX (версия с новыми частотными сетками)")
    
    # Инициализация GPIO
    try:
        setup_gpio()
        print("GPIO инициализированы")
    except Exception as e:
        print(f"Ошибка инициализации GPIO: {e}")
        print(traceback.format_exc())
        return
    
    # Инициализация SPI для VRX1
    try:
        init_vrx1_spi()
        print("SPI для VRX1 инициализирован (CS=CE1)")
    except Exception as e:
        print(f"Ошибка инициализации SPI: {e}")
        print(traceback.format_exc())
        return
    
    # Начальный экран
    app_state = "vrx_select"
    update_display()
    
    # Переменные для антидребезга
    last_select = 1
    last_up = 1
    last_down = 1
    last_band_up = 1
    last_band_down = 1
    
    print("Система готова. Ожидание нажатий...")
    
    try:
        while True:
            # SELECT
            select = GPIO.input(BTN_SELECT)
            if select != last_select:
                if select == GPIO.LOW:
                    # Короткое нажатие
                    if app_state == "vrx_select":
                        # Включаем выбранный VRX
                        set_vrx_power(current_vrx, True)
                        active_vrx = current_vrx
                        app_state = "main"
                        update_display()
                    elif app_state == "main":
                        # Выключаем текущий VRX и возвращаемся в меню выбора
                        if active_vrx:
                            set_vrx_power(active_vrx, False)
                            active_vrx = None
                        app_state = "vrx_select"
                        update_display()
                last_select = select
            
            # UP
            up = GPIO.input(BTN_UP)
            if up != last_up:
                if up == GPIO.LOW:
                    if app_state == "vrx_select":
                        change_vrx('UP')
                    elif app_state == "main":
                        change_channel('UP')
                last_up = up
            
            # DOWN
            down = GPIO.input(BTN_DOWN)
            if down != last_down:
                if down == GPIO.LOW:
                    if app_state == "vrx_select":
                        change_vrx('DOWN')
                    elif app_state == "main":
                        change_channel('DOWN')
                last_down = down
            
            # BAND_UP
            band_up = GPIO.input(BTN_BAND_UP)
            if band_up != last_band_up:
                if band_up == GPIO.LOW and app_state == "main" and current_vrx in ["VRX1", "VRX4"]:
                    change_band('UP')
                last_band_up = band_up
            
            # BAND_DOWN
            band_down = GPIO.input(BTN_BAND_DOWN)
            if band_down != last_band_down:
                if band_down == GPIO.LOW and app_state == "main" and current_vrx in ["VRX1", "VRX4"]:
                    change_band('DOWN')
                last_band_down = band_down
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("Программа остановлена пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        print(traceback.format_exc())
    finally:
        # Выключить все VRX
        for vrx in VRX_CONFIG:
            set_vrx_power(vrx, False)
        # Закрыть SPI
        if vrx1_spi:
            vrx1_spi.close()
        GPIO.cleanup()
        print("Ресурсы освобождены")

if __name__ == "__main__":
    main()
