#!/usr/bin/env python3
"""
统一数据服务 - UnifiedDataService
整合所有数据源，提供统一的缓存管理

三层缓存架构：
- L1: 实时价格 (5分钟) - 盘中高频更新
- L2: 技术指标 (1天) - 每晚23:00更新
- L3: 基本面 (7天) - 每晚23:00更新

使用示例：
    from core.unified_data_service import get_data_service
    
    service = get_data_service()
    data = service.get_stock_data(['000977', '603019'])
"""

import json
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
import threading

# 导入现有的data_fetcher
from core.data_fetcher import DataFetcher

class UnifiedDataService:
    """统一数据服务 - 单例模式"""
    
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
        self.fetcher = DataFetcher()
        self.data_dir = Path(__file__).parent.parent / 'data'
        
        # 三级缓存路径
        self.l1_cache_dir = self.data_dir / 'cache' / 'l1_realtime'
        self.l2_cache_file = self.data_dir / 'cache' / 'l2_technical.pkl'
        self.l3_cache_file = self.data_dir / 'fundamental_cache' / 'enhanced_fundamental.pkl'
        
        # 确保目录存在
        self.l1_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存（L1加速）
        self._memory_cache = {}
        self._memory_cache_lock = threading.Lock()
    
    def _get_l1_cache_path(self, code: str) -> Path:
        """L1缓存路径（实时价格）"""
        return self.l1_cache_dir / f"{code}.pkl"
    
    def _load_l1_cache(self, code: str) -> Optional[Dict]:
        """加载L1缓存（5分钟有效）"""
        # 先检查内存缓存
        with self._memory_cache_lock:
            if code in self._memory_cache:
                cached = self._memory_cache[code]
                elapsed = (time.time() - cached['timestamp']) / 60
                if elapsed < 5:
                    return cached['data']
        
        # 再检查文件缓存
        cache_path = self._get_l1_cache_path(code)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    cached = pickle.load(f)
                elapsed = (time.time() - cached['timestamp']) / 60
                if elapsed < 5:
                    # 同步到内存缓存
                    with self._memory_cache_lock:
                        self._memory_cache[code] = cached
                    return cached['data']
            except Exception:
                pass
        
        return None
    
    def _save_l1_cache(self, code: str, data: Dict):
        """保存L1缓存"""
        cached = {
            'timestamp': time.time(),
            'data': data
        }
        
        # 保存到内存
        with self._memory_cache_lock:
            self._memory_cache[code] = cached
        
        # 保存到文件
        try:
            cache_path = self._get_l1_cache_path(code)
            with open(cache_path, 'wb') as f:
                pickle.dump(cached, f)
        except Exception:
            pass
    
    def _load_l2_cache(self, code: str) -> Optional[Dict]:
        """加载L2缓存（技术指标，1天有效）"""
        if not self.l2_cache_file.exists():
            return None
        
        try:
            with open(self.l2_cache_file, 'rb') as f:
                cache = pickle.load(f)
            
            if code in cache:
                cached = cache[code]
                update_time = datetime.fromisoformat(cached['update_time'])
                if (datetime.now() - update_time).days < 1:
                    return cached['data']
        except Exception:
            pass
        
        return None
    
    def _load_l3_cache(self, code: str) -> Optional[Dict]:
        """加载L3缓存（基本面，7天有效）"""
        if not self.l3_cache_file.exists():
            return None
        
        try:
            with open(self.l3_cache_file, 'rb') as f:
                cache = pickle.load(f)
            
            if code in cache:
                cached = cache[code]
                update_time = datetime.fromisoformat(cached['update_time'])
                if (datetime.now() - update_time).days < 7:
                    return cached['data']
        except Exception:
            pass
        
        return None
    
    def get_stock_data(self, codes: List[str], include_technical: bool = True, 
                       include_fundamental: bool = True) -> Dict:
        """
        获取股票完整数据
        
        Args:
            codes: 股票代码列表
            include_technical: 是否包含技术指标
            include_fundamental: 是否包含基本面数据
        
        Returns:
            Dict: {code: data}
        """
        result = {}
        
        for code in codes:
            try:
                data = self._get_single_stock(code, include_technical, include_fundamental)
                if data:
                    result[code] = data
            except Exception as e:
                print(f"[错误] 获取{code}失败: {e}")
        
        return result
    
    def _get_single_stock(self, code: str, include_technical: bool, 
                          include_fundamental: bool) -> Optional[Dict]:
        """获取单只股票数据"""
        
        # Step 1: 获取实时价格（L1缓存或实时获取）
        l1_data = self._load_l1_cache(code)
        
        if l1_data is None:
            # 实时获取
            try:
                realtime = self.fetcher._fetch_stock_merged(code, primary_only=False)
                if realtime:
                    self._save_l1_cache(code, realtime)
                    l1_data = realtime
            except Exception as e:
                print(f"[警告] {code} 实时数据获取失败: {e}")
                return None
        
        if not l1_data:
            return None
        
        result = l1_data.copy()
        
        # Step 2: 获取技术指标（L2缓存）
        if include_technical:
            l2_data = self._load_l2_cache(code)
            if l2_data:
                # 合并技术指标
                for key in ['high_20d', 'low_20d', 'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'volume_ratio']:
                    if key in l2_data and (key not in result or result[key] in [0, None]):
                        result[key] = l2_data[key]
        
        # Step 3: 获取基本面数据（L3缓存）
        if include_fundamental:
            l3_data = self._load_l3_cache(code)
            if l3_data:
                # 合并基本面数据
                for key in ['pe', 'pb', 'roe', 'industry', 'market_cap']:
                    if key in l3_data:
                        result[key] = l3_data[key]
        
        return result
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        stats = {
            'l1_memory_cache': len(self._memory_cache),
            'l1_file_cache': len(list(self.l1_cache_dir.glob('*.pkl'))),
            'l2_technical_cache': 0,
            'l3_fundamental_cache': 0
        }
        
        if self.l2_cache_file.exists():
            try:
                with open(self.l2_cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    stats['l2_technical_cache'] = len(cache)
            except:
                pass
        
        if self.l3_cache_file.exists():
            try:
                with open(self.l3_cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    stats['l3_fundamental_cache'] = len(cache)
            except:
                pass
        
        return stats

# 全局单例
def get_data_service() -> UnifiedDataService:
    """获取统一数据服务实例"""
    return UnifiedDataService()

if __name__ == '__main__':
    # 测试
    service = get_data_service()
    
    print("缓存统计:")
    stats = service.get_cache_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print("\n测试获取数据:")
    data = service.get_stock_data(['000977', '603019'])
    for code, info in data.items():
        print(f"\n{code}:")
        print(f"  价格: {info.get('current')}")
        print(f"  PE: {info.get('pe')}")
        print(f"  20日高低: {info.get('low_20d')} ~ {info.get('high_20d')}")
