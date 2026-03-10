#!/usr/bin/env python3
"""
板块跟踪模块 - Sector Tracker
跟踪板块轮动，识别领涨板块和龙头股
支持动态板块管理（可添加新板块概念）
"""

import sys
import os
import json
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import get_watchlist_memory
from typing import List, Dict, Tuple
from datetime import datetime

# 默认板块定义
DEFAULT_SECTORS = {
    'AI算力': ['603019', '002230', '000938', '600756', '300418'],
    '半导体': ['600584', '603160', '002371', '688981', '600460'],
    '新能源': ['600733', '002594', '300750', '601012', '600438'],
    '医药': ['603127', '600276', '000538', '300760', '603259'],
    '金融': ['600036', '601318', '600030', '601166', '000001'],
    '消费': ['600519', '000858', '002714', '600887', '603288'],
    '机器人': ['002050', '300124', '002747', '603486', '688169'],
}

class SectorTracker:
    """板块跟踪器 - 支持动态板块管理"""
    
    def __init__(self):
        self.watchlist = get_watchlist_memory()
        self.sector_performance = {}
        self.leaders = {}
        self.SECTORS = self._load_sectors()
    
    def _get_sector_file(self) -> Path:
        """获取板块配置文件路径"""
        current_dir = Path(__file__).parent.parent.absolute()
        return current_dir / "data" / "sectors.json"
    
    def _load_sectors(self) -> Dict[str, List[str]]:
        """加载板块配置（支持动态扩展）"""
        # 默认板块
        sectors = DEFAULT_SECTORS.copy()
        
        # 尝试加载动态板块配置
        try:
            sector_file = self._get_sector_file()
            if sector_file.exists():
                with open(sector_file, 'r', encoding='utf-8') as f:
                    custom_sectors = json.load(f)
                    # 合并自定义板块
                    for sector_name, codes in custom_sectors.items():
                        if sector_name in sectors:
                            # 更新现有板块
                            sectors[sector_name] = list(set(sectors[sector_name] + codes))
                        else:
                            # 添加新板块
                            sectors[sector_name] = codes
                            print(f"加载自定义板块: {sector_name}")
        except Exception as e:
            print(f"加载板块配置失败: {e}")
        
        return sectors
    
    def save_sectors(self) -> bool:
        """保存板块配置到文件"""
        try:
            sector_file = self._get_sector_file()
            sector_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(sector_file, 'w', encoding='utf-8') as f:
                json.dump(self.SECTORS, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存板块配置失败: {e}")
            return False
    
    def add_sector(self, sector_name: str, codes: List[str], save: bool = True) -> bool:
        """添加新板块"""
        if sector_name in self.SECTORS:
            print(f"板块 {sector_name} 已存在，更新成分股")
            self.SECTORS[sector_name] = list(set(self.SECTORS[sector_name] + codes))
        else:
            self.SECTORS[sector_name] = codes
            print(f"新增板块: {sector_name} ({len(codes)}只)")
        
        if save:
            return self.save_sectors()
        return True
    
    def remove_sector(self, sector_name: str, save: bool = True) -> bool:
        """删除板块"""
        if sector_name in self.SECTORS:
            del self.SECTORS[sector_name]
            print(f"删除板块: {sector_name}")
            if save:
                return self.save_sectors()
            return True
        print(f"板块 {sector_name} 不存在")
        return False
    
    def add_stock_to_sector(self, sector_name: str, code: str, save: bool = True) -> bool:
        """向板块添加个股"""
        if sector_name not in self.SECTORS:
            print(f"板块 {sector_name} 不存在")
            return False
        
        if code not in self.SECTORS[sector_name]:
            self.SECTORS[sector_name].append(code)
            print(f"添加 {code} 到板块 {sector_name}")
            if save:
                return self.save_sectors()
        return True
    
    def remove_stock_from_sector(self, sector_name: str, code: str, save: bool = True) -> bool:
        """从板块移除个股"""
        if sector_name not in self.SECTORS:
            return False
        
        if code in self.SECTORS[sector_name]:
            self.SECTORS[sector_name].remove(code)
            print(f"从板块 {sector_name} 移除 {code}")
            if save:
                return self.save_sectors()
        return True
    
    def get_all_sectors(self) -> List[str]:
        """获取所有板块名称"""
        return list(self.SECTORS.keys())
    
    def get_sector_stocks(self, sector_name: str) -> List[str]:
        """获取板块成分股"""
        return self.SECTORS.get(sector_name, [])
    
    def calculate_sector_performance(self) -> Dict[str, Dict]:
        """计算各板块表现 - 优化版：批量获取数据，并行计算"""
        performance = {}
        
        # 1. 收集所有板块的所有股票代码（去重）
        all_codes = set()
        for codes in self.SECTORS.values():
            all_codes.update(codes)
        all_codes = list(all_codes)
        
        print(f"  板块扫描：共 {len(self.SECTORS)} 个板块，{len(all_codes)} 只成分股")
        
        # 2. 一次性批量获取所有股票数据（利用并行优化）
        try:
            all_stock_data = data_fetcher.get_stock_data(all_codes, max_workers=10)
        except Exception as e:
            print(f"  获取板块数据失败: {e}")
            return {}
        
        print(f"  成功获取 {len(all_stock_data)}/{len(all_codes)} 只股票数据")
        
        # 3. 并行计算各板块表现
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def calc_single_sector(args):
            """计算单个板块的表现"""
            sector_name, codes = args
            try:
                total_change = 0
                up_count = 0
                leaders = []
                valid_count = 0
                
                for code in codes:
                    if code not in all_stock_data:
                        continue
                    data = all_stock_data[code]
                    change = data.get('change_pct', 0)
                    total_change += change
                    valid_count += 1
                    
                    if change > 0:
                        up_count += 1
                    
                    leaders.append({
                        'code': code,
                        'name': data.get('name', code),
                        'change_pct': change,
                        'current': data.get('current', 0)
                    })
                
                if valid_count == 0:
                    return None
                
                avg_change = total_change / valid_count
                leaders.sort(key=lambda x: x['change_pct'], reverse=True)
                
                return sector_name, {
                    'avg_change': avg_change,
                    'up_count': up_count,
                    'total_count': valid_count,
                    'leaders': leaders[:3],
                    'leader_code': leaders[0]['code'] if leaders else None
                }
            except Exception as e:
                print(f"  计算板块 {sector_name} 失败: {e}")
                return None
        
        # 使用线程池并行计算各板块
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(calc_single_sector, item): item[0] 
                      for item in self.SECTORS.items()}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    sector_name, data = result
                    performance[sector_name] = data
        
        # 按平均涨幅排序
        self.sector_performance = dict(sorted(
            performance.items(), 
            key=lambda x: x[1]['avg_change'], 
            reverse=True
        ))
        
        return self.sector_performance
    
    def get_top_sectors(self, n: int = 3) -> List[Tuple[str, Dict]]:
        """获取涨幅前N的板块"""
        if not self.sector_performance:
            self.calculate_sector_performance()
        
        return list(self.sector_performance.items())[:n]
    
    def auto_track_sector_leaders(self) -> int:
        """自动跟踪板块龙头并加入自选"""
        added_count = 0
        
        # 获取领涨板块
        top_sectors = self.get_top_sectors(3)
        
        for sector_name, data in top_sectors:
            # 只关注涨幅>1%的板块
            if data['avg_change'] < 1:
                continue
            
            leader = data['leaders'][0] if data['leaders'] else None
            if not leader:
                continue
            
            code = leader['code']
            
            # 如果领涨股涨幅>3%，加入自选关注
            if leader['change_pct'] > 3:
                if not self.watchlist.exists(code):
                    self.watchlist.add(
                        code=code,
                        name=leader['name'],
                        category="板块龙头",
                        priority=8,
                        tags=["板块龙头", sector_name, "领涨"],
                        notes=f"🏆{sector_name}龙头 +{leader['change_pct']:.2f}%"
                    )
                    added_count += 1
                else:
                    # 更新为板块龙头
                    self.watchlist.update(
                        code,
                        category="板块龙头",
                        priority=8,
                        notes=f"🏆{sector_name}龙头 +{leader['change_pct']:.2f}%"
                    )
        
        return added_count
    
    def get_sector_summary(self) -> str:
        """获取板块汇总报告"""
        if not self.sector_performance:
            self.calculate_sector_performance()
        
        lines = ["\n📊 板块轮动监控", "=" * 50]
        
        for sector_name, data in list(self.sector_performance.items())[:5]:
            emoji = "🔥" if data['avg_change'] > 2 else "🟢" if data['avg_change'] > 0 else "🔴"
            lines.append(f"{emoji} {sector_name}: {data['avg_change']:+.2f}% ({data['up_count']}/{data['total_count']})")
            
            # 显示龙头
            for leader in data['leaders'][:2]:
                leader_emoji = "🚀" if leader['change_pct'] > 5 else "📈" if leader['change_pct'] > 0 else "📉"
                lines.append(f"   {leader_emoji} {leader['name']}: {leader['change_pct']:+.2f}%")
        
        lines.append("=" * 50)
        return "\n".join(lines)
    
    def run_sector_scan(self) -> Dict:
        """运行板块扫描"""
        print("\n🔥 启动板块轮动扫描...")
        
        # 1. 计算板块表现
        performance = self.calculate_sector_performance()
        print(f"  扫描了 {len(performance)} 个板块")
        
        # 2. 自动跟踪龙头
        added = self.auto_track_sector_leaders()
        print(f"  新增 {added} 只板块龙头到自选")
        
        return {
            'sectors_scanned': len(performance),
            'top_sector': list(performance.keys())[0] if performance else None,
            'leaders_added': added
        }


# 单例
_sector_tracker = None

def get_sector_tracker() -> SectorTracker:
    """获取板块跟踪器单例"""
    global _sector_tracker
    if _sector_tracker is None:
        _sector_tracker = SectorTracker()
    return _sector_tracker


if __name__ == '__main__':
    tracker = SectorTracker()
    result = tracker.run_sector_scan()
    print(tracker.get_sector_summary())
    print("\n扫描结果:", result)
