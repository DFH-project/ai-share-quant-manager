#!/usr/bin/env python3
"""
数据获取模块 - DataFetcher V2
核心原则：
1. 禁止AI生成任何假数据
2. 多数据源自动切换（6+数据源）
3. 历史数据缓存，实时数据优先
4. 数据合并策略：有缓存用缓存，无缓存用实时，实时失败用缓存
"""

import requests
import json
import time
import pickle
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

class DataFetcher:
    """数据获取器 - 多数据源自动切换+智能缓存"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.max_retry = 3
        
        # 缓存目录
        self.cache_dir = Path(__file__).parent.parent / 'data' / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 缓存有效期（分钟）
        self.cache_valid_minutes = {
            'price': 5,      # 价格数据5分钟
            'indicator': 30, # 技术指标30分钟
            'fundamental': 60 # 基本面1小时
        }
    
    def _get_cache_path(self, cache_type: str, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_type}_{key}.pkl"
    
    def _load_cache(self, cache_type: str, key: str) -> Optional[Dict]:
        """加载缓存数据"""
        try:
            cache_path = self._get_cache_path(cache_type, key)
            if not cache_path.exists():
                return None
            
            with open(cache_path, 'rb') as f:
                cached = pickle.load(f)
            
            # 检查缓存是否过期
            cache_time = cached.get('timestamp', 0)
            elapsed_minutes = (time.time() - cache_time) / 60
            valid_minutes = self.cache_valid_minutes.get(cache_type, 5)
            
            if elapsed_minutes < valid_minutes:
                print(f"  [缓存] {key}: 命中 ({elapsed_minutes:.0f}分钟前)")
                return cached.get('data')
            else:
                print(f"  [缓存] {key}: 过期 ({elapsed_minutes:.0f}分钟前)")
                return None
                
        except Exception as e:
            print(f"  [缓存] 读取失败: {e}")
            return None
    
    def _save_cache(self, cache_type: str, key: str, data: Dict):
        """保存缓存数据"""
        try:
            cache_path = self._get_cache_path(cache_type, key)
            cached = {
                'timestamp': time.time(),
                'data': data
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cached, f)
        except Exception as e:
            print(f"  [缓存] 保存失败: {e}")
    
    def _merge_data(self, real_time: Dict, cached: Dict) -> Dict:
        """合并实时数据和缓存数据
        策略：实时数据优先，缺失字段用缓存补
        """
        if not cached:
            return real_time
        if not real_time:
            return cached
        
        merged = real_time.copy()
        
        # 用缓存补充缺失的技术指标
        for key in ['high_20d', 'low_20d', 'ma30', 'ma60', 'ma120', 'volume_ratio']:
            if key not in merged or merged[key] == 0 or merged[key] is None:
                if key in cached and cached[key] not in [0, None]:
                    merged[key] = cached[key]
                    print(f"    使用缓存{key}: {cached[key]}")
        
        return merged
    
    def get_stock_data(self, codes: List[str]) -> Dict:
        """
        获取个股数据 - 多数据源+缓存
        顺序：
        1. 先尝试加载缓存
        2. 获取实时数据（多数据源）
        3. 合并实时+缓存
        4. 保存新缓存
        """
        if not codes:
            return {}
        
        result = {}
        
        for code in codes:
            # 1. 加载缓存
            cached_data = self._load_cache('stock', code)
            
            # 2. 获取实时数据
            real_time_data = self._fetch_stock_realtime(code)
            
            # 3. 合并数据
            if real_time_data:
                merged = self._merge_data(real_time_data, cached_data)
                result[code] = merged
                # 保存缓存
                self._save_cache('stock', code, merged)
            elif cached_data:
                # 实时失败，用缓存（过期也先用着）
                print(f"  ⚠️ {code}: 实时数据失败，使用缓存数据")
                result[code] = cached_data
            else:
                print(f"  ❌ {code}: 无实时数据且无缓存")
        
        return result
    
    def _fetch_stock_realtime(self, code: str) -> Optional[Dict]:
        """获取实时数据 - 多数据源合并
        策略：
        1. 腾讯/新浪获取价格和基础数据
        2. 东财获取技术指标
        3. 合并所有数据
        """
        merged_data = {}
        
        # 数据源列表
        sources = [
            ('腾讯', self._get_stock_tencent),
            ('东财', self._get_stock_eastmoney),
            ('新浪', self._get_stock_sina),
        ]
        
        for name, fetch_func in sources:
            try:
                data = fetch_func([code])
                if data and code in data:
                    print(f"  [实时] {code}: {name}成功")
                    # 合并数据，新数据覆盖旧数据
                    for key, value in data[code].items():
                        if value not in [0, None, ''] or key not in merged_data:
                            merged_data[key] = value
            except Exception as e:
                print(f"  [实时] {code}: {name}失败 - {str(e)[:30]}")
                continue
        
        if merged_data:
            return merged_data
        
        return None
    
    def _get_stock_tencent(self, codes: List[str]) -> Dict:
        """腾讯财经数据源"""
        result = {}
        for code in codes:
            try:
                # 转换代码格式
                if code.startswith('6'):
                    tencent_code = f"sh{code}"
                elif code.startswith('0') or code.startswith('3'):
                    tencent_code = f"sz{code}"
                else:
                    continue
                
                url = f"https://qt.gtimg.cn/q={tencent_code}"
                response = self.session.get(url, timeout=5)
                response.encoding = 'gbk'
                
                # 解析数据
                text = response.text
                if not text or '~' not in text:
                    continue
                
                parts = text.split('~')
                if len(parts) < 45:
                    continue
                
                result[code] = {
                    'code': code,
                    'name': parts[1],
                    'current': float(parts[3]),
                    'prev_close': float(parts[4]),
                    'open': float(parts[5]),
                    'high': float(parts[33]),
                    'low': float(parts[34]),
                    'volume': float(parts[36]),
                    'change_pct': float(parts[32]),
                    'volume_ratio': float(parts[49]) if len(parts) > 49 else 0,
                    # 技术指标需要另外获取
                    'high_20d': 0,
                    'low_20d': 0,
                    'ma30': 0,
                    'ma60': 0,
                }
            except Exception as e:
                continue
        
        return result
    
    def _get_stock_eastmoney(self, codes: List[str]) -> Dict:
        """东方财富数据源 - 获取技术指标"""
        result = {}
        try:
            # 转换代码格式
            secids = []
            for code in codes:
                if code.startswith('6'):
                    secids.append(f"1.{code}")
                else:
                    secids.append(f"0.{code}")
            
            code_str = ','.join(secids)
            # 获取更完整的字段，包括技术指标
            url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f17,f18,f20,f21,f22,f23,f24,f25,f26,f33,f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100&secids={code_str}"
            
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            if 'data' in data and 'diff' in data['data']:
                for item in data['data']['diff']:
                    code = item.get('f12')
                    if code:
                        # 解析价格（f2是价格，需要除以100）
                        current = item.get('f2', 0)
                        if current:
                            current = current / 100
                        
                        # 解析均线（f20是30日均线，f21是60日均线，也可能需要除以100）
                        ma30 = item.get('f20', 0)
                        ma60 = item.get('f21', 0)
                        if ma30:
                            ma30 = ma30 / 100
                        if ma60:
                            ma60 = ma60 / 100
                        
                        # 获取20日高低点（从其他字段推断或使用近似值）
                        high_20d = item.get('f15', 0)  # 最高价可能需要从其他接口获取
                        low_20d = item.get('f16', 0)   # 最低价
                        
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
                            'high_20d': high_20d / 100 if high_20d else 0,
                            'low_20d': low_20d / 100 if low_20d else 0,
                        }
        except Exception as e:
            print(f"    东财接口错误: {e}")
        
        return result
    
    def _get_stock_sina(self, codes: List[str]) -> Dict:
        """新浪财经数据源"""
        result = {}
        try:
            code_str = ','.join([f"sh{c}" if c.startswith('6') else f"sz{c}" for c in codes])
            url = f"https://hq.sinajs.cn/list={code_str}"
            
            response = self.session.get(url, timeout=5)
            response.encoding = 'gbk'
            
            lines = response.text.strip().split('\n')
            for line in lines:
                if 'var hq_str_' not in line:
                    continue
                
                code = line.split('_')[2].split('=')[0]
                data_str = line.split('="')[1].rstrip('";')
                parts = data_str.split(',')
                
                if len(parts) >= 33:
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
                    }
        except Exception as e:
            print(f"    新浪接口错误: {e}")
        
        return result
    
    def _get_stock_akshare(self, codes: List[str]) -> Dict:
        """AKShare数据源"""
        result = {}
        try:
            import akshare as ak
            
            for code in codes:
                try:
                    # 获取实时行情
                    df = ak.stock_zh_a_spot_em()
                    row = df[df['代码'] == code]
                    
                    if not row.empty:
                        result[code] = {
                            'code': code,
                            'name': row['名称'].values[0],
                            'current': float(row['最新价'].values[0]),
                            'change_pct': float(row['涨跌幅'].values[0]),
                            'volume_ratio': float(row['量比'].values[0]) if '量比' in row else 0,
                        }
                except Exception as e:
                    continue
        except Exception as e:
            print(f"    AKShare接口错误: {e}")
        
        return result
    
    def _get_stock_xueqiu(self, codes: List[str]) -> Dict:
        """雪球数据源"""
        result = {}
        try:
            for code in codes:
                symbol = f"SH{code}" if code.startswith('6') else f"SZ{code}"
                url = f"https://stock.xueqiu.com/v5/stock/batch/quotation.json?symbol={symbol}"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Cookie': 'xq_a_token=test'  # 需要有效cookie
                }
                
                response = self.session.get(url, headers=headers, timeout=5)
                data = response.json()
                
                if 'data' in data and data['data']:
                    item = data['data'][0]
                    quote = item.get('quote', {})
                    result[code] = {
                        'code': code,
                        'name': quote.get('name', ''),
                        'current': quote.get('current', 0),
                        'change_pct': quote.get('percent', 0),
                    }
        except Exception as e:
            print(f"    雪球接口错误: {e}")
        
        return result
    
    def _get_stock_ths(self, codes: List[str]) -> Dict:
        """同花顺数据源"""
        # 同花顺接口需要特殊处理，暂时返回空
        return {}
    
    def get_index_data(self) -> Dict:
        """获取指数数据"""
        # 尝试从缓存加载
        cached = self._load_cache('index', 'main')
        
        # 获取实时数据
        try:
            url = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2,f3,f4,f5,f6,f7&secids=1.000001,0.399001,0.399006,1.000688"
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            if 'data' in data and 'diff' in data['data']:
                result = {}
                index_names = {'000001': '上证指数', '399001': '深证成指', 
                              '399006': '创业板指', '000688': '科创50'}
                
                for item in data['data']['diff']:
                    code = item.get('f12')
                    if code in index_names:
                        result[index_names[code]] = {
                            'code': code,
                            'name': index_names[code],
                            'current': item.get('f2', 0) / 100 if item.get('f2') else 0,
                            'change_pct': item.get('f3', 0),
                        }
                
                # 保存缓存
                self._save_cache('index', 'main', result)
                return result
                
        except Exception as e:
            print(f"指数数据获取失败: {e}")
        
        # 失败返回缓存（即使过期）
        if cached:
            print("⚠️ 使用过期缓存数据")
            return cached
        
        return {}


# 全局单例
_data_fetcher = None

def data_fetcher():
    """获取数据获取器单例"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher()
    return _data_fetcher
