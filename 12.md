trading_bot/
├── config/
│   ├── __init__.py
│   ├── settings.py         ✓ (обновлен)
│   └── logging_config.py   ✓
├── core/
│   ├── __init__.py
│   ├── engine.py          ✓
│   ├── risk_manager.py    ✓

│   └── position_manager.py
├── exchanges/
│   ├── __init__.py
│   ├── base.py           ✓
│   ├── bybit.py          ✓
│   └── okx.py            ✓
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py   ✓
│   ├── orderbook_imbalance.py ✓
│   ├── price_action.py    ✓
│   ├── arbitrage.py       ✓
│   ├── volume_impulse.py  ✓
│   └── combined/
│       ├── __init__.py
│       ├── impulse_imbalance.py ✓
│       └── arbitrage_volume.py   ✓
├── models/
│   ├── __init__.py

│   ├── market_data.py	✓
│   ├── position.py       ✓
│   └── orderbook.py      ✓
├── utils/
│   ├── __init__.py
│   ├── logger.py         ✓
│   ├── metrics.py        ✓

│   ├── matket_utils.py
│   └── validators.py     ✓
├── database/
│   ├── __init__.py
│   └── repository.py     ✓
├── tests/
│   ├── __init__.py
│   ├── test_strategies/  ✓

│   		├── __init__.py
│   		└── test_test_orderbook_imbalance.py     ✓
│   ├── test_exchanges/   ✓

│   		├── __init__.py
│   		└── test_base_exchange.py ✓
│   └── test_risk_manager/   ✓

│   		├── __init__.py
│   		└── test_risk_manager.py ✓
├── scripts/
│   ├── backtest.py       ✓

│   ├── optimize.py
│   └── run_bot.py        ✓
├── monitoring/           ✓
│   ├── __init__.py
│   ├── prometheus.py ✓
│   └── telegram.py ✓
├── data/                 ❌ (новая директория)
│   ├── historical/
│   └── backtest_results/
├── docs/                 ✓
│   ├── API.md	✓
│   ├── SETUP.md	✓
│   └── STRATEGIES.md	✓
├── requirements.txt      ✓
├── README.md            ✓
├── .env.example         ✓
└── docker-compose.yml   ✓
