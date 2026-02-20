#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time
import board
import digitalio
import serial
import threading
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

spi_display = board.SPI()

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
    print("Дисплей ILI9341 инициализирован успешно")
except Exception as e:
    print(f"Ошибка инициализации дисплея: {e}")
    print(traceback.format_exc())
    exit(1)

# ==================== I2C ДИСПЛЕЙ (опционально) ====================
try:
    import adafruit_ssd1306
    i2c = board.I2C()
    i2c_display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
    i2c_display.fill(0)
    i2c_display.show()
    print("I2C дисплей инициализирован успешно")
except ImportError:
    i2c_display = None
    print("Библиотека для I2C дисплея не установлена, пропускаем")
except Exception as e:
    i2c_display = None
    print(f"Ошибка инициализации I2C дисплея: {e}")

# ==================== UART для ESP32 ====================
def setup_uart():
    uart_ports = ['/dev/serial0', '/dev/ttyAMA0', '/dev/ttyS0']
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

# ==================== SPI для VRX1 (RX5808) ====================
vrx1_spi = None
def init_vrx1_spi():
    global vrx1_spi
    vrx1_spi = spidev.SpiDev()
    vrx1_spi.open(0, 1)        # SPI0, CS1 (CE1, GPIO7)
    vrx1_spi.max_speed_hz = 1000000
    vrx1_spi.mode = 0
    vrx1_spi.lsbfirst = True    # LSB first как в Arduino
    # Убедимся, что CS высокий
    GPIO.setup(7, GPIO.OUT)
    GPIO.output(7, GPIO.HIGH)

# ==================== КОНФИГУРАЦИЯ VRX ====================
# Новые частотные сетки для VRX1 и VRX4, остальные как в версии 1.9
VRX_CONFIG = {
    # ---------- VRX1 (5.8 ГГц, SPI, 12 групп по 8 каналов) ----------
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 2,
        # Нет control_pins – управление через SPI
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
    # ---------- VRX4 (3.3 ГГц, прямое 6-битное управление) ----------
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

# ==================== КНОПКИ ====================
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
app_state = "vrx_select"   # vrx_select / main
VERSION = "3.0"
rssi_value = 0
autosearch_active = False
active_vrx = None

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
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
            config = VRX_CONFIG['VRX1']
            state = channel_states['VRX1']
            freq = config['bands'][state['band']][state['channel']]
            draw.text((0, 0), "VRX1 (5.8GHz)", font=font, fill=255)
            draw.text((0, 16), f"Band:{state['band']} CH:{state['channel']+1}", font=font, fill=255)
            draw.text((0, 32), f"Freq:{freq} MHz", font=font, fill=255)
            draw.text((0, 48), f"RSSI:{rssi_value}", font=font, fill=255)
        else:
            draw.text((0, 0), "VRX System", font=font, fill=255)
            draw.text((0, 16), "Select VRX1", font=font, fill=255)
            draw.text((0, 32), "for I2C display", font=font, fill=255)
        i2c_display.image(image)
        i2c_display.show()
    except Exception as e:
        print(f"Ошибка обновления I2C дисплея: {e}")

# ==================== УПРАВЛЕНИЕ ПИТАНИЕМ ====================
def set_vrx_power(vrx, power_on):
    config = VRX_CONFIG[vrx]
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)
    status = "ВКЛ" if power_on else "ВЫКЛ"
    print(f"{vrx} питание: {status} (пин {config['power_pin']})")
    if power_on:
        state = channel_states[vrx]
        if vrx == 'VRX1':
            freq = config['bands'][state['band']][state['channel']]
            set_vrx1_frequency(freq)
        elif vrx == 'VRX4':
            set_vrx4_channel(state['band'], state['channel'])

# ==================== УПРАВЛЕНИЕ VRX1 (SPI) ====================
def set_vrx1_frequency(freq_mhz):
    if freq_mhz < 479:
        print(f"Ошибка: частота {freq_mhz} МГц слишком мала")
        return
    N = (freq_mhz - 479) // 2
    Nhigh = (N >> 5) & 0xFF
    Nlow = N & 0x1F
    data0 = (Nlow << 5) + 17
    data1 = (Nhigh << 4) + (Nlow >> 3)
    data2 = (Nhigh >> 4) & 0xFF
    data3 = 0
    vrx1_spi.xfer2([data0, data1, data2, data3])
    print(f"VRX1: частота {freq_mhz} МГц установлена")

# ==================== УПРАВЛЕНИЕ VRX4 (прямые GPIO) ====================
def set_vrx4_channel(band, channel):
    config = VRX_CONFIG['VRX4']
    chan_data = config['bands'][band][channel]
    cs_bits = chan_data['cs']
    s_bits = chan_data['s']
    GPIO.output(config['control_pins']['CS1'], (cs_bits >> 0) & 1)
    GPIO.output(config['control_pins']['CS2'], (cs_bits >> 1) & 1)
    GPIO.output(config['control_pins']['CS3'], (cs_bits >> 2) & 1)
    GPIO.output(config['control_pins']['S1'], (s_bits >> 0) & 1)
    GPIO.output(config['control_pins']['S2'], (s_bits >> 1) & 1)
    GPIO.output(config['control_pins']['S3'], (s_bits >> 2) & 1)
    print(f"VRX4: Band:{band}, CH:{channel+1}, Частота:{chan_data['freq']} МГц")

# ==================== ЭМУЛЯЦИЯ НАЖАТИЙ ДЛЯ VRX2, VRX3 ====================
def press_button(pin, duration=0.1):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

# ==================== ПЕРЕКЛЮЧЕНИЕ КАНАЛОВ ====================
def change_channel(direction):
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
            max_chan = len(config['channels'])
            if direction == 'UP':
                state['channel'] = (state['channel'] + 1) % max_chan
                press_button(config['control_pins']['CH_UP'])
            else:
                state['channel'] = (state['channel'] - 1) % max_chan
                press_button(config['control_pins']['CH_DOWN'])
        update_display()
        send_state_to_esp32()
    except Exception as e:
        print(f"Ошибка change_channel: {e}")
        traceback.print_exc()

def change_band(direction):
    if current_vrx not in ['VRX1', 'VRX4']:
        return
    state = channel_states[current_vrx]
    config = VRX_CONFIG[current_vrx]
    bands = list(config['bands'].keys())
    idx = bands.index(state['band'])
    if direction == 'UP':
        idx = (idx + 1) % len(bands)
    else:
        idx = (idx - 1) % len(bands)
    state['band'] = bands[idx]
    state['channel'] = 0
    if current_vrx == 'VRX1':
        freq = config['bands'][state['band']][0]
        set_vrx1_frequency(freq)
    else:
        set_vrx4_channel(state['band'], 0)
    update_display()
    send_state_to_esp32()

def change_vrx(direction):
    global current_vrx
    vrx_list = list(VRX_CONFIG.keys())
    idx = vrx_list.index(current_vrx)
    if direction == 'UP':
        idx = (idx + 1) % len(vrx_list)
    else:
        idx = (idx - 1) % len(vrx_list)
    current_vrx = vrx_list[idx]
    update_display()

# ==================== ОТОБРАЖЕНИЕ ====================
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
        for vrx in vrx_list:
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
        print(f"Ошибка show_vrx_selection: {e}")
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
        vrx_type = VRX_CONFIG[current_vrx]['type']
        title = f"{current_vrx} ({vrx_type})"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))
        config = VRX_CONFIG[current_vrx]
        state = channel_states[current_vrx]
        if current_vrx in ['VRX1', 'VRX4']:
            band = state['band']
            channel = state['channel']
            if channel >= len(config['bands'][band]):
                channel = len(config['bands'][band]) - 1
                state['channel'] = channel
            if channel < 0:
                channel = 0
                state['channel'] = 0
            if current_vrx == 'VRX4':
                freq = config['bands'][band][channel]['freq']
            else:
                freq = config['bands'][band][channel]
            freq_text = f"Частота: {freq} МГц"
            freq_width = draw.textlength(freq_text, font=font_medium)
            draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))
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
        if current_vrx == 'VRX1':
            rssi_text = f"RSSI: {rssi_value}"
            rssi_width = draw.textlength(rssi_text, font=font_small)
            draw.text((width//2 - rssi_width//2, 140), rssi_text, font=font_small, fill=(255, 255, 255))
            if autosearch_active:
                search_text = "АВТОПОИСК АКТИВЕН"
                search_width = draw.textlength(search_text, font=font_small)
                draw.text((width//2 - search_width//2, 160), search_text, font=font_small, fill=(255, 0, 0))
        version_text = f"Ver: {VERSION}"
        version_width = draw.textlength(version_text, font=font_small)
        draw.text((width - version_width - 10, height - 20), version_text, font=font_small, fill=(150, 150, 150))
        instr_width = draw.textlength(instruction, font=font_small)
        draw.text((width//2 - instr_width//2, height - 40), instruction, font=font_small, fill=(200, 200, 200))
        disp.image(image)
    except Exception as e:
        print(f"Ошибка show_main_screen: {e}")
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

# ==================== АВТОПОИСК ====================
def autosearch():
    global autosearch_active, rssi_value
    if current_vrx != 'VRX1':
        return
    autosearch_active = True
    update_display()
    best_rssi = 0
    best_band = 'A'
    best_channel = 0
    config = VRX_CONFIG['VRX1']
    state = channel_states['VRX1']
    original_band = state['band']
    original_channel = state['channel']
    try:
        for band in config['bands'].keys():
            for ch in range(len(config['bands'][band])):
                if state['band'] != band:
                    state['band'] = band
                    state['channel'] = 0  # временно, но дальше установим
                # Переключаем на нужный канал
                while state['channel'] != ch:
                    if state['channel'] < ch:
                        state['channel'] += 1
                    else:
                        state['channel'] -= 1
                    set_vrx1_frequency(config['bands'][band][state['channel']])
                    time.sleep(0.2)
                time.sleep(0.5)
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
                    best_band = band
                    best_channel = ch
    except Exception as e:
        print(f"Ошибка в автопоиске: {e}")
        traceback.print_exc()
    finally:
        autosearch_active = False
    # Возврат на лучший канал
    state['band'] = best_band
    state['channel'] = best_channel
    set_vrx1_frequency(config['bands'][best_band][best_channel])
    update_display()
    print(f"Автопоиск завершен. Лучший: {best_band} CH{best_channel+1}, RSSI={best_rssi}")

# ==================== СВЯЗЬ С ESP32 ====================
def send_state_to_esp32():
    if not esp32:
        return
    try:
        state = channel_states[current_vrx]
        config = VRX_CONFIG[current_vrx]
        if current_vrx in ['VRX1', 'VRX4']:
            band = state['band']
            ch = state['channel']
            if current_vrx == 'VRX4':
                freq = config['bands'][band][ch]['freq']
            else:
                freq = config['bands'][band][ch]
        else:
            freq = config['channels'][state['channel']]
        message = f"VRX:{current_vrx}:{state.get('channel', 0)}:{freq}:{rssi_value}\n"
        esp32.write(message.encode())
    except Exception as e:
        print(f"Ошибка отправки на ESP32: {e}")

def handle_esp32_commands():
    if not esp32:
        return
    while True:
        try:
            if esp32.in_waiting > 0:
                command = esp32.readline().decode().strip()
                print(f"Команда от ESP32: {command}")
                if command.startswith("SELECT_"):
                    vrx = command.split("_")[1]
                    if vrx in VRX_CONFIG:
                        if active_vrx:
                            set_vrx_power(active_vrx, False)
                        current_vrx = vrx
                        set_vrx_power(current_vrx, True)
                        active_vrx = current_vrx
                        app_state = "main"
                        update_display()
                        send_state_to_esp32()
                elif command == "CH_UP" and app_state == "main":
                    change_channel('UP')
                elif command == "CH_DOWN" and app_state == "main":
                    change_channel('DOWN')
                elif command == "BAND_UP" and app_state == "main" and current_vrx in ['VRX1','VRX4']:
                    change_band('UP')
                elif command == "BAND_DOWN" and app_state == "main" and current_vrx in ['VRX1','VRX4']:
                    change_band('DOWN')
                elif command == "AUTO_SEARCH" and app_state == "main" and current_vrx == "VRX1":
                    autosearch()
                elif command == "MENU":
                    if app_state == "main":
                        if active_vrx:
                            set_vrx_power(active_vrx, False)
                            active_vrx = None
                        app_state = "vrx_select"
                    else:
                        app_state = "main"
                    update_display()
        except Exception as e:
            print(f"Ошибка обработки команды ESP32: {e}")
        time.sleep(0.1)

# ==================== ИНИЦИАЛИЗАЦИЯ GPIO ====================
def setup_gpio():
    for vrx, config in VRX_CONFIG.items():
        GPIO.setup(config['power_pin'], GPIO.OUT)
        GPIO.output(config['power_pin'], GPIO.HIGH)
        print(f"{vrx} питание: пин {config['power_pin']} HIGH")
    for vrx, config in VRX_CONFIG.items():
        if 'control_pins' in config:
            for pin in config['control_pins'].values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)
    # Для VRX4 сброс пинов в LOW (начальное состояние)
    if 'VRX4' in VRX_CONFIG:
        for pin in VRX_CONFIG['VRX4']['control_pins'].values():
            GPIO.output(pin, GPIO.LOW)
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_BAND_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_BAND_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ==================== ОСНОВНОЙ ЦИКЛ ====================
def main():
    global app_state, current_vrx, active_vrx, rssi_value
    print("Запуск системы управления VRX v3.0")
    try:
        setup_gpio()
        init_vrx1_spi()
        print("GPIO и SPI инициализированы")
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        traceback.print_exc()
        return

    if esp32:
        threading.Thread(target=handle_esp32_commands, daemon=True).start()
        print("Поток ESP32 запущен")

    app_state = "vrx_select"
    update_display()

    last_select = 1
    last_up = 1
    last_down = 1
    last_band_up = 1
    last_band_down = 1
    select_press_time = 0

    try:
        while True:
            now = time.time()
            # SELECT
            select = GPIO.input(BTN_SELECT)
            if select != last_select:
                if select == GPIO.LOW:
                    select_press_time = now
                else:
                    duration = now - select_press_time
                    if duration > 2.0 and app_state == "main" and current_vrx == "VRX1":
                        autosearch()
                    elif duration > 0.1:
                        if app_state == "vrx_select":
                            set_vrx_power(current_vrx, True)
                            active_vrx = current_vrx
                            app_state = "main"
                            update_display()
                        elif app_state == "main":
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
                if band_up == GPIO.LOW and app_state == "main" and current_vrx in ['VRX1','VRX4']:
                    change_band('UP')
                last_band_up = band_up
            # BAND_DOWN
            band_down = GPIO.input(BTN_BAND_DOWN)
            if band_down != last_band_down:
                if band_down == GPIO.LOW and app_state == "main" and current_vrx in ['VRX1','VRX4']:
                    change_band('DOWN')
                last_band_down = band_down
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Программа остановлена пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        traceback.print_exc()
    finally:
        for vrx in VRX_CONFIG:
            set_vrx_power(vrx, False)
        if vrx1_spi:
            vrx1_spi.close()
        if esp32:
            esp32.close()
        GPIO.cleanup()
        print("Ресурсы освобождены")

if __name__ == "__main__":
    main()
