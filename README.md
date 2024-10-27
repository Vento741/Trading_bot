# Crypto Trading Bot

Высокочастотный торговый бот для криптовалютных бирж Bybit и OKX с поддержкой нескольких стратегий и риск-менеджмента.

## Основные возможности

- Поддержка бирж Bybit (Unified Account) и OKX
- Несколько торговых стратегий (Orderbook Imbalance, Price Action, Arbitrage, Volume Impulse)
- Гибкая система риск-менеджмента
- Мониторинг через Prometheus и Grafana
- Уведомления в Telegram
- Бэктестинг и оптимизация стратегий
- Подробное логирование всех операций

## Требования

- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- Docker и Docker Compose (опционально)

## Установка на Windows

### 1. Подготовка окружения

1. Установите Python 3.10 или выше:

   - Скачайте установщик с [официального сайта Python](https://www.python.org/downloads/)
   - При установке отметьте "Add Python to PATH"
   - Проверьте установку: `python --version`
2. Установите Git:

   - Скачайте и установите [Git для Windows](https://git-scm.com/download/win)
   - Проверьте установку: `git --version`
3. Установите PostgreSQL:

   - Скачайте и установите [PostgreSQL](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)
   - Запомните пароль для пользователя postgres
   - Добавьте путь к bin PostgreSQL в PATH (обычно C:\Program Files\PostgreSQL\15\bin)
4. Установите Redis:

   - Скачайте [Redis для Windows](https://github.com/microsoftarchive/redis/releases)
   - Установите и запустите службу Redis

### 2. Клонирование и настройка проекта

1. Клонируйте репозиторий:

```bash
git clone https://github.com/your-repo/trading-bot.git
cd trading-bot
```

2. Создайте виртуальное окружение:

```bash
python -m venv venv
.\venv\Scripts\activate
```

3. Установите зависимости:

```bash
pip install -r requirements.txt
```

4. Создайте файл .env на основе .env.example:

```bash
copy .env.example .env
```

5. Настройте базу данных:

```bash
# Создайте базу данных
psql -U postgres
CREATE DATABASE trading_bot;
\q

# Примените миграции (если используете alembic)
alembic upgrade head
```

### 3. Настройка конфигурации

1. Отредактируйте файл .env:

   - Добавьте API ключи от бирж
   - Настройте параметры базы данных
   - Укажите токен Telegram бота (если нужны уведомления)
2. Проверьте настройки в config/settings.py:

   - Торговые пары
   - Параметры риск-менеджмента
   - Настройки стратегий

### 4. Запуск бота

#### Вариант 1: Прямой запуск

1. Запустите основные сервисы:

```bash
# Запуск Redis (если не установлен как служба)
redis-server

# Проверка статуса PostgreSQL
pg_ctl status -D "C:\Program Files\PostgreSQL\15\data"
# Если не запущен:
pg_ctl start -D "C:\Program Files\PostgreSQL\15\data"
```

2. Запустите бота:

```bash
# Активируйте виртуальное окружение, если еще не активировано
.\venv\Scripts\activate

# Запуск бота
python scripts/run_bot.py
```

#### Вариант 2: Запуск через Docker

1. Установите [Docker Desktop для Windows](https://www.docker.com/products/docker-desktop)
2. Запустите Docker Desktop
3. Запустите контейнеры:

```bash
docker-compose up -d
```

### 5. Мониторинг

1. Grafana доступна по адресу: http://localhost:3000

   - Логин: admin
   - Пароль: admin
2. Prometheus доступен по адресу: http://localhost:9090
3. Логи находятся в директории logs/

## Структура проекта

```
trading_bot/
├── config/          # Конфигурационные файлы
├── core/            # Ядро бота
├── exchanges/       # Коннекторы к биржам
├── strategies/      # Торговые стратегии
├── models/          # Модели данных
├── utils/           # Вспомогательные утилиты
├── database/        # Работа с БД
├── tests/           # Тесты
├── scripts/         # Скрипты запуска
├── monitoring/      # Мониторинг
└── docs/           # Документация
```

## Бэктестинг и оптимизация

1. Запуск бэктеста:

```bash
python scripts/backtest.py --strategy OrderBookImbalance --symbol BTC-USDT --timeframe 5m
```

2. Оптимизация параметров:

```bash
python scripts/optimize.py --strategy OrderBookImbalance --symbol BTC-USDT --timeframe 5m
```

## Поддержка

- Создайте Issue в репозитории
- Обратитесь к документации в директории docs/

## License

MIT
