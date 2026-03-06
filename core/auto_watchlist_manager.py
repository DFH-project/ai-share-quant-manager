#!/usr/bin/env python3
"""
A股自动选股管理器 - Auto Watchlist Manager
三种策略动态管理自选池：
1. 追涨型：板块龙头，强势股（已有）
2. 潜力型：热门板块核心标的
3. 抄底型：调整后低位企稳的热门股
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import WatchlistMemory, get_watchlist_memory
from typing import List, Dict, Tuple
from datetime import datetime

# 热门板块核心标的（潜力股）
HOT_SECTOR_CORE = {
    'AI算力': ['603019', '000938', '600756', '300418', '002230'],
    '半导体': ['600584', '603160', '002371', '688981', '600460'],
    '新能源': ['300750', '601012', '600438', '002594', '300014'],
    '机器人': ['002050', '300124', '002747', '603486', '688169'],
    '医药': ['600276', '000538', '300760', '603259', '600196'],
    '低空经济': ['002151', '300900', '002097', '000099', '300775'],
    '固态电池': ['300073', '002709', '603659', '300450', '002074'],
}

class AutoWatchlistManager:
    """自动选股管理器 - 三策略选股"""
    
    def __init__(self):
        self.watchlist = get_watchlist_memory()
        self.buy_signals = []  # 买入信号池
        self.potential_stocks = []  # 潜力股池
        self.bottom_fishing = []  # 抄底池
        
    def scan_buy_signals(self, stock_pool: List[str] = None) -> List[Dict]:
        """
        策略1: 追涨型 - 扫描买入信号
        检测条件：
        1. 量价齐升（成交量>5日均量1.5倍 + 涨幅>3%）
        2. 强势上涨（涨幅>5%）
        3. 突破新高
        4. 资金流入
        """
        signals = []
        
        if stock_pool is None:
            stock_pool = self._get_default_scan_pool()
        
        try:
            stock_data = data_fetcher.get_stock_data(stock_pool[:50])
            
            for code, data in stock_data.items():
                signal_score = 0
                reasons = []
                
                # 条件1: 量价齐升
                if data.get('volume_ratio', 0) > 1.5 and data.get('change_pct', 0) > 3:
                    signal_score += 30
                    reasons.append("量价齐升")
                
                # 条件2: 强势上涨
                if data.get('change_pct', 0) > 5:
                    signal_score += 25
                    reasons.append("强势上涨")
                
                # 条件3: 突破新高
                if data.get('high_20d', 0) > 0 and data.get('current', 0) >= data.get('high_20d', 0) * 0.98:
                    signal_score += 20
                    reasons.append("接近20日新高")
                
                # 条件4: 资金流入
                if data.get('main_force_flow', 0) > 0:
                    signal_score += 15
                    reasons.append("主力流入")
                
                if signal_score >= 50:
                    signals.append({
                        'code': code,
                        'name': data.get('name', code),
                        'price': data.get('current', 0),
                        'change_pct': data.get('change_pct', 0),
                        'score': signal_score,
                        'reasons': reasons,
                        'sector': data.get('sector', ''),
                        'strategy': '追涨型',
                        'time': datetime.now().strftime('%H:%M')
                    })
            
            signals.sort(key=lambda x: x['score'], reverse=True)
            self.buy_signals = signals[:10]
            
        except Exception as e:
            print(f"扫描买入信号失败: {e}")
        
        return self.buy_signals
    
    def scan_potential_stocks(self) -> List[Dict]:
        """
        策略2: 潜力型 - 扫描热门板块核心标的
        特征：
        1. 属于热门板块核心标的
        2. 尚未大幅上涨（涨幅<3%）
        3. 有资金关注迹象
        4. 技术形态良好（均线多头排列初期）
        """
        potentials = []
        
        try:
            # 收集所有热门板块核心标的
            all_core_stocks = []
            for sector, codes in HOT_SECTOR_CORE.items():
                all_core_stocks.extend([(code, sector) for code in codes])
            
            # 去重
            unique_stocks = list(set(all_core_stocks))
            codes = [item[0] for item in unique_stocks]
            code_to_sector = {item[0]: item[1] for item in unique_stocks}
            
            stock_data = data_fetcher.get_stock_data(codes)
            
            for code, data in stock_data.items():
                change_pct = data.get('change_pct', 0)
                
                # 条件：尚未大涨但有潜力
                if 0 < change_pct < 3:  # 微涨，有启动迹象
                    score = 0
                    reasons = []
                    
                    # 热门板块加分
                    score += 20
                    reasons.append(f"热门板块-{code_to_sector.get(code, '')}")
                    
                    # 资金流入加分
                    if data.get('main_force_flow', 0) > 0:
                        score += 15
                        reasons.append("资金关注")
                    
                    # 成交量温和放大
                    if data.get('volume_ratio', 0) > 1.2:
                        score += 10
                        reasons.append("量能温和")
                    
                    if score >= 30:
                        potentials.append({
                            'code': code,
                            'name': data.get('name', code),
                            'price': data.get('current', 0),
                            'change_pct': change_pct,
                            'score': score,
                            'reasons': reasons,
                            'sector': code_to_sector.get(code, ''),
                            'strategy': '潜力型',
                            'time': datetime.now().strftime('%H:%M')
                        })
            
            potentials.sort(key=lambda x: x['score'], reverse=True)
            self.potential_stocks = potentials[:8]
            
        except Exception as e:
            print(f"扫描潜力股失败: {e}")
        
        return self.potential_stocks
    
    def scan_bottom_fishing(self, stock_pool: List[str] = None) -> List[Dict]:
        """
        策略3: 抄底型 - 扫描调整后低位企稳的热门股
        特征：
        1. 属于热门板块
        2. 近期调整充分（从高点回调>10%）
        3. 出现企稳信号（缩量十字星、下影线）
        4. 今日微涨或止跌（跌幅<2%）
        """
        bottoms = []
        
        if stock_pool is None:
            # 扫描热门板块核心标的
            stock_pool = []
            for codes in HOT_SECTOR_CORE.values():
                stock_pool.extend(codes)
        
        try:
            stock_data = data_fetcher.get_stock_data(stock_pool[:40])
            
            for code, data in stock_data.items():
                change_pct = data.get('change_pct', 0)
                high_20d = data.get('high_20d', 0)
                current = data.get('current', 0)
                
                # 条件1: 有前期高点且回调充分
                if high_20d > 0 and current < high_20d * 0.90:  # 从20日高点回调>10%
                    score = 0
                    reasons = []
                    
                    # 止跌信号
                    if -2 < change_pct < 2:  # 跌幅收窄或微涨
                        score += 25
                        reasons.append("止跌企稳")
                    
                    # 缩量（抛压减轻）
                    if data.get('volume_ratio', 0) < 0.8:
                        score += 20
                        reasons.append("缩量惜售")
                    
                    # 下影线（支撑有效）
                    if data.get('low', 0) > 0:
                        lower_shadow = (current - data.get('low', current)) / data.get('low', 1) * 100
                        if lower_shadow > 1:  # 有下影线
                            score += 15
                            reasons.append("下方支撑")
                    
                    # 热门板块属性
                    score += 10
                    reasons.append("热门板块调整")
                    
                    if score >= 40:
                        pullback_pct = (high_20d - current) / high_20d * 100
                        bottoms.append({
                            'code': code,
                            'name': data.get('name', code),
                            'price': current,
                            'change_pct': change_pct,
                            'pullback_pct': pullback_pct,
                            'score': score,
                            'reasons': reasons,
                            'strategy': '抄底型',
                            'time': datetime.now().strftime('%H:%M')
                        })
            
            bottoms.sort(key=lambda x: x['score'], reverse=True)
            self.bottom_fishing = bottoms[:8]
            
        except Exception as e:
            print(f"扫描抄底机会失败: {e}")
        
        return self.bottom_fishing
    
    def auto_add_to_watchlist(self, signals: List[Dict] = None, strategy_type: str = "追涨型") -> int:
        """自动将信号股加入自选，按策略分类"""
        if signals is None:
            signals = self.buy_signals
        
        category_map = {
            '追涨型': '重点监控-追涨',
            '潜力型': '重点监控-潜力',
            '抄底型': '重点监控-抄底'
        }
        
        priority_map = {
            '追涨型': 10,
            '潜力型': 8,
            '抄底型': 7
        }
        
        emoji_map = {
            '追涨型': '🚀',
            '潜力型': '💎',
            '抄底型': '🎯'
        }
        
        category = category_map.get(strategy_type, '重点监控')
        priority = priority_map.get(strategy_type, 8)
        emoji = emoji_map.get(strategy_type, '✳️')
        
        added_count = 0
        for signal in signals:
            code = signal['code']
            
            # 如果已存在，更新
            if self.watchlist.exists(code):
                self.watchlist.update(
                    code,
                    category=category,
                    priority=priority,
                    notes=f"{emoji}{strategy_type}:{signal['score']}分 {' '.join(signal['reasons'])} {signal['time']}"
                )
            else:
                # 新加入自选
                self.watchlist.add(
                    code=code,
                    name=signal['name'],
                    category=category,
                    priority=priority,
                    tags=["自动发现", strategy_type],
                    notes=f"{emoji}{strategy_type} {signal['score']}分 {' '.join(signal['reasons'])} 价格:{signal['price']:.2f}"
                )
                added_count += 1
        
        return added_count
    
    def auto_remove_from_watchlist(self) -> int:
        """自动移除走坏的股票"""
        removed_count = 0
        watchlist_items = self.watchlist.get_all()
        
        codes = [item.code for item in watchlist_items]
        if not codes:
            return 0
        
        try:
            stock_data = data_fetcher.get_stock_data(codes)
            
            for item in watchlist_items:
                code = item.code
                if code not in stock_data:
                    continue
                
                data = stock_data[code]
                change_pct = data.get('change_pct', 0)
                
                # 不同策略不同止损条件
                should_remove = False
                remove_reason = ""
                
                if '追涨' in item.category and change_pct < -5:
                    should_remove = True
                    remove_reason = f"追涨股大跌{change_pct:.2f}%"
                
                elif '抄底' in item.category and change_pct < -3:
                    # 抄底失败，继续探底
                    should_remove = True
                    remove_reason = f"抄底失败跌{change_pct:.2f}%"
                
                elif '潜力' in item.category and change_pct < -4:
                    should_remove = True
                    remove_reason = f"潜力股破位跌{change_pct:.2f}%"
                
                if should_remove:
                    self.watchlist.update(
                        code,
                        category="观察",
                        priority=0,
                        notes=f"❌已降级-{remove_reason} {datetime.now().strftime('%H:%M')}"
                    )
                    removed_count += 1
        
        except Exception as e:
            print(f"自动移除检查失败: {e}")
        
        return removed_count
    
    def get_strategy_summary(self) -> Dict[str, List[Dict]]:
        """获取三策略汇总"""
        return {
            '追涨型': self.buy_signals[:5],
            '潜力型': self.potential_stocks[:5],
            '抄底型': self.bottom_fishing[:5]
        }
    
    def run_full_scan(self) -> Dict:
        """完整三策略扫描"""
        print("\n" + "="*60)
        print("🔍 启动三策略全量扫描")
        print("="*60)
        
        # 1. 追涨型扫描
        print("\n【策略1: 追涨型 - 板块龙头+强势股】")
        chase_signals = self.scan_buy_signals()
        chase_added = self.auto_add_to_watchlist(chase_signals, '追涨型')
        print(f"  发现 {len(chase_signals)} 个追涨信号，新增 {chase_added} 只")
        
        # 2. 潜力型扫描
        print("\n【策略2: 潜力型 - 热门板块核心标的】")
        potential_signals = self.scan_potential_stocks()
        potential_added = self.auto_add_to_watchlist(potential_signals, '潜力型')
        print(f"  发现 {len(potential_signals)} 个潜力标的，新增 {potential_added} 只")
        
        # 3. 抄底型扫描
        print("\n【策略3: 抄底型 - 热门板块调整后的低位机会】")
        bottom_signals = self.scan_bottom_fishing()
        bottom_added = self.auto_add_to_watchlist(bottom_signals, '抄底型')
        print(f"  发现 {len(bottom_signals)} 个抄底机会，新增 {bottom_added} 只")
        
        # 4. 清理走坏的股票
        removed = self.auto_remove_from_watchlist()
        print(f"\n  降级 {removed} 只走坏的股票")
        
        print("="*60)
        
        return {
            'chase': {'found': len(chase_signals), 'added': chase_added, 'signals': chase_signals[:3]},
            'potential': {'found': len(potential_signals), 'added': potential_added, 'signals': potential_signals[:3]},
            'bottom': {'found': len(bottom_signals), 'added': bottom_added, 'signals': bottom_signals[:3]},
            'removed': removed
        }
    
    def _get_default_scan_pool(self) -> List[str]:
        """获取默认扫描池"""
        pool = set(self.watchlist.get_codes())
        # 加入热门板块核心标的
        for codes in HOT_SECTOR_CORE.values():
            pool.update(codes)
        return list(pool)


# 单例
_auto_manager = None

def get_auto_manager() -> AutoWatchlistManager:
    """获取自动管理器单例"""
    global _auto_manager
    if _auto_manager is None:
        _auto_manager = AutoWatchlistManager()
    return _auto_manager


if __name__ == '__main__':
    manager = AutoWatchlistManager()
    result = manager.run_full_scan()
    print("\n扫描结果:", result)
