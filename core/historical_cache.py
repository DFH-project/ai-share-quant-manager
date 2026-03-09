#!/usr/bin/env python3
"""
历史数据缓存模块 - HistoricalDataCache
负责：
1. K线数据缓存（日K、周K）
2. 技术指标缓存（均线、MACD等）
3. 基本面数据缓存（PE/PB/ROE等）
4. 板块历史数据缓存

更新策略：
- 收盘后自动更新（15:30）
- 盘中使用缓存数据
- 拒绝过时数据
"""

import requests
import json
import pickle
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import threading

class HistoricalDataCache:
    """历史数据缓存管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 缓存目录
        self.cache_dir = Path(__file__).parent.parent / 'data' / 'historical_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._memory_cache = {}
        self._cache_lock = threading.Lock()
    
    def _get_cache_file(self, data_type: str, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{data_type}_{key}.pkl"
    
    def _is_cache_valid(self, cache_file: Path, max_age_hours: int = 24) -> bool:
        """检查缓存是否有效（默认24小时）"""
        if not cache_file.exists():
            return False
        
        # 检查修改时间
        mtime = cache_file.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        
        if age_hours > max_age_hours:
            print(f"  [缓存] {cache_file.stem}: 过期 ({age_hours:.1f}小时前)")
            return False
        
        return True
    
    def _load_cache(self, data_type: str, key: str) -> Optional[Dict]:
        """加载缓存"""
        # 先检查内存
        mem_key = f"{data_type}_{key}"
        with self._cache_lock:
            if mem_key in self._memory_cache:
                return self._memory_cache[mem_key]
        
        # 再检查文件
        cache_file = self._get_cache_file(data_type, key)
        if not self._is_cache_valid(cache_file):
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            # 更新内存缓存
            with self._cache_lock:
                self._memory_cache[mem_key] = data
            
            return data
        except Exception as e:
            return None
    
    def _save_cache(self, data_type: str, key: str, data: Dict):
        """保存缓存"""
        mem_key = f"{data_type}_{key}"
        
        # 更新内存
        with self._cache_lock:
            self._memory_cache[mem_key] = data
        
        # 更新文件
        cache_file = self._get_cache_file(data_type, key)
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            pass
    
    # ==================== K线数据 ====================
    
    def get_kline_data(self, code: str, period: str = 'day', count: int = 60) -> Optional[List[Dict]]:
        """
        获取K线数据（日K或周K）
        
        Args:
            code: 股票代码
            period: day/week
            count: 获取多少根K线
        
        Returns:
            List[Dict]: K线数据列表
        """
        cache_key = f"{code}_{period}_{count}"
        
        # 检查缓存
        cached = self._load_cache('kline', cache_key)
        if cached:
            return cached.get('data')
        
        # 获取实时数据
        kline_data = self._fetch_kline_eastmoney(code, period, count)
        
        if kline_data:
            # 缓存数据
            self._save_cache('kline', cache_key, {
                'code': code,
                'period': period,
                'count': count,
                'data': kline_data,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
        
        return kline_data
    
    def _fetch_kline_eastmoney(self, code: str, period: str, count: int) -> Optional[List[Dict]]:
        """从东财获取K线数据"""
        try:
            # 转换代码
            if code.startswith('6'):
                secid = f"1.{code}"
            else:
                secid = f"0.{code}"
            
            # 日K或周K
            kltype = 101 if period == 'day' else 102
            
            url = f"https://push2.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt={kltype}&fqt=0&end=20500101&lmt={count}"
            
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            if 'data' in data and 'klines' in data['data']:
                klines = []
                for line in data['data']['klines']:
                    parts = line.split(',')
                    if len(parts) >= 6:
                        klines.append({
                            'date': parts[0],
                            'open': float(parts[1]),
                            'close': float(parts[2]),
                            'high': float(parts[3]),
                            'low': float(parts[4]),
                            'volume': float(parts[5]),
                            'amount': float(parts[6]) if len(parts) > 6 else 0,
                        })
                return klines
        except Exception as e:
            print(f"[K线] {code} 获取失败: {e}")
        
        return None
    
    # ==================== 技术指标计算 ====================
    
    def calculate_ma(self, code: str, days: List[int] = [5, 10, 20, 30, 60]) -> Dict[int, float]:
        """
        计算移动平均线
        
        Args:
            code: 股票代码
            days: 均线周期列表
        
        Returns:
            Dict[int, float]: {5: MA5, 10: MA10, ...}
        """
        # 获取K线数据
        klines = self.get_kline_data(code, 'day', max(days) + 5)
        
        if not klines or len(klines) < max(days):
            return {d: 0 for d in days}
        
        mas = {}
        for day in days:
            if len(klines) >= day:
                closes = [k['close'] for k in klines[-day:]]
                mas[day] = sum(closes) / len(closes)
            else:
                mas[day] = 0
        
        return mas
    
    def get_high_low_n_days(self, code: str, n: int = 20) -> Tuple[float, float]:
        """
        获取N日高低点
        
        Returns:
            (high, low)
        """
        klines = self.get_kline_data(code, 'day', n)
        
        if not klines:
            return (0, 0)
        
        highs = [k['high'] for k in klines]
        lows = [k['low'] for k in klines]
        
        return (max(highs), min(lows))
    
    # ==================== 基本面数据 ====================
    
    def get_fundamental_data(self, code: str) -> Optional[Dict]:
        """
        获取基本面数据（PE/PB/ROE等）
        """
        # 检查缓存
        cached = self._load_cache('fundamental', code)
        if cached:
            return cached.get('data')
        
        # 获取实时数据
        fundamental = self._fetch_fundamental_eastmoney(code)
        
        if fundamental:
            self._save_cache('fundamental', code, {
                'code': code,
                'data': fundamental,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
        
        return fundamental
    
    def _fetch_fundamental_eastmoney(self, code: str) -> Optional[Dict]:
        """从东财获取基本面数据"""
        try:
            if code.startswith('6'):
                secid = f"1.{code}"
            else:
                secid = f"0.{code}"
            
            url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100"
            
            response = self.session.get(url, timeout=8)
            data = response.json()
            
            if 'data' in data:
                d = data['data']
                return {
                    'code': code,
                    'name': d.get('f58', ''),
                    'pe': d.get('f57', 0),  # 市盈率
                    'pb': d.get('f59', 0),  # 市净率
                    'roe': d.get('f60', 0),  # ROE
                    'eps': d.get('f61', 0),  # 每股收益
                    'bps': d.get('f62', 0),  # 每股净资产
                    'total_shares': d.get('f63', 0),  # 总股本
                    'float_shares': d.get('f64', 0),  # 流通股本
                    'market_cap': d.get('f65', 0),  # 总市值
                    'float_cap': d.get('f66', 0),  # 流通市值
                    'industry': d.get('f100', ''),  # 所属行业
                }
        except Exception as e:
            print(f"[基本面] {code} 获取失败: {e}")
        
        return None
    
    # ==================== 板块历史数据 ====================
    
    def get_sector_history(self, sector_name: str) -> Optional[Dict]:
        """
        获取板块历史表现数据
        """
        cache_key = sector_name
        cached = self._load_cache('sector', cache_key)
        if cached:
            return cached.get('data')
        
        # TODO: 实现板块历史数据获取
        return None
    
    # ==================== 批量更新（收盘后调用） ====================
    
    def batch_update_all(self, codes: List[str]):
        """
        收盘后批量更新所有缓存
        """
        print(f"\n[{'='*70}]")
        print(f"📊 收盘后批量更新缓存 - {datetime.now().strftime('%H:%M')}")
        print(f"[{'='*70}]\n")
        
        total = len(codes)
        updated = 0
        failed = 0
        
        for i, code in enumerate(codes, 1):
            try:
                # 更新K线
                kline = self._fetch_kline_eastmoney(code, 'day', 60)
                if kline:
                    self._save_cache('kline', f"{code}_day_60", {
                        'code': code,
                        'period': 'day',
                        'count': 60,
                        'data': kline,
                        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                
                # 更新基本面
                fundamental = self._fetch_fundamental_eastmoney(code)
                if fundamental:
                    self._save_cache('fundamental', code, {
                        'code': code,
                        'data': fundamental,
                        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                
                updated += 1
                if i % 10 == 0:
                    print(f"  进度: {i}/{total} ({updated}成功 {failed}失败)")
                
                # 适当延时，避免请求过快
                time.sleep(0.1)
                
            except Exception as e:
                failed += 1
                continue
        
        print(f"\n✅ 更新完成: {updated}只成功, {failed}只失败")
        print(f"[{'='*70}]\n")
    
    def clear_all_cache(self):
        """清空所有缓存（谨慎使用）"""
        with self._cache_lock:
            self._memory_cache.clear()
        
        for f in self.cache_dir.glob("*.pkl"):
            try:
                f.unlink()
            except:
                pass
        
        print("✅ 所有缓存已清空")


# 全局实例
historical_cache = HistoricalDataCache()
