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

# ========== НОВЫЕ ПОЛНЫЕ ЧАСТОТНЫЕ СЕТКИ ==========

# Частотная сетка для VRX1 (5.8 ГГц) из 5.8.ino (12 бандов по 8 каналов)
VRX1_CHANNELS = [
    # Band A
    5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600,
    # Band B
    5362, 5399, 5436, 5473, 5500, 5547, 5584, 5621,
    # Band E
    5300, 5348, 5366, 5384, 5400, 5420, 5438, 5456,
    # Band F
    5129, 5159, 5189, 5219, 5249, 5279, 5309, 5339,
    # Band R
    4990, 5020, 5050, 5080, 5110, 5150, 5170, 5200,
    # Band P
    5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613,
    # Band L
    4875, 4884, 4900, 4858, 4995, 5032, 5069, 5099,
    # Band U
    5960, 5980, 6000, 6020, 6030, 6040, 6050, 6060,
    # Band O
    5865, 5845, 5825, 5805, 5785, 5765, 5745, 5735,
    # Band H
    5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866,
    # Band T
    5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945,
    # Band N
    5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880
]

# Данные для VRX4 (3.3 ГГц) из 3.3.ino (8 бандов по 8 каналов)
# Каждый канал: (частота, cs_bits, s_bits)
VRX4_CHANNELS = [
    # FR1 (S=000)
    (3360, 0b000, 0b000), (3380, 0b001, 0b000), (3400, 0b010, 0b000), (3420, 0b011, 0b000),
    (3440, 0b100, 0b000), (3460, 0b101, 0b000), (3480, 0b110, 0b000), (3500, 0b111, 0b000),
    # FR2 (S=001)
    (3200, 0b000, 0b001), (3220, 0b001, 0b001), (3240, 0b010, 0b001), (3260, 0b011, 0b001),
    (3280, 0b100, 0b001), (3300, 0b101, 0b001), (3320, 0b110, 0b001), (3340, 0b111, 0b001),
    # FR3 (S=010)
    (3330, 0b000, 0b010), (3350, 0b001, 0b010), (3370, 0b010, 0b010), (3390, 0b011, 0b010),
    (3410, 0b100, 0b010), (3430, 0b101, 0b010), (3450, 0b110, 0b010), (3470, 0b111, 0b010),
    # FR4 (S=011)
    (3170, 0b000, 0b011), (3190, 0b001, 0b011), (3210, 0b010, 0b011), (3230, 0b011, 0b011),
    (3250, 0b100, 0b011), (3270, 0b101, 0b011), (3290, 0b110, 0b011), (3310, 0b111, 0b011),
    # FR5 (S=100)
    (3320, 0b000, 0b100), (3345, 0b001, 0b100), (3370, 0b010, 0b100), (3395, 0b011, 0b100),
    (3420, 0b100, 0b100), (3445, 0b101, 0b100), (3470, 0b110, 0b100), (3495, 0b111, 0b100),
    # FR6 (S=101)
    (3310, 0b000, 0b101), (3330, 0b001, 0b101), (3355, 0b010, 0b101), (3380, 0b011, 0b101),
    (3405, 0b100, 0b101), (3430, 0b101, 0b101), (3455, 0b110, 0b101), (3480, 0b111, 0b101),
    # FR7 (S=110)
    (3220, 0b000, 0b110), (3240, 0b001, 0b110), (3260, 0b010, 0b110), (3280, 0b011, 0b110),
    (3300, 0b100, 0b110), (3320, 0b101, 0b110), (3340, 0b110, 0b110), (3360, 0b111, 0b110),
    # FR8 (S=111)
    (3060, 0b000, 0b111), (3080, 0b001, 0b111), (3100, 0b010, 0b111), (3120, 0b011, 0b111),
    (3140, 0b100, 0b111), (3160, 0b101, 0b111), (3180, 0b110, 0b111), (3200, 0b111, 0b111)
]

# Конфигурация VRX с обновлёнными пинами и каналами
VRX_CONFIG = {
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 2,
        # Пины для программного SPI (CLK, MOSI, CS) – выбраны свободные GPIO
        'spi_pins': {'clk': 18, 'mosi': 16, 'cs': 14},
        'channels': VRX1_CHANNELS  # плоский список частот
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
        # Пины для параллельного управления CS и S
        'cs_pins': [7, 8, 9],    # CS1, CS2, CS3
        's_pins': [10, 11, 15],  # S1, S2, S3
        'channels': VRX4_CHANNELS  # список кортежей (freq, cs_bits, s_bits)
    }
}

# Кнопки управления
BTN_SELECT = 27
BTN_UP = 22
BTN_DOWN = 23

# Текущее состояние
current_vrx = 'VRX1'
channel_states = {
    'VRX1': {'channel': 0},   # индекс от 0 до 95
    'VRX2': {'channel': 0},
    'VRX3': {'channel': 0},
    'VRX4': {'channel': 0},   # индекс от 0 до 63
}
app_state = "vrx_select"
VERSION = "2.0"
rssi_value = 0
autosearch_active = False
active_vrx = None

# Функции для работы с дисплеем (оставлены без изменений)
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

# Функция управления питанием (инвертированная логика)
def set_vrx_power(vrx, power_on):
    config = VRX_CONFIG[vrx]
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)
    status = "ВКЛ" if power_on else "ВЫКЛ"
    print(f"{vrx} питание: {status}")

def reset_vrx_channels(vrx):
    channel_states[vrx]['channel'] = 0
    print(f"{vrx}: канал сброшен на 0")

# ========== СПЕЦИАЛИЗИРОВАННЫЕ ФУНКЦИИ УПРАВЛЕНИЯ VRX ==========

# ---- для VRX1 (5.8 ГГц, программный SPI) ----
def init_vrx1_spi():
    """Настройка пинов для программного SPI VRX1"""
    pins = VRX_CONFIG['VRX1']['spi_pins']
    GPIO.setup(pins['clk'], GPIO.OUT)
    GPIO.setup(pins['mosi'], GPIO.OUT)
    GPIO.setup(pins['cs'], GPIO.OUT)
    GPIO.output(pins['clk'], GPIO.LOW)
    GPIO.output(pins['mosi'], GPIO.LOW)
    GPIO.output(pins['cs'], GPIO.HIGH)  # CS неактивен (высокий)

def spi_send_byte(byte, clk_pin, mosi_pin):
    """Отправляет один байт LSB first через программный SPI"""
    for i in range(8):
        # Устанавливаем бит данных (начиная с младшего)
        bit = (byte >> i) & 1
        GPIO.output(mosi_pin, bit)
        # Тактовый импульс
        GPIO.output(clk_pin, GPIO.HIGH)
        time.sleep(0.000001)  # небольшая задержка
        GPIO.output(clk_pin, GPIO.LOW)
        time.sleep(0.000001)

def set_vrx1_frequency(freq_mhz):
    """Устанавливает частоту VRX1 через программный SPI"""
    # Вычисляем N по формуле из скетча
    N = int((freq_mhz - 479) / 2)
    Nhigh = N >> 5
    Nlow = N & 0x1F
    data0 = Nlow * 32 + 17
    data1 = Nhigh * 16 + Nlow // 8
    data2 = Nhigh // 16
    data3 = 0

    pins = VRX_CONFIG['VRX1']['spi_pins']
    # Активируем CS
    GPIO.output(pins['cs'], GPIO.LOW)
    time.sleep(0.00001)
    # Отправляем 4 байта
    spi_send_byte(data0, pins['clk'], pins['mosi'])
    spi_send_byte(data1, pins['clk'], pins['mosi'])
    spi_send_byte(data2, pins['clk'], pins['mosi'])
    spi_send_byte(data3, pins['clk'], pins['mosi'])
    # Деактивируем CS
    GPIO.output(pins['cs'], GPIO.HIGH)
    print(f"VRX1 установлена частота {freq_mhz} МГц")

# ---- для VRX4 (3.3 ГГц, параллельное управление) ----
def set_vrx4_channel(index):
    """Устанавливает канал VRX4 по индексу (0-63)"""
    if index < 0 or index >= len(VRX4_CHANNELS):
        return
    freq, cs_bits, s_bits = VRX4_CHANNELS[index]
    cs_pins = VRX_CONFIG['VRX4']['cs_pins']
    s_pins = VRX_CONFIG['VRX4']['s_pins']

    # Устанавливаем CS пины (бит 0 - младший, соответствует CS1?)
    # В скетче порядок: cs1Pin, cs2Pin, cs3Pin соответствуют битам 2,1,0 или 0,1,2?
    # В функции setChannel они устанавливаются так:
    # digitalWrite(cs1Pin, INVERT_SIGNALS ^ ((ch.cs_bits >> 2) & 1));
    # digitalWrite(cs2Pin, INVERT_SIGNALS ^ ((ch.cs_bits >> 1) & 1));
    # digitalWrite(cs3Pin, INVERT_SIGNALS ^ ((ch.cs_bits >> 0) & 1));
    # Значит cs1 = бит 2, cs2 = бит 1, cs3 = бит 0. Инвертирование не используем.
    GPIO.output(cs_pins[0], (cs_bits >> 2) & 1)
    GPIO.output(cs_pins[1], (cs_bits >> 1) & 1)
    GPIO.output(cs_pins[2], (cs_bits >> 0) & 1)

    # S пины: s1Pin, s2Pin, s3Pin соответствуют битам 2,1,0 аналогично
    GPIO.output(s_pins[0], (s_bits >> 2) & 1)
    GPIO.output(s_pins[1], (s_bits >> 1) & 1)
    GPIO.output(s_pins[2], (s_bits >> 0) & 1)

    print(f"VRX4 установлен канал {index+1}: {freq} МГц (cs={cs_bits:03b}, s={s_bits:03b})")

# ---- общая функция переключения канала ----
def change_channel(direction):
    global autosearch_active
    state = channel_states[current_vrx]
    config = VRX_CONFIG[current_vrx]
    channels = config['channels']
    max_index = len(channels) - 1

    # Изменяем индекс
    if direction == 'UP':
        state['channel'] = (state['channel'] + 1) % len(channels)
    else:
        state['channel'] = (state['channel'] - 1) % len(channels)

    # Вызываем соответствующий метод установки
    if current_vrx == 'VRX1':
        freq = channels[state['channel']]
        set_vrx1_frequency(freq)
    elif current_vrx == 'VRX4':
        set_vrx4_channel(state['channel'])
    else:
        # Для остальных VRX используем старый метод с кнопками
        if direction == 'UP':
            press_button(config['control_pins']['CH_UP'])
        else:
            press_button(config['control_pins']['CH_DOWN'])

    # Обновление дисплея
    update_display()
    send_state_to_esp32()

# Остальные функции (show_vrx_selection, show_main_screen, update_display, setup_gpio, press_button, autosearch, send_state_to_esp32, handle_esp32_commands, change_vrx, main)
# нужно модифицировать с учётом новых каналов и, возможно, отображения.

# В show_main_screen нужно корректно получать частоту для VRX1 и VRX4.
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
        channels = config['channels']
        idx = state['channel']
        if idx >= len(channels):
            idx = len(channels)-1
            state['channel'] = idx

        # Получаем частоту в зависимости от типа VRX
        if current_vrx == 'VRX1':
            freq = channels[idx]
            channel_display = idx + 1
            total = len(channels)
        elif current_vrx == 'VRX4':
            freq = channels[idx][0]  # первый элемент кортежа
            channel_display = idx + 1
            total = len(channels)
        else:
            freq = channels[idx]
            channel_display = idx + 1
            total = len(channels)

        # Отображаем частоту
        freq_text = f"Частота: {freq} МГц"
        freq_width = draw.textlength(freq_text, font=font_medium)
        draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))

        # Номер канала
        channel_text = f"Канал: {channel_display}/{total}"
        channel_width = draw.textlength(channel_text, font=font_small)
        draw.text((width//2 - channel_width//2, 90), channel_text, font=font_small, fill=(255, 255, 255))

        # RSSI только для VRX1 (пока)
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
        if current_vrx == 'VRX1':
            instruction = "UP: канал+  DOWN: канал-  HOLD SELECT: автопоиск"
        else:
            instruction = "UP: канал+  DOWN: канал-  SELECT: меню"
        instr_width = draw.textlength(instruction, font=font_small)
        draw.text((width//2 - instr_width//2, height - 40), instruction, font=font_small, fill=(200, 200, 200))

        disp.image(image)

    except Exception as e:
        print(f"Ошибка обновления дисплея: {e}")
        try:
            image, width, height = create_display_image()
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
            disp.image(image)
        except:
            pass

    update_i2c_display()

def show_vrx_selection():
    # без изменений
    ...

def update_display():
    if app_state == "vrx_select":
        show_vrx_selection()
    elif app_state == "main":
        show_main_screen()

# Инициализация GPIO с добавлением новых пинов
def setup_gpio():
    for vrx, config in VRX_CONFIG.items():
        GPIO.setup(config['power_pin'], GPIO.OUT)
        GPIO.output(config['power_pin'], GPIO.HIGH)
        print(f"{vrx} питание инициализировано (пин {config['power_pin']}: HIGH)")

    # Для VRX с control_pins (старые)
    for vrx, config in VRX_CONFIG.items():
        if 'control_pins' in config:
            for pin in config['control_pins'].values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)

    # Для VRX1 (SPI пины)
    if 'spi_pins' in VRX_CONFIG['VRX1']:
        init_vrx1_spi()

    # Для VRX4 (CS и S пины)
    if 'cs_pins' in VRX_CONFIG['VRX4']:
        for pin in VRX_CONFIG['VRX4']['cs_pins']:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)  # начальное состояние
        for pin in VRX_CONFIG['VRX4']['s_pins']:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

    # Кнопки
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def press_button(pin, duration=0.1):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

# Автопоиск оставляем только для VRX1 (пока)
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
    channels = config['channels']

    try:
        for ch_idx in range(len(channels)):
            # Устанавливаем канал
            if state['channel'] != ch_idx:
                state['channel'] = ch_idx
                set_vrx1_frequency(channels[ch_idx])
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
                best_channel = ch_idx
    except Exception as e:
        print(f"Ошибка в автопоиске: {e}")
    finally:
        autosearch_active = False

    # Возвращаемся к лучшему каналу
    if state['channel'] != best_channel:
        state['channel'] = best_channel
        set_vrx1_frequency(channels[best_channel])
    update_display()
    print(f"Автопоиск завершен. Лучший канал: {best_channel+1}, RSSI: {best_rssi}")

def send_state_to_esp32():
    if not esp32:
        return
    vrx = current_vrx
    state = channel_states[vrx]
    config = VRX_CONFIG[vrx]
    channels = config['channels']
    idx = state['channel']
    if idx >= len(channels):
        idx = len(channels)-1
    if vrx == 'VRX1':
        freq = channels[idx]
    elif vrx == 'VRX4':
        freq = channels[idx][0]
    else:
        freq = channels[idx]
    message = f"VRX:{vrx}:{idx}:{freq}:{rssi_value}\n"
    try:
        esp32.write(message.encode())
        print(f"Отправлено на ESP32: {message.strip()}")
    except Exception as e:
        print(f"Ошибка отправки на ESP32: {e}")

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
                        app_state = "main"
                        update_display()
                        send_state_to_esp32()
                elif command == "CH_UP" and app_state == "main":
                    change_channel('UP')
                elif command == "CH_DOWN" and app_state == "main":
                    change_channel('DOWN')
                elif command == "AUTO_SEARCH" and app_state == "main" and current_vrx == "VRX1":
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

def main():
    global app_state, current_vrx, active_vrx
    print("Запуск системы управления VRX...")
    try:
        setup_gpio()
        print("GPIO инициализированы успешно")
    except Exception as e:
        print(f"Ошибка инициализации GPIO: {e}")
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
