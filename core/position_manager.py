from typing import Dict, List, Optional
from models.position import Position
from utils.logger import setup_logger
import asyncio
import time

class PositionManager:
    def __init__(self, risk_manager, exchanges: Dict):
        self.risk_manager = risk_manager
        self.exchanges = exchanges
        self.positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, Dict] = {}
        self.logger = setup_logger('position_manager')
        
    async def open_position(self, signal: Dict) -> Optional[Position]:
        """Открытие новой позиции"""
        try:
            # Проверка риск-лимитов
            if not self.risk_manager.can_open_position(
                signal['symbol'], 
                signal['size'],
                signal['entry_price']
            ):
                return None
                
            exchange = self.exchanges[signal['exchange']]
            order = await exchange.place_order(
                symbol=signal['symbol'],
                side=signal['side'],
                order_type='limit',
                size=signal['size'],
                price=signal['entry_price']
            )
            
            if order['status'] == 'filled':
                position = Position(
                    symbol=signal['symbol'],
                    side=signal['side'],
                    entry_price=order['price'],
                    size=order['size'],
                    take_profit=signal['take_profit'],
                    stop_loss=signal['stop_loss'],
                    strategy=signal['strategy'],
                    exchange=signal['exchange']
                )
                
                self.positions[signal['symbol']] = position
                return position
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error opening position: {str(e)}")
            return None
            
    async def close_position(self, symbol: str, reason: str = '') -> bool:
        """Закрытие позиции"""
        try:
            if symbol not in self.positions:
                return False
                
            position = self.positions[symbol]
            exchange = self.exchanges[position.exchange]
            
            close_side = 'sell' if position.side == 'long' else 'buy'
            order = await exchange.place_order(
                symbol=symbol,
                side=close_side,
                order_type='market',
                size=position.size
            )
            
            if order['status'] == 'filled':
                pnl = self.calculate_pnl(position, order['price'])
                self.risk_manager.on_trade_closed({
                    'symbol': symbol,
                    'pnl': pnl,
                    'reason': reason
                })
                
                del self.positions[symbol]
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            return False
            
    async def update_positions(self):
        """Обновление всех позиций"""
        for symbol, position in list(self.positions.items()):
            try:
                exchange = self.exchanges[position.exchange]
                current_price = exchange.get_price(symbol)
                position.update_price(current_price)
                
                # Проверка условий закрытия
                if self.should_close_position(position):
                    await self.close_position(symbol, 'tp_sl_hit')
                    
            except Exception as e:
                self.logger.error(f"Error updating position {symbol}: {str(e)}")
                
    def should_close_position(self, position: Position) -> bool:
        """Проверка условий закрытия позиции"""
        if position.side == 'long':
            if position.current_price >= position.take_profit:
                return True
            if position.current_price <= position.stop_loss:
                return True
        else:
            if position.current_price <= position.take_profit:
                return True
            if position.current_price >= position.stop_loss:
                return True
                
        return False
        
    @staticmethod
    def calculate_pnl(position: Position, close_price: float) -> float:
        """Расчет PnL позиции"""
        if position.side == 'long':
            return (close_price - position.entry_price) * position.size
        else:
            return (position.entry_price - close_price) * position.size
            
    async def close_all_positions(self, reason: str = 'emergency'):
        """Закрытие всех позиций"""
        close_tasks = [
            self.close_position(symbol, reason)
            for symbol in list(self.positions.keys())
        ]
        await asyncio.gather(*close_tasks)
        
    def get_position_summary(self) -> Dict:
        """Получение сводки по позициям"""
        return {
            symbol: {
                'side': pos.side,
                'size': pos.size,
                'entry_price': pos.entry_price,
                'current_price': pos.current_price,
                'unrealized_pnl': pos.unrealized_pnl,
                'duration': time.time() - pos.entry_time
            }
            for symbol, pos in self.positions.items()
        }
        
    def get_total_exposure(self) -> float:
        """Расчет общей экспозиции"""
        return sum(
            abs(pos.size * pos.current_price)
            for pos in self.positions.values()
        )