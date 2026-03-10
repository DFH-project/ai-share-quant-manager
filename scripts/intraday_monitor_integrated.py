#!/usr/bin/env python3
"""
intraday_monitor_integrated.py - 整合版盘中监控
结合V1的板块扫描和V2的自选股分级管理
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import get_watchlist_memory  # V1兼容
from core.watchlist_memory_v2 import get_watchlist_memory_v2, migrate_from_v1
from core.sector_tracker import get_sector_tracker
from core.auto_watchlist_manager import get_auto_manager
from core.multi_dimension_analyzer import get_analyzer
from core.intraday_monitor_v2 import IntradayMonitorV2
from typing import List, Dict
from datetime import datetime
import json


class IntegratedIntradayMonitor:
    """整合版盘中监控 - V1+V2"""
    
    def __init__(self):
        self.watchlist_v1 = get_watchlist_memory()  # 兼容V1
        self.watchlist_v2 = get_watchlist_memory_v2()  # V2分级管理
        self.sector_tracker = get_sector_tracker()
        self.auto_manager = get_auto_manager()
        self.analyzer = get_analyzer()
        self.monitor_v2 = IntradayMonitorV2()
        
        # 确保V2数据已迁移
        if len(self.watchlist_v2.get_all()) == 0 and len(self.watchlist_v1.get_all()) > 0:
            print("首次运行，正在从V1迁移数据到V2...")
            migrate_from_v1()
    
    def run(self, full_scan: bool = True) -> Dict:
        """
        运行整合监控
        
        Args:
            full_scan: 是否执行全量板块扫描（每30分钟一次）
        """
        print("\n" + "="*80)
        print(f"📊 A股盘中监控（整合版）- {datetime.now().strftime('%H:%M:%S')}")
        print("="*80)
        
        # 1. 大盘概况
        self._show_market_overview()
        
        # 2. V2分级监控 - 自选股（核心）
        print("\n" + "-"*80)
        print("🔍 自选股分级监控")
        print("-"*80)
        v2_report = self.monitor_v2.run_full_monitoring()
        
        # 3. 买入信号（特别关注）
        buy_signals = v2_report.get('buy_signals', [])
        
        # 4. 板块扫描（可选，每30分钟）
        sector_signals = []
        if full_scan:
            print("\n" + "-"*80)
            print("🔄 板块轮动扫描")
            print("-"*80)
            sector_signals = self._scan_sectors()
        
        # 5. 五策略选股（可选）
        strategy_signals = []
        if full_scan:
            print("\n" + "-"*80)
            print("🎯 五策略选股扫描")
            print("-"*80)
            strategy_signals = self._run_strategy_scan()
        
        # 6. 汇总报告
        report = self._generate_report(buy_signals, sector_signals, strategy_signals)
        
        return report
    
    def _show_market_overview(self):
        """显示大盘概况"""
        try:
            index_data = data_fetcher.get_index_data()
            sh_change = index_data.get('sh_change_pct', 0)
            sh_emoji = "📈" if sh_change > 0 else "📉"
            
            print(f"\n{sh_emoji} 大盘概况")
            print(f"  上证指数: {index_data.get('sh_index', 0):.2f} ({sh_change:+.2f}%)")
            print(f"  深证成指: {index_data.get('sz_index', 0):.2f} ({index_data.get('sz_change_pct', 0):+.2f}%)")
            print(f"  创业板指: {index_data.get('cy_index', 0):.2f} ({index_data.get('cy_change_pct', 0):+.2f}%)")
        except Exception as e:
            print(f"  获取大盘数据失败: {e}")
    
    def _scan_sectors(self) -> List[Dict]:
        """扫描板块轮动"""
        signals = []
        try:
            sector_data = self.sector_tracker.calculate_sector_performance()
            
            print("\n板块表现:")
            sorted_sectors = sorted(sector_data.items(), 
                                   key=lambda x: x[1]['avg_change'], reverse=True)
            
            for sector_name, perf in sorted_sectors:
                avg_change = perf['avg_change']
                emoji = "🔥" if avg_change > 2 else ("📈" if avg_change > 0 else "📉")
                status = "强势" if avg_change > 1.5 else ("一般" if avg_change > 0 else "弱势")
                
                print(f"  {emoji} {sector_name}: {avg_change:+.2f}% ({perf['up_count']}/{perf['total']}{status})")
                
                # 强势板块提醒
                if avg_change > 2:
                    signals.append({
                        'type': '板块强势',
                        'sector': sector_name,
                        'change': avg_change,
                        'message': f'{sector_name}板块强势上涨{avg_change:.2f}%'
                    })
            
            # 识别板块龙头
            print("\n板块龙头:")
            for sector_name, perf in sorted_sectors[:3]:
                if perf.get('leaders'):
                    for leader in perf['leaders'][:2]:
                        print(f"  🏆 {sector_name}: {leader['name']}({leader['code']}) {leader['change_pct']:+.2f}%")
                        
        except Exception as e:
            print(f"  板块扫描失败: {e}")
        
        return signals
    
    def _run_strategy_scan(self) -> List[Dict]:
        """运行策略扫描"""
        signals = []
        try:
            # 强势股低吸
            dip_signals = self.auto_manager.scan_dip_buy_opportunities()
            if dip_signals:
                print(f"\n💧 强势股低吸机会 ({len(dip_signals)}个):")
                for s in dip_signals[:3]:
                    print(f"  {s['name']}({s['code']}) {s['change_pct']:+.2f}% - {s['suggestion']}")
                    signals.append({
                        'type': '低吸',
                        'code': s['code'],
                        'name': s['name'],
                        'score': s['score']
                    })
            
            # 多维度优选
            multi_signals = self.auto_manager.scan_multi_dimension_opportunities()
            if multi_signals:
                print(f"\n⭐ 多维度优选 ({len(multi_signals)}个):")
                for s in multi_signals[:3]:
                    print(f"  {s['name']}({s['code']}) 综合{s['score']:.0f}分 - {s['suggestion'][:30]}")
                    signals.append({
                        'type': '多维优选',
                        'code': s['code'],
                        'name': s['name'],
                        'score': s['score']
                    })
                    
        except Exception as e:
            print(f"  策略扫描失败: {e}")
        
        return signals
    
    def _generate_report(self, buy_signals: List[Dict], 
                        sector_signals: List[Dict],
                        strategy_signals: List[Dict]) -> Dict:
        """生成监控报告"""
        print("\n" + "="*80)
        print("📋 监控总结")
        print("="*80)
        
        all_signals = buy_signals + sector_signals + strategy_signals
        
        # 按重要性分类
        strong_buy = [s for s in all_signals if s.get('strength') == '强' or s.get('score', 0) >= 70]
        medium_buy = [s for s in all_signals if s.get('strength') == '中等' or 60 <= s.get('score', 0) < 70]
        
        print(f"\n强势买入信号 ({len(strong_buy)}个):")
        for s in strong_buy[:5]:
            emoji = "🚀" if s.get('type') == '追涨' else ("💧" if s.get('type') == '低吸' else "⭐")
            print(f"  {emoji} {s.get('name', '')}({s.get('code', '')}) - {s.get('reason', s.get('message', ''))}")
        
        print(f"\n一般买入信号 ({len(medium_buy)}个):")
        for s in medium_buy[:5]:
            print(f"  • {s.get('name', '')}({s.get('code', '')}) - {s.get('reason', s.get('message', ''))}")
        
        # 统计
        v2_stats = self.watchlist_v2.get_statistics()
        print(f"\n自选股状态:")
        print(f"  总计: {v2_stats['total']}只")
        print(f"  🔴特别关注: {v2_stats['by_attention'].get('特别关注', 0)}只")
        print(f"  🟡一般关注: {v2_stats['by_attention'].get('一般关注', 0)}只")
        print(f"  🟢观察: {v2_stats['by_attention'].get('观察', 0)}只")
        
        print("\n" + "="*80)
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'buy_signals': {
                'strong': strong_buy,
                'medium': medium_buy
            },
            'sector_signals': sector_signals,
            'strategy_signals': strategy_signals,
            'watchlist_stats': v2_stats
        }
    
    def quick_monitor(self):
        """快速监控模式 - 只监控特别关注股票"""
        print("\n" + "="*80)
        print(f"⚡ 快速监控模式 - {datetime.now().strftime('%H:%M:%S')}")
        print("="*80)
        
        # 只执行V2高优先级监控
        high_items = self.watchlist_v2.get_by_attention_level('特别关注')
        
        if not high_items:
            print("暂无特别关注股票")
            return
        
        print(f"\n🔴 特别关注 ({len(high_items)}只):")
        
        codes = [item.code for item in high_items]
        stock_data = data_fetcher.get_stock_data(codes)
        
        alerts = []
        for item in high_items:
            if item.code not in stock_data:
                continue
            
            data = stock_data[item.code]
            change_pct = data.get('change_pct', 0)
            price = data.get('current', 0)
            
            emoji = item.get_strategy_emoji()
            
            # 重要波动提醒
            if abs(change_pct) >= 3:
                alert_emoji = "🔥" if change_pct > 0 else "❄️"
                print(f"  {alert_emoji} {emoji} {item.name}({item.code}) {change_pct:+.2f}% {price:.2f}")
                alerts.append({
                    'code': item.code,
                    'name': item.name,
                    'change_pct': change_pct,
                    'price': price
                })
            else:
                print(f"  {emoji} {item.name}({item.code}) {change_pct:+.2f}% {price:.2f}")
        
        print(f"\n提醒: {len(alerts)}只股票波动超过3%")
        return alerts


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='A股盘中监控（整合版）')
    parser.add_argument('--quick', action='store_true', help='快速模式（只监控特别关注）')
    parser.add_argument('--full', action='store_true', help='全量模式（包含板块扫描）')
    parser.add_argument('--v2-list', action='store_true', help='显示V2自选股列表')
    parser.add_argument('--detail', type=str, help='查看某只股票的详细分析')
    
    args = parser.parse_args()
    
    monitor = IntegratedIntradayMonitor()
    
    if args.v2_list:
        # 显示V2列表
        wl = get_watchlist_memory_v2()
        wl.display()
    
    elif args.detail:
        # 查看详细分析
        from scripts.add_stock_with_analysis import view_stock_detail
        view_stock_detail(args.detail)
    
    elif args.quick:
        # 快速模式
        monitor.quick_monitor()
    
    else:
        # 标准模式（默认）
        full_scan = args.full
        monitor.run(full_scan=full_scan)


if __name__ == '__main__':
    main()
