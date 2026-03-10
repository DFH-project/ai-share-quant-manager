#!/usr/bin/env python3
"""
enhanced_backtest.py - 增强版回测系统 v2.0
完整功能:
1. 多策略回测 (均线/突破/RSI/MACD)
2. 参数优化 (网格搜索最优参数)
3. 与选股策略联动 (回测验证后再入库)
4. 性能报告 (收益/风险/胜率/回撤)
5. 与现有系统完全集成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import itertools

from core.data_fetcher import data_fetcher
from core.config_manager import get_config


@dataclass
class Trade:
    """交易记录"""
    date: str
    code: str
    action: str
    price: float
    quantity: int
    value: float
    pnl: float = 0  # 平仓时计算


@dataclass
class BacktestReport:
    """回测报告"""
    strategy_name: str
    code: str
    name: str
    start_date: str
    end_date: str
    
    # 收益指标
    total_return: float
    annual_return: float
    total_trades: int
    
    # 风险指标
    max_drawdown: float
    volatility: float
    var_95: float
    
    # 交易指标
    win_rate: float
    profit_factor: float
    avg_profit: float
    avg_loss: float
    
    # 综合指标
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    
    # 详细数据
    trades: List[Trade]
    equity_curve: List[Tuple[str, float]]
    daily_returns: List[float]
    
    # 参数
    params: Dict
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


class StrategyLibrary:
    """策略库 - 预定义策略"""
    
    @staticmethod
    def ma_cross(klines: List[Dict], index: int, 
                short: int = 5, long: int = 20) -> str:
        """均线交叉策略"""
        if index < long:
            return 'HOLD'
        
        closes = [k['close'] for k in klines[index-long:index+1]]
        short_ma = sum(closes[-short:]) / short
        long_ma = sum(closes) / long
        
        prev_closes = [k['close'] for k in klines[index-long:index]]
        prev_short = sum(prev_closes[-short:]) / short
        prev_long = sum(prev_closes) / long
        
        if prev_short <= prev_long and short_ma > long_ma:
            return 'BUY'
        if prev_short >= prev_long and short_ma < long_ma:
            return 'SELL'
        return 'HOLD'
    
    @staticmethod
    def breakout(klines: List[Dict], index: int, 
                lookback: int = 20) -> str:
        """突破策略"""
        if index < lookback:
            return 'HOLD'
        
        current = klines[index]
        prev_high = max([k['high'] for k in klines[index-lookback:index]])
        prev_low = min([k['low'] for k in klines[index-lookback:index]])
        
        if current['close'] > prev_high:
            return 'BUY'
        if current['close'] < prev_low:
            return 'SELL'
        return 'HOLD'
    
    @staticmethod
    def rsi_strategy(klines: List[Dict], index: int,
                    period: int = 14, overbought: int = 70, oversold: int = 30) -> str:
        """RSI策略"""
        if index < period:
            return 'HOLD'
        
        closes = [k['close'] for k in klines[index-period:index+1]]
        
        # 计算RSI
        gains = []
        losses = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        if rsi < oversold:
            return 'BUY'
        if rsi > overbought:
            return 'SELL'
        return 'HOLD'
    
    @staticmethod
    def macd_strategy(klines: List[Dict], index: int,
                     fast: int = 12, slow: int = 26, signal: int = 9) -> str:
        """MACD策略"""
        if index < slow + signal:
            return 'HOLD'
        
        closes = [k['close'] for k in klines[index-slow-signal:index+1]]
        
        # 计算EMA
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_values = [data[0]]
            for i in range(1, len(data)):
                ema_values.append(data[i] * multiplier + ema_values[-1] * (1 - multiplier))
            return ema_values
        
        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        
        macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal_line = ema(macd_line, signal)
        
        # 金叉/死叉
        if len(macd_line) >= 2 and len(signal_line) >= 2:
            if macd_line[-2] <= signal_line[-2] and macd_line[-1] > signal_line[-1]:
                return 'BUY'
            if macd_line[-2] >= signal_line[-2] and macd_line[-1] < signal_line[-1]:
                return 'SELL'
        
        return 'HOLD'


class EnhancedBacktester:
    """增强版回测器"""
    
    def __init__(self, initial_cash: float = 100000):
        self.initial_cash = initial_cash
        self.config = get_config()
    
    def run_backtest(self, 
                    code: str,
                    start_date: str,
                    end_date: str,
                    strategy_func: Callable,
                    strategy_name: str = "自定义策略",
                    **strategy_params) -> Optional[BacktestReport]:
        """
        执行回测
        
        Args:
            code: 股票代码
            start_date: 开始日期 '2024-01-01'
            end_date: 结束日期 '2024-12-31'
            strategy_func: 策略函数
            strategy_name: 策略名称
            **strategy_params: 策略参数
        """
        try:
            # 获取K线数据
            klines = data_fetcher._get_kline_eastmoney(code, days=252)
            
            # 过滤日期
            klines = [k for k in klines if start_date <= k['date'] <= end_date]
            
            if len(klines) < 20:
                print(f"❌ {code} 数据不足")
                return None
            
            # 获取股票名称
            name = code
            try:
                stock_data = data_fetcher.get_stock_data([code])
                if code in stock_data:
                    name = stock_data[code].get('name', code)
            except:
                pass
            
            # 回测状态
            cash = self.initial_cash
            position = 0
            trades = []
            equity_curve = []
            daily_returns = []
            
            # 回测主循环
            for i, k in enumerate(klines):
                date = k['date']
                price = k['close']
                
                # 记录权益
                current_equity = cash + position * price
                equity_curve.append((date, current_equity))
                
                # 计算日收益率
                if i > 0:
                    prev_equity = equity_curve[-2][1]
                    daily_return = (current_equity - prev_equity) / prev_equity
                    daily_returns.append(daily_return)
                
                # 策略信号
                signal = strategy_func(klines, i, **strategy_params)
                
                # 执行交易
                if signal == 'BUY' and position == 0:
                    # 买入
                    quantity = int(cash / price / 100) * 100
                    if quantity >= 100:
                        cost = quantity * price * 1.0005
                        if cash >= cost:
                            cash -= cost
                            position = quantity
                            trades.append(Trade(
                                date=date, code=code, action='BUY',
                                price=price, quantity=quantity, value=cost
                            ))
                
                elif signal == 'SELL' and position > 0:
                    # 卖出
                    revenue = position * price * 0.9995
                    pnl = revenue - trades[-1].value if trades else 0
                    cash += revenue
                    trades.append(Trade(
                        date=date, code=code, action='SELL',
                        price=price, quantity=position, value=revenue, pnl=pnl
                    ))
                    position = 0
            
            # 计算结果
            final_equity = cash + position * klines[-1]['close']
            total_return = (final_equity - self.initial_cash) / self.initial_cash
            
            days = len(klines)
            annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
            
            # 风险指标
            max_dd = self._calc_max_drawdown(equity_curve)
            volatility = np.std(daily_returns) * np.sqrt(252) if daily_returns else 0
            var_95 = np.percentile(daily_returns, 5) if daily_returns else 0
            
            # 交易指标
            closed_trades = [t for t in trades if t.action == 'SELL']
            total_trades = len(closed_trades)
            
            wins = [t for t in closed_trades if t.pnl > 0]
            losses = [t for t in closed_trades if t.pnl <= 0]
            
            win_rate = len(wins) / total_trades if total_trades > 0 else 0
            
            avg_profit = sum(t.pnl for t in wins) / len(wins) if wins else 0
            avg_loss = abs(sum(t.pnl for t in losses) / len(losses)) if losses else 1
            profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
            
            # 综合指标
            sharpe = (annual_return - 0.03) / volatility if volatility > 0 else 0
            
            downside_returns = [r for r in daily_returns if r < 0]
            downside_std = np.std(downside_returns) * np.sqrt(252) if downside_returns else 0
            sortino = (annual_return - 0.03) / downside_std if downside_std > 0 else 0
            
            calmar = annual_return / max_dd if max_dd > 0 else 0
            
            return BacktestReport(
                strategy_name=strategy_name,
                code=code,
                name=name,
                start_date=start_date,
                end_date=end_date,
                total_return=total_return,
                annual_return=annual_return,
                total_trades=total_trades,
                max_drawdown=max_dd,
                volatility=volatility,
                var_95=var_95,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_profit=avg_profit,
                avg_loss=avg_loss,
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                calmar_ratio=calmar,
                trades=trades,
                equity_curve=equity_curve,
                daily_returns=daily_returns,
                params=strategy_params
            )
            
        except Exception as e:
            print(f"❌ 回测失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calc_max_drawdown(self, equity_curve: List[Tuple[str, float]]) -> float:
        """计算最大回撤"""
        if not equity_curve:
            return 0
        
        max_dd = 0
        peak = equity_curve[0][1]
        
        for date, value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def optimize_params(self, code: str, start_date: str, end_date: str,
                       strategy_func: Callable, param_grid: Dict) -> List[BacktestReport]:
        """
        参数优化 - 网格搜索
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            strategy_func: 策略函数
            param_grid: 参数网格，如 {'short': [5, 10], 'long': [20, 30]}
        """
        print(f"🔍 开始参数优化: {code}")
        print(f"   参数空间: {param_grid}")
        
        # 生成参数组合
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))
        
        results = []
        
        for combo in combinations:
            params = dict(zip(keys, combo))
            print(f"   测试参数: {params}")
            
            result = self.run_backtest(
                code, start_date, end_date,
                strategy_func, **params
            )
            
            if result:
                results.append(result)
        
        # 按夏普比率排序
        results.sort(key=lambda x: x.sharpe_ratio, reverse=True)
        
        print(f"✅ 参数优化完成，共测试 {len(results)} 组")
        
        return results


def print_backtest_report(report: BacktestReport):
    """打印回测报告"""
    print("\n" + "="*70)
    print(f"📊 回测报告 - {report.strategy_name}")
    print(f"   标的: {report.name}({report.code})")
    print(f"   周期: {report.start_date} ~ {report.end_date}")
    print("="*70)
    
    print(f"\n💰 收益指标:")
    print(f"   总收益率: {report.total_return*100:+.2f}%")
    print(f"   年化收益率: {report.annual_return*100:+.2f}%")
    print(f"   交易次数: {report.total_trades}")
    
    print(f"\n📉 风险指标:")
    print(f"   最大回撤: {report.max_drawdown*100:.2f}%")
    print(f"   年化波动率: {report.volatility*100:.2f}%")
    print(f"   VaR(95%): {report.var_95*100:.2f}%")
    
    print(f"\n🎯 交易指标:")
    print(f"   胜率: {report.win_rate*100:.1f}%")
    print(f"   盈亏比: {report.profit_factor:.2f}")
    print(f"   平均盈利: ¥{report.avg_profit:.2f}")
    print(f"   平均亏损: ¥{report.avg_loss:.2f}")
    
    print(f"\n⭐ 综合评分:")
    print(f"   夏普比率: {report.sharpe_ratio:.2f}")
    print(f"   索提诺比率: {report.sortino_ratio:.2f}")
    print(f"   卡尔玛比率: {report.calmar_ratio:.2f}")
    
    if report.params:
        print(f"\n⚙️ 最优参数:")
        for k, v in report.params.items():
            print(f"   {k}: {v}")
    
    print("="*70)


# 便捷函数
def quick_backtest(code: str, strategy: str = 'ma_cross', **params) -> Optional[BacktestReport]:
    """
    快速回测
    
    Args:
        code: 股票代码
        strategy: 策略名称 'ma_cross'/'breakout'/'rsi'/'macd'
        **params: 策略参数
    """
    backtester = EnhancedBacktester()
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    strategies = {
        'ma_cross': (StrategyLibrary.ma_cross, '均线交叉'),
        'breakout': (StrategyLibrary.breakout, '突破策略'),
        'rsi': (StrategyLibrary.rsi_strategy, 'RSI策略'),
        'macd': (StrategyLibrary.macd_strategy, 'MACD策略')
    }
    
    if strategy not in strategies:
        print(f"❌ 未知策略: {strategy}")
        return None
    
    strategy_func, strategy_name = strategies[strategy]
    
    return backtester.run_backtest(
        code, start_date, end_date,
        strategy_func, strategy_name, **params
    )


if __name__ == '__main__':
    # 测试
    print("🧪 测试增强版回测系统...")
    
    # 测试均线策略
    report = quick_backtest('300750', 'ma_cross', short=5, long=20)
    if report:
        print_backtest_report(report)
    
    # 测试参数优化
    backtester = EnhancedBacktester()
    results = backtester.optimize_params(
        '300750',
        '2024-01-01',
        '2024-12-31',
        StrategyLibrary.ma_cross,
        {'short': [5, 10], 'long': [20, 30]}
    )
    
    if results:
        print(f"\n🏆 最优参数组合:")
        print_backtest_report(results[0])
