#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import board
import digitalio
import serial
import threading
import traceback
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
cs_pin = digitalio.DigitalInOut(board.CE0)   # GPIO8
dc_pin = digitalio.DigitalInOut(board.D24)   # GPIO24
reset_pin = digitalio.DigitalInOut(board.D25) # GPIO25
BAUDRATE = 24000000

# Инициализация SPI
spi = board.SPI()

# Инициализация дисплея ILI9341
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
    print(f"Ошибка инициализации дисплея ILI9341: {e}")
    print(traceback.format_exc())
    exit(1)

# Инициализация I2C дисплея SSD1306 (если доступен)
i2c_display = None
if I2C_DISPLAY_AVAILABLE:
    try:
        i2c = board.I2C()  # использует пины GPIO2 (SDA) и GPIO3 (SCL)
        i2c_display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
        i2c_display.fill(0)
        i2c_display.show()
        print("I2C дисплей SSD1306 инициализирован успешно")
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

# ========== КОНФИГУРАЦИЯ VRX ==========
VRX_CONFIG = {
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 18,           # питание
        'spi_cs': 7,               # CS для SPI (не путать с CS дисплея)
        'channels': [               # 96 каналов из 5.8.ino
            5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600,  # A
            5362, 5399, 5436, 5473, 5500, 5547, 5584, 5621,  # B
            5300, 5348, 5366, 5384, 5400, 5420, 5438, 5456,  # E
            5129, 5159, 5189, 5219, 5249, 5279, 5309, 5339,  # F
            4990, 5020, 5050, 5080, 5110, 5150, 5170, 5200,  # R
            5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613,  # P
            4875, 4884, 4900, 4858, 4995, 5032, 5069, 5099,  # L
            5960, 5980, 6000, 6020, 6030, 6040, 6050, 6060,  # U
            5865, 5845, 5825, 5805, 5785, 5765, 5745, 5735,  # O
            5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866,  # H
            5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945,  # T
            5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880   # N
        ]
    },
    'VRX2': {
        'type': '1.2GHz',
        'power_pin': 15,
        'control_pins': {'CH_UP': 19, 'CH_DOWN': 26},
        'channels': [
            1010, 1040, 1080, 1120, 1160, 1200, 1240,
            1280, 1320, 1360, 1258, 1100, 1140
        ]
    },
    'VRX3': {
        'type': '1.5GHz',
        'power_pin': 14,
        'control_pins': {'CH_UP': 21, 'CH_DOWN': 20},
        'channels': [
            1405, 1430, 1455, 1480, 1505, 1530, 1555,
            1580, 1605, 1630, 1655, 1680
        ]
    },
    'VRX4': {
        'type': '3.3GHz',
        'power_pin': 4,
        'cs_pins': [5, 6, 12],      # три пина для CS
        's_pins': [13, 16, 17],     # три пина для S
        # Каналы: (частота, cs_bits, s_bits) – 64 канала из 3.3.ino
        'channels': [
            # band0 (FR1)
            (3360, 0b000, 0b000), (3380, 0b001, 0b000), (3400, 0b010, 0b000), (3420, 0b011, 0b000),
            (3440, 0b100, 0b000), (3460, 0b101, 0b000), (3480, 0b110, 0b000), (3500, 0b111, 0b000),
            # band1 (FR2)
            (3200, 0b000, 0b001), (3220, 0b001, 0b001), (3240, 0b010, 0b001), (3260, 0b011, 0b001),
            (3280, 0b100, 0b001), (3300, 0b101, 0b001), (3320, 0b110, 0b001), (3340, 0b111, 0b001),
            # band2 (FR3)
            (3330, 0b000, 0b010), (3350, 0b001, 0b010), (3370, 0b010, 0b010), (3390, 0b011, 0b010),
            (3410, 0b100, 0b010), (3430, 0b101, 0b010), (3450, 0b110, 0b010), (3470, 0b111, 0b010),
            # band3 (FR4)
            (3170, 0b000, 0b011), (3190, 0b001, 0b011), (3210, 0b010, 0b011), (3230, 0b011, 0b011),
            (3250, 0b100, 0b011), (3270, 0b101, 0b011), (3290, 0b110, 0b011), (3310, 0b111, 0b011),
            # band4 (FR5)
            (3320, 0b000, 0b100), (3345, 0b001, 0b100), (3370, 0b010, 0b100), (3395, 0b011, 0b100),
            (3420, 0b100, 0b100), (3445, 0b101, 0b100), (3470, 0b110, 0b100), (3495, 0b111, 0b100),
            # band5 (FR6)
            (3310, 0b000, 0b101), (3330, 0b001, 0b101), (3355, 0b010, 0b101), (3380, 0b011, 0b101),
            (3405, 0b100, 0b101), (3430, 0b101, 0b101), (3455, 0b110, 0b101), (3480, 0b111, 0b101),
            # band6 (FR7)
            (3220, 0b000, 0b110), (3240, 0b001, 0b110), (3260, 0b010, 0b110), (3280, 0b011, 0b110),
            (3300, 0b100, 0b110), (3320, 0b101, 0b110), (3340, 0b110, 0b110), (3360, 0b111, 0b110),
            # band7 (FR8)
            (3060, 0b000, 0b111), (3080, 0b001, 0b111), (3100, 0b010, 0b111), (3120, 0b011, 0b111),
            (3140, 0b100, 0b111), (3160, 0b101, 0b111), (3180, 0b110, 0b111), (3200, 0b111, 0b111)
        ]
    }
}

# Кнопки управления
BTN_SELECT = 27
BTN_UP = 22
BTN_DOWN = 23

# Текущее состояние
current_vrx = 'VRX1'
channel_states = {
    'VRX1': {'channel': 0},
    'VRX2': {'channel': 0},
    'VRX3': {'channel': 0},
    'VRX4': {'channel': 0},
}
app_state = "vrx_select"
VERSION = "2.0"  # обновленная версия
rssi_value = 0
autosearch_active = False
active_vrx = None

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_display_dimensions():
    if disp.rotation % 180 == 90:
        return disp.height, disp.width
    else:
        return disp.width, disp.height

def create_display_image():
    width, height = get_display_dimensions()
    return Image.new("RGB", (width, height)), width, height

def get_channel_freq(vrx, channel_idx):
    """Возвращает частоту в МГц для заданного VRX и индекса канала"""
    config = VRX_CONFIG[vrx]
    ch_data = config['channels'][channel_idx]
    if isinstance(ch_data, tuple):
        return ch_data[0]
    else:
        return ch_data

def update_i2c_display():
    if not i2c_display:
        return
    try:
        image = Image.new("1", (i2c_display.width, i2c_display.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, i2c_display.width, i2c_display.height), outline=0, fill=0)
        font = ImageFont.load_default()
        if app_state == "main" and current_vrx == "VRX1":
            freq = get_channel_freq(current_vrx, channel_states[current_vrx]['channel'])
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
        traceback.print_exc()

# ========== УПРАВЛЕНИЕ ПИТАНИЕМ ==========
def set_vrx_power(vrx, power_on):
    config = VRX_CONFIG[vrx]
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)
    status = "ВКЛ" if power_on else "ВЫКЛ"
    print(f"{vrx} питание: {status} (пин {config['power_pin']})")

def reset_vrx_channels(vrx):
    channel_states[vrx]['channel'] = 0
    print(f"{vrx}: канал сброшен на 0")

# ========== ПРЯМОЕ УПРАВЛЕНИЕ ЧАСТОТОЙ ==========
def set_frequency_vrx1(freq_mhz):
    """Установка частоты для VRX1 через SPI (RX5808)"""
    cs = VRX_CONFIG['VRX1']['spi_cs']
    # Формула из скетча 5.8.ino: N = (freq - 479) / 2
    N = int((freq_mhz - 479) / 2)
    # Подготовка данных для регистров (LSB first)
    data0 = ((N & 0x1F) << 3) | 0x01   # младшие 5 бит N + бит 0
    data1 = ((N >> 5) & 0x3F) << 2     # следующие 6 бит
    data2 = (N >> 11) & 0x03           # старшие 2 бита
    data3 = 0x00
    GPIO.output(cs, GPIO.LOW)
    spi.xfer2([data0, data1, data2, data3])
    GPIO.output(cs, GPIO.HIGH)
    print(f"VRX1: установлена частота {freq_mhz} МГц")

def set_frequency_vrx4(channel_index):
    """Установка частоты для VRX4 через пины CS и S"""
    config = VRX_CONFIG['VRX4']
    freq, cs_bits, s_bits = config['channels'][channel_index]
    cs_pins = config['cs_pins']
    s_pins = config['s_pins']
    # Устанавливаем CS пины (старший бит -> cs_pins[0])
    GPIO.output(cs_pins[0], (cs_bits >> 2) & 1)
    GPIO.output(cs_pins[1], (cs_bits >> 1) & 1)
    GPIO.output(cs_pins[2], (cs_bits >> 0) & 1)
    # Устанавливаем S пины
    GPIO.output(s_pins[0], (s_bits >> 2) & 1)
    GPIO.output(s_pins[1], (s_bits >> 1) & 1)
    GPIO.output(s_pins[2], (s_bits >> 0) & 1)
    print(f"VRX4: установлена частота {freq} МГц, CS:{cs_bits:03b}, S:{s_bits:03b}")

def apply_current_channel():
    """Применить текущий канал для активного VRX (если требуется прямая установка)"""
    if current_vrx == 'VRX1':
        freq = VRX_CONFIG['VRX1']['channels'][channel_states['VRX1']['channel']]
        set_frequency_vrx1(freq)
    elif current_vrx == 'VRX4':
        set_frequency_vrx4(channel_states['VRX4']['channel'])
    # Для VRX2 и VRX3 ничего не делаем (управление кнопками)

# ========== ОТОБРАЖЕНИЕ ==========
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
        traceback.print_exc()
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
        if state['channel'] >= len(config['channels']):
            state['channel'] = len(config['channels']) - 1
        if state['channel'] < 0:
            state['channel'] = 0
        freq = get_channel_freq(current_vrx, state['channel'])
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
        traceback.print_exc()
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

# ========== УПРАВЛЕНИЕ КАНАЛАМИ ==========
def press_button(pin, duration=0.1):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

def change_channel(direction):
    try:
        state = channel_states[current_vrx]
        config = VRX_CONFIG[current_vrx]
        if direction == 'UP':
            state['channel'] = (state['channel'] + 1) % len(config['channels'])
        else:
            state['channel'] = (state['channel'] - 1) % len(config['channels'])
        # Применяем канал в зависимости от типа VRX
        if current_vrx == 'VRX1':
            freq = config['channels'][state['channel']]
            set_frequency_vrx1(freq)
        elif current_vrx == 'VRX4':
            set_frequency_vrx4(state['channel'])
        else:
            pin = config['control_pins']['CH_UP' if direction == 'UP' else 'CH_DOWN']
            press_button(pin)
        freq_display = get_channel_freq(current_vrx, state['channel'])
        print(f"{current_vrx}: Канал {state['channel']+1}, Частота {freq_display} МГц")
        update_display()
        send_state_to_esp32()
    except Exception as e:
        print(f"Ошибка переключения канала: {e}")
        traceback.print_exc()

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
    try:
        for channel in range(len(config['channels'])):
            set_frequency_vrx1(config['channels'][channel])
            state['channel'] = channel
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
                best_channel = channel
    except Exception as e:
        print(f"Ошибка в автопоиске: {e}")
        traceback.print_exc()
    finally:
        autosearch_active = False
    set_frequency_vrx1(config['channels'][best_channel])
    state['channel'] = best_channel
    update_display()
    print(f"Автопоиск завершен. Лучший канал: {best_channel+1}, RSSI: {best_rssi}")

# ========== ВЗАИМОДЕЙСТВИЕ С ESP32 ==========
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
        freq = get_channel_freq(vrx, state['channel'])
        message = f"VRX:{vrx}:{state['channel']}:{freq}:{rssi_value}\n"
        esp32.write(message.encode())
        print(f"Отправлено на ESP32: {message.strip()}")
    except Exception as e:
        print(f"Ошибка отправки на ESP32: {e}")
        traceback.print_exc()

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
                        apply_current_channel()  # установить частоту после включения
                        active_vrx = current_vrx
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
            traceback.print_exc()
        time.sleep(0.1)

# ========== ОБРАБОТКА КНОПОК ==========
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

# ========== ИНИЦИАЛИЗАЦИЯ GPIO ==========
def setup_gpio():
    # Пины питания VRX
    for vrx, config in VRX_CONFIG.items():
        GPIO.setup(config['power_pin'], GPIO.OUT)
        GPIO.output(config['power_pin'], GPIO.HIGH)  # все выключены
    # SPI CS для VRX1
    GPIO.setup(VRX_CONFIG['VRX1']['spi_cs'], GPIO.OUT)
    GPIO.output(VRX_CONFIG['VRX1']['spi_cs'], GPIO.HIGH)
    # Параллельные пины для VRX4
    vrx4 = VRX_CONFIG['VRX4']
    for pin in vrx4['cs_pins'] + vrx4['s_pins']:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    # Пины эмуляции кнопок для VRX2, VRX3
    for vrx in ['VRX2', 'VRX3']:
        for pin in VRX_CONFIG[vrx]['control_pins'].values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
    # Кнопки
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ========== ОСНОВНОЙ ЦИКЛ ==========
def main():
    global app_state, current_vrx, active_vrx
    print("Запуск системы управления VRX...")
    try:
        setup_gpio()
        print("GPIO инициализированы успешно")
    except Exception as e:
        print(f"Ошибка инициализации GPIO: {e}")
        traceback.print_exc()
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
        traceback.print_exc()
        return
    last_select = 1
    last_up = 1
    last_down = 1
    select_press_time = 0
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
                    if press_duration > 2.0 and app_state == "main" and current_vrx == "VRX1":
                        autosearch()
                    elif press_duration > 0.1:
                        if app_state == "vrx_select":
                            set_vrx_power(current_vrx, True)
                            apply_current_channel()  # установить частоту после включения
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
            # UP
            up_btn = GPIO.input(BTN_UP)
            if up_btn != last_up:
                if up_btn == GPIO.LOW:
                    if app_state == "vrx_select":
                        change_vrx('UP')
                    elif app_state == "main":
                        change_channel('UP')
                last_up = up_btn
            # DOWN
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
        traceback.print_exc()
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
