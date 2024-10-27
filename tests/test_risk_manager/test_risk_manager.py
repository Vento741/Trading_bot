import pytest
from decimal import Decimal
from datetime import datetime
import asyncio
from typing import Dict

from core.risk_manager import RiskManager
from models.position import Position

@pytest.fixture
def risk_config():
    """Базовая конфигурация риск-менеджера"""
    return {
        'max_position_size': 0.05,
        'max_total_risk': 0.15,
        'max_correlated_positions': 3,
        'max_drawdown_pct': 40.0,
        'pause_after_losses': 10
    }

@pytest.fixture
def risk_manager(risk_config):
    """Фикстура риск-менеджера"""
    return RiskManager(risk_config)

@pytest.fixture
def sample_position():
    """Фикстура тестовой позиции"""
    return Position(
        symbol='BTC-USDT',
        side='long',
        entry_price=50000.0,
        size=0.1,
        take_profit=51000.0,
        stop_loss=49000.0,
        strategy='test',
        exchange='bybit'
    )

def test_initial_state(risk_manager):
    """Тест начального состояния"""
    assert risk_manager.consecutive_losses == 0
    assert risk_manager.is_trading_allowed
    assert len(risk_manager.positions) == 0

def test_position_size_limit(risk_manager):
    """Тест лимита размера позиции"""
    # Проверяем слишком большую позицию
    can_open = risk_manager.can_open_position(
        symbol='BTC-USDT',
        size=1.0,  # Слишком большой размер
        price=50000.0
    )
    assert not can_open
    
    # Проверяем допустимый размер позиции
    can_open = risk_manager.can_open_position(
        symbol='BTC-USDT',
        size=0.01,
        price=50000.0
    )
    assert can_open

def test_consecutive_losses(risk_manager):
    """Тест последовательных убытков"""
    # Симулируем убыточные сделки
    for _ in range(risk_manager.pause_after_losses - 1):
        risk_manager.on_trade_closed({'pnl': -100})
        assert risk_manager.is_trading_allowed
        
    # Последняя убыточная сделка должна остановить торговлю
    risk_manager.on_trade_closed({'pnl': -100})
    assert not risk_manager.is_trading_allowed

def test_drawdown_limit(risk_manager):
    """Тест лимита просадки"""
    risk_manager.initial_balance = 100000
    risk_manager.current_balance = 60000  # 40% просадка
    
    can_open = risk_manager.can_open_position(
        symbol='BTC-USDT',
        size=0.01,
        price=50000.0
    )
    assert not can_open

def test_correlated_positions(risk_manager, sample_position):
    """Тест коррелированных позиций"""
    # Добавляем несколько коррелированных позиций
    for i in range(risk_manager.max_correlated_positions):
        position = sample_position
        position.symbol = f'BTC-USDT-{i}'
        risk_manager.positions[position.symbol] = position
        
    # Пытаемся открыть еще одну позицию
    can_open = risk_manager.can_open_position(
        symbol='BTC-USDT-new',
        size=0.01,
        price=50000.0
    )
    assert not can_open

@pytest.mark.asyncio
async def test_emergency_close(risk_manager, sample_position):
    """Тест экстренного закрытия позиций"""
    risk_manager.positions['BTC-USDT'] = sample_position
    risk_manager.initial_balance = 100000
    risk_manager.current_balance = 50000  # 50% просадка
    
    should_close = risk_manager.should_emergency_close()
    assert should_close

def test_position_sizing(risk_manager):
    """Тест расчета размера позиции"""
    base_size = 0.1
    
    # Нормальные условия
    adjusted_size = risk_manager.adjust_position_size(base_size, 'BTC-USDT')
    assert adjusted_size <= base_size
    
    # После убытков размер должен уменьшиться
    risk_manager.on_trade_closed({'pnl': -100})
    new_adjusted_size = risk_manager.adjust_position_size(base_size, 'BTC-USDT')
    assert new_adjusted_size < adjusted_size

def test_risk_metrics(risk_manager, sample_position):
    """Тест расчета метрик риска"""
    risk_manager.positions['BTC-USDT'] = sample_position
    risk_manager.current_balance = 95000
    risk_manager.peak_balance = 100000
    
    metrics = risk_manager.calculate_risk_metrics()
    assert metrics.total_exposure > 0
    assert 0 <= metrics.max_drawdown <= 100
    assert isinstance(metrics.correlation_matrix, dict)

@pytest.mark.asyncio
async def test_risk_updates(risk_manager):
    """Тест обновления риск-параметров"""
    await risk_manager.update_balance(100000)
    
    # Проверяем обновление пикового баланса
    await risk_manager.update_balance(110000)
    assert risk_manager.peak_balance == 110000
    
    # Проверяем расчет просадки
    await risk_manager.update_balance(90000)
    drawdown = risk_manager.calculate_drawdown()
    assert drawdown == pytest.approx(18.18, rel=1e-2)  # (110000-90000)/110000 * 100