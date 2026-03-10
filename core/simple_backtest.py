#!/usr/bin/env python3
"""
simple_backtest.py - 简化版回测框架
核心原则:
1. 不依赖外部库(如Backtrader)，减少依赖
2. 与现有系统完全兼容
3. 支持策略信号回测验证
4. 零侵入设计，不影响现有功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from core.data_fetcher import data_fetcher
from core.historical_cache import HistoricalDataCache


@dataclass
class TradeRecord:
    """交易记录"""
    date: str
    code: str
    action: str  # BUY/SELL
    price: float
    quantity: int
    value: float
    reason: str


@dataclass
class BacktestResult:
    """回测结果"""
    total_return: float  # 总收益率
    annual_return: float  # 年化收益率
    max_drawdown: float  # 最大回撤
    sharpe_ratio: float  # 夏普比率
    total_trades: int  # 总交易次数
    win_rate: float  # 胜率
    profit_factor: float  # 盈亏比
    trades: List[TradeRecord]  # 交易记录
    equity_curve: List[Tuple[str, float]]  # 权益曲线


class SimpleBacktester:
    """简化版回测器 - 零侵入设计"""
    
    def __init__(self, initial_cash: float = 100000):
        self.initial_cash = initial_cash
        self.cache = HistoricalDataCache()
        
    def backtest_strategy(self, 
                         code: str,
                         start_date: str,
                         end_date: str,
                         strategy_func,
                         **strategy_params) -> Optional[BacktestResult]:
        """
        回测策略
        
        Args:
            code: 股票代码
            start_date: 开始日期 '2024-01-01'
            end_date: 结束日期 '2024-12-31'
            strategy_func: 策略函数
            **strategy_params: 策略参数
        
        Returns:
            BacktestResult: 回测结果
        """
        try:
            # 获取历史K线数据
            klines = self._get_historical_data(code, start_date, end_date)
            if not klines or len(klines) < 20:
                print(f"❌ {code} 历史数据不足")
                return None
            
            # 初始化
            cash = self.initial_cash
            position = 0
            trades = []
            equity_curve = []
            
            # 回测主循环
            for i, k in enumerate(klines):
                date = k['date']
                price = k['close']
                
                # 计算当前权益
                current_equity = cash + position * price
                equity_curve.append((date, current_equity))
                
                # 调用策略函数获取信号
                signal = strategy_func(klines, i, position, **strategy_params)
                
                if signal == 'BUY' and position == 0 and cash > price * 100:
                    # 买入
                    quantity = min(int(cash / price / 100) * 100, 1000)
                    if quantity >= 100:
                        cost = quantity * price * 1.0005  # 含手续费
                        if cash >= cost:
                            cash -= cost
                            position = quantity
                            trades.append(TradeRecord(
                                date=date,
                                code=code,
                                action='BUY',
                                price=price,
                                quantity=quantity,
                                value=cost,
                                reason='策略买入信号'
                            ))
                
                elif signal == 'SELL' and position > 0:
                    # 卖出
                    revenue = position * price * 0.9995  # 含手续费
                    cash += revenue
                    trades.append(TradeRecord(
                        date=date,
                        code=code,
                        action='SELL',
                        price=price,
                        quantity=position,
                        value=revenue,
                        reason='策略卖出信号'
                    ))
                    position = 0
            
            # 计算结果
            final_equity = cash + position * klines[-1]['close']
            total_return = (final_equity - self.initial_cash) / self.initial_cash
            
            # 年化收益率
            days = len(klines)
            annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
            
            # 最大回撤
            max_drawdown = self._calculate_max_drawdown(equity_curve)
            
            # 夏普比率
            sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
            
            # 交易统计
            total_trades = len([t for t in trades if t.action == 'SELL'])
            
            # 胜率计算
            wins = 0
            buy_price = 0
            for t in trades:
                if t.action == 'BUY':
                    buy_price = t.price
                elif t.action == 'SELL' and buy_price > 0:
                    if t.price > buy_price:
                        wins += 1
            win_rate = wins / total_trades if total_trades > 0 else 0
            
            # 盈亏比
            profits = []
            losses = []
            for i, t in enumerate(trades):
                if t.action == 'SELL':
                    # 找到对应的买入
                    for j in range(i-1, -1, -1):
                        if trades[j].action == 'BUY':
                            pnl = (t.price - trades[j].price) / trades[j].price
                            if pnl > 0:
                                profits.append(pnl)
                            else:
                                losses.append(abs(pnl))
                            break
            
            avg_profit = sum(profits) / len(profits) if profits else 0
            avg_loss = sum(losses) / len(losses) if losses else 1
            profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
            
            return BacktestResult(
                total_return=total_return,
                annual_return=annual_return,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                total_trades=total_trades,
                win_rate=win_rate,
                profit_factor=profit_factor,
                trades=trades,
                equity_curve=equity_curve
            )
            
        except Exception as e:
            print(f"❌ 回测失败: {e}")
            return None
    
    def _get_historical_data(self, code: str, start_date: str, end_date: str) -> List[Dict]:
        """获取历史数据"""
        try:
            # 使用data_fetcher获取K线
            klines = data_fetcher._get_kline_eastmoney(code, days=252)
            
            # 过滤日期范围
            filtered = []
            for k in klines:
                if start_date <= k['date'] <= end_date:
                    filtered.append(k)
            
            return filtered
        except:
            return []
    
    def _calculate_max_drawdown(self, equity_curve: List[Tuple[str, float]]) -> float:
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
    
    def _calculate_sharpe_ratio(self, equity_curve: List[Tuple[str, float]]) -> float:
        """计算夏普比率"""
        if len(equity_curve) < 2:
            return 0
        
        # 计算日收益率
        returns = []
        for i in range(1, len(equity_curve)):
            r = (equity_curve[i][1] - equity_curve[i-1][1]) / equity_curve[i-1][1]
            returns.append(r)
        
        if not returns:
            return 0
        
        avg_return = sum(returns) / len(returns)
        std_return = (sum([(r - avg_return)**2 for r in returns]) / len(returns)) ** 0.5
        
        if std_return == 0:
            return 0
        
        # 年化夏普比率
        sharpe = (avg_return * 252) / (std_return * (252**0.5))
        return sharpe


# 预设策略函数
def ma_cross_strategy(klines: List[Dict], index: int, position: int, 
                     short_ma: int = 5, long_ma: int = 20) -> str:
    """
    均线交叉策略
    - 短期均线上穿长期均线: 买入
    - 短期均线下穿长期均线: 卖出
    """
    if index < long_ma:
        return 'HOLD'
    
    # 计算均线
    short_values = [k['close'] for k in klines[index-short_ma+1:index+1]]
    long_values = [k['close'] for k in klines[index-long_ma+1:index+1]]
    
    short_ma_val = sum(short_values) / len(short_values)
    long_ma_val = sum(long_values) / len(long_values)
    
    # 前一日的均线
    if index > 0:
        prev_short = sum([k['close'] for k in klines[index-short_ma:index]]) / short_ma
        prev_long = sum([k['close'] for k in klines[index-long_ma:index]]) / long_ma
        
        # 金叉
        if prev_short <= prev_long and short_ma_val > long_ma_val:
            return 'BUY'
        
        # 死叉
        if prev_short >= prev_long and short_ma_val < long_ma_val:
            return 'SELL'
    
    return 'HOLD'


def breakout_strategy(klines: List[Dict], index: int, position: int,
                     lookback: int = 20) -> str:
    """
    突破策略
    - 突破前高买入
    - 跌破前低卖出
    """
    if index < lookback:
        return 'HOLD'
    
    current = klines[index]
    prev_high = max([k['high'] for k in klines[index-lookback:index]])
    prev_low = min([k['low'] for k in klines[index-lookback:index]])
    
    if current['close'] > prev_high and position == 0:
        return 'BUY'
    
    if current['close'] < prev_low and position > 0:
        return 'SELL'
    
    return 'HOLD'


def print_backtest_result(result: BacktestResult):
    """打印回测结果"""
    print("\n" + "="*70)
    print("📊 回测结果报告")
    print("="*70)
    print(f"\n💰 收益指标:")
    print(f"   总收益率: {result.total_return*100:+.2f}%")
    print(f"   年化收益率: {result.annual_return*100:+.2f}%")
    print(f"   最大回撤: {result.max_drawdown*100:.2f}%")
    print(f"   夏普比率: {result.sharpe_ratio:.2f}")
    
    print(f"\n📈 交易统计:")
    print(f"   总交易次数: {result.total_trades}")
    print(f"   胜率: {result.win_rate*100:.1f}%")
    print(f"   盈亏比: {result.profit_factor:.2f}")
    
    print(f"\n📝 最近5笔交易:")
    for t in result.trades[-5:]:
        print(f"   {t.date} {t.action} {t.code} @ {t.price:.2f} x {t.quantity}")
    
    print("="*70)


# 便捷函数
def backtest_stock(code: str, start_date: str = None, end_date: str = None,
                  strategy='ma_cross', **params) -> Optional[BacktestResult]:
    """
    便捷回测函数
    
    Args:
        code: 股票代码
        start_date: 开始日期，默认一年前
        end_date: 结束日期，默认今天
        strategy: 策略名称 'ma_cross'/'breakout'
        **params: 策略参数
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    backtester = SimpleBacktester()
    
    if strategy == 'ma_cross':
        return backtester.backtest_strategy(code, start_date, end_date, 
                                           ma_cross_strategy, **params)
    elif strategy == 'breakout':
        return backtester.backtest_strategy(code, start_date, end_date,
                                           breakout_strategy, **params)
    else:
        print(f"❌ 未知策略: {strategy}")
        return None


if __name__ == '__main__':
    # 测试回测
    print("🧪 测试回测功能...")
    
    # 测试均线策略
    result = backtest_stock('300750', strategy='ma_cross', short_ma=5, long_ma=20)
    if result:
        print_backtest_result(result)
    else:
        print("❌ 回测失败")
