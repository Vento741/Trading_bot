from typing import Any, Dict, List, Optional, Union
import re
from decimal import Decimal
import time

class ValidationError(Exception):
    """Исключение для ошибок валидации"""
    pass

class Validator:
    @staticmethod
    def validate_symbol(symbol: str) -> bool:
        """Валидация торгового символа"""
        pattern = r'^[A-Z0-9]{2,20}-[A-Z]{2,10}$'
        if not re.match(pattern, symbol):
            raise ValidationError(f"Invalid symbol format: {symbol}")
        return True
        
    @staticmethod
    def validate_order_params(params: Dict) -> bool:
        """Валидация параметров ордера"""
        required_fields = ['symbol', 'side', 'size']
        for field in required_fields:
            if field not in params:
                raise ValidationError(f"Missing required field: {field}")
                
        # Проверка стороны ордера
        if params['side'].lower() not in ['buy', 'sell', 'long', 'short']:
            raise ValidationError(f"Invalid order side: {params['side']}")
            
        # Проверка размера
        try:
            size = float(params['size'])
            if size <= 0:
                raise ValidationError(f"Invalid order size: {size}")
        except ValueError:
            raise ValidationError(f"Invalid order size format: {params['size']}")
            
        # Проверка цены для лимитных ордеров
        if 'price' in params:
            try:
                price = float(params['price'])
                if price <= 0:
                    raise ValidationError(f"Invalid price: {price}")
            except ValueError:
                raise ValidationError(f"Invalid price format: {params['price']}")
                
        return True
        
    @staticmethod
    def validate_position_params(params: Dict) -> bool:
        """Валидация параметров позиции"""
        required_fields = ['symbol', 'side', 'size', 'entry_price']
        for field in required_fields:
            if field not in params:
                raise ValidationError(f"Missing required field: {field}")
                
        # Валидация стоп-лосса и тейк-профита
        if 'stop_loss' in params:
            try:
                stop_loss = float(params['stop_loss'])
                if stop_loss <= 0:
                    raise ValidationError(f"Invalid stop loss: {stop_loss}")
            except ValueError:
                raise ValidationError(f"Invalid stop loss format: {params['stop_loss']}")
                
        if 'take_profit' in params:
            try:
                take_profit = float(params['take_profit'])
                if take_profit <= 0:
                    raise ValidationError(f"Invalid take profit: {take_profit}")
            except ValueError:
                raise ValidationError(f"Invalid take profit format: {params['take_profit']}")
                
        return True
        
    @staticmethod
    def validate_strategy_params(params: Dict) -> bool:
        """Валидация параметров стратегии"""
        required_fields = ['name', 'symbols']
        for field in required_fields:
            if field not in params:
                raise ValidationError(f"Missing required field: {field}")
                
        # Проверка списка символов
        if not isinstance(params['symbols'], list) or not params['symbols']:
            raise ValidationError("Symbols must be a non-empty list")
            
        for symbol in params['symbols']:
            Validator.validate_symbol(symbol)
            
        return True
        
    @staticmethod
    def validate_timeframe(timeframe: str) -> bool:
        """Валидация таймфрейма"""
        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '1M']
        if timeframe not in valid_timeframes:
            raise ValidationError(f"Invalid timeframe: {timeframe}")
        return True
        
    @staticmethod
    def validate_risk_params(params: Dict) -> bool:
        """Валидация параметров риск-менеджмента"""
        required_fields = ['max_position_size', 'max_drawdown']
        for field in required_fields:
            if field not in params:
                raise ValidationError(f"Missing required field: {field}")
                
        # Проверка максимального размера позиции
        try:
            max_pos_size = float(params['max_position_size'])
            if not (0 < max_pos_size <= 1):
                raise ValidationError(f"Max position size must be between 0 and 1: {max_pos_size}")
        except ValueError:
            raise ValidationError(f"Invalid max position size format: {params['max_position_size']}")
            
        # Проверка максимальной просадки
        try:
            max_drawdown = float(params['max_drawdown'])
            if not (0 < max_drawdown <= 1):
                raise ValidationError(f"Max drawdown must be between 0 and 1: {max_drawdown}")
        except ValueError:
            raise ValidationError(f"Invalid max drawdown format: {params['max_drawdown']}")
            
        return True
        
    @staticmethod
    def validate_api_credentials(credentials: Dict) -> bool:
        """Валидация API-ключей"""
        required_fields = ['api_key', 'api_secret']
        for field in required_fields:
            if field not in credentials:
                raise ValidationError(f"Missing required field: {field}")
                
        # Проверка формата API-ключа
        if not re.match(r'^[A-Za-z0-9]{30,}$', credentials['api_key']):
            raise ValidationError("Invalid API key format")
            
        # Проверка формата секретного ключа
        if not re.match(r'^[A-Za-z0-9]{30,}$', credentials['api_secret']):
            raise ValidationError("Invalid API secret format")
            
        return True
        
    @staticmethod
    def validate_orderbook(orderbook: Dict) -> bool:
        """Валидация данных книги ордеров"""
        required_fields = ['symbol', 'bids', 'asks']
        for field in required_fields:
            if field not in orderbook:
                raise ValidationError(f"Missing required field: {field}")
                
        # Проверка формата ордеров
        for side in ['bids', 'asks']:
            if not isinstance(orderbook[side], list):
                raise ValidationError(f"Invalid {side} format")
                
            for order in orderbook[side]:
                if not isinstance(order, (list, tuple)) or len(order) != 2:
                    raise ValidationError(f"Invalid order format in {side}")
                    
                try:
                    price, size = float(order[0]), float(order[1])
                    if price <= 0 or size <= 0:
                        raise ValidationError(f"Invalid price or size in {side}")
                except ValueError:
                    raise ValidationError(f"Invalid number format in {side}")
                    
        # Проверка корректности цен
        if orderbook['bids'] and orderbook['asks']:
            if float(orderbook['bids'][0][0]) >= float(orderbook['asks'][0][0]):
                raise ValidationError("Invalid orderbook: best bid >= best ask")
                
        return True
        
    @staticmethod
    def validate_trade_data(trade: Dict) -> bool:
        """Валидация данных о сделке"""
        required_fields = ['symbol', 'price', 'size', 'side', 'timestamp']
        for field in required_fields:
            if field not in trade:
                raise ValidationError(f"Missing required field: {field}")
                
        # Проверка цены и объема
        try:
            price = float(trade['price'])
            size = float(trade['size'])
            if price <= 0 or size <= 0:
                raise ValidationError("Invalid price or size")
        except ValueError:
            raise ValidationError("Invalid number format in trade data")
            
        # Проверка временной метки
        try:
            timestamp = float(trade['timestamp'])
            if timestamp > time.time() + 60:  # Допуск в 1 минуту для расхождения времени
                raise ValidationError("Invalid timestamp: future date")
        except ValueError:
            raise ValidationError("Invalid timestamp format")
            
        return True