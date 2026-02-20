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

# ========== НОВЫЕ ТАБЛИЦЫ ЧАСТОТ (из скетчей) ==========
# VRX1 (5.8GHz) – 12 бандов по 8 каналов (всего 96)
VRX1_BANDS = [
    {"name": "A", "freqs": [5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600]},
    {"name": "B", "freqs": [5362, 5399, 5436, 5473, 5500, 5547, 5584, 5621]},
    {"name": "E", "freqs": [5300, 5348, 5366, 5384, 5400, 5420, 5438, 5456]},
    {"name": "F", "freqs": [5129, 5159, 5189, 5219, 5249, 5279, 5309, 5339]},
    {"name": "R", "freqs": [4990, 5020, 5050, 5080, 5110, 5150, 5170, 5200]},
    {"name": "P", "freqs": [5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613]},
    {"name": "L", "freqs": [4875, 4884, 4900, 4858, 4995, 5032, 5069, 5099]},
    {"name": "U", "freqs": [5960, 5980, 6000, 6020, 6030, 6040, 6050, 6060]},
    {"name": "O", "freqs": [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5735]},
    {"name": "H", "freqs": [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866]},
    {"name": "T", "freqs": [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945]},
    {"name": "N", "freqs": [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880]},
]

# VRX4 (3.3GHz) – 8 бандов по 8 каналов (всего 64) из 3.3.ino
VRX4_BANDS = [
    {"name": "FR1", "freqs": [3360, 3380, 3400, 3420, 3440, 3460, 3480, 3500]},
    {"name": "FR2", "freqs": [3200, 3220, 3240, 3260, 3280, 3300, 3320, 3340]},
    {"name": "FR3", "freqs": [3330, 3350, 3370, 3390, 3410, 3430, 3450, 3470]},
    {"name": "FR4", "freqs": [3170, 3190, 3210, 3230, 3250, 3270, 3290, 3310]},
    {"name": "FR5", "freqs": [3320, 3345, 3370, 3395, 3420, 3445, 3470, 3495]},
    {"name": "FR6", "freqs": [3310, 3330, 3355, 3380, 3405, 3430, 3455, 3480]},
    {"name": "FR7", "freqs": [3220, 3240, 3260, 3280, 3300, 3320, 3340, 3360]},
    {"name": "FR8", "freqs": [3060, 3080, 3100, 3120, 3140, 3160, 3180, 3200]},
]

# ========== КОНФИГУРАЦИЯ VRX ==========
VRX_CONFIG = {
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 2,
        'interface': 'spi',           # прямое SPI-управление
        'cs_pin': 7,                   # пин CS для SPI (выбран свободный GPIO7)
        'bands': VRX1_BANDS,           # список бандов
    },
    'VRX2': {
        'type': '1.2GHz',
        'power_pin': 3,
        'control_pins': {'CH_UP': 19, 'CH_DOWN': 26},
        'channels': [1010, 1040, 1080, 1120, 1160, 1200, 1240, 1280, 1320, 1360, 1258, 1100, 1140],
    },
    'VRX3': {
        'type': '1.5GHz',
        'power_pin': 4,
        'control_pins': {'CH_UP': 21, 'CH_DOWN': 20},
        'channels': [1405, 1430, 1455, 1480, 1505, 1530, 1555, 1580, 1605, 1630, 1655, 1680],
    },
    'VRX4': {
        'type': '3.3GHz',
        'power_pin': 17,
        'interface': 'parallel',       # параллельное управление (CS + S)
        'cs_pins': [9, 10, 11],        # 3 пина CS (выбраны свободные)
        's_pins': [14, 15, 16],        # 3 пина S
        'bands': VRX4_BANDS,
    },
}

# Кнопки управления
BTN_SELECT = 27
BTN_UP = 22
BTN_DOWN = 23

# Текущее состояние: для VRX1 и VRX4 храним (band_index, channel_index), для остальных – линейный индекс
channel_states = {
    'VRX1': {'band': 0, 'channel': 0},
    'VRX2': {'channel': 0},
    'VRX3': {'channel': 0},
    'VRX4': {'band': 0, 'channel': 0},
}

app_state = "vrx_select"
VERSION = "2.0"
rssi_value = 0
autosearch_active = False
active_vrx = None

# ========== ФУНКЦИИ УПРАВЛЕНИЯ ==========
def set_vrx_power(vrx, power_on):
    """Включение/выключение питания VRX (инвертированная логика)"""
    config = VRX_CONFIG[vrx]
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)

def reset_vrx_channels(vrx):
    """Сброс каналов VRX"""
    if vrx in ['VRX1', 'VRX4']:
        channel_states[vrx]['band'] = 0
        channel_states[vrx]['channel'] = 0
    else:
        channel_states[vrx]['channel'] = 0

def set_frequency_spi(freq_mhz, cs_pin):
    """Установка частоты через SPI (для VRX1, как в 5.8.ino)"""
    # Расчет регистров для RX5808
    N = (freq_mhz - 479) // 2
    data0 = (N & 0x1F) * 32 + 17
    data1 = ((N >> 5) & 0x3F) * 16 + ((N >> 5) >> 2)
    data2 = (N >> 11) & 0x0F
    data3 = 0

    # Активация CS
    GPIO.output(cs_pin, GPIO.LOW)
    spi.write(bytes([data0, data1, data2, data3]))
    GPIO.output(cs_pin, GPIO.HIGH)

def set_frequency_parallel(band_index, channel_index, cs_pins, s_pins):
    """Установка частоты через параллельные пины CS и S (для VRX4, как в 3.3.ino)"""
    # Получаем биты из таблицы (здесь для простоты используем индексы,
    # но в реальности биты могут зависеть от конкретного канала.
    # В 3.3.ino каждый канал имеет свои cs_bits и s_bits.
    # Для демонстрации используем линейное отображение: band -> cs, channel -> s.
    # В реальности нужно хранить биты в структуре данных.
    # Здесь мы реализуем упрощённо: cs = band (0..7), s = channel (0..7) в виде трёхбитных чисел.
    cs_bits = band_index
    s_bits = channel_index
    for i, pin in enumerate(cs_pins):
        GPIO.output(pin, (cs_bits >> i) & 1)
    for i, pin in enumerate(s_pins):
        GPIO.output(pin, (s_bits >> i) & 1)

def set_vrx_channel(vrx):
    """Установить текущий канал для VRX в соответствии с состоянием"""
    config = VRX_CONFIG[vrx]
    if vrx == 'VRX1':
        band = channel_states[vrx]['band']
        channel = channel_states[vrx]['channel']
        freq = config['bands'][band]['freqs'][channel]
        set_frequency_spi(freq, config['cs_pin'])
        print(f"VRX1 установлен: банд {config['bands'][band]['name']} канал {channel+1} частота {freq} МГц")
    elif vrx == 'VRX4':
        band = channel_states[vrx]['band']
        channel = channel_states[vrx]['channel']
        freq = config['bands'][band]['freqs'][channel]
        set_frequency_parallel(band, channel, config['cs_pins'], config['s_pins'])
        print(f"VRX4 установлен: банд {config['bands'][band]['name']} канал {channel+1} частота {freq} МГц")
    else:
        # Для остальных VRX управление через эмуляцию кнопок (ничего не делаем, т.к. канал меняется press_button)
        pass

# Эмуляция нажатия кнопки на VRX (для старых типов)
def press_button(pin, duration=0.1):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

def change_channel(direction, modifier=False):
    """
    Изменение канала/банда.
    modifier=False: UP/DOWN меняют канал внутри текущего банда (для VRX1/4) или линейный канал (для остальных).
    modifier=True:  UP/DOWN меняют банд (только для VRX1/4).
    """
    global current_vrx
    state = channel_states[current_vrx]
    config = VRX_CONFIG[current_vrx]

    if current_vrx in ['VRX1', 'VRX4']:
        bands = config['bands']
        if modifier:  # меняем банд
            if direction == 'UP':
                state['band'] = (state['band'] + 1) % len(bands)
            else:
                state['band'] = (state['band'] - 1) % len(bands)
            # При смене банда сбрасываем канал на 0 (как в скетчах)
            state['channel'] = 0
        else:  # меняем канал внутри банда
            if direction == 'UP':
                state['channel'] = (state['channel'] + 1) % len(bands[state['band']]['freqs'])
            else:
                state['channel'] = (state['channel'] - 1) % len(bands[state['band']]['freqs'])
        # Устанавливаем частоту через соответствующий интерфейс
        set_vrx_channel(current_vrx)
    else:
        # Старое поведение: линейное переключение каналов через эмуляцию кнопок
        channels = config['channels']
        if direction == 'UP':
            state['channel'] = (state['channel'] + 1) % len(channels)
            press_button(config['control_pins']['CH_UP'])
        else:
            state['channel'] = (state['channel'] - 1) % len(channels)
            press_button(config['control_pins']['CH_DOWN'])

    update_display()
    send_state_to_esp32()

# ========== АВТОПОИСК ДЛЯ VRX1 ==========
def autosearch():
    global autosearch_active, rssi_value, current_vrx
    if current_vrx != 'VRX1':
        return

    autosearch_active = True
    update_display()

    config = VRX_CONFIG['VRX1']
    state = channel_states['VRX1']
    best_rssi = -1
    best_band = 0
    best_channel = 0

    # Сохраняем исходную позицию
    orig_band = state['band']
    orig_channel = state['channel']

    # Сканируем все банды и каналы
    for b_idx, band in enumerate(config['bands']):
        for c_idx, freq in enumerate(band['freqs']):
            # Устанавливаем частоту
            set_frequency_spi(freq, config['cs_pin'])
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
                best_band = b_idx
                best_channel = c_idx

    # Возвращаемся на лучший канал
    state['band'] = best_band
    state['channel'] = best_channel
    set_vrx_channel('VRX1')
    autosearch_active = False
    update_display()
    print(f"Автопоиск завершён. Лучший: банд {config['bands'][best_band]['name']} канал {best_channel+1}, RSSI={best_rssi}")

# ========== ОТОБРАЖЕНИЕ ==========
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
            band = config['bands'][state['band']]
            freq = band['freqs'][state['channel']]
            draw.text((0, 0), f"VRX1 (5.8GHz)", font=font, fill=255)
            draw.text((0, 16), f"{band['name']} CH{state['channel']+1}", font=font, fill=255)
            draw.text((0, 32), f"Freq: {freq} MHz", font=font, fill=255)
            draw.text((0, 48), f"RSSI: {rssi_value}", font=font, fill=255)
            if autosearch_active:
                draw.text((0, 56), "Auto Search", font=font, fill=255)
        else:
            draw.text((0, 0), "VRX System", font=font, fill=255)
            draw.text((0, 16), "Select VRX1", font=font, fill=255)
            draw.text((0, 32), "for I2C display", font=font, fill=255)

        i2c_display.image(image)
        i2c_display.show()
    except Exception as e:
        print(f"Ошибка обновления I2C дисплея: {e}")

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
            font_large = font_medium = font_small = ImageFont.load_default()

        title = "ВЫБОР VRX"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))

        y_pos = 60
        for vrx in VRX_CONFIG:
            color = (0, 255, 0) if vrx == current_vrx else (255, 255, 255)
            text = f"{vrx} ({VRX_CONFIG[vrx]['type']})"
            draw.text((width//2 - 100, y_pos), text, font=font_medium, fill=color)
            y_pos += 30

        instruction = "SELECT: выбрать  UP/DOWN: переключение"
        instr_width = draw.textlength(instruction, font=font_small)
        draw.text((width//2 - instr_width//2, height - 30), instruction, font=font_small, fill=(200, 200, 200))

        disp.image(image)
    except Exception as e:
        print(f"Ошибка отображения выбора VRX: {e}")

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
            font_large = font_medium = font_small = ImageFont.load_default()

        config = VRX_CONFIG[current_vrx]
        state = channel_states[current_vrx]

        # Заголовок
        title = f"{current_vrx} ({config['type']})"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))

        # Для VRX1 и VRX4 отображаем банд и канал
        if current_vrx in ['VRX1', 'VRX4']:
            band = config['bands'][state['band']]
            freq = band['freqs'][state['channel']]
            band_name = band['name']
            channel_num = state['channel'] + 1
            total_channels = len(band['freqs'])
            band_info = f"Банд: {band_name}  Канал: {channel_num}/{total_channels}"
        else:
            # Для остальных – линейный канал
            channels = config['channels']
            freq = channels[state['channel']]
            band_info = f"Канал: {state['channel']+1}/{len(channels)}"

        # Частота
        freq_text = f"Частота: {freq} МГц"
        freq_width = draw.textlength(freq_text, font=font_medium)
        draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))

        # Информация о банде/канале
        band_width = draw.textlength(band_info, font=font_small)
        draw.text((width//2 - band_width//2, 90), band_info, font=font_small, fill=(255, 255, 255))

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
        if current_vrx == 'VRX1':
            instruction = "UP/DOWN: канал  SEL+UP/DOWN: банд  HOLD SEL: автопоиск"
        elif current_vrx == 'VRX4':
            instruction = "UP/DOWN: канал  SEL+UP/DOWN: банд  SELECT: меню"
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

def update_display():
    if app_state == "vrx_select":
        show_vrx_selection()
    elif app_state == "main":
        show_main_screen()

# ========== НАСТРОЙКА GPIO ==========
def setup_gpio():
    # Пины питания VRX
    for vrx, config in VRX_CONFIG.items():
        GPIO.setup(config['power_pin'], GPIO.OUT)
        GPIO.output(config['power_pin'], GPIO.HIGH)

    # Пины управления для старых VRX (VRX2, VRX3)
    for vrx in ['VRX2', 'VRX3']:
        config = VRX_CONFIG[vrx]
        for pin in config['control_pins'].values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)

    # Пины для VRX1 (SPI CS)
    GPIO.setup(VRX_CONFIG['VRX1']['cs_pin'], GPIO.OUT)
    GPIO.output(VRX_CONFIG['VRX1']['cs_pin'], GPIO.HIGH)

    # Пины для VRX4 (параллельные)
    for pin in VRX_CONFIG['VRX4']['cs_pins'] + VRX_CONFIG['VRX4']['s_pins']:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    # Кнопки
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ========== ОТПРАВКА СОСТОЯНИЯ НА ESP32 ==========
def send_state_to_esp32():
    if not esp32:
        return
    vrx = current_vrx
    state = channel_states[vrx]
    config = VRX_CONFIG[vrx]

    if vrx in ['VRX1', 'VRX4']:
        band = config['bands'][state['band']]
        freq = band['freqs'][state['channel']]
        band_name = band['name']
        message = f"VRX:{vrx}:{band_name}:{state['channel']+1}:{freq}:{rssi_value}\n"
    else:
        channels = config['channels']
        freq = channels[state['channel']]
        message = f"VRX:{vrx}:{state['channel']+1}:{freq}:{rssi_value}\n"

    try:
        esp32.write(message.encode())
        print(f"Отправлено на ESP32: {message.strip()}")
    except Exception as e:
        print(f"Ошибка отправки на ESP32: {e}")

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
                        # Устанавливаем начальный канал (для VRX1/4 вызываем прямое управление)
                        if vrx in ['VRX1', 'VRX4']:
                            set_vrx_channel(vrx)
                        app_state = "main"
                        update_display()
                        send_state_to_esp32()
                elif command == "CH_UP":
                    if app_state == "main":
                        change_channel('UP', modifier=False)
                elif command == "CH_DOWN":
                    if app_state == "main":
                        change_channel('DOWN', modifier=False)
                elif command == "BAND_UP":
                    if app_state == "main" and current_vrx in ['VRX1', 'VRX4']:
                        change_channel('UP', modifier=True)
                elif command == "BAND_DOWN":
                    if app_state == "main" and current_vrx in ['VRX1', 'VRX4']:
                        change_channel('DOWN', modifier=True)
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
        time.sleep(0.1)

# ========== ПЕРЕКЛЮЧЕНИЕ VRX В РЕЖИМЕ ВЫБОРА ==========
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
    select_held = False

    print("Система готова к работе")

    try:
        while True:
            current_time = time.time()

            # Кнопка SELECT
            select_btn = GPIO.input(BTN_SELECT)
            if select_btn != last_select:
                if select_btn == GPIO.LOW:
                    select_press_time = current_time
                    select_held = False
                else:
                    press_duration = current_time - select_press_time
                    if press_duration > 2.0 and app_state == "main" and current_vrx == "VRX1":
                        autosearch()
                    elif press_duration > 0.1:
                        if app_state == "vrx_select":
                            set_vrx_power(current_vrx, True)
                            active_vrx = current_vrx
                            if current_vrx in ['VRX1', 'VRX4']:
                                set_vrx_channel(current_vrx)
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

            # Кнопка UP
            up_btn = GPIO.input(BTN_UP)
            if up_btn != last_up:
                if up_btn == GPIO.LOW:
                    # Если SELECT уже нажат (удерживается), то modifier=True
                    modifier = (GPIO.input(BTN_SELECT) == GPIO.LOW)
                    if app_state == "vrx_select":
                        change_vrx('UP')
                    elif app_state == "main":
                        change_channel('UP', modifier=modifier)
                last_up = up_btn

            # Кнопка DOWN
            down_btn = GPIO.input(BTN_DOWN)
            if down_btn != last_down:
                if down_btn == GPIO.LOW:
                    modifier = (GPIO.input(BTN_SELECT) == GPIO.LOW)
                    if app_state == "vrx_select":
                        change_vrx('DOWN')
                    elif app_state == "main":
                        change_channel('DOWN', modifier=modifier)
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
