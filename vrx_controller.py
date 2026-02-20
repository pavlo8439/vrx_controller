#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import math
import board
import digitalio
import threading
import traceback
from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import ili9341
import spidev  # для SPI (MCP3008 и RX5808)

# Попробуем импортировать библиотеку для I2C дисплея
try:
    import adafruit_ssd1306
    I2C_DISPLAY_AVAILABLE = True
    print("Библиотека для I2C дисплея доступна")
except ImportError:
    I2C_DISPLAY_AVAILABLE = False
    print("Библиотека для I2C дисплея недоступна")

# ========== НАСТРОЙКА GPIO ==========
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ========== ДИСПЛЕЙ ILI9341 (SPI) ==========
cs_pin = digitalio.DigitalInOut(board.CE0)
dc_pin = digitalio.DigitalInOut(board.D24)
reset_pin = digitalio.DigitalInOut(board.D25)
BAUDRATE = 24000000
spi = board.SPI()

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
    print("Дисплей ILI9341 инициализирован успешно")
except Exception as e:
    print(f"Ошибка инициализации дисплея: {e}")
    traceback.print_exc()
    exit(1)

# ========== I2C ДИСПЛЕЙ (SSD1306) ==========
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
        traceback.print_exc()
        i2c_display = None

# ========== НАСТРОЙКА SPI ДЛЯ MCP3008 И RX5808 ==========
# Создаём объект SPI (используем аппаратный SPI0)
spi_dev = spidev.SpiDev()
spi_dev.open(0, 0)  # SPI0, CE0 (но мы будем управлять CS вручную)
spi_dev.max_speed_hz = 1000000
spi_dev.mode = 0
spi_dev.bits_per_word = 8
spi_dev.lsbfirst = True  # для RX5808 нужен LSB first

# Пины CS для разных устройств
RX5808_CS_PIN = 7      # GPIO7 (CE1) для модуля RX5808
MCP3008_CS_PIN = 8     # GPIO8 (CE0) для MCP3008 (если не конфликтует с дисплеем)
GPIO.setup(RX5808_CS_PIN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(MCP3008_CS_PIN, GPIO.OUT, initial=GPIO.HIGH)

# ========== КОНФИГУРАЦИЯ VRX ==========
# Полная частотная сетка 5.8 ГГц (12 диапазонов x 8 каналов = 96)
# Данные из Arduino-скетча
BANDS_5G = [
    ("A", [5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600]),
    ("B", [5362, 5399, 5436, 5473, 5500, 5547, 5584, 5621]),
    ("E", [5300, 5348, 5366, 5384, 5400, 5420, 5438, 5456]),
    ("F", [5129, 5159, 5189, 5219, 5249, 5279, 5309, 5339]),
    ("R", [4990, 5020, 5050, 5080, 5110, 5150, 5170, 5200]),
    ("P", [5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613]),
    ("L", [4875, 4884, 4900, 4858, 4995, 5032, 5069, 5099]),
    ("U", [5960, 5980, 6000, 6020, 6030, 6040, 6050, 6060]),
    ("O", [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5735]),
    ("H", [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866]),
    ("T", [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945]),
    ("N", [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880])
]

VRX_CONFIG = {
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 2,
        # Пины управления (CH_UP/CH_DOWN) больше не используются для VRX1,
        # оставлены для совместимости, но не применяются.
        'control_pins': {'CH_UP': 6, 'CH_DOWN': 13},
        'bands': BANDS_5G,          # список кортежей (имя, список частот)
        'current_band': 0,           # индекс текущего диапазона
        'current_ch': 0,              # индекс канала в диапазоне
        'spi_cs': RX5808_CS_PIN,     # пин CS для модуля RX5808
        'rssi_channel': 0,            # канал MCP3008 для RSSI
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
        'control_pins': {'CH_UP': 12, 'CH_DOWN': 5},
        'channels': [
            3290, 3310, 3330, 3350, 3370, 3390, 3410, 3430,
            3450, 3470, 3490, 3510, 3530, 3550, 3570, 3590,
            3610, 3630, 3650, 3670, 3690, 3710, 3730, 3750,
            3770, 3790, 3810, 3830, 3850, 3870, 3890, 3910
        ]
    }
}

# ========== КНОПКИ ==========
BTN_SELECT = 27
BTN_UP = 22
BTN_DOWN = 23

# ========== ГЛОБАЛЬНЫЕ СОСТОЯНИЯ ==========
current_vrx = 'VRX1'
app_state = "vrx_select"          # "vrx_select" или "main"
VERSION = "2.0"                    # обновлённая версия
active_vrx = None                  # какой VRX сейчас включен

# Состояния каналов для VRX2-4 (оставляем как было)
channel_states = {
    'VRX2': {'channel': 0},
    'VRX3': {'channel': 0},
    'VRX4': {'channel': 0},
}

# Для VRX1 храним отдельно
vrx1_band = 0
vrx1_channel = 0

# Параметры RSSI
rssi_raw = 0
rssi_filtered = 0
rssi_percent = 0
rssi_min = 50
rssi_max = 614
rssi_buffer = [0]*5
rssi_buffer_idx = 0

# Автопоиск
autosearch_active = False
autosearch_band = 0
autosearch_ch = 0
autosearch_best_rssi = -1
autosearch_best_band = 0
autosearch_best_ch = 0
autosearch_total = 0
autosearch_start_time = 0

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С VRX1 ==========

def set_rx5808_frequency(freq_mhz):
    """Установка частоты на модуле RX5808 через SPI."""
    # Формула: N = (freq - 479) / 2
    N = (freq_mhz - 479) // 2
    Nhigh = N >> 5
    Nlow = N & 0x1F
    data0 = (Nlow << 5) + 17   # в Arduino: Nlow * 32 + 17 (сдвиг влево на 5)
    data1 = (Nhigh << 4) + (Nlow >> 3)  # Nhigh*16 + Nlow/8
    data2 = Nhigh >> 4
    data3 = 0

    # Отправка данных по SPI с ручным управлением CS
    GPIO.output(RX5808_CS_PIN, GPIO.LOW)
    spi_dev.writebytes([data0, data1, data2, data3])
    GPIO.output(RX5808_CS_PIN, GPIO.HIGH)
    # print(f"Установлена частота {freq_mhz} МГц")

def read_mcp3008(channel):
    """Чтение значения с MCP3008 по SPI (канал 0..7)."""
    if channel < 0 or channel > 7:
        return 0
    # Команда: стартовый бит, режим single-ended, номер канала
    cmd = [1, (8 + channel) << 4, 0]
    GPIO.output(MCP3008_CS_PIN, GPIO.LOW)
    resp = spi_dev.xfer2(cmd)
    GPIO.output(MCP3008_CS_PIN, GPIO.HIGH)
    # Ответ: 10 бит, объединяем второй и третий байт
    value = ((resp[1] & 3) << 8) + resp[2]
    return value

def apply_rssi_filter(raw):
    """Комбинированный фильтр (медиана + экспоненциальный)."""
    global rssi_buffer, rssi_buffer_idx
    # Медианный фильтр на 5 отсчётов
    rssi_buffer[rssi_buffer_idx] = raw
    rssi_buffer_idx = (rssi_buffer_idx + 1) % 5
    # Сортировка для медианы
    temp = sorted(rssi_buffer)
    median = temp[2]
    # Экспоненциальное сглаживание (alpha = 0.3)
    global rssi_filtered
    rssi_filtered = int(0.3 * median + 0.7 * rssi_filtered)
    return rssi_filtered

def update_rssi():
    """Обновить значение RSSI (вызывать периодически)."""
    global rssi_raw, rssi_filtered, rssi_percent, rssi_min, rssi_max
    raw = read_mcp3008(VRX_CONFIG['VRX1']['rssi_channel'])
    rssi_raw = raw
    filtered = apply_rssi_filter(raw)
    # Автокалибровка min/max (как в Arduino)
    if not autosearch_active:
        if filtered < rssi_min and filtered > 0:
            rssi_min = filtered
        if filtered > rssi_max and filtered <= 700:
            rssi_max = filtered
        if rssi_max - rssi_min < 50:
            rssi_max = rssi_min + 50
    if rssi_max > rssi_min:
        rssi_percent = int((filtered - rssi_min) * 100 / (rssi_max - rssi_min))
        rssi_percent = max(0, min(100, rssi_percent))
    else:
        rssi_percent = 0

def set_vrx1_frequency_by_index(band_idx, ch_idx):
    """Установить частоту VRX1 по индексам диапазона и канала."""
    band_name, freqs = VRX_CONFIG['VRX1']['bands'][band_idx]
    freq = freqs[ch_idx]
    set_rx5808_frequency(freq)
    return freq

def vrx1_change_channel(direction):
    """Изменить канал в текущем диапазоне (UP/DOWN)."""
    global vrx1_channel, vrx1_band
    band_name, freqs = VRX_CONFIG['VRX1']['bands'][vrx1_band]
    if direction == 'UP':
        vrx1_channel = (vrx1_channel + 1) % len(freqs)
    else:
        vrx1_channel = (vrx1_channel - 1) % len(freqs)
    set_vrx1_frequency_by_index(vrx1_band, vrx1_channel)

def vrx1_change_band(direction):
    """Изменить диапазон (UP/DOWN с модификатором SELECT)."""
    global vrx1_band, vrx1_channel
    bands = VRX_CONFIG['VRX1']['bands']
    if direction == 'UP':
        vrx1_band = (vrx1_band + 1) % len(bands)
    else:
        vrx1_band = (vrx1_band - 1) % len(bands)
    # При смене диапазона сбрасываем канал на первый
    vrx1_channel = 0
    set_vrx1_frequency_by_index(vrx1_band, vrx1_channel)

def autosearch():
    """Автоматический поиск лучшего канала (сканирование всех 96)."""
    global autosearch_active, autosearch_band, autosearch_ch
    global autosearch_best_rssi, autosearch_best_band, autosearch_best_ch
    global autosearch_total, autosearch_start_time, rssi_percent

    if current_vrx != 'VRX1':
        return

    autosearch_active = True
    autosearch_band = 0
    autosearch_ch = 0
    autosearch_best_rssi = -1
    autosearch_best_band = 0
    autosearch_best_ch = 0
    autosearch_total = 0
    autosearch_start_time = time.time()

    # Массив для хранения средних RSSI по каждому каналу
    rssi_averages = [0] * 96
    measurements_per_channel = 20
    channel_measure_count = 0

    print("Автопоиск запущен")
    update_display()

    # Перебираем все каналы
    for band_idx, (band_name, freqs) in enumerate(VRX_CONFIG['VRX1']['bands']):
        for ch_idx in range(len(freqs)):
            if not autosearch_active:  # прерывание по кнопке
                break
            # Устанавливаем частоту
            set_vrx1_frequency_by_index(band_idx, ch_idx)
            time.sleep(0.2)  # ждём стабилизации

            # Измеряем RSSI несколько раз
            total = 0
            for _ in range(measurements_per_channel):
                update_rssi()
                total += rssi_filtered
                time.sleep(0.05)
            avg = total // measurements_per_channel
            idx = band_idx * 8 + ch_idx
            rssi_averages[idx] = avg

            # Конвертируем в проценты
            if rssi_max > rssi_min:
                percent = int((avg - rssi_min) * 100 / (rssi_max - rssi_min))
                percent = max(0, min(100, percent))
            else:
                percent = 0

            # Проверка на лучший
            if percent >= 25 and percent > autosearch_best_rssi:
                autosearch_best_rssi = percent
                autosearch_best_band = band_idx
                autosearch_best_ch = ch_idx
                print(f"Новый лучший: диапазон {band_name}, канал {ch_idx+1}, RSSI {percent}%")

            autosearch_total += 1
            update_display()

    # Завершение
    autosearch_active = False
    if autosearch_best_rssi >= 25:
        # Устанавливаем лучший канал
        vrx1_band = autosearch_best_band
        vrx1_channel = autosearch_best_ch
        set_vrx1_frequency_by_index(vrx1_band, vrx1_channel)
        print(f"Автопоиск завершён. Лучший: диапазон {VRX_CONFIG['VRX1']['bands'][vrx1_band][0]}, канал {vrx1_channel+1}, RSSI {autosearch_best_rssi}%")
    else:
        print("Автопоиск завершён: сигнал не найден")
    update_display()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ДИСПЛЕЯ ==========

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
            band_name, freqs = VRX_CONFIG['VRX1']['bands'][vrx1_band]
            freq = freqs[vrx1_channel]
            draw.text((0, 0), f"VRX1 {band_name}", font=font, fill=255)
            draw.text((0, 16), f"{freq} MHz", font=font, fill=255)
            draw.text((0, 32), f"RSSI: {rssi_percent}%", font=font, fill=255)
            if autosearch_active:
                draw.text((0, 48), "AUTO SEARCH", font=font, fill=255)
        else:
            draw.text((0, 0), "VRX System", font=font, fill=255)
            draw.text((0, 16), "Select VRX1", font=font, fill=255)
            draw.text((0, 32), "for I2C display", font=font, fill=255)
        i2c_display.image(image)
        i2c_display.show()
    except Exception as e:
        print(f"Ошибка I2C дисплея: {e}")

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
        for i, vrx in enumerate(VRX_CONFIG.keys()):
            color = (0, 255, 0) if vrx == current_vrx else (255, 255, 255)
            text = f"{vrx} ({VRX_CONFIG[vrx]['type']})"
            draw.text((width//2 - 100, y_pos), text, font=font_medium, fill=color)
            y_pos += 30

        instr = "SELECT: выбрать  UP/DOWN: переключение"
        instr_width = draw.textlength(instr, font=font_small)
        draw.text((width//2 - instr_width//2, height - 30), instr, font=font_small, fill=(200,200,200))

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

        # Заголовок
        vrx_type = VRX_CONFIG[current_vrx]['type']
        title = f"{current_vrx} ({vrx_type})"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))

        if current_vrx == 'VRX1':
            # Отображение для VRX1
            band_name, freqs = VRX_CONFIG['VRX1']['bands'][vrx1_band]
            freq = freqs[vrx1_channel]
            # Частота
            freq_text = f"{freq} МГц"
            freq_width = draw.textlength(freq_text, font=font_medium)
            draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255,255,255))
            # Диапазон и канал
            band_ch_text = f"Диапазон {band_name}  Канал {vrx1_channel+1}/8"
            band_ch_width = draw.textlength(band_ch_text, font=font_small)
            draw.text((width//2 - band_ch_width//2, 90), band_ch_text, font=font_small, fill=(255,255,255))
            # RSSI
            rssi_text = f"RSSI: {rssi_percent}%"
            rssi_width = draw.textlength(rssi_text, font=font_small)
            draw.text((width//2 - rssi_width//2, 120), rssi_text, font=font_small, fill=(255,255,255))
            # Полоска RSSI
            bar_len = int(rssi_percent * 1.5)  # максимум 150 пикселей
            draw.rectangle((width//2 - 75, 140, width//2 - 75 + bar_len, 150), fill=(0,255,0))
            # Статус автопоиска
            if autosearch_active:
                search_text = "АВТОПОИСК АКТИВЕН"
                search_width = draw.textlength(search_text, font=font_small)
                draw.text((width//2 - search_width//2, 160), search_text, font=font_small, fill=(255,0,0))
            # Подсказки
            instr = "UP/DOWN: канал  SEL+UP/DOWN: диапазон  HOLD SEL: автопоиск"
        else:
            # Для VRX2-4 (старая логика)
            config = VRX_CONFIG[current_vrx]
            state = channel_states[current_vrx]
            if state['channel'] >= len(config['channels']):
                state['channel'] = len(config['channels']) - 1
            freq = config['channels'][state['channel']]
            freq_text = f"Частота: {freq} МГц"
            freq_width = draw.textlength(freq_text, font=font_medium)
            draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255,255,255))
            channel_text = f"Канал: {state['channel']+1}/{len(config['channels'])}"
            channel_width = draw.textlength(channel_text, font=font_small)
            draw.text((width//2 - channel_width//2, 90), channel_text, font=font_small, fill=(255,255,255))
            instr = "UP: канал+  DOWN: канал-  SELECT: меню"

        # Версия
        version_text = f"Ver: {VERSION}"
        version_width = draw.textlength(version_text, font=font_small)
        draw.text((width - version_width - 10, height - 20), version_text, font=font_small, fill=(150,150,150))

        # Инструкция
        instr_width = draw.textlength(instr, font=font_small)
        draw.text((width//2 - instr_width//2, height - 40), instr, font=font_small, fill=(200,200,200))

        disp.image(image)
    except Exception as e:
        print(f"Ошибка обновления дисплея: {e}")
        traceback.print_exc()
        try:
            image, width, height = create_display_image()
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, width, height), fill=(0,0,0))
            disp.image(image)
        except:
            pass
    update_i2c_display()

def update_display():
    if app_state == "vrx_select":
        show_vrx_selection()
    elif app_state == "main":
        show_main_screen()

# ========== УПРАВЛЕНИЕ ПИТАНИЕМ И КАНАЛАМИ (ДЛЯ ВСЕХ VRX) ==========

def set_vrx_power(vrx, power_on):
    config = VRX_CONFIG[vrx]
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)
    status = "ВКЛ" if power_on else "ВЫКЛ"
    print(f"{vrx} питание: {status}")

def reset_vrx_channels(vrx):
    if vrx == 'VRX1':
        # Для VRX1 сброс не требуется, но можно вернуть на первый диапазон/канал
        global vrx1_band, vrx1_channel
        vrx1_band = 0
        vrx1_channel = 0
    else:
        channel_states[vrx]['channel'] = 0

def change_channel(direction):
    """Изменение канала для текущего VRX."""
    global vrx1_band, vrx1_channel
    if current_vrx == 'VRX1':
        vrx1_change_channel(direction)
    else:
        state = channel_states[current_vrx]
        config = VRX_CONFIG[current_vrx]
        if direction == 'UP':
            state['channel'] = (state['channel'] + 1) % len(config['channels'])
            press_button(config['control_pins']['CH_UP'])
        else:
            state['channel'] = (state['channel'] - 1) % len(config['channels'])
            press_button(config['control_pins']['CH_DOWN'])
        # Обеспечение границ
        if state['channel'] < 0:
            state['channel'] = 0
        if state['channel'] >= len(config['channels']):
            state['channel'] = len(config['channels']) - 1
        freq = config['channels'][state['channel']]
        print(f"{current_vrx}: Канал {state['channel']+1}, Частота {freq} МГц")
    update_display()

def change_band(direction):
    """Изменение диапазона для VRX1 (только)."""
    if current_vrx == 'VRX1':
        vrx1_change_band(direction)
        update_display()

def press_button(pin, duration=0.1):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

# ========== НАСТРОЙКА GPIO ==========

def setup_gpio():
    # Пины питания VRX
    for vrx, config in VRX_CONFIG.items():
        GPIO.setup(config['power_pin'], GPIO.OUT)
        GPIO.output(config['power_pin'], GPIO.HIGH)  # изначально выкл
        print(f"{vrx} питание: пин {config['power_pin']} = HIGH")

    # Управляющие пины для VRX2-4
    for vrx, config in VRX_CONFIG.items():
        if vrx != 'VRX1':  # для VRX1 они не используются, но на всякий случай настроим
            for pin in config['control_pins'].values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)

    # Кнопки
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ========== ОСНОВНОЙ ЦИКЛ ==========

def main():
    global app_state, current_vrx, active_vrx
    global vrx1_band, vrx1_channel
    global autosearch_active

    print("Запуск системы управления VRX (версия с улучшенным VRX1)...")
    setup_gpio()

    # Инициализация VRX1: устанавливаем первую частоту
    set_vrx1_frequency_by_index(0, 0)

    # Начинаем с экрана выбора
    app_state = "vrx_select"
    update_display()

    # Переменные для обработки кнопок
    last_select = 1
    last_up = 1
    last_down = 1
    select_press_time = 0
    select_held = False
    select_hold_triggered = False

    try:
        while True:
            now = time.time()
            # Обновление RSSI для VRX1 (если он активен или в фоне)
            if current_vrx == 'VRX1' or autosearch_active:
                update_rssi()

            # Чтение кнопок
            select = GPIO.input(BTN_SELECT)
            up = GPIO.input(BTN_UP)
            down = GPIO.input(BTN_DOWN)

            # Обработка SELECT
            if select != last_select:
                if select == GPIO.LOW:  # нажата
                    select_press_time = now
                    select_held = True
                    select_hold_triggered = False
                else:  # отпущена
                    press_duration = now - select_press_time
                    if not select_hold_triggered:
                        if press_duration > 2.0 and app_state == "main" and current_vrx == 'VRX1':
                            # Долгое нажатие без модификатора -> автопоиск
                            if not autosearch_active:
                                autosearch_thread = threading.Thread(target=autosearch, daemon=True)
                                autosearch_thread.start()
                            select_hold_triggered = True
                        elif press_duration > 0.1 and not select_hold_triggered:
                            # Короткое нажатие
                            if app_state == "vrx_select":
                                # Включаем выбранный VRX
                                set_vrx_power(current_vrx, True)
                                active_vrx = current_vrx
                                app_state = "main"
                                update_display()
                            elif app_state == "main":
                                # Выключаем текущий VRX и возвращаемся в меню
                                if active_vrx:
                                    set_vrx_power(active_vrx, False)
                                    reset_vrx_channels(active_vrx)
                                    active_vrx = None
                                app_state = "vrx_select"
                                update_display()
                    select_held = False
                last_select = select

            # Обработка UP/DOWN с учётом модификатора SELECT для VRX1
            if up != last_up:
                if up == GPIO.LOW:
                    if app_state == "vrx_select":
                        change_vrx('UP')
                    elif app_state == "main":
                        if current_vrx == 'VRX1' and select_held and not select_hold_triggered:
                            # Удержание SELECT + UP -> смена диапазона
                            change_band('UP')
                            select_hold_triggered = True  # предотвращаем автопоиск
                        else:
                            change_channel('UP')
                last_up = up

            if down != last_down:
                if down == GPIO.LOW:
                    if app_state == "vrx_select":
                        change_vrx('DOWN')
                    elif app_state == "main":
                        if current_vrx == 'VRX1' and select_held and not select_hold_triggered:
                            change_band('DOWN')
                            select_hold_triggered = True
                        else:
                            change_channel('DOWN')
                last_down = down

            # Автоматическое обновление дисплея во время автопоиска
            if autosearch_active:
                # Обновляем чаще
                time.sleep(0.1)
                update_display()
            else:
                time.sleep(0.05)

    except KeyboardInterrupt:
        print("Программа завершена")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        traceback.print_exc()
    finally:
        # Выключаем все VRX
        for vrx in VRX_CONFIG:
            set_vrx_power(vrx, False)
            reset_vrx_channels(vrx)
        GPIO.cleanup()
        spi_dev.close()
        print("Ресурсы освобождены")

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

if __name__ == "__main__":
    main()
