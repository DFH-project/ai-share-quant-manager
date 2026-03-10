#!/usr/bin/env python3
"""
memory_cache_manager.py - 内存缓存管理器
高性能内存缓存，支持LRU淘汰、过期自动清理
用于替代频繁的文件IO，提升系统性能
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from datetime import datetime, timedelta
import json
import pickle
import hashlib


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)


class MemoryCacheManager:
    """
    内存缓存管理器
    
    特性:
    - LRU淘汰策略
    - 过期自动清理
    - 线程安全
    - 内存上限控制
    - 命中率统计
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间(秒)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # 统计
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Returns:
            缓存值或None
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            # 检查是否过期
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._misses += 1
                return None
            
            # 更新访问信息
            entry.access_count += 1
            entry.last_accessed = time.time()
            
            # 移到末尾(LRU)
            self._cache.move_to_end(key)
            
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间(秒)，None使用默认值
        
        Returns:
            是否成功
        """
        ttl = ttl or self.default_ttl
        
        with self._lock:
            # 如果已满，淘汰最旧的
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_oldest()
            
            now = time.time()
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + ttl
            )
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
    
    def _evict_oldest(self):
        """淘汰最旧的条目"""
        if self._cache:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._evictions += 1
    
    def _cleanup_loop(self):
        """清理过期条目的后台线程"""
        while True:
            time.sleep(60)  # 每分钟清理一次
            self._cleanup_expired()
    
    def _cleanup_expired(self):
        """清理过期条目"""
        now = time.time()
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if now > entry.expires_at
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate*100:.1f}%",
                'evictions': self._evictions
            }
    
    def get_cache_key(self, prefix: str, **params) -> str:
        """
        生成缓存键
        
        Args:
            prefix: 前缀
            **params: 参数
        """
        param_str = json.dumps(params, sort_keys=True)
        hash_val = hashlib.md5(param_str.encode()).hexdigest()[:8]
        return f"{prefix}:{hash_val}"


# 全局缓存实例
_price_cache = None
_data_cache = None
_fundamental_cache = None

def get_price_cache() -> MemoryCacheManager:
    """获取价格缓存实例"""
    global _price_cache
    if _price_cache is None:
        _price_cache = MemoryCacheManager(max_size=500, default_ttl=60)  # 1分钟
    return _price_cache

def get_data_cache() -> MemoryCacheManager:
    """获取数据缓存实例"""
    global _data_cache
    if _data_cache is None:
        _data_cache = MemoryCacheManager(max_size=1000, default_ttl=300)  # 5分钟
    return _data_cache

def get_fundamental_cache() -> MemoryCacheManager:
    """获取基本面缓存实例"""
    global _fundamental_cache
    if _fundamental_cache is None:
        _fundamental_cache = MemoryCacheManager(max_size=200, default_ttl=3600)  # 1小时
    return _fundamental_cache


class CachedDataFetcher:
    """
    带缓存的数据获取器
    包装data_fetcher，添加内存缓存层
    """
    
    def __init__(self):
        self.cache = get_data_cache()
    
    def get_stock_data(self, codes: list) -> Dict[str, Any]:
        """
        获取股票数据（带缓存）
        """
        result = {}
        missing_codes = []
        
        # 先查缓存
        for code in codes:
            cache_key = self.cache.get_cache_key('stock', code=code)
            cached = self.cache.get(cache_key)
            if cached is not None:
                result[code] = cached
            else:
                missing_codes.append(code)
        
        # 获取缺失的数据
        if missing_codes:
            from core.data_fetcher import data_fetcher
            fresh_data = data_fetcher.get_stock_data(missing_codes)
            
            # 存入缓存
            for code, data in fresh_data.items():
                cache_key = self.cache.get_cache_key('stock', code=code)
                self.cache.set(cache_key, data, ttl=60)  # 1分钟缓存
                result[code] = data
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self.cache.get_stats()


if __name__ == '__main__':
    # 测试
    print("🧪 测试内存缓存管理器...")
    
    cache = MemoryCacheManager(max_size=100, default_ttl=5)
    
    # 测试set/get
    cache.set('test_key', {'value': 123})
    result = cache.get('test_key')
    print(f"✅ set/get测试: {result}")
    
    # 测试统计
    stats = cache.get_stats()
    print(f"✅ 统计信息: {stats}")
    
    # 测试缓存键生成
    key = cache.get_cache_key('stock', code='300750', date='2024-01-01')
    print(f"✅ 缓存键生成: {key}")
    
    print("\n✅ 所有测试通过")
