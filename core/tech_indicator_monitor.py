#!/usr/bin/env python3
"""
tech_indicator_monitor.py - 技术指标监控模块
功能：
1. 计算常用技术指标（MACD、KDJ、均线等）
2. 监控金叉死叉信号
3. 趋势判断
"""

import akshare as ak
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class TechSignal:
    """技术信号"""
    code: str
    name: str
    indicator: str  # MACD/KDJ/MA等
    signal_type: str  # 金叉/死叉/突破等
    strength: str  # 强/中/弱
    current_value: float
    description: str
    timestamp: str


class TechIndicatorCalculator:
    """技术指标计算器"""
    
    @staticmethod
    def calculate_ma(data: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """计算移动平均线"""
        for period in periods:
            data[f'MA{period}'] = data['close'].rolling(window=period).mean()
        return data
    
    @staticmethod
    def calculate_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算MACD"""
        ema_fast = data['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = data['close'].ewm(span=slow, adjust=False).mean()
        data['MACD'] = ema_fast - ema_slow
        data['MACD_Signal'] = data['MACD'].ewm(span=signal, adjust=False).mean()
        data['MACD_Hist'] = data['MACD'] - data['MACD_Signal']
        return data
    
    @staticmethod
    def calculate_kdj(data: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """计算KDJ"""
        low_list = data['low'].rolling(window=n, min_periods=n).min()
        high_list = data['high'].rolling(window=n, min_periods=n).max()
        rsv = (data['close'] - low_list) / (high_list - low_list) * 100
        
        data['K'] = rsv.ewm(alpha=1/m1, adjust=False).mean()
        data['D'] = data['K'].ewm(alpha=1/m2, adjust=False).mean()
        data['J'] = 3 * data['K'] - 2 * data['D']
        return data
    
    @staticmethod
    def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算RSI"""
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        return data
    
    @staticmethod
    def calculate_bollinger(data: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
        """计算布林带"""
        data['BOLL_MID'] = data['close'].rolling(window=period).mean()
        data['BOLL_STD'] = data['close'].rolling(window=period).std()
        data['BOLL_UP'] = data['BOLL_MID'] + std_dev * data['BOLL_STD']
        data['BOLL_DOWN'] = data['BOLL_MID'] - std_dev * data['BOLL_STD']
        return data


class TechSignalDetector:
    """技术信号检测器"""
    
    @staticmethod
    def detect_macd_signals(data: pd.DataFrame) -> List[TechSignal]:
        """检测MACD金叉死叉"""
        signals = []
        code = data.index[-1] if len(data) > 0 else 'unknown'
        
        if len(data) < 2:
            return signals
        
        # 检查金叉（MACD上穿Signal）
        if data['MACD'].iloc[-2] < data['MACD_Signal'].iloc[-2] and \
           data['MACD'].iloc[-1] > data['MACD_Signal'].iloc[-1]:
            signals.append(TechSignal(
                code=code,
                name='',
                indicator='MACD',
                signal_type='金叉',
                strength='强' if data['MACD'].iloc[-1] < 0 else '中',
                current_value=data['MACD'].iloc[-1],
                description=f"MACD金叉，数值{data['MACD'].iloc[-1]:.3f}",
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        
        # 检查死叉（MACD下穿Signal）
        elif data['MACD'].iloc[-2] > data['MACD_Signal'].iloc[-2] and \
             data['MACD'].iloc[-1] < data['MACD_Signal'].iloc[-1]:
            signals.append(TechSignal(
                code=code,
                name='',
                indicator='MACD',
                signal_type='死叉',
                strength='强' if data['MACD'].iloc[-1] > 0 else '中',
                current_value=data['MACD'].iloc[-1],
                description=f"MACD死叉，数值{data['MACD'].iloc[-1]:.3f}",
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        
        return signals
    
    @staticmethod
    def detect_kdj_signals(data: pd.DataFrame) -> List[TechSignal]:
        """检测KDJ金叉死叉"""
        signals = []
        code = data.index[-1] if len(data) > 0 else 'unknown'
        
        if len(data) < 2:
            return signals
        
        k_current, d_current = data['K'].iloc[-1], data['D'].iloc[-1]
        k_prev, d_prev = data['K'].iloc[-2], data['D'].iloc[-2]
        
        # KDJ金叉（K上穿D）
        if k_prev < d_prev and k_current > d_current:
            if k_current < 20:  # 超卖区金叉
                strength = '强'
                desc = f"KDJ超卖区金叉，K={k_current:.1f}"
            else:
                strength = '中'
                desc = f"KDJ金叉，K={k_current:.1f}"
            
            signals.append(TechSignal(
                code=code, name='', indicator='KDJ',
                signal_type='金叉', strength=strength,
                current_value=k_current, description=desc,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        
        # KDJ死叉（K下穿D）
        elif k_prev > d_prev and k_current < d_current:
            if k_current > 80:  # 超买区死叉
                strength = '强'
                desc = f"KDJ超买区死叉，K={k_current:.1f}"
            else:
                strength = '中'
                desc = f"KDJ死叉，K={k_current:.1f}"
            
            signals.append(TechSignal(
                code=code, name='', indicator='KDJ',
                signal_type='死叉', strength=strength,
                current_value=k_current, description=desc,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        
        return signals
    
    @staticmethod
    def detect_ma_signals(data: pd.DataFrame) -> List[TechSignal]:
        """检测均线信号"""
        signals = []
        code = data.index[-1] if len(data) > 0 else 'unknown'
        
        if len(data) < 2:
            return signals
        
        close = data['close'].iloc[-1]
        close_prev = data['close'].iloc[-2]
        
        # 突破5日线
        ma5 = data['MA5'].iloc[-1]
        ma5_prev = data['MA5'].iloc[-2]
        
        if close_prev < ma5_prev and close > ma5:
            signals.append(TechSignal(
                code=code, name='', indicator='MA5',
                signal_type='突破', strength='中',
                current_value=close,
                description=f"突破5日线 ¥{ma5:.2f}",
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        elif close_prev > ma5_prev and close < ma5:
            signals.append(TechSignal(
                code=code, name='', indicator='MA5',
                signal_type='跌破', strength='中',
                current_value=close,
                description=f"跌破5日线 ¥{ma5:.2f}",
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        
        return signals


class TechMonitor:
    """技术指标监控器"""
    
    def __init__(self):
        self.calculator = TechIndicatorCalculator()
        self.detector = TechSignalDetector()
    
    def fetch_stock_data(self, code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """获取股票历史数据"""
        try:
            # 使用akshare获取日线数据
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=None, end_date=None, adjust="qfq")
            if df is None or len(df) == 0:
                return None
            
            # 只取最近days天
            df = df.tail(days).copy()
            
            # 标准化列名
            df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'amplitude', 'pct_change', 'change_amount', 'turnover']
            
            return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
            return None
    
    def analyze_stock(self, code: str, name: str = '') -> Dict:
        """分析单个股票"""
        df = self.fetch_stock_data(code)
        if df is None:
            return {'error': '获取数据失败'}
        
        # 计算指标
        df = self.calculator.calculate_ma(df)
        df = self.calculator.calculate_macd(df)
        df = self.calculator.calculate_kdj(df)
        df = self.calculator.calculate_rsi(df)
        
        # 检测信号
        signals = []
        signals.extend(self.detector.detect_macd_signals(df))
        signals.extend(self.detector.detect_kdj_signals(df))
        signals.extend(self.detector.detect_ma_signals(df))
        
        # 设置名称
        for s in signals:
            s.name = name
        
        # 获取当前指标值
        latest = df.iloc[-1]
        
        return {
            'code': code,
            'name': name,
            'current_price': latest['close'],
            'price_change': latest['pct_change'],
            'indicators': {
                'MA5': latest.get('MA5', 0),
                'MA10': latest.get('MA10', 0),
                'MA20': latest.get('MA20', 0),
                'MACD': latest.get('MACD', 0),
                'K': latest.get('K', 0),
                'D': latest.get('D', 0),
                'RSI': latest.get('RSI', 0)
            },
            'signals': signals,
            'trend': self._judge_trend(df)
        }
    
    def _judge_trend(self, df: pd.DataFrame) -> str:
        """判断趋势"""
        if len(df) < 20:
            return "数据不足"
        
        latest = df.iloc[-1]
        
        # 多头排列判断
        ma5 = latest.get('MA5', 0)
        ma10 = latest.get('MA10', 0)
        ma20 = latest.get('MA20', 0)
        
        if ma5 > ma10 > ma20:
            return "多头排列"
        elif ma5 < ma10 < ma20:
            return "空头排列"
        else:
            return "震荡整理"
    
    def scan_watchlist(self, watchlist: List[Dict]) -> List[TechSignal]:
        """扫描自选股列表"""
        all_signals = []
        
        print(f"\n📊 开始技术指标分析 ({len(watchlist)}只股票)...")
        print("-" * 60)
        
        for item in watchlist:
            code = item.get('code')
            name = item.get('name', code)
            
            if not code:
                continue
            
            try:
                result = self.analyze_stock(code, name)
                if 'error' not in result and result['signals']:
                    all_signals.extend(result['signals'])
                    for sig in result['signals']:
                        print(f"📈 [{name}] {sig.indicator}{sig.signal_type} - {sig.description}")
            except Exception as e:
                print(f"分析{name}失败: {e}")
        
        return all_signals
    
    def format_signal_report(self, signals: List[TechSignal]) -> str:
        """格式化信号报告"""
        if not signals:
            return "📊 技术指标监控：无显著信号"
        
        report = []
        report.append("\n" + "=" * 70)
        report.append("📈 技术指标信号监控")
        report.append("=" * 70)
        report.append(f"发现 {len(signals)} 个技术信号\n")
        
        # 按强度分组
        strong_signals = [s for s in signals if s.strength == '强']
        medium_signals = [s for s in signals if s.strength == '中']
        
        if strong_signals:
            report.append("\n【🔥 强信号】")
            for sig in strong_signals:
                report.append(f"\n{sig.code} {sig.name}")
                report.append(f"   {sig.indicator} {sig.signal_type} - {sig.description}")
                report.append(f"   时间: {sig.timestamp}")
        
        if medium_signals:
            report.append("\n\n【📊 中等信号】")
            for sig in medium_signals:
                report.append(f"\n{sig.code} {sig.name}")
                report.append(f"   {sig.indicator} {sig.signal_type} - {sig.description}")
        
        report.append("\n" + "=" * 70)
        
        return '\n'.join(report)


def main():
    """测试"""
    monitor = TechMonitor()
    
    # 测试单只股票
    result = monitor.analyze_stock('603127', '昭衍新药')
    print(f"\n昭衍新药技术分析:")
    print(f"当前价格: {result['current_price']}")
    print(f"趋势: {result['trend']}")
    print(f"MACD: {result['indicators']['MACD']:.3f}")
    print(f"KDJ K值: {result['indicators']['K']:.1f}")
    
    if result['signals']:
        print(f"\n技术信号:")
        for sig in result['signals']:
            print(f"  - {sig.indicator}{sig.signal_type}: {sig.description}")


if __name__ == '__main__':
    main()
