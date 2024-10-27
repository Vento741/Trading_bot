from typing import Dict, List, Optional
import time
from datetime import datetime, timedelta
import numpy as np
from collections import deque
import pandas as pd

class MetricsCollector:
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        
        # Метрики производительности
        self.trades: List[Dict] = []
        self.daily_pnl = []
        self.execution_times = deque(maxlen=window_size)
        self.slippage_metrics = deque(maxlen=window_size)
        
        # Метрики системы
        self.latency_metrics = deque(maxlen=window_size)
        self.memory_usage = deque(maxlen=window_size)
        self.cpu_usage = deque(maxlen=window_size)
        
        # Временные метки
        self.start_time = time.time()
        self.last_update = self.start_time
        
    def record_trade(self, trade: Dict):
        """Записать информацию о сделке"""
        self.trades.append({
            'timestamp': time.time(),
            'symbol': trade['symbol'],
            'side': trade['side'],
            'size': trade['size'],
            'entry_price': trade['entry_price'],
            'exit_price': trade.get('exit_price'),
            'pnl': trade.get('pnl', 0),
            'duration': trade.get('duration', 0),
            'strategy': trade.get('strategy', 'unknown')
        })
        
        # Обновляем дневной P&L
        current_date = datetime.now().date()
        if not self.daily_pnl or self.daily_pnl[-1]['date'] != current_date:
            self.daily_pnl.append({
                'date': current_date,
                'pnl': trade.get('pnl', 0)
            })
        else:
            self.daily_pnl[-1]['pnl'] += trade.get('pnl', 0)
            
    def record_execution_time(self, execution_time: float):
        """Записать время исполнения операции"""
        self.execution_times.append(execution_time)
        
    def record_slippage(self, expected_price: float, executed_price: float):
        """Записать данные о проскальзывании"""
        slippage = abs(executed_price - expected_price) / expected_price
        self.slippage_metrics.append(slippage)
        
    def record_latency(self, latency: float):
        """Записать данные о задержке"""
        self.latency_metrics.append(latency)
        
    def record_system_metrics(self, memory_usage: float, cpu_usage: float):
        """Записать системные метрики"""
        self.memory_usage.append(memory_usage)
        self.cpu_usage.append(cpu_usage)
        
    def get_performance_metrics(self) -> Dict:
        """Получить метрики производительности"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'average_profit': 0,
                'sharpe_ratio': 0
            }
            
        # Базовые метрики
        total_trades = len(self.trades)
        profitable_trades = sum(1 for trade in self.trades if trade['pnl'] > 0)
        win_rate = profitable_trades / total_trades
        
        # Profit Factor
        gross_profit = sum(trade['pnl'] for trade in self.trades if trade['pnl'] > 0)
        gross_loss = abs(sum(trade['pnl'] for trade in self.trades if trade['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
        
        # Average metrics
        avg_profit = sum(trade['pnl'] for trade in self.trades) / total_trades
        avg_duration = sum(trade['duration'] for trade in self.trades) / total_trades
        
        # Sharpe Ratio (using daily returns)
        daily_returns = [day['pnl'] for day in self.daily_pnl]
        if len(daily_returns) > 1:
            returns_arr = np.array(daily_returns)
            sharpe = np.mean(returns_arr) / np.std(returns_arr) * np.sqrt(365)
        else:
            sharpe = 0
            
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'average_profit': avg_profit,
            'average_duration': avg_duration,
            'sharpe_ratio': sharpe,
            'max_drawdown': self.calculate_max_drawdown(),
            'execution_stats': self.get_execution_stats(),
            'slippage_stats': self.get_slippage_stats()
        }
        
    def get_execution_stats(self) -> Dict:
        """Получить статистику исполнения"""
        if not self.execution_times:
            return {
                'avg_execution_time': 0,
                'max_execution_time': 0,
                'min_execution_time': 0
            }
            
        return {
            'avg_execution_time': np.mean(self.execution_times),
            'max_execution_time': max(self.execution_times),
            'min_execution_time': min(self.execution_times),
            'std_execution_time': np.std(self.execution_times)
        }
        
    def get_slippage_stats(self) -> Dict:
        """Получить статистику проскальзывания"""
        if not self.slippage_metrics:
            return {
                'avg_slippage': 0,
                'max_slippage': 0,
                'min_slippage': 0
            }
            
        return {
            'avg_slippage': np.mean(self.slippage_metrics),
            'max_slippage': max(self.slippage_metrics),
            'min_slippage': min(self.slippage_metrics),
            'std_slippage': np.std(self.slippage_metrics)
        }
        
    def calculate_max_drawdown(self) -> float:
        """Рассчитать максимальную просадку"""
        if not self.daily_pnl:
            return 0
            
        cumulative_returns = np.cumsum([day['pnl'] for day in self.daily_pnl])
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (running_max - cumulative_returns) / running_max
        return float(np.max(drawdowns)) if len(drawdowns) > 0 else 0
        
    def get_system_metrics(self) -> Dict:
        """Получить системные метрики"""
        if not self.latency_metrics:
            return {
                'avg_latency': 0,
                'avg_memory_usage': 0,
                'avg_cpu_usage': 0
            }
            
        return {
            'avg_latency': np.mean(self.latency_metrics),
            'max_latency': max(self.latency_metrics),
            'avg_memory_usage': np.mean(self.memory_usage),
            'avg_cpu_usage': np.mean(self.cpu_usage),
            'uptime': time.time() - self.start_time
        }
        
    def get_strategy_performance(self) -> Dict:
        """Получить производительность по стратегиям"""
        if not self.trades:
            return {}
            
        strategy_metrics = {}
        df = pd.DataFrame(self.trades)
        
        for strategy in df['strategy'].unique():
            strategy_trades = df[df['strategy'] == strategy]
            profitable_trades = len(strategy_trades[strategy_trades['pnl'] > 0])
            total_trades = len(strategy_trades)
            
            strategy_metrics[strategy] = {
                'total_trades': total_trades,
                'win_rate': profitable_trades / total_trades if total_trades > 0 else 0,
                'total_pnl': float(strategy_trades['pnl'].sum()),
                'avg_pnl': float(strategy_trades['pnl'].mean()),
                'avg_duration': float(strategy_trades['duration'].mean())
            }
            
        return strategy_metrics
        
    def export_metrics(self, format: str = 'json') -> str:
        """Экспорт метрик в различных форматах"""
        data = {
            'performance': self.get_performance_metrics(),
            'system': self.get_system_metrics(),
            'strategy_performance': self.get_strategy_performance(),
            'timestamp': time.time()
        }
        
        if format == 'json':
            import json
            return json.dumps(data, indent=2)
        elif format == 'csv':
            # Упрощенный экспорт основных метрик в CSV
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            for category, metrics in data.items():
                if isinstance(metrics, dict):
                    for metric, value in metrics.items():
                        writer.writerow([category, metric, value])
                        
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")