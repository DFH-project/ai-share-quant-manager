"""
watchlist_memory_v2.py - 自选股记忆模块V2
升级功能：
1. 自选分级管理：特别关注/一般关注/观察
2. 策略类型标记：追涨型/低吸型/潜力型/抄底型/价值型/震荡型/补涨型
3. 选股原因深度记录
4. 买入计划管理
5. 关联板块追踪
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum


class AttentionLevel(Enum):
    """关注级别"""
    HIGH = "特别关注"      # 高频监控，实时提醒
    MEDIUM = "一般关注"   # 常规监控，重要信号提醒
    LOW = "观察"          # 低频监控，仅极端情况提醒


class StrategyType(Enum):
    """策略类型"""
    CHASE = "追涨型"      # 板块龙头，强势突破
    DIP = "低吸型"        # 强势股回调买入
    POTENTIAL = "潜力型"  # 热门板块蓄势待发
    BOTTOM = "抄底型"     # 大跌后低位企稳
    VALUE = "价值型"      # 低估值高ROE
    CONSOLIDATION = "震荡型"  # 震荡整理等待突破
    LAGGARD = "补涨型"    # 板块滞涨个股
    MULTI = "多维优选型"  # 多维度综合评分高
    FLASH = "急跌反弹型"  # 单日大跌后的反弹
    SECTOR_LEADER = "板块龙头"  # 板块领涨龙头
    MANUAL = "手动添加"   # 用户手动添加


@dataclass
class EntryPlan:
    """买入计划"""
    entry_price: float = 0.0          # 计划买入价
    stop_loss: float = 0.0            # 止损价
    target_price: float = 0.0         # 目标价
    position_size: str = ""           # 建议仓位（轻仓/半仓/重仓）
    holding_period: str = ""          # 持有周期（短线/中线/长线）
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EntryPlan':
        return cls(**data)


@dataclass
class SelectionReason:
    """选股原因详细记录"""
    primary_reason: str = ""          # 主要原因
    secondary_reasons: List[str] = field(default_factory=list)  # 次要原因
    key_indicators: Dict[str, any] = field(default_factory=dict)  # 关键指标
    market_context: str = ""          # 当时市场环境
    sector_context: str = ""          # 板块情况
    risk_factors: List[str] = field(default_factory=list)  # 风险因素
    selection_time: str = ""          # 选股时间
    expected_scenario: str = ""       # 预期走势
    invalidation_conditions: List[str] = field(default_factory=list)  # 失效条件
    
    def to_dict(self) -> dict:
        return {
            'primary_reason': self.primary_reason,
            'secondary_reasons': self.secondary_reasons,
            'key_indicators': self.key_indicators,
            'market_context': self.market_context,
            'sector_context': self.sector_context,
            'risk_factors': self.risk_factors,
            'selection_time': self.selection_time,
            'expected_scenario': self.expected_scenario,
            'invalidation_conditions': self.invalidation_conditions
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SelectionReason':
        return cls(
            primary_reason=data.get('primary_reason', ''),
            secondary_reasons=data.get('secondary_reasons', []),
            key_indicators=data.get('key_indicators', {}),
            market_context=data.get('market_context', ''),
            sector_context=data.get('sector_context', ''),
            risk_factors=data.get('risk_factors', []),
            selection_time=data.get('selection_time', ''),
            expected_scenario=data.get('expected_scenario', ''),
            invalidation_conditions=data.get('invalidation_conditions', [])
        )


@dataclass
class WatchlistItemV2:
    """自选股条目V2 - 增强版"""
    # 基础信息
    code: str                           # 股票代码
    name: str                           # 股票名称
    added_date: str                     # 添加日期
    
    # 分级管理
    attention_level: str = "一般关注"    # 特别关注/一般关注/观察
    strategy_type: str = "手动添加"      # 策略类型
    
    # 关联信息
    category: str = "default"           # 分类
    tags: List[str] = field(default_factory=list)  # 标签
    linked_sectors: List[str] = field(default_factory=list)  # 关联板块
    
    # 深度信息
    selection_reason: SelectionReason = field(default_factory=SelectionReason)  # 选股原因
    entry_plan: EntryPlan = field(default_factory=EntryPlan)  # 买入计划
    
    # 监控配置
    priority: int = 0                   # 优先级(0-100)
    alert_threshold: Dict[str, float] = field(default_factory=dict)  # 提醒阈值
    
    # 动态记录
    notes: str = ""                     # 简要备注
    update_history: List[Dict] = field(default_factory=list)  # 更新历史
    performance_tracking: Dict = field(default_factory=dict)  # 表现追踪
    
    def __post_init__(self):
        if isinstance(self.selection_reason, dict):
            self.selection_reason = SelectionReason.from_dict(self.selection_reason)
        if isinstance(self.entry_plan, dict):
            self.entry_plan = EntryPlan.from_dict(self.entry_plan)
        if self.tags is None:
            self.tags = []
        if self.linked_sectors is None:
            self.linked_sectors = []
        if self.alert_threshold is None:
            self.alert_threshold = {}
        if self.update_history is None:
            self.update_history = []
        if self.performance_tracking is None:
            self.performance_tracking = {}
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'added_date': self.added_date,
            'attention_level': self.attention_level,
            'strategy_type': self.strategy_type,
            'category': self.category,
            'tags': self.tags,
            'linked_sectors': self.linked_sectors,
            'selection_reason': self.selection_reason.to_dict(),
            'entry_plan': self.entry_plan.to_dict(),
            'priority': self.priority,
            'alert_threshold': self.alert_threshold,
            'notes': self.notes,
            'update_history': self.update_history,
            'performance_tracking': self.performance_tracking
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'WatchlistItemV2':
        """从字典创建"""
        return cls(
            code=data.get('code', ''),
            name=data.get('name', ''),
            added_date=data.get('added_date', ''),
            attention_level=data.get('attention_level', '一般关注'),
            strategy_type=data.get('strategy_type', '手动添加'),
            category=data.get('category', 'default'),
            tags=data.get('tags', []),
            linked_sectors=data.get('linked_sectors', []),
            selection_reason=SelectionReason.from_dict(data.get('selection_reason', {})),
            entry_plan=EntryPlan.from_dict(data.get('entry_plan', {})),
            priority=data.get('priority', 0),
            alert_threshold=data.get('alert_threshold', {}),
            notes=data.get('notes', ''),
            update_history=data.get('update_history', []),
            performance_tracking=data.get('performance_tracking', {})
        )
    
    def get_strategy_emoji(self) -> str:
        """获取策略类型对应的emoji"""
        emoji_map = {
            '追涨型': '🚀',
            '低吸型': '💧',
            '潜力型': '💎',
            '抄底型': '🎯',
            '价值型': '💰',
            '震荡型': '⏳',
            '补涨型': '📈',
            '多维优选型': '⭐',
            '急跌反弹型': '⚡',
            '板块龙头': '🏆',
            '手动添加': '📌'
        }
        return emoji_map.get(self.strategy_type, '📌')
    
    def get_attention_emoji(self) -> str:
        """获取关注级别对应的emoji"""
        emoji_map = {
            '特别关注': '🔴',
            '一般关注': '🟡',
            '观察': '🟢'
        }
        return emoji_map.get(self.attention_level, '⚪')
    
    def update_performance(self, current_price: float, change_pct: float):
        """更新表现追踪"""
        if 'price_history' not in self.performance_tracking:
            self.performance_tracking['price_history'] = []
        
        self.performance_tracking['price_history'].append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'price': current_price,
            'change_pct': change_pct
        })
        
        # 只保留最近50条记录
        if len(self.performance_tracking['price_history']) > 50:
            self.performance_tracking['price_history'] = self.performance_tracking['price_history'][-50:]
    
    def add_update_record(self, field_name: str, old_value: any, new_value: any, reason: str = ""):
        """添加更新记录"""
        self.update_history.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'field': field_name,
            'old': old_value,
            'new': new_value,
            'reason': reason
        })
        
        # 只保留最近20条更新记录
        if len(self.update_history) > 20:
            self.update_history = self.update_history[-20:]


class WatchlistMemoryV2:
    """自选股记忆管理器V2 - 增强版"""
    
    def __init__(self, data_file: str = None):
        # 使用绝对路径
        if data_file is None:
            current_dir = Path(__file__).parent.parent.absolute()
            data_file = current_dir / "data" / "watchlist_v2.json"
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.watchlist: Dict[str, WatchlistItemV2] = {}
        self.categories: Set[str] = {"default", "关注", "持仓", "观察", "自选"}
        self._load()
    
    def _load(self) -> None:
        """从文件加载"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item_data in data.get('watchlist', []):
                        item = WatchlistItemV2.from_dict(item_data)
                        self.watchlist[item.code] = item
                    self.categories.update(data.get('categories', []))
                print(f"已加载 {len(self.watchlist)} 只自选股(V2)")
            except Exception as e:
                print(f"加载自选股V2失败: {e}")
                self.watchlist = {}
    
    def _save(self) -> None:
        """保存到文件"""
        try:
            data = {
                'watchlist': [item.to_dict() for item in self.watchlist.values()],
                'categories': list(self.categories),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存自选股V2失败: {e}")
    
    def add(self, code: str, name: str = "", 
            attention_level: str = "一般关注",
            strategy_type: str = "手动添加",
            category: str = "default",
            notes: str = "",
            tags: List[str] = None,
            linked_sectors: List[str] = None,
            selection_reason: SelectionReason = None,
            entry_plan: EntryPlan = None,
            priority: int = 0,
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
        
        # 根据策略类型设置默认优先级
        if priority == 0:
            priority_map = {
                '特别关注': 90,
                '一般关注': 50,
                '观察': 20
            }
            priority = priority_map.get(attention_level, 50)
        
        item = WatchlistItemV2(
            code=code,
            name=name,
            added_date=datetime.now().strftime('%Y-%m-%d'),
            attention_level=attention_level,
            strategy_type=strategy_type,
            category=category,
            notes=notes,
            tags=tags or [],
            linked_sectors=linked_sectors or [],
            selection_reason=selection_reason or SelectionReason(),
            entry_plan=entry_plan or EntryPlan(),
            priority=priority
        )
        
        self.watchlist[code] = item
        self._save()
        emoji = item.get_strategy_emoji()
        level_emoji = item.get_attention_emoji()
        print(f"{level_emoji} 已添加 {code} ({name}) [{attention_level}] {emoji}[{strategy_type}]")
        return True
    
    def add_with_full_analysis(self, code: str, name: str,
                               attention_level: str,
                               strategy_type: str,
                               selection_reason: SelectionReason,
                               entry_plan: EntryPlan,
                               linked_sectors: List[str] = None,
                               notes: str = "") -> bool:
        """完整添加，包含深度分析"""
        code = code.strip()
        if not code:
            return False
        
        if code in self.watchlist:
            # 更新已有股票
            item = self.watchlist[code]
            item.attention_level = attention_level
            item.strategy_type = strategy_type
            item.selection_reason = selection_reason
            item.entry_plan = entry_plan
            item.linked_sectors = linked_sectors or []
            item.notes = notes
            item.add_update_record('full_update', 'old', 'new', '完整更新')
        else:
            # 新建
            item = WatchlistItemV2(
                code=code,
                name=name,
                added_date=datetime.now().strftime('%Y-%m-%d'),
                attention_level=attention_level,
                strategy_type=strategy_type,
                selection_reason=selection_reason,
                entry_plan=entry_plan,
                linked_sectors=linked_sectors or [],
                notes=notes,
                priority=90 if attention_level == '特别关注' else 50
            )
            self.watchlist[code] = item
        
        self._save()
        return True
    
    def remove(self, code: str) -> bool:
        """移除股票"""
        code = code.strip()
        if code in self.watchlist:
            item = self.watchlist.pop(code)
            self._save()
            print(f"已移除 {code} ({item.name})")
            return True
        return False
    
    def update(self, code: str, **kwargs) -> bool:
        """更新股票信息"""
        code = code.strip()
        if code not in self.watchlist:
            return False
        
        item = self.watchlist[code]
        for key, value in kwargs.items():
            if hasattr(item, key):
                old_value = getattr(item, key)
                setattr(item, key, value)
                item.add_update_record(key, old_value, value)
        
        self._save()
        return True
    
    def get(self, code: str) -> Optional[WatchlistItemV2]:
        """获取单个股票"""
        return self.watchlist.get(code.strip())
    
    def get_all(self) -> List[WatchlistItemV2]:
        """获取所有股票"""
        return list(self.watchlist.values())
    
    def get_codes(self) -> List[str]:
        """获取所有代码"""
        return list(self.watchlist.keys())
    
    def get_by_attention_level(self, level: str) -> List[WatchlistItemV2]:
        """按关注级别获取"""
        return [item for item in self.watchlist.values() if item.attention_level == level]
    
    def get_by_strategy(self, strategy: str) -> List[WatchlistItemV2]:
        """按策略类型获取"""
        return [item for item in self.watchlist.values() if item.strategy_type == strategy]
    
    def get_high_priority(self) -> List[WatchlistItemV2]:
        """获取高优先级股票（特别关注）"""
        return [item for item in self.watchlist.values() 
                if item.attention_level == '特别关注']
    
    def get_by_sector(self, sector: str) -> List[WatchlistItemV2]:
        """按关联板块获取"""
        return [item for item in self.watchlist.values() 
                if sector in item.linked_sectors]
    
    def exists(self, code: str) -> bool:
        """检查是否存在"""
        return code.strip() in self.watchlist
    
    def get_monitoring_config(self) -> Dict:
        """获取监控配置（用于大盘监控联动）"""
        config = {
            'high_attention': [],      # 特别关注 - 高频监控
            'medium_attention': [],    # 一般关注 - 常规监控
            'low_attention': [],       # 观察 - 低频监控
            'by_strategy': {}          # 按策略分组
        }
        
        for item in self.watchlist.values():
            code_info = {
                'code': item.code,
                'name': item.name,
                'strategy': item.strategy_type,
                'alert_threshold': item.alert_threshold,
                'entry_plan': item.entry_plan.to_dict() if item.entry_plan else {},
                'selection_reason': item.selection_reason.to_dict() if item.selection_reason else {}
            }
            
            if item.attention_level == '特别关注':
                config['high_attention'].append(code_info)
            elif item.attention_level == '一般关注':
                config['medium_attention'].append(code_info)
            else:
                config['low_attention'].append(code_info)
            
            # 按策略分组
            strategy = item.strategy_type
            if strategy not in config['by_strategy']:
                config['by_strategy'][strategy] = []
            config['by_strategy'][strategy].append(code_info)
        
        return config
    
    def display(self) -> None:
        """显示自选股列表"""
        if not self.watchlist:
            print("自选股列表为空")
            return
        
        # 按关注级别和优先级排序
        items = sorted(self.watchlist.values(), 
                      key=lambda x: (x.attention_level != '特别关注', 
                                   x.attention_level != '一般关注',
                                   -x.priority))
        
        print(f"\n{'='*100}")
        print(f"{'代码':<10}{'名称':<12}{'关注级别':<10}{'策略':<12}{'板块':<20}{'买入价':<10}{'备注'}")
        print(f"{'-'*100}")
        
        for item in items:
            level_emoji = item.get_attention_emoji()
            strategy_emoji = item.get_strategy_emoji()
            sectors = ','.join(item.linked_sectors[:2]) if item.linked_sectors else ''
            entry = f"{item.entry_plan.entry_price:.2f}" if item.entry_plan and item.entry_plan.entry_price > 0 else '-'
            notes = item.notes[:25] + ".." if len(item.notes) > 25 else item.notes
            print(f"{level_emoji}{item.code:<8}{item.name:<10}{item.attention_level:<8}"
                  f"{strategy_emoji}{item.strategy_type:<10}{sectors:<18}{entry:<8}{notes}")
        
        print(f"{'='*100}")
        
        # 统计信息
        high = len(self.get_by_attention_level('特别关注'))
        medium = len(self.get_by_attention_level('一般关注'))
        low = len(self.get_by_attention_level('观察'))
        print(f"总计: {len(self.watchlist)} 只 | 🔴特别关注:{high} 🟡一般关注:{medium} 🟢观察:{low}")
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        stats = {
            'total': len(self.watchlist),
            'by_attention': {'特别关注': 0, '一般关注': 0, '观察': 0},
            'by_strategy': {},
            'by_sector': {}
        }
        
        for item in self.watchlist.values():
            # 按关注级别统计
            if item.attention_level in stats['by_attention']:
                stats['by_attention'][item.attention_level] += 1
            
            # 按策略统计
            strategy = item.strategy_type
            stats['by_strategy'][strategy] = stats['by_strategy'].get(strategy, 0) + 1
            
            # 按板块统计
            for sector in item.linked_sectors:
                stats['by_sector'][sector] = stats['by_sector'].get(sector, 0) + 1
        
        return stats
    
    def clear(self) -> None:
        """清空"""
        self.watchlist.clear()
        self._save()
        print("已清空自选股")


# 单例
_watchlist_memory_v2 = None

def get_watchlist_memory_v2(data_file: str = None) -> WatchlistMemoryV2:
    """获取管理器单例"""
    global _watchlist_memory_v2
    if _watchlist_memory_v2 is None:
        _watchlist_memory_v2 = WatchlistMemoryV2(data_file)
    return _watchlist_memory_v2


# 兼容函数：从V1迁移到V2
def migrate_from_v1(v1_data_file: str = None, v2_data_file: str = None) -> int:
    """从V1迁移数据到V2"""
    from core.watchlist_memory import get_watchlist_memory
    
    v1 = get_watchlist_memory(v1_data_file)
    v2 = get_watchlist_memory_v2(v2_data_file)
    
    migrated = 0
    for item in v1.get_all():
        # 根据category映射到strategy_type
        strategy_map = {
            '重点监控-追涨': '追涨型',
            '重点监控-低吸': '低吸型',
            '重点监控-潜力': '潜力型',
            '重点监控-抄底': '抄底型',
            '重点监控-优选': '多维优选型',
            '重点监控-震荡': '震荡型',
            '重点监控-补涨': '补涨型',
            '重点监控-价值': '价值型',
            '重点监控-AI算力': '板块龙头',
            '重点监控-半导体': '板块龙头',
            '重点监控-新能源': '板块龙头',
            '重点监控-机器人': '板块龙头',
            '板块龙头': '板块龙头',
            '特别关注-AI算力': '板块龙头',
            '特别关注-CPO': '板块龙头',
            '观察': '手动添加'
        }
        
        strategy = strategy_map.get(item.category, '手动添加')
        attention = '特别关注' if item.priority >= 80 else ('一般关注' if item.priority >= 40 else '观察')
        
        # 解析notes提取选股原因
        selection_reason = SelectionReason(
            primary_reason=item.notes[:50] if item.notes else '从V1迁移',
            selection_time=item.added_date
        )
        
        success = v2.add_with_full_analysis(
            code=item.code,
            name=item.name,
            attention_level=attention,
            strategy_type=strategy,
            selection_reason=selection_reason,
            entry_plan=EntryPlan(),
            linked_sectors=item.tags if item.tags else [],
            notes=item.notes
        )
        
        if success:
            migrated += 1
    
    print(f"迁移完成: {migrated} 只股票从V1迁移到V2")
    return migrated


if __name__ == '__main__':
    # 测试
    wl = get_watchlist_memory_v2()
    wl.display()
