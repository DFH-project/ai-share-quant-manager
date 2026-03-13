#!/usr/bin/env python3
"""
夜间缓存更新脚本 - Nightly Cache Update
每晚23:00运行，更新以下数据：
1. 技术指标缓存（MA、20日高低点等）- 有效期1天
2. 基本面数据缓存（PE/PB/ROE）- 有效期7天

使用场景：
- 定时任务：0 23 * * *
- 手动执行：python3 scripts/nightly_cache_update.py
"""

import sys
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_fetcher import DataFetcher

class NightlyCacheUpdater:
    """夜间缓存更新器"""
    
    def __init__(self):
        self.fetcher = DataFetcher()
        self.data_dir = Path(__file__).parent.parent / 'data'
        
        # 缓存文件路径
        self.technical_cache = self.data_dir / 'cache' / 'technical_indicators.pkl'
        self.fundamental_cache = self.data_dir / 'fundamental_cache' / 'enhanced_fundamental.pkl'
        
        # 确保目录存在
        self.technical_cache.parent.mkdir(parents=True, exist_ok=True)
        self.fundamental_cache.parent.mkdir(parents=True, exist_ok=True)
    
    def load_stock_list(self) -> list:
        """加载需要更新的股票列表"""
        stocks = []
        
        # 从watchlist加载
        watchlist_file = self.data_dir / 'watchlist.json'
        if watchlist_file.exists():
            try:
                with open(watchlist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    stocks.extend(data.get('stocks', []))
            except Exception as e:
                print(f"[警告] 加载watchlist失败: {e}")
        
        # 去重
        stocks = list(set(stocks))
        print(f"[信息] 需要更新缓存的股票数: {len(stocks)}")
        return stocks
    
    def update_technical_cache(self, codes: list) -> dict:
        """更新技术指标缓存"""
        print("\n" + "="*60)
        print("更新技术指标缓存")
        print("="*60)
        
        cache_data = {}
        success_count = 0
        
        for i, code in enumerate(codes, 1):
            try:
                print(f"[{i}/{len(codes)}] {code} 获取技术指标...", end=' ')
                
                # 获取技术指标（从东财K线计算）
                indicators = self.fetcher._get_technical_indicators(code)
                
                if indicators:
                    cache_data[code] = {
                        'data': indicators,
                        'update_time': datetime.now().isoformat()
                    }
                    success_count += 1
                    print("✓")
                else:
                    print("✗ 无数据")
                    
            except Exception as e:
                print(f"✗ 失败: {e}")
        
        # 保存缓存
        if cache_data:
            with open(self.technical_cache, 'wb') as f:
                pickle.dump(cache_data, f)
            
            # 同时保存JSON便于查看
            json_path = self.technical_cache.with_suffix('.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n技术指标缓存更新完成: {success_count}/{len(codes)}")
        return cache_data
    
    def update_fundamental_cache(self, codes: list) -> dict:
        """更新基本面数据缓存"""
        print("\n" + "="*60)
        print("更新基本面数据缓存")
        print("="*60)
        
        # 加载现有缓存
        cache_data = {}
        if self.fundamental_cache.exists():
            try:
                with open(self.fundamental_cache, 'rb') as f:
                    cache_data = pickle.load(f)
                print(f"[信息] 加载现有缓存: {len(cache_data)} 只股票")
            except Exception as e:
                print(f"[警告] 加载现有缓存失败: {e}")
        
        success_count = 0
        skip_count = 0
        
        for i, code in enumerate(codes, 1):
            try:
                # 检查是否需要更新（7天内更新过则跳过）
                if code in cache_data:
                    last_update = cache_data[code].get('update_time', '')
                    if last_update:
                        last_dt = datetime.fromisoformat(last_update)
                        if (datetime.now() - last_dt).days < 7:
                            print(f"[{i}/{len(codes)}] {code} 跳过（7天内已更新）")
                            skip_count += 1
                            continue
                
                print(f"[{i}/{len(codes)}] {code} 获取基本面数据...", end=' ')
                
                # 从东财获取基本面数据
                fundamental = self._fetch_fundamental_from_eastmoney(code)
                
                if fundamental:
                    cache_data[code] = {
                        'data': fundamental,
                        'update_time': datetime.now().isoformat()
                    }
                    success_count += 1
                    print("✓")
                else:
                    print("✗ 无数据")
                    
            except Exception as e:
                print(f"✗ 失败: {e}")
        
        # 保存缓存
        if cache_data:
            with open(self.fundamental_cache, 'wb') as f:
                pickle.dump(cache_data, f)
            
            # 同时保存JSON便于查看
            json_path = self.fundamental_cache.with_suffix('.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n基本面缓存更新完成: 新增{success_count}, 跳过{skip_count}, 总计{len(cache_data)}")
        return cache_data
    
    def _fetch_fundamental_from_eastmoney(self, code: str) -> dict:
        """从东方财富获取基本面数据"""
        import requests
        
        # 6开头=沪市, 5开头=沪市ETF, 其他=深市
        secid = f"1.{code}" if code.startswith(('6', '5')) else f"0.{code}"
        
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'fltt': 2,
            'invt': 2,
            'fields': 'f57,f58,f162,f167,f170,f177,f183,f184,f185,f186,f187,f188',
            'secid': secid
        }
        
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if data.get('data'):
            d = data['data']
            return {
                'name': d.get('f58', ''),
                'pe': d.get('f162', 0) / 100 if d.get('f162') else None,  # 动态市盈率
                'pb': d.get('f167', 0) / 100 if d.get('f167') else None,  # 市净率
                'roe': d.get('f170', 0) / 100 if d.get('f170') else None,  # ROE
                'total_shares': d.get('f177', 0),  # 总股本
                'market_cap': round(d.get('f177', 0) * d.get('f43', 0) / 100000000, 2) if d.get('f177') and d.get('f43') else None,  # 市值(亿)
                'industry': d.get('f188', ''),  # 行业
            }
        
        return None
    
    def run(self):
        """执行完整的夜间缓存更新"""
        print("="*60)
        print(f"夜间缓存更新开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # 加载股票列表
        codes = self.load_stock_list()
        
        if not codes:
            print("[错误] 没有需要更新的股票")
            return
        
        # 更新技术指标缓存
        self.update_technical_cache(codes)
        
        # 更新基本面缓存
        self.update_fundamental_cache(codes)
        
        print("\n" + "="*60)
        print(f"夜间缓存更新完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

if __name__ == '__main__':
    updater = NightlyCacheUpdater()
    updater.run()
