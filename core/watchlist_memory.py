"""
watchlist_memory.py - 自选股记忆模块
管理用户自选股列表，支持持久化存储
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class WatchlistItem:
    """自选股条目"""
    code: str                    # 股票代码
    name: str                    # 股票名称
    added_date: str              # 添加日期
    category: str = "default"    # 分类（如：关注、持仓、观察）
    notes: str = ""              # 备注
    tags: List[str] = None       # 标签
    priority: int = 0            # 优先级
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class WatchlistMemory:
    """自选股记忆管理器"""
    
    def __init__(self, data_file: str = "./data/watchlist.json"):
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.watchlist: Dict[str, WatchlistItem] = {}
        self.categories: Set[str] = {"default", "关注", "持仓", "观察", "自选"}
        self._load()
    
    def _load(self) -> None:
        """从文件加载自选股列表"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item_data in data.get('watchlist', []):
                        item = WatchlistItem(**item_data)
                        self.watchlist[item.code] = item
                    self.categories.update(data.get('categories', []))
                print(f"已加载 {len(self.watchlist)} 只自选股")
            except Exception as e:
                print(f"加载自选股失败: {e}")
                self.watchlist = {}
    
    def _save(self) -> None:
        """保存自选股列表到文件"""
        try:
            data = {
                'watchlist': [asdict(item) for item in self.watchlist.values()],
                'categories': list(self.categories),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存自选股失败: {e}")
    
    def add(self, code: str, name: str = "", category: str = "default",
            notes: str = "", tags: List[str] = None, priority: int = 0,
            data_fetcher=None) -> bool:
        """添加股票到自选股"""
        code = code.strip()
        if not code:
            print("股票代码不能为空")
            return False
        
        if code in self.watchlist:
            print(f"股票 {code} 已在自选股中")
            return False
        
        # 如果未提供名称，尝试获取
        if not name and data_fetcher:
            try:
                name = data_fetcher.get_stock_name(code)
            except:
                name = code
        
        if not name:
            name = code
        
        item = WatchlistItem(
            code=code,
            name=name,
            added_date=datetime.now().strftime('%Y-%m-%d'),
            category=category,
            notes=notes,
            tags=tags or [],
            priority=priority
        )
        
        self.watchlist[code] = item
        self._save()
        print(f"已添加 {code} ({name}) 到自选股")
        return True
    
    def remove(self, code: str) -> bool:
        """从自选股中移除股票"""
        code = code.strip()
        if code in self.watchlist:
            item = self.watchlist.pop(code)
            self._save()
            print(f"已从自选股移除 {code} ({item.name})")
            return True
        print(f"股票 {code} 不在自选股中")
        return False
    
    def update(self, code: str, **kwargs) -> bool:
        """更新自选股信息"""
        code = code.strip()
        if code not in self.watchlist:
            print(f"股票 {code} 不在自选股中")
            return False
        
        item = self.watchlist[code]
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        
        self._save()
        print(f"已更新 {code} 的信息")
        return True
    
    def get(self, code: str) -> Optional[WatchlistItem]:
        """获取单个自选股信息"""
        return self.watchlist.get(code.strip())
    
    def get_all(self) -> List[WatchlistItem]:
        """获取所有自选股"""
        return list(self.watchlist.values())
    
    def get_codes(self) -> List[str]:
        """获取所有自选股代码"""
        return list(self.watchlist.keys())
    
    def get_by_category(self, category: str) -> List[WatchlistItem]:
        """按分类获取自选股"""
        return [item for item in self.watchlist.values() if item.category == category]
    
    def get_by_tag(self, tag: str) -> List[WatchlistItem]:
        """按标签获取自选股"""
        return [item for item in self.watchlist.values() if tag in item.tags]
    
    def add_category(self, category: str) -> None:
        """添加新分类"""
        self.categories.add(category)
        self._save()
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self.categories)
    
    def exists(self, code: str) -> bool:
        """检查股票是否在自选股中"""
        return code.strip() in self.watchlist
    
    def clear(self) -> None:
        """清空自选股"""
        self.watchlist.clear()
        self._save()
        print("已清空自选股")
    
    def import_from_list(self, codes: List[str], data_fetcher=None, 
                         category: str = "default") -> int:
        """从代码列表批量导入"""
        count = 0
        for code in codes:
            if self.add(code, category=category, data_fetcher=data_fetcher):
                count += 1
        return count
    
    def export_to_list(self) -> List[str]:
        """导出为代码列表"""
        return self.get_codes()
    
    def get_statistics(self) -> Dict:
        """获取自选股统计信息"""
        stats = {
            'total': len(self.watchlist),
            'by_category': {},
            'by_tag': {}
        }
        
        for item in self.watchlist.values():
            # 按分类统计
            cat = item.category
            stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1
            
            # 按标签统计
            for tag in item.tags:
                stats['by_tag'][tag] = stats['by_tag'].get(tag, 0) + 1
        
        return stats
    
    def get_stats(self) -> Dict:
        """获取统计信息（兼容接口）"""
        return self.get_statistics()
    
    def get_symbols(self) -> List[str]:
        """获取所有股票代码（兼容接口）"""
        return self.get_codes()
    
    def display(self) -> None:
        """显示自选股列表"""
        if not self.watchlist:
            print("自选股列表为空")
            return
        
        print(f"\n{'='*80}")
        print(f"{'代码':<10}{'名称':<12}{'分类':<10}{'添加日期':<12}{'备注':<20}")
        print(f"{'-'*80}")
        
        for item in sorted(self.watchlist.values(), key=lambda x: x.priority, reverse=True):
            notes = item.notes[:18] + ".." if len(item.notes) > 18 else item.notes
            print(f"{item.code:<10}{item.name:<12}{item.category:<10}{item.added_date:<12}{notes:<20}")
        
        print(f"{'='*80}")
        print(f"总计: {len(self.watchlist)} 只股票")


# 单例模式
_watchlist_memory = None

def get_watchlist_memory(data_file: str = "./data/watchlist.json") -> WatchlistMemory:
    """获取自选股记忆管理器单例"""
    global _watchlist_memory
    if _watchlist_memory is None:
        _watchlist_memory = WatchlistMemory(data_file)
    return _watchlist_memory
