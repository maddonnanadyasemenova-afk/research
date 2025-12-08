# Инструкция по развертыванию бота

## Вариант 1: Запуск на локальном сервере / VPS

### Требования
- Python 3.11+
- Постоянное подключение к интернету
- Ubuntu/Debian/CentOS или любой Linux

### Шаги

1. **Скопируйте файлы на сервер**
```bash
scp -r telegram_bot/ user@your-server:/home/user/
```

2. **Подключитесь к серверу**
```bash
ssh user@your-server
```

3. **Установите зависимости**
```bash
cd /home/user/telegram_bot
pip3 install -r requirements.txt
```

4. **Настройте переменные окружения**
Отредактируйте `.env` файл:
- `TELEGRAM_BOT_TOKEN` - токен вашего бота от @BotFather
- `BUILT_IN_FORGE_API_KEY` - ключ Manus API (если используете)

5. **Запустите бота**
```bash
python3 bot.py
```

### Запуск в фоновом режиме с помощью systemd

Создайте файл `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Marketing Research AI Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telegram_bot
ExecStart=/usr/bin/python3 /home/ubuntu/telegram_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

## Вариант 2: Запуск через Docker

### Создайте Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

### Запустите контейнер

```bash
docker build -t marketing-research-bot .
docker run -d --name bot --restart always marketing-research-bot
```

## Вариант 3: Запуск на Heroku

1. Создайте `Procfile`:
```
worker: python bot.py
```

2. Создайте `runtime.txt`:
```
python-3.11.0
```

3. Деплой:
```bash
heroku create your-bot-name
git push heroku main
heroku ps:scale worker=1
```

## Вариант 4: Запуск на Railway.app

1. Подключите GitHub репозиторий
2. Railway автоматически определит Python проект
3. Добавьте переменные окружения в настройках
4. Деплой произойдет автоматически

## Мониторинг

### Просмотр логов (systemd)
```bash
sudo journalctl -u telegram-bot -f
```

### Просмотр логов (Docker)
```bash
docker logs -f bot
```

## Обновление бота

1. Остановите бота
2. Обновите файлы
3. Перезапустите бота

```bash
sudo systemctl stop telegram-bot
# обновите файлы
sudo systemctl start telegram-bot
```

## Резервное копирование

Регулярно делайте бэкап базы данных:
```bash
cp bot_database.db bot_database_backup_$(date +%Y%m%d).db
```

## Безопасность

- ✅ Никогда не коммитьте `.env` файл в Git
- ✅ Используйте переменные окружения для секретов
- ✅ Регулярно обновляйте зависимости
- ✅ Настройте файрвол на сервере
- ✅ Используйте HTTPS для webhook (если используете)

## Поддержка

При возникновении проблем проверьте:
1. Логи бота
2. Подключение к интернету
3. Правильность токенов в `.env`
4. Версию Python (должна быть 3.11+)
