#!/usr/bin/env python3
"""
统一数据管理模块 - DataManager V3 (集成历史缓存)
核心设计：
1. 单例模式，全局数据只获取一次
2. 多级缓存（内存+文件+历史数据）
3. 并行数据获取（5只并发）
4. 智能数据源切换
5. 数据复用，禁止重复API调用
6. 历史K线、均线、基本面缓存集成
"""

import requests
import json
import time
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 导入历史缓存
from core.historical_cache import historical_cache

class DataManager:
    """统一数据管理器 - 全局单例"""
    
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
        self.cache_dir = Path(__file__).parent.parent / 'data' / 'cache_v3'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存（提高速度）
        self._memory_cache = {}
        self._cache_lock = threading.Lock()
        
        # 缓存有效期配置
        self.cache_ttl = {
            'price': 60,        # 价格1分钟
            'indicator': 300,   # 技术指标5分钟
            'fundamental': 1800, # 基本面30分钟
            'kline': 3600,      # K线1小时
        }
        
        # 数据源配置（优先级顺序）
        self.data_sources = [
            ('tencent', self._fetch_tencent),
            ('eastmoney', self._fetch_eastmoney),
            ('sina', self._fetch_sina),
            ('akshare', self._fetch_akshare),
        ]
    
    # ==================== 缓存管理 ====================
    
    def _get_cache_key(self, data_type: str, code: str) -> str:
        """生成缓存key"""
        return f"{data_type}_{code}"
    
    def _get_memory_cache(self, key: str) -> Optional[Dict]:
        """获取内存缓存"""
        with self._cache_lock:
            if key in self._memory_cache:
                cached_time, data = self._memory_cache[key]
                # 检查是否过期（默认5分钟）
                if time.time() - cached_time < 300:
                    return data
                else:
                    del self._memory_cache[key]
        return None
    
    def _set_memory_cache(self, key: str, data: Dict):
        """设置内存缓存"""
        with self._cache_lock:
            self._memory_cache[key] = (time.time(), data)
    
    def _get_file_cache(self, data_type: str, code: str) -> Optional[Dict]:
        """获取文件缓存"""
        try:
            cache_file = self.cache_dir / f"{data_type}_{code}.pkl"
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'rb') as f:
                cached = pickle.load(f)
            
            # 检查过期
            ttl = self.cache_ttl.get(data_type, 300)
            if time.time() - cached['timestamp'] < ttl:
                # 同时更新内存缓存
                self._set_memory_cache(self._get_cache_key(data_type, code), cached['data'])
                return cached['data']
        except Exception as e:
            pass
        return None
    
    def _set_file_cache(self, data_type: str, code: str, data: Dict):
        """设置文件缓存"""
        try:
            cache_file = self.cache_dir / f"{data_type}_{code}.pkl"
            with open(cache_file, 'wb') as f:
                pickle.dump({
                    'timestamp': time.time(),
                    'data': data
                }, f)
        except Exception as e:
            pass
    
    # ==================== 数据源获取 ====================
    
    def _fetch_tencent(self, codes: List[str]) -> Dict[str, Dict]:
        """腾讯数据源"""
        result = {}
        try:
            # 批量请求（腾讯支持多股票）
            code_str = ','.join([f"sh{c}" if c.startswith('6') else f"sz{c}" for c in codes])
            url = f"https://qt.gtimg.cn/q={code_str}"
            
            response = self.session.get(url, timeout=5)
            response.encoding = 'gbk'
            
            for line in response.text.split(';'):
                if 'v_' not in line or '~' not in line:
                    continue
                
                # 解析股票代码
                code_start = line.find('v_') + 2
                code_end = line.find('=')
                if code_start < 0 or code_end < 0:
                    continue
                
                tencent_code = line[code_start:code_end]
                code = tencent_code[2:]  # 去掉sh/sz前缀
                
                # 解析数据
                data_start = line.find('="') + 2
                data_end = line.rfind('"')
                if data_start < 2 or data_end < 0:
                    continue
                
                parts = line[data_start:data_end].split('~')
                if len(parts) < 45:
                    continue
                
                try:
                    # 腾讯数据字段索引（根据实际格式调整）
                    # ~分隔，关键字段：
                    # [1]=名称, [2]=代码, [3]=当前价, [4]=昨收, [5]=今开
                    # [6]=成交量, [7]=外盘, [8]=内盘, [9]=买一价, [10]=买一量
                    # [33]=最高价, [34]=最低价, [36]=成交额, [38]=换手率
                    # [44]=总市值, [45]=流通市值, [46]=市净率, [52]=市盈率
                    
                    current = float(parts[3]) if parts[3] else 0
                    prev_close = float(parts[4]) if parts[4] else 0
                    
                    # 价格有效性检查
                    if current <= 0 or current > 10000 or prev_close <= 0:
                        continue
                    
                    result[code] = {
                        'code': code,
                        'name': parts[1] if len(parts) > 1 else code,
                        'current': current,
                        'prev_close': prev_close,
                        'open': float(parts[5]) if len(parts) > 5 and parts[5] else prev_close,
                        'high': float(parts[33]) if len(parts) > 33 and parts[33] else current,
                        'low': float(parts[34]) if len(parts) > 34 and parts[34] else current,
                        'volume': float(parts[6]) if len(parts) > 6 and parts[6] else 0,
                        'change_pct': ((current - prev_close) / prev_close * 100) if prev_close > 0 else 0,
                        'volume_ratio': float(parts[49]) if len(parts) > 49 and parts[49] else 1.0,
                        'pe': float(parts[52]) if len(parts) > 52 and parts[52] else 0,
                        'pb': float(parts[46]) if len(parts) > 46 and parts[46] else 0,
                        'market_cap': float(parts[44]) if len(parts) > 44 and parts[44] else 0,
                        'turnover': float(parts[38]) if len(parts) > 38 and parts[38] else 0,
                        'data_source': 'tencent',
                    }
                except Exception as e:
                    continue
        except Exception as e:
            print(f"[腾讯] 获取失败: {e}")
        
        return result
    
    def _fetch_eastmoney(self, codes: List[str]) -> Dict[str, Dict]:
        """东方财富数据源 - 提供技术指标"""
        result = {}
        try:
            secids = []
            for code in codes:
                if code.startswith('6'):
                    secids.append(f"1.{code}")
                else:
                    secids.append(f"0.{code}")
            
            code_str = ','.join(secids)
            fields = "f12,f14,f2,f3,f4,f5,f6,f7,f10,f17,f18,f20,f21,f22,f23,f24,f25,f26,f33,f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100"
            
            url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields={fields}&secids={code_str}"
            
            response = self.session.get(url, timeout=8)
            data = response.json()
            
            if 'data' in data and 'diff' in data['data']:
                for item in data['data']['diff']:
                    code = item.get('f12')
                    if not code:
                        continue
                    
                    # 价格需要除以100
                    current = item.get('f2', 0)
                    if current:
                        current = current / 100
                    
                    ma30 = item.get('f20', 0)
                    ma60 = item.get('f21', 0)
                    if ma30: ma30 = ma30 / 100
                    if ma60: ma60 = ma60 / 100
                    
                    result[code] = {
                        'code': code,
                        'name': item.get('f14', ''),
                        'current': current,
                        'change_pct': item.get('f3', 0),
                        'open': item.get('f17', 0) / 100 if item.get('f17') else 0,
                        'high': item.get('f15', 0) / 100 if item.get('f15') else 0,
                        'low': item.get('f16', 0) / 100 if item.get('f16') else 0,
                        'prev_close': item.get('f18', 0) / 100 if item.get('f18') else 0,
                        'volume_ratio': item.get('f10', 0),
                        'ma30': ma30,
                        'ma60': ma60,
                        'ma120': item.get('f23', 0) / 100 if item.get('f23') else 0,
                        'high_20d': item.get('f44', 0) / 100 if item.get('f44') else 0,
                        'low_20d': item.get('f45', 0) / 100 if item.get('f45') else 0,
                        'pe': item.get('f33', 0),
                        'pb': item.get('f34', 0),
                        'data_source': 'eastmoney',
                    }
        except Exception as e:
            print(f"[东财] 获取失败: {e}")
        
        return result
    
    def _fetch_sina(self, codes: List[str]) -> Dict[str, Dict]:
        """新浪数据源"""
        result = {}
        try:
            code_str = ','.join([f"sh{c}" if c.startswith('6') else f"sz{c}" for c in codes])
            url = f"https://hq.sinajs.cn/list={code_str}"
            
            response = self.session.get(url, timeout=5)
            response.encoding = 'gbk'
            
            for line in response.text.strip().split('\n'):
                if 'var hq_str_' not in line:
                    continue
                
                code = line.split('_')[2].split('=')[0]
                data_str = line.split('="')[1].rstrip('";')
                parts = data_str.split(',')
                
                if len(parts) >= 33:
                    try:
                        result[code] = {
                            'code': code,
                            'name': parts[0],
                            'current': float(parts[3]),
                            'prev_close': float(parts[2]),
                            'open': float(parts[1]),
                            'high': float(parts[4]),
                            'low': float(parts[5]),
                            'volume': float(parts[8]),
                            'change_pct': (float(parts[3]) - float(parts[2])) / float(parts[2]) * 100 if float(parts[2]) > 0 else 0,
                            'data_source': 'sina',
                        }
                    except:
                        continue
        except Exception as e:
            print(f"[新浪] 获取失败: {e}")
        
        return result
    
    def _fetch_akshare(self, codes: List[str]) -> Dict[str, Dict]:
        """AKShare数据源"""
        result = {}
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            
            for code in codes:
                row = df[df['代码'] == code]
                if not row.empty:
                    result[code] = {
                        'code': code,
                        'name': row['名称'].values[0],
                        'current': float(row['最新价'].values[0]),
                        'change_pct': float(row['涨跌幅'].values[0]),
                        'volume_ratio': float(row['量比'].values[0]) if '量比' in row else 1.0,
                        'data_source': 'akshare',
                    }
        except Exception as e:
            print(f"[AKShare] 获取失败: {e}")
        
        return result
    
    # ==================== 核心API ====================
    
    def fetch_stock_data(self, codes: List[str]) -> Dict[str, Dict]:
        """
        获取股票完整数据（实时+历史技术指标）
        
        策略：
        1. 获取实时价格数据
        2. 从历史缓存获取K线、均线
        3. 从历史缓存获取基本面
        4. 合并所有数据
        """
        if not codes:
            return {}
        
        result = {}
        
        for code in codes:
            # 1. 实时数据
            real_time = self._get_real_time_data(code)
            
            # 2. 历史技术指标
            ma_data = historical_cache.calculate_ma(code, [5, 10, 20, 30, 60])
            high_20d, low_20d = historical_cache.get_high_low_n_days(code, 20)
            
            # 3. 基本面数据
            fundamental = historical_cache.get_fundamental_data(code)
            
            # 4. 合并数据
            if real_time:
                merged = real_time.copy()
                
                # 添加技术指标
                merged['ma5'] = ma_data.get(5, 0)
                merged['ma10'] = ma_data.get(10, 0)
                merged['ma20'] = ma_data.get(20, 0)
                merged['ma30'] = ma_data.get(30, 0)
                merged['ma60'] = ma_data.get(60, 0)
                merged['high_20d'] = high_20d
                merged['low_20d'] = low_20d
                
                # 添加基本面
                if fundamental:
                    merged['pe'] = fundamental.get('pe', 0)
                    merged['pb'] = fundamental.get('pb', 0)
                    merged['roe'] = fundamental.get('roe', 0)
                    merged['industry'] = fundamental.get('industry', '')
                
                result[code] = merged
        
        return result
    
    def _get_real_time_data(self, code: str) -> Optional[Dict]:
        """获取实时数据（带缓存）"""
        # 检查内存缓存
        cache_key = self._get_cache_key('price', code)
        cached = self._get_memory_cache(cache_key)
        if cached:
            return cached
        
        # 并行获取多源数据
        merged = {}
        for source_name, fetch_func in self.data_sources:
            try:
                data = fetch_func([code])
                if data and code in data:
                    for key, value in data[code].items():
                        if value not in [0, None, ''] or key not in merged:
                            merged[key] = value
            except:
                continue
        
        if merged:
            self._set_memory_cache(cache_key, merged)
            self._set_file_cache('price', code, merged)
        
        return merged if merged else None
    
    def get_index_data(self) -> Dict:
        """获取指数数据"""
        cache_key = 'index_main'
        
        # 检查缓存
        cached = self._get_memory_cache(cache_key)
        if cached:
            return cached
        
        try:
            url = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2,f3&secids=1.000001,0.399001,0.399006,1.000688"
            response = self.session.get(url, timeout=5)
            data = response.json()
            
            result = {}
            if 'data' in data and 'diff' in data['data']:
                index_names = {'000001': '上证指数', '399001': '深证成指', 
                              '399006': '创业板指', '000688': '科创50'}
                
                for item in data['data']['diff']:
                    code = item.get('f12')
                    if code in index_names:
                        current = item.get('f2', 0)
                        if current:
                            current = current / 100
                        
                        result[index_names[code]] = {
                            'code': code,
                            'name': index_names[code],
                            'current': current,
                            'change_pct': item.get('f3', 0),
                        }
            
            # 缓存
            self._set_memory_cache(cache_key, result)
            return result
            
        except Exception as e:
            # 失败返回空
            return {}
    
    def clear_cache(self):
        """清空所有缓存"""
        with self._cache_lock:
            self._memory_cache.clear()
        
        # 清空文件缓存
        for f in self.cache_dir.glob("*.pkl"):
            try:
                f.unlink()
            except:
                pass


# 全局数据管理器实例
data_manager = DataManager()

# 兼容旧接口
def data_fetcher():
    return data_manager
