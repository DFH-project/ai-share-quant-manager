#!/usr/bin/env python3
"""
sector_rotation_monitor.py - AI产业链板块轮动监控
追踪资金流向，发现板块轮动机会
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Dict, List
from core.data_fetcher import data_fetcher
from core.memory_cache_manager import CachedDataFetcher
from core.config_manager import cfg


class SectorRotationMonitor:
    """板块轮动监控器"""
    
    def __init__(self):
        self.cached_fetcher = CachedDataFetcher()
        
        # AI产业链细分板块
        self.sectors = {
            'CPO光模块': [
                ('300308', '中际旭创'),
                ('300502', '新易盛'),
                ('300394', '天孚通信'),
                ('002281', '光迅科技'),
            ],
            'AI服务器': [
                ('601138', '工业富联'),
                ('603019', '中科曙光'),
                ('000977', '浪潮信息'),
            ],
            'AI芯片': [
                ('688256', '寒武纪'),
                ('688008', '澜起科技'),
                ('688525', '佰维存储'),
            ],
            '半导体设备': [
                ('002371', '北方华创'),
                ('688012', '中微公司'),
                ('688072', '拓荆科技'),
            ],
            '芯片制造': [
                ('688981', '中芯国际'),
                ('688396', '华润微'),
            ]
        }
    
    def analyze_sector(self, sector_name: str, stocks: List[tuple]) -> Dict:
        """分析单个板块"""
        codes = [s[0] for s in stocks]
        
        try:
            stock_data = self.cached_fetcher.get_stock_data(codes)
        except:
            return None
        
        changes = []
        volumes = []
        leaders = []
        
        for code, name in stocks:
            if code in stock_data:
                data = stock_data[code]
                change = data.get('change_pct', 0)
                volume = data.get('volume', 0)
                
                changes.append(change)
                volumes.append(volume)
                
                if change > 3:
                    leaders.append((name, change, '🔥'))
                elif change < -3:
                    leaders.append((name, change, '❄️'))
        
        if not changes:
            return None
        
        avg_change = sum(changes) / len(changes)
        max_change = max(changes)
        min_change = min(changes)
        
        # 计算板块强度得分
        strength = avg_change + len([c for c in changes if c > 0]) * 0.5
        
        return {
            'name': sector_name,
            'avg_change': avg_change,
            'max_change': max_change,
            'min_change': min_change,
            'strength': strength,
            'leaders': sorted(leaders, key=lambda x: -x[1])[:3],
            'count': len(changes),
            'up_count': len([c for c in changes if c > 0])
        }
    
    def run_monitoring(self):
        """运行板块轮动监控"""
        print("\n" + "="*70)
        print(f"🔄 AI产业链板块轮动监控 - {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        results = []
        
        for sector_name, stocks in self.sectors.items():
            result = self.analyze_sector(sector_name, stocks)
            if result:
                results.append(result)
        
        # 按板块强度排序
        results.sort(key=lambda x: x['strength'], reverse=True)
        
        print("\n📊 板块强度排名:")
        for i, r in enumerate(results, 1):
            emoji = '🥇' if i == 1 else ('🥈' if i == 2 else ('🥉' if i == 3 else f'{i}.'))
            trend_emoji = '📈' if r['avg_change'] > 2 else ('📊' if r['avg_change'] > -2 else '📉')
            up_ratio = r['up_count'] / r['count'] * 100
            print(f"   {emoji} {r['name']:12s} {trend_emoji} {r['avg_change']:+5.2f}% ({r['up_count']}/{r['count']}只涨)")
            
            if r['leaders']:
                print(f"      龙头: {', '.join([f'{n}({e}{c:+.1f}%)' for n, c, e in r['leaders']])}")
        
        # 资金流向判断
        print("\n💰 资金流向分析:")
        top_sector = results[0] if results else None
        bottom_sector = results[-1] if results else None
        
        if top_sector and top_sector['avg_change'] > 2:
            print(f"   🔥 资金流入: {top_sector['name']} (+{top_sector['avg_change']:.1f}%)")
        if bottom_sector and bottom_sector['avg_change'] < -2:
            print(f"   ❄️ 资金流出: {bottom_sector['name']} ({bottom_sector['avg_change']:.1f}%)")
        
        # 轮动建议
        print("\n🎯 轮动策略建议:")
        strong_sectors = [r for r in results if r['avg_change'] > 1.5]
        weak_sectors = [r for r in results if r['avg_change'] < -1.5]
        
        if strong_sectors:
            print(f"   强势板块: {', '.join([r['name'] for r in strong_sectors[:2]])} - 可追涨")
        if weak_sectors:
            print(f"   弱势板块: {', '.join([r['name'] for r in weak_sectors[:2]])} - 等回调或回避")
        
        if not strong_sectors and not weak_sectors:
            print("   板块震荡，无明显轮动信号")
        
        # 缓存统计
        stats = self.cached_fetcher.get_stats()
        print(f"\n💾 数据缓存: 命中率 {stats['hit_rate']}, 条目 {stats['size']}")
        
        return results


if __name__ == '__main__':
    monitor = SectorRotationMonitor()
    monitor.run_monitoring()
