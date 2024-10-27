import sys
from pathlib import Path
import asyncio
import json
from typing import Dict, List
import numpy as np
from datetime import datetime
import optuna
from concurrent.futures import ProcessPoolExecutor

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import STRATEGY_CONFIGS, BACKTEST_CONFIG
from scripts.backtest import Backtester
from utils.logger import setup_logger

logger = setup_logger('optimizer')

class StrategyOptimizer:
    def __init__(self, strategy_name: str, symbol: str, timeframe: str):
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.timeframe = timeframe
        self.base_config = STRATEGY_CONFIGS[strategy_name].copy()
        self.study = None
        
    async def optimize(self, n_trials: int = 100, n_jobs: int = 4):
        """Запуск оптимизации параметров стратегии"""
        logger.info(f"Starting optimization for {self.strategy_name}")
        
        # Создание исследования Optuna
        self.study = optuna.create_study(
            direction="maximize",
            study_name=f"{self.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            sampler=optuna.samplers.TPESampler(seed=42)
        )
        
        # Параллельная оптимизация
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = []
            for _ in range(n_trials):
                futures.append(
                    executor.submit(self._objective)
                )
            
            for future in futures:
                try:
                    self.study.tell(future.result()[0], future.result()[1])
                except Exception as e:
                    logger.error(f"Trial failed: {str(e)}")
                    
        # Сохранение результатов
        self._save_results()
        
    def _objective(self, trial: optuna.Trial) -> float:
        """Целевая функция для оптимизации"""
        # Генерация параметров для тестирования
        params = self._generate_params(trial)
        
        try:
            # Создание бэктестера с новыми параметрами
            backtester = Backtester({
                **BACKTEST_CONFIG,
                'strategy_params': params
            })
            
            # Запуск бэктеста
            results = asyncio.run(backtester.run_backtest(
                self.symbol,
                self.timeframe,
                params
            ))
            
            # Расчет метрики для оптимизации
            return self._calculate_objective(results)
            
        except Exception as e:
            logger.error(f"Error in trial: {str(e)}")
            return float('-inf')
            
    def _generate_params(self, trial: optuna.Trial) -> Dict:
        """Генерация параметров для тестирования"""
        if self.strategy_name == 'OrderBookImbalance':
            return {
                'min_imbalance_ratio': trial.suggest_float('min_imbalance_ratio', 1.5, 5.0),
                'large_order_threshold': trial.suggest_float('large_order_threshold', 50.0, 200.0),
                'min_spread': trial.suggest_float('min_spread', 0.0001, 0.001),
                'take_profit_pct': trial.suggest_float('take_profit_pct', 0.001, 0.005),
                'stop_loss_pct': trial.suggest_float('stop_loss_pct', 0.0005, 0.003)
            }
        elif self.strategy_name == 'PriceAction':
            return {
                'min_impulse_pct': trial.suggest_float('min_impulse_pct', 0.001, 0.005),
                'volume_threshold': trial.suggest_float('volume_threshold', 1.5, 3.0),
                'retracement_min': trial.suggest_float('retracement_min', 0.2, 0.4),
                'retracement_max': trial.suggest_float('retracement_max', 0.4, 0.6)
            }
        # Добавить параметры для других стратегий...
        
    def _calculate_objective(self, results: Dict) -> float:
        """Расчет целевой метрики для оптимизации"""
        # Комбинированная метрика
        sharpe_ratio = results['sharpe_ratio']
        profit_factor = results['profit_factor']
        win_rate = results['win_rate']
        max_drawdown = abs(results['max_drawdown'])
        
        # Штраф за большую просадку
        drawdown_penalty = np.exp(-max_drawdown / 20)  # 20% базовая просадка
        
        # Итоговая метрика
        return (sharpe_ratio * 0.4 + 
                profit_factor * 0.3 + 
                win_rate * 0.3) * drawdown_penalty
                
    def _save_results(self):
        """Сохранение результатов оптимизации"""
        results_dir = Path(BACKTEST_CONFIG['results_dir']) / 'optimization'
        results_dir.mkdir(exist_ok=True, parents=True)
        
        # Лучшие параметры
        best_params = self.study.best_params
        best_value = self.study.best_value
        
        # Все тесты
        trials_data = []
        for trial in self.study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                trials_data.append({
                    'params': trial.params,
                    'value': trial.value
                })
                
        results = {
            'strategy': self.strategy_name,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'best_params': best_params,
            'best_value': best_value,
            'all_trials': trials_data,
            'timestamp': datetime.now().isoformat()
        }
        
        file_path = results_dir / f"optimization_{self.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(file_path, 'w') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Optimization results saved to {file_path}")
        logger.info(f"Best parameters: {best_params}")
        logger.info(f"Best value: {best_value}")

async def main():
    try:
        # Параметры оптимизации
        strategy_name = "OrderBookImbalance"  # или другая стратегия
        symbol = "BTC-USDT"
        timeframe = "5m"
        n_trials = 100
        n_jobs = 4
        
        optimizer = StrategyOptimizer(strategy_name, symbol, timeframe)
        await optimizer.optimize(n_trials, n_jobs)
        
    except Exception as e:
        logger.error(f"Optimization error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())