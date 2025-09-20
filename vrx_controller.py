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

# Конфигурация VRX с полной частотной сеткой
VRX_CONFIG = {
    'VRX1': {
        'type': '5.8GHz',
        'power_pin': 2,
        'control_pins': {'CH_UP': 6, 'CH_DOWN': 13, 'BAND_UP': 19, 'BAND_DOWN': 26},
        'channels': {
            'A': [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725],
            'B': [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866],
            'E': [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945],
            'F': [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880],
            'R': [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917],
            'H': [5653, 5693, 5733, 5773, 5813, 5853, 5893, 5933],
            'L': [5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613],
            'U': [5325, 5348, 5366, 5384, 5402, 5420, 5438, 5456],
            'O': [5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600],
            'X': [4990, 5020, 5050, 5080, 5110, 5140, 5170, 5200]
        }
    },
    'VRX2': {
        'type': '1.2GHz',
        'power_pin': 3,
        'control_pins': {'CH_UP': 21, 'CH_DOWN': 20},
        'channels': [
            1010, 1040, 1080, 1120, 1160, 1200, 1240,
            1280, 1320, 1360, 1258, 1100, 1140
        ]
    },
    'VRX3': {
        'type': '1.5GHz',
        'power_pin': 4,
        'control_pins': {'CH_UP': 16, 'CH_DOWN': 12},
        'channels': [
            1405, 1430, 1455, 1480, 1505, 1530, 1555,
            1580, 1605, 1630, 1655, 1680
        ]
    },
    'VRX4': {
        'type': '3.3GHz',
        'power_pin': 17,
        'control_pins': {'CH_UP': 27, 'CH_DOWN': 22},
        'channels': [
            3290, 3310, 3330, 3350, 3370, 3390, 3410, 3430,
            3450, 3470, 3490, 3510, 3530, 3550, 3570, 3590,
            3610, 3630, 3650, 3670, 3690, 3710, 3730, 3750,
            3770, 3790, 3810, 3830, 3850, 3870, 3890, 3910
        ]
    }
}

# Кнопки управления
BTN_SELECT = 5      # Выбор VRX/подтверждение
BTN_UP = 23         # Переключение канала вверх/band вверх для VRX1
BTN_DOWN = 24       # Переключение канала вниз/band вниз для VRX1
BTN_BAND = 18       # Переключение между каналом и band для VRX1

# Текущее состояние
current_vrx = 'VRX1'
channel_states = {
    'VRX1': {'band': 'A', 'channel': 0},
    'VRX2': {'channel': 0},
    'VRX3': {'channel': 0},
    'VRX4': {'channel': 0},
}
app_state = "vrx_select"  # Начинаем с выбора VRX
VERSION = "2.0"
active_vrx = None  # Текущий активный VRX
vrx1_mode = "channel"  # Режим для VRX1: "channel" или "band"

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

# Функция для управления питанием VRX (инвертированная логика)
def set_vrx_power(vrx, power_on):
    config = VRX_CONFIG[vrx]
    # Инвертированная логика: LOW = включено, HIGH = выключено
    GPIO.output(config['power_pin'], GPIO.LOW if power_on else GPIO.HIGH)
    status = "ВКЛ" if power_on else "ВЫКЛ"
    print(f"{vrx} питание: {status} (пин: {config['power_pin']}, состояние: {'LOW' if power_on else 'HIGH'})")

# Функция для отображения экрана выбора VRX
def show_vrx_selection():
    try:
        image, width, height = create_display_image()
        draw = ImageDraw.Draw(image)
        
        # Фон
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

# Функция для отображения основного экрана
def show_main_screen():
    try:
        image, width, height = create_display_image()
        draw = ImageDraw.Draw(image)
        
        # Фон
        draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
        
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Заголовок с названием VRX
        vrx_type = VRX_CONFIG[current_vrx]['type']
        title = f"{current_vrx} ({vrx_type})"
        title_width = draw.textlength(title, font=font_large)
        draw.text((width//2 - title_width//2, 10), title, font=font_large, fill=(255, 0, 0))
        
        # Получение текущей частоты
        config = VRX_CONFIG[current_vrx]
        state = channel_states[current_vrx]
        
        if current_vrx == 'VRX1':
            # Для VRX1 показываем band и channel
            freq = config['channels'][state['band']][state['channel']]
            
            # Текущая частота
            freq_text = f"Частота: {freq} МГц"
            freq_width = draw.textlength(freq_text, font=font_medium)
            draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))
            
            # Band и канал
            band_text = f"Группа: {state['band']}"
            band_width = draw.textlength(band_text, font=font_small)
            draw.text((width//2 - band_width//2, 90), band_text, font=font_small, fill=(255, 255, 255))
            
            channel_text = f"Канал: {state['channel'] + 1}"
            channel_width = draw.textlength(channel_text, font=font_small)
            draw.text((width//2 - channel_width//2, 110), channel_text, font=font_small, fill=(255, 255, 255))
            
            # Режим управления
            mode_text = f"Режим: {vrx1_mode}"
            mode_width = draw.textlength(mode_text, font=font_small)
            draw.text((width//2 - mode_width//2, 130), mode_text, font=font_small, fill=(255, 255, 255))
        else:
            # Для других VRX показываем только канал
            freq = config['channels'][state['channel']]
            
            # Текущая частота
            freq_text = f"Частота: {freq} МГц"
            freq_width = draw.textlength(freq_text, font=font_medium)
            draw.text((width//2 - freq_width//2, 50), freq_text, font=font_medium, fill=(255, 255, 255))
            
            # Номер канала
            channel_text = f"Канал: {state['channel'] + 1}/{len(config['channels'])}"
            channel_width = draw.textlength(channel_text, font=font_small)
            draw.text((width//2 - channel_width//2, 90), channel_text, font=font_small, fill=(255, 255, 255))
        
        # Версия программы
        version_text = f"Ver: {VERSION}"
        version_width = draw.textlength(version_text, font=font_small)
        draw.text((width - version_width - 10, height - 20), version_text, font=font_small, fill=(150, 150, 150))
        
        # Инструкция
        if current_vrx == 'VRX1':
            instruction = "UP/DOWN: канал/группа  BAND: режим  SELECT: меню"
        else:
            instruction = "UP/DOWN: канал  SELECT: меню"
            
        instr_width = draw.textlength(instruction, font=font_small)
        draw.text((width//2 - instr_width//2, height - 40), instruction, font=font_small, fill=(200, 200, 200))
        
        disp.image(image)
        
    except Exception as e:
        print(f"Ошибка обновления дисплея: {e}")
        print(traceback.format_exc())
        # В случае ошибки показываем черный экран
        try:
            image, width, height = create_display_image()
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
            disp.image(image)
        except:
            pass

# Обновление дисплея
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
        # Изначально все VRX выключены (HIGH)
        GPIO.output(config['power_pin'], GPIO.HIGH)
        print(f"{vrx} питание инициализировано (пин {config['power_pin']}: HIGH)")
    
    # Настройка управляющих пинов VRX
    for vrx, config in VRX_CONFIG.items():
        for pin in config['control_pins'].values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
    
    # Настройка кнопок
    GPIO.setup(BTN_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_BAND, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Эмуляция нажатия кнопки на VRX
def press_button(pin, duration=0.1):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.HIGH)

# Переключение каналов
def change_channel(direction):
    try:
        state = channel_states[current_vrx]
        config = VRX_CONFIG[current_vrx]
        
        if current_vrx == 'VRX1':
            if vrx1_mode == "channel":
                # Переключение канала для VRX1
                if direction == 'UP':
                    state['channel'] = (state['channel'] + 1) % len(config['channels'][state['band']])
                    press_button(config['control_pins']['CH_UP'])
                else:
                    state['channel'] = (state['channel'] - 1) % len(config['channels'][state['band']])
                    press_button(config['control_pins']['CH_DOWN'])
            else:
                # Переключение band для VRX1
                bands = list(config['channels'].keys())
                current_band_index = bands.index(state['band'])
                
                if direction == 'UP':
                    new_index = (current_band_index + 1) % len(bands)
                    state['band'] = bands[new_index]
                    press_button(config['control_pins']['BAND_UP'])
                else:
                    new_index = (current_band_index - 1) % len(bands)
                    state['band'] = bands[new_index]
                    press_button(config['control_pins']['BAND_DOWN'])
                
                # Сбрасываем канал при смене band
                state['channel'] = 0
        else:
            # Для других VRX просто переключаем каналы
            if direction == 'UP':
                state['channel'] = (state['channel'] + 1) % len(config['channels'])
                press_button(config['control_pins']['CH_UP'])
            else:
                state['channel'] = (state['channel'] - 1) % len(config['channels'])
                press_button(config['control_pins']['CH_DOWN'])
        
        # Гарантируем, что канал находится в допустимых пределах
        if current_vrx == 'VRX1':
            max_channel = len(config['channels'][state['band']]) - 1
        else:
            max_channel = len(config['channels']) - 1
            
        if state['channel'] < 0:
            state['channel'] = 0
        if state['channel'] > max_channel:
            state['channel'] = max_channel
        
        # Получаем текущую частоту
        if current_vrx == 'VRX1':
            freq = config['channels'][state['band']][state['channel']]
        else:
            freq = config['channels'][state['channel']]
        
        print(f"{current_vrx}: {'Группа' if vrx1_mode == 'band' and current_vrx == 'VRX1' else 'Канал'} {state['band'] if current_vrx == 'VRX1' else ''} {state['channel']+1}, Частота {freq} МГц")
        
        update_display()
    except Exception as e:
        print(f"Ошибка переключения канала: {e}")
        print(traceback.format_exc())

# Основная функция
def main():
    global app_state, current_vrx, active_vrx, vrx1_mode
    
    print("Запуск системы управления VRX...")
    
    # Инициализация GPIO
    try:
        setup_gpio()
        print("GPIO инициализированы успешно")
    except Exception as e:
        print(f"Ошибка инициализации GPIO: {e}")
        print(traceback.format_exc())
        return
    
    # Начинаем с экрана выбора VRX
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
    last_band = 1
    select_press_time = 0
    
    print("Система готова к работе")
    
    try:
        while True:
            current_time = time.time()
            
            # Обработка кнопки SELECT
            select_btn = GPIO.input(BTN_SELECT)
            if select_btn != last_select:
                if select_btn == GPIO.LOW:
                    select_press_time = current_time
                else:
                    # Кнопка отпущена
                    press_duration = current_time - select_press_time
                    
                    if press_duration > 0.1:
                        # Короткое нажатие
                        if app_state == "vrx_select":
                            # Включаем выбранный VRX
                            set_vrx_power(current_vrx, True)
                            active_vrx = current_vrx
                            
                            app_state = "main"
                            update_display()
                        elif app_state == "main":
                            # Выключаем текущий VRX при возврате в меню
                            if active_vrx:
                                set_vrx_power(active_vrx, False)
                                active_vrx = None
                            
                            app_state = "vrx_select"
                            update_display()
                
                last_select = select_btn
            
            # Обработка кнопки UP
            up_btn = GPIO.input(BTN_UP)
            if up_btn != last_up:
                if up_btn == GPIO.LOW:
                    if app_state == "vrx_select":
                        # Переключение VRX в режиме выбора
                        vrx_list = list(VRX_CONFIG.keys())
                        current_index = vrx_list.index(current_vrx)
                        current_index = (current_index + 1) % len(vrx_list)
                        current_vrx = vrx_list[current_index]
                        update_display()
                    elif app_state == "main":
                        change_channel('UP')
                last_up = up_btn
            
            # Обработка кнопки DOWN
            down_btn = GPIO.input(BTN_DOWN)
            if down_btn != last_down:
                if down_btn == GPIO.LOW:
                    if app_state == "vrx_select":
                        # Переключение VRX в режиме выбора
                        vrx_list = list(VRX_CONFIG.keys())
                        current_index = vrx_list.index(current_vrx)
                        current_index = (current_index - 1) % len(vrx_list)
                        current_vrx = vrx_list[current_index]
                        update_display()
                    elif app_state == "main":
                        change_channel('DOWN')
                last_down = down_btn
            
            # Обработка кнопки BAND (только для VRX1 в основном режиме)
            band_btn = GPIO.input(BTN_BAND)
            if band_btn != last_band:
                if band_btn == GPIO.LOW and app_state == "main" and current_vrx == "VRX1":
                    # Переключение режима для VRX1
                    vrx1_mode = "band" if vrx1_mode == "channel" else "channel"
                    print(f"VRX1 режим изменен на: {vrx1_mode}")
                    update_display()
                last_band = band_btn
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("Программа завершена по запросу пользователя")
    except Exception as e:
        print(f"Критическая ошибка в основном цикле: {e}")
        print(traceback.format_exc())
    finally:
        # Выключаем все VRX при завершении программы
        for vrx in VRX_CONFIG:
            set_vrx_power(vrx, False)
        
        GPIO.cleanup()
        print("Ресурсы освобождены")

if __name__ == "__main__":
    main()
