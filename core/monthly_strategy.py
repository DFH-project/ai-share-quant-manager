"""
monthly_strategy.py - 月度策略模块
基于技术指标的月度选股策略
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class SignalType(Enum):
    """信号类型"""
    BUY = "买入"
    SELL = "卖出"
    HOLD = "持有"
    WATCH = "关注"


@dataclass
class StrategySignal:
    """策略信号"""
    code: str
    name: str
    signal: SignalType
    score: float           # 综合评分 0-100
    reasons: List[str]     # 信号原因
    indicators: Dict       # 技术指标值
    generated_at: str      # 生成时间


class MonthlyStrategy:
    """月度选股策略"""
    
    def __init__(self, data_fetcher):
        """
        初始化策略
        Args:
            data_fetcher: DataFetcherV2 实例
        """
        self.data_fetcher = data_fetcher
        self.signals: List[StrategySignal] = []
        
        # 策略参数
        self.params = {
            'ma_short': 5,      # 短期均线
            'ma_medium': 20,    # 中期均线
            'ma_long': 60,      # 长期均线
            'rsi_period': 14,   # RSI周期
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'volume_ma': 20,    # 成交量均线
            'min_score': 60     # 最小信号分数
        }
    
    def calculate_ma(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算移动平均线"""
        return df['close'].rolling(window=period).mean()
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算MACD指标"""
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return macd, signal, hist
    
    def calculate_bollinger(self, df: pd.DataFrame, period: int = 20, std: int = 2):
        """计算布林带"""
        ma = df['close'].rolling(window=period).mean()
        std_dev = df['close'].rolling(window=period).std()
        upper = ma + (std_dev * std)
        lower = ma - (std_dev * std)
        return upper, ma, lower
    
    def analyze_stock(self, code: str, name: str = "") -> Optional[StrategySignal]:
        """分析单只股票"""
        # 获取历史数据
        df = self.data_fetcher.get_daily_data(code)
        if df is None or df.empty or len(df) < 60:
            return None
        
        # 计算技术指标
        df['ma5'] = self.calculate_ma(df, self.params['ma_short'])
        df['ma20'] = self.calculate_ma(df, self.params['ma_medium'])
        df['ma60'] = self.calculate_ma(df, self.params['ma_long'])
        df['rsi'] = self.calculate_rsi(df, self.params['rsi_period'])
        df['macd'], df['macd_signal'], df['macd_hist'] = self.calculate_macd(df)
        df['volume_ma20'] = df['volume'].rolling(window=self.params['volume_ma']).mean()
        df['boll_upper'], df['boll_mid'], df['boll_lower'] = self.calculate_bollinger(df)
        
        # 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        score = 0
        reasons = []
        indicators = {
            'close': round(latest['close'], 2),
            'ma5': round(latest['ma5'], 2) if not pd.isna(latest['ma5']) else None,
            'ma20': round(latest['ma20'], 2) if not pd.isna(latest['ma20']) else None,
            'ma60': round(latest['ma60'], 2) if not pd.isna(latest['ma60']) else None,
            'rsi': round(latest['rsi'], 2) if not pd.isna(latest['rsi']) else None,
            'macd': round(latest['macd'], 4) if not pd.isna(latest['macd']) else None,
            'volume_ratio': round(latest['volume'] / latest['volume_ma20'], 2) if not pd.isna(latest['volume_ma20']) else None
        }
        
        # 均线多头排列
        if indicators['ma5'] and indicators['ma20'] and indicators['ma60']:
            if latest['close'] > indicators['ma5'] > indicators['ma20'] > indicators['ma60']:
                score += 25
                reasons.append("均线多头排列")
            elif latest['close'] > indicators['ma20']:
                score += 10
                reasons.append("股价在20日均线上方")
        
        # RSI判断
        if indicators['rsi']:
            if indicators['rsi'] < self.params['rsi_oversold']:
                score += 20
                reasons.append(f"RSI超卖({indicators['rsi']})")
            elif indicators['rsi'] < 50:
                score += 10
                reasons.append("RSI处于低位")
            elif indicators['rsi'] > self.params['rsi_overbought']:
                score -= 15
                reasons.append(f"RSI超买({indicators['rsi']})")
        
        # MACD判断
        if indicators['macd'] and not pd.isna(latest['macd_signal']):
            if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
                score += 20
                reasons.append("MACD金叉")
            elif latest['macd'] > latest['macd_signal']:
                score += 10
                reasons.append("MACD在零轴上方")
        
        # 成交量判断
        if indicators['volume_ratio']:
            if indicators['volume_ratio'] > 2:
                score += 15
                reasons.append("成交量显著放大")
            elif indicators['volume_ratio'] > 1.5:
                score += 10
                reasons.append("成交量温和放大")
        
        # 布林带判断
        if not pd.isna(latest['boll_lower']) and not pd.isna(latest['boll_upper']):
            if latest['close'] < latest['boll_lower']:
                score += 10
                reasons.append("股价触及布林带下轨")
            elif latest['close'] > latest['boll_upper']:
                score -= 10
                reasons.append("股价突破布林带上轨")
        
        # 确定信号类型
        if score >= 70:
            signal = SignalType.BUY
        elif score >= 50:
            signal = SignalType.WATCH
        elif score <= 30:
            signal = SignalType.SELL
        else:
            signal = SignalType.HOLD
        
        return StrategySignal(
            code=code,
            name=name or code,
            signal=signal,
            score=min(100, max(0, score)),
            reasons=reasons,
            indicators=indicators,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def scan_watchlist(self, watchlist) -> List[StrategySignal]:
        """扫描自选股列表生成信号"""
        self.signals = []
        items = watchlist.get_all()
        
        print(f"\n开始扫描 {len(items)} 只自选股...")
        
        for item in items:
            signal = self.analyze_stock(item.code, item.name)
            if signal and signal.score >= self.params['min_score']:
                self.signals.append(signal)
                print(f"  ✓ {item.code} ({item.name}): {signal.signal.value} - 评分:{signal.score}")
        
        # 按分数排序
        self.signals.sort(key=lambda x: x.score, reverse=True)
        
        print(f"生成 {len(self.signals)} 个交易信号")
        return self.signals
    
    def scan_market(self, limit: int = 100) -> List[StrategySignal]:
        """扫描整个市场（限于性能，只扫描部分）"""
        self.signals = []
        
        # 获取股票列表
        df = self.data_fetcher.get_stock_list()
        if df.empty:
            return []
        
        # 按市值排序，取前limit只
        if 'market_cap' in df.columns:
            df = df.nlargest(limit, 'market_cap')
        
        codes = df['code'].tolist()[:limit]
        names = dict(zip(df['code'], df['name'])) if 'name' in df.columns else {}
        
        print(f"\n开始扫描市场前 {len(codes)} 只股票...")
        
        for code in codes:
            signal = self.analyze_stock(code, names.get(code, code))
            if signal and signal.score >= self.params['min_score']:
                self.signals.append(signal)
                print(f"  ✓ {code}: {signal.signal.value} - 评分:{signal.score}")
        
        # 按分数排序
        self.signals.sort(key=lambda x: x.score, reverse=True)
        
        print(f"生成 {len(self.signals)} 个交易信号")
        return self.signals
    
    def get_top_signals(self, n: int = 10, signal_type: Optional[SignalType] = None) -> List[StrategySignal]:
        """获取排名靠前的信号"""
        signals = self.signals
        if signal_type:
            signals = [s for s in signals if s.signal == signal_type]
        return signals[:n]
    
    def generate_monthly_report(self) -> Dict:
        """生成月度策略报告"""
        buy_signals = [s for s in self.signals if s.signal == SignalType.BUY]
        watch_signals = [s for s in self.signals if s.signal == SignalType.WATCH]
        sell_signals = [s for s in self.signals if s.signal == SignalType.SELL]
        
        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_signals': len(self.signals),
            'buy_count': len(buy_signals),
            'watch_count': len(watch_signals),
            'sell_count': len(sell_signals),
            'top_buy': [
                {
                    'code': s.code,
                    'name': s.name,
                    'score': s.score,
                    'reasons': s.reasons,
                    'indicators': s.indicators
                }
                for s in buy_signals[:10]
            ],
            'top_watch': [
                {
                    'code': s.code,
                    'name': s.name,
                    'score': s.score,
                    'reasons': s.reasons
                }
                for s in watch_signals[:10]
            ]
        }
        
        return report
    
    def display_signals(self, signals: Optional[List[StrategySignal]] = None) -> None:
        """显示信号列表"""
        signals = signals or self.signals
        
        if not signals:
            print("暂无交易信号")
            return
        
        print(f"\n{'='*100}")
        print(f"{'代码':<10}{'名称':<12}{'信号':<8}{'评分':<8}{'关键指标':<40}{'原因'}")
        print(f"{'-'*100}")
        
        for s in signals[:20]:  # 只显示前20个
            indicator_str = f"RSI:{s.indicators.get('rsi')} MACD:{s.indicators.get('macd')}"
            reasons = ", ".join(s.reasons[:2]) if s.reasons else ""
            print(f"{s.code:<10}{s.name:<12}{s.signal.value:<8}{s.score:<8}{indicator_str:<40}{reasons}")
        
        print(f"{'='*100}")
        print(f"显示前 {min(20, len(signals))}/{len(signals)} 个信号")


# 单例
_monthly_strategy = None

def get_monthly_strategy(data_fetcher=None) -> MonthlyStrategy:
    """获取月度策略单例"""
    global _monthly_strategy
    if _monthly_strategy is None:
        if data_fetcher is None:
            from core.data_fetcher_v2 import get_data_fetcher
            data_fetcher = get_data_fetcher()
        _monthly_strategy = MonthlyStrategy(data_fetcher)
    return _monthly_strategy
