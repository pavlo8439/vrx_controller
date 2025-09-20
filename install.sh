#!/bin/bash

echo "Установка системы управления VRX"
echo "================================="

# Обновление системы
echo "Обновление системы..."
sudo apt update
sudo apt upgrade -y

# Установка необходимых пакетов
echo "Установка необходимых пакетов..."
sudo apt install -y python3 python3-pip python3-venv python3-pil python3-numpy python3-serial fonts-dejavu

# Создание виртуального окружения
echo "Создание виртуального окружения..."
python3 -m venv ~/vrx_env
source ~/vrx_env/bin/activate

# Установка Python-библиотек
echo "Установка Python-библиотек..."
pip install adafruit-circuitpython-rgb-display RPi.GPIO pyserial pillow

# Включение SPI и UART
echo "Настройка SPI и UART..."
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_serial 2

# Добавление настроек в config.txt
echo "Добавление настроек в config.txt..."
sudo bash -c 'cat >> /boot/config.txt << EOF

# Настройки для VRX Controller
enable_uart=1
dtoverlay=disable-bt
EOF'

# Отключение сервиса Bluetooth
echo "Отключение сервиса Bluetooth..."
sudo systemctl disable hciuart

# Скачивание основного скрипта
echo "Скачивание основного скрипта..."
wget -O ~/vrx_controller.py https://raw.githubusercontent.com/pavlo8439/vrx_controller/main/vrx_controller.py

# Создание службы автозапуска
echo "Создание службы автозапуска..."
sudo bash -c 'cat > /etc/systemd/system/vrx.service << EOF
[Unit]
Description=VRX Controller Service
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/pi/vrx_env/bin/python /home/pi/vrx_controller.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF'

# Перезагрузка служб
echo "Перезагрузка служб..."
sudo systemctl daemon-reload
sudo systemctl enable vrx.service

# Предоставление прав на GPIO
echo "Предоставление прав на GPIO..."
sudo usermod -a -G gpio pi

echo "Установка завершена!"
echo "Для запуска сервиса выполните: sudo systemctl start vrx.service"
echo "Для просмотра логов: journalctl -u vrx.service -f"
