#!/usr/bin/env python3
"""
数据获取模块 - DataFetcher V2 (并行优化版)
底层死规则：
1. 禁止AI生成任何假数据
2. 数据获取失败必须报错，不能瞎编
3. 多数据源配置：腾讯→东财→新浪→AKShare，自动重试+合并数据
4. 历史数据缓存，实时数据优先，缓存补充缺失字段
5. 只返回真实数据或明确报错
6. 并行获取加速 - 使用线程池
"""

import requests
import json
import time
import pickle
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
        
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"stock_{key}.pkl"
    
    def _load_cache(self, key: str) -> Optional[Dict]:
        """加载缓存数据（5分钟内有效）"""
        try:
            cache_path = self._get_cache_path(key)
            if not cache_path.exists():
                return None
            
            with open(cache_path, 'rb') as f:
                cached = pickle.load(f)
            
            # 检查缓存是否过期（5分钟）
            cache_time = cached.get('timestamp', 0)
            elapsed_minutes = (time.time() - cache_time) / 60
            
            if elapsed_minutes < 5:
                print(f"  [缓存] {key}: 命中 ({elapsed_minutes:.0f}分钟前)")
                return cached.get('data')
            else:
                print(f"  [缓存] {key}: 过期 ({elapsed_minutes:.0f}分钟前)")
                return None
                
        except Exception as e:
            return None
    
    def _save_cache(self, key: str, data: Dict):
        """保存缓存数据"""
        try:
            cache_path = self._get_cache_path(key)
            cached = {
                'timestamp': time.time(),
                'data': data
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cached, f)
        except Exception as e:
            pass
    
    def _merge_stock_data(self, real_time: Dict, cached: Dict) -> Dict:
        """
        合并实时数据和缓存数据 - 智能合并
        
        策略：
        1. 实时数据覆盖缓存（价格和基础数据）
        2. 缓存补充缺失的技术指标（K线类数据变化较慢，可复用）
        3. 标记数据来源，便于调试
        """
        if not cached:
            return real_time
        if not real_time:
            return cached
        
        merged = real_time.copy()
        
        # 用缓存补充缺失的技术指标（K线类数据可以跨天复用）
        technical_keys = ['high_20d', 'low_20d', 'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'volume_ratio']
        for key in technical_keys:
            if key not in merged or merged[key] in [0, None]:
                if key in cached and cached[key] not in [0, None]:
                    merged[key] = cached[key]
                    merged[f'{key}_source'] = 'cache'
        
        # 添加合并标记
        merged['_data_merged'] = True
        
        return merged
        
    def get_index_data(self) -> Dict:
        """
        获取指数数据 - 多数据源自动切换
        顺序：腾讯 → 东财 → 新浪
        失败时报错，绝不生成假数据
        """
        errors = []
        
        for i in range(self.max_retry):
            # 尝试1: 腾讯
            try:
                data = self._get_index_tencent()
                if self._validate_index_data(data):
                    return data
            except Exception as e:
                errors.append(f"腾讯({i+1}): {e}")
                time.sleep(1)
            
            # 尝试2: 东方财富
            try:
                data = self._get_index_eastmoney()
                if self._validate_index_data(data):
                    return data
            except Exception as e:
                errors.append(f"东财({i+1}): {e}")
                time.sleep(1)
            
            # 尝试3: 新浪
            try:
                data = self._get_index_sina()
                if self._validate_index_data(data):
                    return data
            except Exception as e:
                errors.append(f"新浪({i+1}): {e}")
                time.sleep(1)
        
        # 全部失败，报错
        error_msg = f"❌ 所有数据源获取失败（重试{self.max_retry}次）: {'; '.join(errors[-5:])}"
        print(error_msg)
        raise Exception(error_msg)
    
    def get_stock_data(self, codes: List[str], max_workers: int = 8) -> Dict:
        """
        获取个股数据 - 多数据源自动切换+智能缓存+并行处理
        策略：
        1. 先尝试加载缓存
        2. 获取实时数据（多数据源合并）- 并行处理
        3. 合并实时+缓存
        4. 保存新缓存
        
        Args:
            codes: 股票代码列表
            max_workers: 并行线程数，默认8
        """
        if not codes:
            return {}
        
        result = {}
        lock = threading.Lock()
        
        def fetch_single_stock(code):
            """获取单只股票数据"""
            try:
                # 1. 加载缓存
                cached_data = self._load_cache(code)
                
                # 2. 获取实时数据（多源合并）- 获取完整数据（含技术指标）
                real_time_data = self._fetch_stock_merged(code, primary_only=False)
                
                # 3. 合并数据
                if real_time_data:
                    merged = self._merge_stock_data(real_time_data, cached_data)
                    # 保存缓存
                    self._save_cache(code, merged)
                    with lock:
                        result[code] = merged
                elif cached_data:
                    # 实时失败，用缓存（过期也先用着）
                    print(f"  ⚠️ {code}: 实时数据失败，使用缓存数据")
                    with lock:
                        result[code] = cached_data
                else:
                    print(f"  ❌ {code}: 无实时数据且无缓存")
            except Exception as e:
                print(f"  ❌ {code}: 获取异常 - {str(e)[:40]}")
        
        # 使用线程池并行获取
        print(f"  并行获取 {len(codes)} 只股票数据 (线程数: {max_workers})...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_single_stock, code): code for code in codes}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"  ❌ {code}: 线程执行失败 - {e}")
        
        print(f"  ✅ 成功获取 {len(result)}/{len(codes)} 只股票数据")
        return result
    
    def _fetch_stock_merged(self, code: str, primary_only: bool = True) -> Optional[Dict]:
        """获取实时数据 - 优化版
        策略：
        - primary_only=True: 只使用腾讯（最快）
        - primary_only=False: 腾讯+新浪双源合并（含技术指标）
        
        数据源：
        1. 腾讯（主）：基础数据最快
        2. 新浪财经（辅）：实时数据
        3. 东方财富（兜底）：技术指标（K线数据）
        
        已移除AKShare（太慢）
        """
        merged_data = {}
        
        # 主数据源：腾讯（最快）
        try:
            data = self._get_stock_tencent([code])
            if data and code in data:
                merged_data = data[code].copy()
        except Exception as e:
            print(f"  [实时] {code}: 腾讯失败 - {str(e)[:30]}")
        
        # 腾讯失败，尝试新浪
        if not merged_data:
            try:
                data = self._get_stock_sina([code])
                if data and code in data:
                    print(f"  [实时] {code}: 新浪兜底成功")
                    merged_data = data[code].copy()
            except Exception as e:
                print(f"  [实时] {code}: 新浪失败 - {str(e)[:30]}")
        
        # 如果只需要主源（基础数据），直接返回
        if merged_data and primary_only:
            return merged_data
        
        # 需要完整数据（含技术指标）
        if merged_data:
            # 尝试从东财获取技术指标（K线数据）
            try:
                indicators = self._get_technical_indicators(code)
                if indicators:
                    merged_data.update(indicators)
                    print(f"  [实时] {code}: 技术指标补充成功")
            except Exception as e:
                print(f"  [实时] {code}: 技术指标获取失败 - {str(e)[:30]}")
        
        if merged_data:
            return merged_data
        
        return None
    
    def _validate_index_data(self, data: Dict) -> bool:
        """验证指数数据是否合理"""
        if not data:
            return False
        
        for name, info in data.items():
            price = info.get('current', 0)
            # 上证指数合理范围 2500-5000
            if '上证' in name and (price < 2500 or price > 5000):
                return False
            # 深证成指合理范围 8000-18000
            if '深证' in name and (price < 8000 or price > 18000):
                return False
            # 创业板指合理范围 1500-4500
            if '创业' in name and (price < 1500 or price > 4500):
                return False
        
        return True
    
    def _get_index_tencent(self) -> Dict:
        """腾讯指数 - 真实数据"""
        url = "http://qt.gtimg.cn/q=sh000001,sz399001,sz399006"
        resp = self.session.get(url, timeout=10)
        resp.encoding = 'gb2312'
        
        result = {}
        for line in resp.text.split(';'):
            if 'v_' in line:
                parts = line.split('="')
                if len(parts) >= 2:
                    code = parts[0].replace('v_', '')
                    data = parts[1].strip().split('~')
                    if len(data) > 45:
                        name_map = {
                            'sh000001': '上证指数',
                            'sz399001': '深证成指',
                            'sz399006': '创业板指'
                        }
                        result[name_map.get(code, code)] = {
                            'current': float(data[3]),
                            'change_pct': float(data[32]),
                            'volume': float(data[36])
                        }
        
        if not result:
            raise Exception("腾讯返回空数据")
        
        return result
    
    def _get_index_eastmoney(self) -> Dict:
        """东方财富指数 - 真实数据"""
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            'fltt': 2,
            'invt': 2,
            'fields': 'f12,f13,f14,f2,f3,f4,f5',
            'secids': '1.000001,0.399001,0.399006'
        }
        resp = self.session.get(url, params=params, timeout=10)
        data = resp.json()
        
        result = {}
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                name = item.get('f14')
                result[name] = {
                    'current': item.get('f2', 0) / 100,
                    'change_pct': item.get('f3', 0),
                    'volume': item.get('f5', 0)
                }
        
        if not result:
            raise Exception("东财返回空数据")
        
        return result
    
    def _get_index_sina(self) -> Dict:
        """新浪指数 - 真实数据"""
        url = "https://hq.sinajs.cn/list=sh000001,sz399001,sz399006"
        resp = self.session.get(url, timeout=10)
        resp.encoding = 'gb2312'
        
        result = {}
        lines = resp.text.strip().split(';')
        name_map = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指'
        }
        
        for line in lines:
            if 'var hq_str_' in line:
                code = line.split('var hq_str_')[1].split('=')[0]
                data_str = line.split('="')[1].strip('"')
                data = data_str.split(',')
                if len(data) > 3:
                    name = name_map.get(code, code)
                    current = float(data[3])
                    prev_close = float(data[2])
                    change_pct = (current / prev_close - 1) * 100 if prev_close > 0 else 0
                    result[name] = {
                        'current': current,
                        'change_pct': change_pct,
                        'volume': 0
                    }
        
        if not result:
            raise Exception("新浪返回空数据")
        
        return result
    
    def _get_stock_tencent(self, codes: List[str]) -> Dict:
        """腾讯个股 - 真实数据"""
        tencent_codes = []
        for code in codes:
            if code.startswith('6'):
                tencent_codes.append(f'sh{code}')
            else:
                tencent_codes.append(f'sz{code}')
        
        url = f"http://qt.gtimg.cn/q={','.join(tencent_codes)}"
        resp = self.session.get(url, timeout=10)
        resp.encoding = 'gb2312'
        
        result = {}
        for line in resp.text.split(';'):
            if 'v_' in line:
                parts = line.split('="')
                if len(parts) >= 2:
                    code = parts[0].replace('v_', '').replace('sh', '').replace('sz', '')
                    data = parts[1].strip().split('~')
                    if len(data) > 45:
                        result[code] = {
                            'name': data[1],
                            'current': float(data[3]),
                            'change_pct': float(data[32]),
                            'volume': float(data[36])
                        }
        
        if not result:
            raise Exception("腾讯个股返回空数据")
        
        return result
    
    def _get_stock_eastmoney(self, codes: List[str]) -> Dict:
        """东方财富个股 - 真实数据"""
        result = {}
        for code in codes:
            secid = f"1.{code}" if code.startswith('6') else f"0.{code}"
            url = "https://push2.eastmoney.com/api/qt/stock/get"
            params = {
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'fltt': 2,
                'invt': 2,
                'fields': 'f43,f44,f45,f46,f47,f48,f57,f58,f60',
                'secid': secid
            }
            resp = self.session.get(url, params=params, timeout=5)
            data = resp.json()
            
            if data.get('data'):
                d = data['data']
                current = d.get('f43', 0) / 100
                prev_close = d.get('f60', 0) / 100
                change_pct = (current / prev_close - 1) * 100 if prev_close > 0 else 0
                result[code] = {
                    'name': d.get('f58', ''),
                    'current': current,
                    'change_pct': change_pct
                }
        
        if not result:
            raise Exception("东财个股返回空数据")
        
        return result
    
    def _get_stock_sina(self, codes: List[str]) -> Dict:
        """新浪财经个股 - 真实数据，含技术指标"""
        result = {}
        for code in codes:
            try:
                sina_code = f"sh{code}" if code.startswith('6') else f"sz{code}"
                url = f"https://hq.sinajs.cn/list={sina_code}"
                resp = self.session.get(url, timeout=5)
                resp.encoding = 'gb2312'
                
                # 解析新浪数据格式
                if 'var hq_str_' in resp.text:
                    data_str = resp.text.split('="')[1].strip('";')
                    data = data_str.split(',')
                    if len(data) >= 33:
                        result[code] = {
                            'name': data[0],
                            'open': float(data[1]),
                            'prev_close': float(data[2]),
                            'current': float(data[3]),
                            'high': float(data[4]),
                            'low': float(data[5]),
                            'volume': float(data[8]),
                            'change_pct': (float(data[3]) / float(data[2]) - 1) * 100 if float(data[2]) > 0 else 0,
                            'bid1': float(data[11]),  # 买一价
                            'ask1': float(data[21]),  # 卖一价
                        }
            except Exception as e:
                continue
        
        if not result:
            raise Exception("新浪返回空数据")
        
        return result
    
    def _get_kline_eastmoney(self, code: str, days: int = 20) -> List[Dict]:
        """
        东方财富K线数据 - 主要技术指标来源
        用于计算技术指标（20日高低点、均线、量比等）
        """
        try:
            secid = f"1.{code}" if code.startswith('6') else f"0.{code}"
            url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                'secid': secid,
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57',
                'klt': '101',  # 日K
                'fqt': '1',    # 前复权
                'end': '20500101',
                'lmt': str(days + 5)  # 多取几天确保有足够数据
            }
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()
            
            if data and data.get('data') and data['data'].get('klines'):
                klines = data['data']['klines']
                result = []
                for k in klines[-days:]:
                    # 格式: date,open,close,low,high,volume,amount
                    parts = k.split(',')
                    if len(parts) >= 6:
                        result.append({
                            'date': parts[0],
                            'open': float(parts[1]),
                            'close': float(parts[2]),
                            'low': float(parts[3]),
                            'high': float(parts[4]),
                            'volume': float(parts[5])
                        })
                return result
            
            return []
        except Exception as e:
            return []

    def _get_kline_sina(self, code: str, days: int = 20) -> List[Dict]:
        """
        获取新浪K线数据（备用）
        新浪接口已失效，直接使用东财
        """
        return self._get_kline_eastmoney(code, days)
    
    def _get_technical_indicators(self, code: str) -> Dict:
        """
        计算技术指标（基于K线数据）
        返回：20日高低点、均线、量比等
        """
        try:
            klines = self._get_kline_sina(code, days=25)
            if len(klines) < 20:
                return {}
            
            closes = [k['close'] for k in klines]
            volumes = [k['volume'] for k in klines]
            
            # 最近20日
            recent_20 = closes[-20:]
            recent_5 = closes[-5:]
            
            # 计算指标
            high_20d = max([k['high'] for k in klines[-20:]])
            low_20d = min([k['low'] for k in klines[-20:]])
            ma5 = sum(recent_5) / len(recent_5)
            ma20 = sum(recent_20) / len(recent_20)
            
            # 量比（今日成交量 / 近5日平均）
            today_volume = volumes[-1]
            avg_5d_volume = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else today_volume
            volume_ratio = today_volume / avg_5d_volume if avg_5d_volume > 0 else 1
            
            return {
                'high_20d': high_20d,
                'low_20d': low_20d,
                'ma5': ma5,
                'ma20': ma20,
                'volume_ratio': volume_ratio
            }
        except Exception as e:
            return {}
    
    def _get_stock_akshare(self, codes: List[str]) -> Dict:
        """AKShare个股 - 已禁用，使用新浪财经替代"""
        raise Exception("AKShare已禁用，使用新浪财经替代")
    
    def get_fundamental_data(self, code: str) -> Dict:
        """
        获取基本面数据 - 真实PE/PB/ROE等
        多数据源：东方财富（优先）
        失败时报错，绝不生成假数据
        """
        errors = []
        
        # 尝试1: 东方财富（最稳定）
        try:
            return self._get_fundamental_eastmoney(code)
        except Exception as e:
            errors.append(f"东财基本面: {e}")
        
        # 全部失败
        error_msg = f"❌ 基本面数据获取失败: {'; '.join(errors)}"
        print(error_msg)
        raise Exception(error_msg)
    
    def _get_fundamental_akshare(self, code: str) -> Dict:
        """AKShare基本面数据 - 已禁用"""
        raise Exception("AKShare已禁用")
    
    def _get_fundamental_eastmoney(self, code: str) -> Dict:
        """东方财富基本面数据 - 真实数据"""
        secid = f"1.{code}" if code.startswith('6') else f"0.{code}"
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'fltt': 2,
            'invt': 2,
            'fields': 'f162,f163,f167,f168,f170,f171,f57,f58,f60,f61',
            'secid': secid
        }
        resp = self.session.get(url, params=params, timeout=10)
        data = resp.json()
        
        if not data.get('data'):
            raise Exception("东财返回空数据")
        
        d = data['data']
        result = {
            'pe': d.get('f162', 0) / 100 if d.get('f162') else None,  # 动态PE
            'pb': d.get('f167', 0) / 100 if d.get('f167') else None,  # PB
            'roe': d.get('f163', 0) / 100 if d.get('f163') else None,  # ROE
        }
        
        # 过滤无效数据
        result = {k: v for k, v in result.items() if v is not None and v > 0}
        
        if not result:
            raise Exception("东财基本面数据无效")
        
        return result
    
    def get_batch_fundamental(self, codes: List[str]) -> Dict[str, Dict]:
        """批量获取基本面数据"""
        result = {}
        for code in codes:
            try:
                result[code] = self.get_fundamental_data(code)
            except Exception as e:
                print(f"获取 {code} 基本面失败: {e}")
                # 失败时不生成假数据，而是标记为失败
                result[code] = {'error': str(e)}
        return result


# 全局数据获取器实例
data_fetcher = DataFetcher()

if __name__ == '__main__':
    # 测试多数据源
    try:
        print("测试多数据源获取...")
        print("\n1. 获取指数数据:")
        index = data_fetcher.get_index_data()
        for name, data in index.items():
            print(f"   {name}: {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        print("\n2. 获取个股数据:")
        stocks = data_fetcher.get_stock_data(['601138', '603019', '000977'])
        for code, data in stocks.items():
            print(f"   {data['name']}({code}): {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        print("\n✅ 多数据源测试成功！")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
