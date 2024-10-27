# 📚 API Документация Trading Bot

## 🔧 Основные эндпоинты

### WebSocket API

```python
# Подключение к WebSocket
ws_url = 'wss://stream.bybit.com/v5/public/spot'  # Unified Account
```

#### Подписка на каналы данных

```javascript
// Книга ордеров
{
    "op": "subscribe",
    "args": [
        {
            "category": "spot",
            "symbol": "BTCUSDT",
            "channel": "orderbook.25"
        }
    ]
}

// Тиковые данные
{
    "op": "subscribe",
    "args": [
        {
            "category": "spot",
            "symbol": "BTCUSDT",
            "channel": "trade"
        }
    ]
}
```

## 📈 Торговые функции

### Размещение ордера

```python
async def place_order(
    symbol: str,          # Торговая пара (например, "BTCUSDT")
    side: str,            # "buy" или "sell"
    order_type: str,      # "limit" или "market"
    size: float,          # Размер позиции
    price: float = None   # Цена (для лимитных ордеров)
) -> Dict:
    """
    Размещение ордера на бирже.
  
    Пример:
    order = await exchange.place_order(
        symbol="BTCUSDT",
        side="buy",
        order_type="limit",
        size=0.001,
        price=50000.0
    )
    """
```

### Отмена ордера

```python
async def cancel_order(
    symbol: str,    # Торговая пара
    order_id: str   # ID ордера
) -> bool:
    """
    Отмена активного ордера.
  
    Пример:
    success = await exchange.cancel_order(
        symbol="BTCUSDT",
        order_id="1234567"
    )
    """
```

## 📊 Получение данных

### Книга ордеров

```python
async def get_orderbook(
    symbol: str,
    depth: int = 25  # Глубина стакана
) -> Dict[str, List]:
    """
    Получение книги ордеров.
  
    Возвращает:
    {
        'bids': [[price, size], ...],
        'asks': [[price, size], ...]
    }
    """
```

### Позиции

```python
async def get_positions(
    symbol: Optional[str] = None  # Если None - все позиции
) -> List[Dict]:
    """
    Получение открытых позиций.
  
    Возвращает:
    [{
        'symbol': str,
        'side': str,
        'size': float,
        'entry_price': float,
        'leverage': float,
        'unrealized_pnl': float
    }, ...]
    """
```

## 💼 Управление рисками

### Установка стоп-лосса

```python
async def set_stop_loss(
    symbol: str,
    price: float,
    position_idx: int = 0  # Индекс позиции для hedged режима
) -> bool:
    """
    Установка стоп-лосса для позиции.
  
    Пример:
    success = await exchange.set_stop_loss(
        symbol="BTCUSDT",
        price=49500.0
    )
    """
```

## 📱 Уведомления

### Telegram

```python
async def send_notification(
    message: str,
    level: str = 'INFO'  # INFO/WARNING/ERROR
) -> None:
    """
    Отправка уведомления в Telegram.
  
    Пример:
    await notifier.send_notification(
        "Открыта позиция BTC/USDT: 0.001 @ 50000"
    )
    """
```

## 📊 Метрики

### Prometheus

```python
# Основные метрики
trades_total = Counter('trades_total', 'Количество сделок', ['strategy', 'symbol'])
pnl_total = Gauge('pnl_total', 'Общий P&L', ['strategy'])
position_size = Gauge('position_size', 'Размер позиции', ['symbol'])
execution_time = Histogram('trade_execution_seconds', 'Время исполнения')
```

## 🔍 Примеры использования

### Открытие позиции

```python
# Пример открытия позиции с полным циклом
async def open_position(symbol: str, side: str, size: float, price: float):
    # 1. Проверка рисков
    if not risk_manager.can_open_position(symbol, size, price):
        return None
      
    # 2. Размещение ордера
    order = await exchange.place_order(
        symbol=symbol,
        side=side,
        order_type='limit',
        size=size,
        price=price
    )
  
    # 3. Установка стоп-лосса и тейк-профита
    if order['status'] == 'filled':
        await exchange.set_stop_loss(symbol, price * 0.99)
        await exchange.set_take_profit(symbol, price * 1.01)
      
        # 4. Отправка уведомления
        await notifier.send_notification(
            f"Открыта позиция {symbol}: {size} @ {price}"
        )
      
    return order
```

### Мониторинг позиции

```python
async def monitor_position(symbol: str):
    while True:
        position = await exchange.get_position(symbol)
        if position:
            # Обновление метрик
            position_size.labels(symbol=symbol).set(position['size'])
          
            # Проверка условий выхода
            if should_close_position(position):
                await close_position(symbol)
                break
              
        await asyncio.sleep(1)
```

## ⚠️ Обработка ошибок

```python
try:
    await exchange.place_order(...)
except ExchangeError as e:
    logger.error(f"Ошибка размещения ордера: {e}")
    await notifier.send_notification(
        f"Ошибка: {str(e)}", 
        level='ERROR'
    )
```

## 📌 Важные замечания

1. Все запросы к API выполняются асинхронно
2. Используйте обработку ошибок для всех критических операций
3. Следите за лимитами запросов к API
4. Регулярно проверяйте статус подключения к WebSocket
5. Используйте тестовую сеть для отладки

Подробную документацию по API бирж можно найти здесь:

- [Bybit API Docs](https://bybit-exchange.github.io/docs/v5/intro)
- [OKX API Docs](https://www.okx.com/docs-v5/en/)
