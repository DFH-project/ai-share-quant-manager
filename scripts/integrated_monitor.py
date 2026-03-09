#!/usr/bin/env python3
"""
联动监控体系 - IntegratedMonitor
整合：监控 + 自选管理 + 持仓分析
核心设计：
1. 数据只获取一次
2. 并行分析
3. 统一输出
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_manager import data_manager
from core.parallel_analyzer import parallel_analyzer
from core.watchlist_memory import get_watchlist_memory
from typing import Dict, List
from datetime import datetime
import json
from pathlib import Path


class IntegratedMonitor:
    """联动监控器"""
    
    def __init__(self):
        self.data_manager = data_manager
        self.analyzer = parallel_analyzer
        self.watchlist = get_watchlist_memory()
        
    def load_portfolio(self) -> List[Dict]:
        """加载持仓"""
        try:
            portfolio_path = Path(__file__).parent.parent / 'data' / 'portfolio.json'
            if portfolio_path.exists():
                with open(portfolio_path, 'r', encoding='utf-8') as f:
                    portfolio = json.load(f)
                    return portfolio.get('positions', [])
        except Exception as e:
            print(f"[持仓] 加载失败: {e}")
        return []
    
    def run_monitor(self) -> Dict:
        """
        执行完整监控流程
        
        流程：
        1. 获取大盘数据
        2. 合并所有需要监控的股票（持仓+自选）
        3. 并行获取数据（5只并发）
        4. 并行分析
        5. 生成报告
        """
        print(f"\n[{'='*70}]")
        print(f"📊 联动监控启动 - {datetime.now().strftime('%H:%M:%S')}")
        print(f"[{'='*70}]\n")
        
        # 1. 大盘
        print("1️⃣ 获取大盘数据...")
        market = self.data_manager.get_index_data()
        sh = market.get('上证指数', {})
        print(f"   上证指数: {sh.get('current', 0):.2f} ({sh.get('change_pct', 0):+.2f}%)\n")
        
        # 2. 合并监控列表
        print("2️⃣ 合并监控列表...")
        positions = self.load_portfolio()
        watchlist_items = self.watchlist.get_all()
        
        position_codes = [p['code'] for p in positions]
        watchlist_codes = [item.code for item in watchlist_items]
        
        # 去重合并
        all_codes = list(set(position_codes + watchlist_codes))
        print(f"   持仓: {len(position_codes)}只")
        print(f"   自选: {len(watchlist_codes)}只")
        print(f"   去重后: {len(all_codes)}只\n")
        
        # 3. 并行获取数据（核心优化点）
        print("3️⃣ 并行获取数据（5只并发）...")
        stock_data = self.data_manager.fetch_stock_data(all_codes)
        print(f"   成功获取: {len(stock_data)}/{len(all_codes)}只\n")
        
        # 4. 并行分析（核心优化点）
        print("4️⃣ 并行分析（5只并发）...")
        analysis_results = self.analyzer.analyze_stocks(all_codes, stock_data)
        print(f"   完成分析: {len(analysis_results)}只\n")
        
        # 5. 生成报告
        print("5️⃣ 生成联动报告...\n")
        report = self._generate_report(positions, watchlist_items, stock_data, analysis_results)
        
        return report
    
    def _generate_report(self, positions, watchlist_items, stock_data, analysis_results) -> Dict:
        """生成统一报告"""
        
        # 持仓监控
        print("📈 持仓监控")
        print("-" * 70)
        position_alerts = []
        for pos in positions:
            code = pos['code']
            if code in stock_data and code in analysis_results:
                data = stock_data[code]
                analysis = analysis_results[code]
                
                cost = pos['cost_price']
                current = data['current']
                pnl = (current - cost) / cost * 100
                change = data['change_pct']
                
                emoji = "📉" if change < -3 else "🔴" if change < 0 else "🟢"
                print(f"{emoji} {pos['name']}({code}): {current:.2f} ({change:+.2f}%) 盈亏:{pnl:+.1f}%")
                
                # 持仓健康度
                health = analysis.total_score
                if health < 40:
                    print(f"   ⚠️ 健康度{health:.0f}分，建议关注")
                    position_alerts.append({
                        'code': code,
                        'name': pos['name'],
                        'action': '关注',
                        'reason': f'健康度{health:.0f}分'
                    })
        
        # 策略选股
        print(f"\n🎯 策略选股")
        print("-" * 70)
        
        # 大跌反弹机会
        dip_opportunities = []
        for code, analysis in analysis_results.items():
            if analysis.change_pct < -5 and analysis.total_score > 55:
                dip_opportunities.append(analysis)
        
        if dip_opportunities:
            print("💧 急跌反弹机会:")
            for opp in sorted(dip_opportunities, key=lambda x: x.change_pct)[:5]:
                print(f"   📉 {opp.name}({opp.code}): 跌{opp.change_pct:.1f}% 评分{opp.total_score:.0f}分")
        
        # 强势信号
        strong_signals = []
        for code, analysis in analysis_results.items():
            if analysis.change_pct > 3 and analysis.total_score > 65:
                strong_signals.append(analysis)
        
        if strong_signals:
            print("\n🚀 强势信号:")
            for sig in sorted(strong_signals, key=lambda x: x.change_pct, reverse=True)[:5]:
                print(f"   📈 {sig.name}({sig.code}): 涨{sig.change_pct:.1f}% 评分{sig.total_score:.0f}分")
        
        # 高分标的
        print("\n⭐ 多维度优选(评分>65):")
        top_stocks = [a for a in analysis_results.values() if a.total_score >= 65]
        top_stocks.sort(key=lambda x: x.total_score, reverse=True)
        for s in top_stocks[:5]:
            print(f"   ⭐ {s.name}({s.code}): {s.total_score:.0f}分 - {s.suggestion}")
        
        print(f"\n[{'='*70}]")
        print("✅ 联动监控完成")
        print(f"[{'='*70}]\n")
        
        return {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'positions_count': len(positions),
            'watchlist_count': len(watchlist_items),
            'data_fetched': len(stock_data),
            'analysis_done': len(analysis_results),
            'dip_opportunities': len(dip_opportunities),
            'strong_signals': len(strong_signals),
            'top_stocks': len(top_stocks),
        }


def main():
    """主函数"""
    monitor = IntegratedMonitor()
    report = monitor.run_monitor()
    
    print("📊 监控统计:")
    for key, value in report.items():
        if key != 'timestamp':
            print(f"   {key}: {value}")


if __name__ == '__main__':
    main()
