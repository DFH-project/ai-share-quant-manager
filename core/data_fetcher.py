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
        """合并实时数据和缓存数据"""
        if not cached:
            return real_time
        if not real_time:
            return cached
        
        merged = real_time.copy()
        
        # 用缓存补充缺失的技术指标
        for key in ['high_20d', 'low_20d', 'ma30', 'ma60', 'volume_ratio']:
            if key not in merged or merged[key] == 0 or merged[key] is None:
                if key in cached and cached[key] not in [0, None]:
                    merged[key] = cached[key]
        
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
                
                # 2. 获取实时数据（多源合并）
                real_time_data = self._fetch_stock_merged(code)
                
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
        - primary_only=False: 腾讯+东财双源合并
        
        已移除AKShare（太慢），保留东财作为兜底
        """
        merged_data = {}
        
        # 主数据源：腾讯（最快）
        try:
            data = self._get_stock_tencent([code])
            if data and code in data:
                merged_data = data[code].copy()
        except Exception as e:
            print(f"  [实时] {code}: 腾讯失败 - {str(e)[:30]}")
        
        # 如果腾讯成功且只需要主源，直接返回
        if merged_data and primary_only:
            return merged_data
        
        # 腾讯失败或需要双源，尝试东财
        if not merged_data or not primary_only:
            try:
                data = self._get_stock_eastmoney([code])
                if data and code in data:
                    print(f"  [实时] {code}: 东财兜底成功")
                    # 合并数据
                    for key, value in data[code].items():
                        if value not in [0, None, ''] or key not in merged_data:
                            merged_data[key] = value
            except Exception as e:
                print(f"  [实时] {code}: 东财失败 - {str(e)[:30]}")
        
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
    
    def _get_stock_akshare(self, codes: List[str]) -> Dict:
        """AKShare个股 - 真实数据"""
        try:
            import akshare as ak
            
            # 获取全市场数据
            sh_df = ak.stock_sh_a_spot_em()
            sz_df = ak.stock_sz_a_spot_em()
            import pandas as pd
            all_df = pd.concat([sh_df, sz_df], ignore_index=True)
            
            result = {}
            for code in codes:
                stock = all_df[all_df['代码'] == code]
                if not stock.empty:
                    result[code] = {
                        'name': stock.iloc[0]['名称'],
                        'current': float(stock.iloc[0]['最新价']),
                        'change_pct': float(stock.iloc[0]['涨跌幅'])
                    }
            
            if not result:
                raise Exception("AKShare返回空数据")
            
            return result
        except Exception as e:
            raise Exception(f"AKShare获取失败: {e}")
    
    def get_fundamental_data(self, code: str) -> Dict:
        """
        获取基本面数据 - 真实PE/PB/ROE等
        多数据源：AKShare → 东方财富
        失败时报错，绝不生成假数据
        """
        errors = []
        
        # 尝试1: AKShare
        try:
            return self._get_fundamental_akshare(code)
        except Exception as e:
            errors.append(f"AKShare基本面: {e}")
        
        # 尝试2: 东方财富
        try:
            return self._get_fundamental_eastmoney(code)
        except Exception as e:
            errors.append(f"东财基本面: {e}")
        
        # 全部失败
        error_msg = f"❌ 基本面数据获取失败: {'; '.join(errors)}"
        print(error_msg)
        raise Exception(error_msg)
    
    def _get_fundamental_akshare(self, code: str) -> Dict:
        """AKShare基本面数据 - 真实数据"""
        import akshare as ak
        
        # 获取个股指标
        df = ak.stock_individual_info_em(symbol=code)
        if df is None or df.empty:
            raise Exception("AKShare返回空数据")
        
        result = {}
        for _, row in df.iterrows():
            key = row.get('item', '')
            value = row.get('value', '')
            
            if '市盈率' in key or 'PE' in key:
                try:
                    result['pe'] = float(value)
                except:
                    pass
            elif '市净率' in key or 'PB' in key:
                try:
                    result['pb'] = float(value)
                except:
                    pass
            elif 'ROE' in key or '净资产收益率' in key:
                try:
                    result['roe'] = float(value)
                except:
                    pass
            elif '总市值' in key:
                try:
                    result['market_cap'] = float(value)
                except:
                    pass
            elif '流通市值' in key:
                try:
                    result['float_cap'] = float(value)
                except:
                    pass
            elif '所属行业' in key:
                result['industry'] = str(value)
        
        if not result:
            raise Exception("AKShare基本面数据解析失败")
        
        return result
    
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
