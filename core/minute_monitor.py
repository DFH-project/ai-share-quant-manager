#!/usr/bin/env python3
"""
minute_monitor.py - 分钟级监控系统
支持30分钟级别的自选股票监控
内存缓存优先，减少API调用
与现有系统完全联动
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from core.data_fetcher import data_fetcher
from core.memory_cache_manager import get_price_cache, CachedDataFetcher
from core.smart_alert_system import SmartAlertSystem
from core.config_manager import get_config


@dataclass
class MinuteBar:
    """分钟K线数据"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MinuteMonitor:
    """分钟级监控器 - 30分钟级别"""
    
    def __init__(self, interval_minutes: int = 30):
        """
        Args:
            interval_minutes: 监控间隔，默认30分钟
        """
        self.interval = interval_minutes
        self.cache = get_price_cache()
        self.cached_fetcher = CachedDataFetcher()
        self.alert_system = SmartAlertSystem()
        self.config = get_config()
        
        # 分钟数据存储
        self.minute_bars: Dict[str, List[MinuteBar]] = {}
        self._lock = threading.RLock()
        
        # 回调函数
        self.callbacks: List[Callable] = []
        
        # 运行状态
        self._running = False
        self._monitor_thread = None
    
    def start_monitoring(self, codes: List[str]):
        """
        开始监控
        
        Args:
            codes: 监控的股票代码列表
        """
        if self._running:
            print("⚠️ 监控已在运行中")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(codes,),
            daemon=True
        )
        self._monitor_thread.start()
        
        print(f"✅ 分钟级监控已启动 - 间隔{self.interval}分钟")
        print(f"📊 监控股票: {', '.join(codes[:5])}{'...' if len(codes) > 5 else ''}")
    
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        print("✅ 分钟级监控已停止")
    
    def _monitor_loop(self, codes: List[str]):
        """监控主循环"""
        while self._running:
            try:
                # 执行监控
                self._check_minute_data(codes)
                
                # 等待下一次监控
                time.sleep(self.interval * 60)
                
            except Exception as e:
                print(f"❌ 监控错误: {e}")
                time.sleep(60)  # 出错后1分钟重试
    
    def _check_minute_data(self, codes: List[str]):
        """检查分钟数据"""
        timestamp = datetime.now()
        print(f"\n{'='*60}")
        print(f"📊 分钟级监控 - {timestamp.strftime('%H:%M')}")
        print(f"{'='*60}")
        
        # 使用缓存获取数据
        stock_data = self.cached_fetcher.get_stock_data(codes)
        
        alerts = []
        for code in codes:
            if code not in stock_data:
                continue
            
            data = stock_data[code]
            current_price = data.get('current', 0)
            
            # 更新分钟数据
            self._update_minute_bar(code, data, timestamp)
            
            # 检查30分钟变化
            change_30m = self._get_30min_change(code)
            
            if abs(change_30m) >= 0.02:  # 30分钟变化2%
                alert = {
                    'code': code,
                    'name': data.get('name', code),
                    'change_30m': change_30m,
                    'current_price': current_price,
                    'timestamp': timestamp
                }
                alerts.append(alert)
                
                emoji = "📈" if change_30m > 0 else "📉"
                print(f"{emoji} {alert['name']}({code}) 30分钟{change_30m*100:+.2f}%")
        
        # 执行智能预警检查
        print(f"\n🚨 智能预警检查...")
        alert_events = self.alert_system.check_alerts(codes)
        
        if alert_events:
            print(f"⚠️ 触发 {len(alert_events)} 个预警:")
            for event in alert_events:
                print(f"  {event.level}: {event.message}")
                alerts.append({
                    'type': 'alert',
                    'event': event
                })
        else:
            print("✅ 无预警触发")
        
        # 执行回调
        if alerts:
            for callback in self.callbacks:
                try:
                    callback(alerts)
                except:
                    pass
        
        # 显示缓存统计
        stats = self.cache.get_stats()
        print(f"\n💾 缓存统计: {stats}")
    
    def _update_minute_bar(self, code: str, data: Dict, timestamp: datetime):
        """更新分钟K线数据"""
        with self._lock:
            if code not in self.minute_bars:
                self.minute_bars[code] = []
            
            bar = MinuteBar(
                timestamp=timestamp,
                open=data.get('open', data.get('current', 0)),
                high=data.get('high', data.get('current', 0)),
                low=data.get('low', data.get('current', 0)),
                close=data.get('current', 0),
                volume=data.get('volume', 0)
            )
            
            self.minute_bars[code].append(bar)
            
            # 只保留最近4小时的数据
            cutoff = timestamp - timedelta(hours=4)
            self.minute_bars[code] = [
                b for b in self.minute_bars[code]
                if b.timestamp > cutoff
            ]
    
    def _get_30min_change(self, code: str) -> float:
        """获取30分钟涨跌幅"""
        with self._lock:
            if code not in self.minute_bars or len(self.minute_bars[code]) < 2:
                return 0
            
            bars = self.minute_bars[code]
            
            # 找到30分钟前的数据
            cutoff = datetime.now() - timedelta(minutes=30)
            past_bars = [b for b in bars if b.timestamp <= cutoff]
            
            if not past_bars:
                return 0
            
            past_price = past_bars[-1].close
            current_price = bars[-1].close
            
            return (current_price - past_price) / past_price if past_price > 0 else 0
    
    def get_minute_trend(self, code: str, minutes: int = 30) -> Dict:
        """获取分钟级趋势"""
        with self._lock:
            if code not in self.minute_bars:
                return {'error': '无数据'}
            
            bars = self.minute_bars[code]
            if len(bars) < 2:
                return {'error': '数据不足'}
            
            cutoff = datetime.now() - timedelta(minutes=minutes)
            recent_bars = [b for b in bars if b.timestamp >= cutoff]
            
            if not recent_bars:
                return {'error': '无近期数据'}
            
            opens = [b.open for b in recent_bars]
            highs = [b.high for b in recent_bars]
            lows = [b.low for b in recent_bars]
            closes = [b.close for b in recent_bars]
            volumes = [b.volume for b in recent_bars]
            
            return {
                'period': minutes,
                'bars_count': len(recent_bars),
                'open': opens[0],
                'high': max(highs),
                'low': min(lows),
                'close': closes[-1],
                'change': (closes[-1] - opens[0]) / opens[0] if opens[0] > 0 else 0,
                'total_volume': sum(volumes),
                'avg_price': sum(closes) / len(closes) if closes else 0
            }
    
    def register_callback(self, callback: Callable):
        """注册监控回调"""
        self.callbacks.append(callback)


def run_minute_monitor(codes: List[str], interval: int = 30):
    """
    便捷函数：运行分钟级监控
    
    Args:
        codes: 股票代码列表
        interval: 监控间隔(分钟)
    """
    monitor = MinuteMonitor(interval_minutes=interval)
    
    # 注册回调 - 打印预警
    def on_alert(alerts):
        print(f"\n🔔 收到 {len(alerts)} 个信号")
    
    monitor.register_callback(on_alert)
    
    # 启动监控
    monitor.start_monitoring(codes)
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️ 停止监控...")
        monitor.stop_monitoring()


if __name__ == '__main__':
    # 测试
    print("🧪 测试分钟级监控...")
    
    # 测试30分钟监控
    test_codes = ['300750', '002594']
    
    monitor = MinuteMonitor(interval_minutes=1)  # 1分钟间隔测试
    monitor.start_monitoring(test_codes)
    
    # 运行5分钟
    time.sleep(300)
    
    monitor.stop_monitoring()
    print("✅ 测试完成")
