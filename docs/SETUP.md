# 🚀 Руководство по установке Trading Bot (Windows)

## 📋 Содержание

- [Системные требования](#-системные-требования)
- [Подготовка системы](#-подготовка-системы)
- [Установка основных компонентов](#-установка-основных-компонентов)
- [Настройка проекта](#-настройка-проекта)
- [Конфигурация](#-конфигурация)
- [Запуск бота](#-запуск-бота)
- [Проверка работоспособности](#-проверка-работоспособности)
- [Решение проблем](#-решение-проблем)

## 💻 Системные требования

### Минимальные требования

- Windows 10/11 (64-bit)
- 8 GB RAM
- 4-core CPU
- 100 GB свободного места
- Стабильное интернет-соединение (минимум 10 Mbps)

### Рекомендуемые требования

- Windows 10/11 (64-bit)
- 16+ GB RAM
- 6+ core CPU
- 250+ GB SSD
- Высокоскоростное интернет-соединение (50+ Mbps)

## 🔧 Подготовка системы

### 1. Установка Windows Terminal (рекомендуется)

1. Откройте Microsoft Store
2. Найдите "Windows Terminal"
3. Нажмите "Установить"

### 2. Установка Visual Studio Code

1. Скачайте [Visual Studio Code](https://code.visualstudio.com/)
2. Запустите установщик
3. При установке отметьте:
   - ✅ Add "Open with Code" action to Windows Explorer file context menu
   - ✅ Add to PATH

## 📦 Установка основных компонентов

### 1. Python 3.10+

```powershell
# Откройте Windows Terminal от администратора и выполните:

# 1. Скачайте Python 3.10+ с официального сайта
Start-Process "https://www.python.org/downloads/"

# 2. При установке обязательно отметьте:
# ✅ Add Python to PATH
# ✅ Install pip
```

### 2. Git

```powershell
# 1. Скачайте Git
Start-Process "https://git-scm.com/download/win"

# 2. При установке выберите:
# - Use Visual Studio Code as Git's default editor
# - Git from the command line and also from 3rd-party software
# - Use Windows' default console window
```

### 3. PostgreSQL

```powershell
# 1. Скачайте PostgreSQL
Start-Process "https://www.enterprisedb.com/downloads/postgres-postgresql-downloads"

# 2. При установке:
# - Выберите версию 15+
# - Запомните пароль для пользователя postgres
# - Порт: 5432 (по умолчанию)
# ✅ Отметьте pgAdmin 4 при установке
```

### 4. Redis

```powershell
# 1. Установите Redis через WSL2
wsl --install
wsl --install -d Ubuntu

# 2. В Ubuntu WSL выполните:
sudo apt update
sudo apt install redis-server

# 3. Запустите Redis
sudo service redis-server start
```

## 🛠 Настройка проекта

### 1. Клонирование репозитория

```powershell
# Создайте директорию для проекта
mkdir C:\Trading
cd C:\Trading

# Клонируйте репозиторий
git clone https://github.com/your-repo/trading-bot.git
cd trading-bot
```

### 2. Создание виртуального окружения

```powershell
# Создание venv
python -m venv venv

# Активация
.\venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt
```

### 3. Настройка базы данных

```powershell
# Откройте pgAdmin 4
# 1. Создайте новую базу данных:
#    - Имя: trading_bot
#    - Кодировка: UTF8
#    - Сортировка: English_United States.1252

# Или через командную строку:
psql -U postgres
CREATE DATABASE trading_bot;
\q

# Применение миграций
alembic upgrade head
```

## ⚙️ Конфигурация

### 1. Настройка .env

```powershell
# Создайте .env файл
copy .env.example .env
```

Отредактируйте .env в VS Code:

```env
# Биржи
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_TESTNET=True  # Измените на False для реальной торговли

# База данных
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_bot
DB_USER=postgres
DB_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Логирование
LOG_LEVEL=INFO

# Telegram (опционально)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 2. Проверка конфигурации

```powershell
# Проверьте настройки в файлах:
code config/settings.py  # Основные настройки
code config/logging_config.py  # Настройки логирования
```

## 🚀 Запуск бота

### 1. Запуск в обычном режиме

```powershell
# Активируйте виртуальное окружение
.\venv\Scripts\activate

# Запустите бота
python scripts/run_bot.py
```

### 2. Запуск через Docker

```powershell
# Установите Docker Desktop для Windows
# https://www.docker.com/products/docker-desktop

# Запустите контейнеры
docker-compose up -d

# Проверка логов
docker-compose logs -f trading_bot
```

## ✅ Проверка работоспособности

### 1. Проверка сервисов

```powershell
# PostgreSQL
pg_isready -h localhost

# Redis (в WSL)
wsl redis-cli ping

# Проверка логов
Get-Content .\logs\trading_bot.log -Tail 20
```

### 2. Мониторинг

- Grafana: http://localhost:3000
  - Login: admin
  - Password: admin
- Prometheus: http://localhost:9090

### 3. Тестирование стратегий

```powershell
# Запуск бэктеста
python scripts/backtest.py --strategy OrderBookImbalance --symbol BTC-USDT

# Оптимизация
python scripts/optimize.py --strategy OrderBookImbalance --symbol BTC-USDT
```

## 🔧 Решение проблем

### PostgreSQL не запускается

```powershell
# Проверьте статус службы
services.msc
# Найдите postgresql-x64-15 и запустите

# Или через командную строку
pg_ctl start -D "C:\Program Files\PostgreSQL\15\data"
```

### Redis не подключается

```powershell
# Проверьте WSL
wsl --status

# Перезапустите Redis
wsl sudo service redis-server restart
```

### Проблемы с подключением к биржам

1. Проверьте API ключи
2. Убедитесь, что включен VPN (если нужно)
3. Проверьте лог-файлы в директории logs/

### Общие проблемы

1. Проверьте версии всех компонентов:

```powershell
python --version
pg_config --version
redis-cli --version
docker --version
```

2. Проверьте свободное место на диске:

```powershell
wmic logicaldisk get size,freespace,caption
```

3. Мониторинг ресурсов:

```powershell
# Откройте диспетчер задач
taskmgr
```

## 📱 Дополнительно

### Настройка уведомлений в Telegram

1. Создайте бота через @BotFather
2. Получите токен бота
3. Добавьте бота в группу
4. Получите chat_id
5. Обновите .env файл

### Автозапуск при старте системы

1. Создайте bat файл:

```batch
@echo off
cd C:\Trading\trading-bot
call .\venv\Scripts\activate
python scripts\run_bot.py
```

2. Добавьте ярлык в:

```
C:\Users\[Username]\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
```

Для дополнительной помощи или вопросов обращайтесь в [Issue Tracker](https://github.com/your-repo/trading-bot/issues).
