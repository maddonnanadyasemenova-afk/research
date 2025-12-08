#!/bin/bash

# Скрипт для запуска Telegram-бота

cd /home/ubuntu/telegram_bot

echo "🤖 Запуск Marketing Research AI Bot..."

# Проверка зависимостей
if ! python3 -c "import telegram" 2>/dev/null; then
    echo "📦 Установка зависимостей..."
    sudo pip3 install -r requirements.txt -q
fi

# Запуск бота
echo "✅ Бот запущен!"
python3 bot.py
