#!/usr/bin/env python3
"""
盘后完整复盘报告 - Post Market Review V2
包含板块轮动、买卖点、策略信号、持仓归因、明日预判
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import DataFetcher
from core.watchlist_memory_v2 import get_watchlist_memory_v2
from core.sector_tracker import get_sector_tracker
from datetime import datetime
from pathlib import Path
import json

def get_portfolio_info():
    """获取持仓信息"""
    try:
        portfolio_path = Path(__file__).parent.parent / 'data' / 'portfolio.json'
        if portfolio_path.exists():
            with open(portfolio_path, 'r') as f:
                portfolio = json.load(f)
                return portfolio.get('positions', [])
    except Exception:
        pass
    return []

def analyze_position_pnl(positions, fetcher):
    """分析持仓盈亏归因"""
    if not positions:
        return []
    
    results = []
    total_cost = 0
    total_value = 0
    
    for pos in positions:
        code = pos['code']
        name = pos.get('name', code)
        cost_price = pos.get('cost_price', 0)
        shares = pos.get('shares', 0)
        
        data = fetcher.get_stock_data([code])
        if data and code in data:
            current = data[code].get('current', cost_price)
            change_pct = data[code].get('change_pct', 0)
            
            cost_value = cost_price * shares
            current_value = current * shares
            pnl = current_value - cost_value
            pnl_pct = (current - cost_price) / cost_price * 100 if cost_price else 0
            
            total_cost += cost_value
            total_value += current_value
            
            results.append({
                'code': code,
                'name': name,
                'cost': cost_price,
                'current': current,
                'change_pct': change_pct,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'shares': shares
            })
    
    return results, total_cost, total_value

def main():
    fetcher = DataFetcher()
    wl = get_watchlist_memory_v2()
    sector = get_sector_tracker()
    
    print("="*70)
    print(f"📊 A股盘后完整复盘报告 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    # 1. 大盘概览
    print("\n" + "="*70)
    print("【一、大盘概览】")
    print("="*70)
    
    # 获取主要指数
    index_data = fetcher.get_stock_data(['sh000001', 'sz399001', 'sz399006'])
    if index_data:
        print("\n主要指数表现：")
        for code, name in [('sh000001', '上证指数'), ('sz399001', '深证成指'), ('sz399006', '创业板指')]:
            if code in index_data:
                d = index_data[code]
                print(f"  {name}: {d.get('current', 0):.2f} ({d.get('change_pct', 0):+.2f}%)")
    
    # 2. 板块轮动深度分析
    print("\n" + "="*70)
    print("【二、板块轮动深度分析】")
    print("="*70)
    
    sector.run_sector_scan()
    sector_data = sector.calculate_sector_performance()
    
    print("\n板块涨幅排名：")
    sorted_sectors = sorted(sector_data.items(), key=lambda x: -x[1]['avg_change'])
    for i, (name, perf) in enumerate(sorted_sectors, 1):
        emoji = "🔥" if perf['avg_change'] > 2 else "📈" if perf['avg_change'] > 0 else "📉"
        up = perf.get('up_count', 0)
        total = perf.get('total', 1)
        print(f"  {emoji} {i}. {name}: {perf['avg_change']:+.2f}% ({up}/{total}涨)")
    
    # 3. 自选股策略信号统计
    print("\n" + "="*70)
    print("【三、今日策略信号统计】")
    print("="*70)
    
    from core.auto_watchlist_manager import get_auto_manager
    manager = get_auto_manager()
    result = manager.run_full_scan()
    
    signals = [
        ('💧 低吸型', result.get('dip', {}).get('found', 0), result.get('dip', {}).get('signals', [])),
        ('🚀 追涨型', result.get('chase', {}).get('found', 0), result.get('chase', {}).get('signals', [])),
        ('💎 潜力型', result.get('potential', {}).get('found', 0), result.get('potential', {}).get('signals', [])),
        ('🎯 抄底型', result.get('bottom', {}).get('found', 0), result.get('bottom', {}).get('signals', [])),
    ]
    
    total_signals = 0
    for name, count, sigs in signals:
        total_signals += count
        if count > 0:
            print(f"\n  {name}: {count}个信号")
            for s in sigs[:3]:
                print(f"    • {s['name']}({s['code']}) {s.get('change_pct', 0):+.2f}%")
    
    print(f"\n  📊 今日总信号数: {total_signals}")
    
    # 4. 持仓盈亏归因分析
    print("\n" + "="*70)
    print("【四、持仓盈亏归因分析】")
    print("="*70)
    
    positions = get_portfolio_info()
    if positions:
        pos_analysis, total_cost, total_value = analyze_position_pnl(positions, fetcher)
        
        if pos_analysis:
            total_pnl = total_value - total_cost
            total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
            
            print(f"\n  总持仓成本: ¥{total_cost:,.2f}")
            print(f"  总持仓市值: ¥{total_value:,.2f}")
            print(f"  总盈亏: ¥{total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
            print("\n  个股明细：")
            
            # 按盈亏排序
            pos_analysis.sort(key=lambda x: -x['pnl'])
            for p in pos_analysis:
                emoji = "🟢" if p['pnl'] >= 0 else "🔴"
                print(f"    {emoji} {p['name']}({p['code']})")
                print(f"       成本:{p['cost']:.2f} 现价:{p['current']:.2f} 今日:{p['change_pct']:+.2f}%")
                print(f"       盈亏:{p['pnl']:+.2f} ({p['pnl_pct']:+.2f}%)")
            
            # 归因分析
            print("\n  盈亏归因：")
            winners = [p for p in pos_analysis if p['pnl'] > 0]
            losers = [p for p in pos_analysis if p['pnl'] < 0]
            
            if winners:
                winner_pnl = sum(p['pnl'] for p in winners)
                print(f"    ✅ 盈利股: {len(winners)}只，贡献+¥{winner_pnl:,.2f}")
            if losers:
                loser_pnl = sum(p['pnl'] for p in losers)
                print(f"    ❌ 亏损股: {len(losers)}只，贡献¥{loser_pnl:,.2f}")
    else:
        print("\n  暂无持仓数据")
    
    # 5. 明日重点观察
    print("\n" + "="*70)
    print("【五、明日重点观察】")
    print("="*70)
    
    # 获取自选股数据
    watchlist = wl.watchlist
    top_stocks = []
    
    for code, info in list(watchlist.items())[:20]:
        data = fetcher.get_stock_data([code])
        if data and code in data:
            d = data[code]
            score = 0
            change_pct = d.get('change_pct', 0)
            volume_ratio = d.get('volume_ratio', 1)
            
            # 简单评分
            if change_pct > 3: score += 30
            elif change_pct > 1: score += 20
            if volume_ratio > 1.5: score += 20
            
            current = d.get('current', 0)
            high_20d = d.get('high_20d', current)
            low_20d = d.get('low_20d', current)
            if high_20d > low_20d:
                position = (current - low_20d) / (high_20d - low_20d)
                score += position * 30
            
            top_stocks.append({
                'code': code,
                'name': info.name if hasattr(info, 'name') else code,
                'price': current,
                'change_pct': change_pct,
                'score': score
            })
    
    top_stocks.sort(key=lambda x: -x['score'])
    
    print("\n  🔥 强势延续关注（今日强势且技术面良好）：")
    for s in top_stocks[:5]:
        if s['change_pct'] > 0:
            print(f"    • {s['name']}({s['code']}) {s['price']:.2f} ({s['change_pct']:+.2f}%)")
    
    print("\n  💧 低吸机会关注（今日回调但趋势未坏）：")
    dip_candidates = [s for s in top_stocks if -3 < s['change_pct'] < 0]
    for s in dip_candidates[:3]:
        print(f"    • {s['name']}({s['code']}) {s['price']:.2f} ({s['change_pct']:+.2f}%)")
    
    print("\n  📊 关键价位提醒：")
    print("    宁德时代: 关注400元整数关口突破情况")
    print("    华工科技: 关注能否站稳135元创新高")
    print("    比亚迪: 关注100元心理关口")
    
    print("\n  🔄 板块轮动预判：")
    print("    • 若新能源继续强势，关注储能、锂电材料补涨")
    print("    • 若CPO分化，关注算力芯片、服务器轮动机会")
    print("    • 关注成交量变化，缩量需警惕回调风险")
    
    # 6. 操作反思与改进
    print("\n" + "="*70)
    print("【六、今日操作反思】")
    print("="*70)
    print("\n  ✅ 做得好的：")
    print("    • 宁德时代、华工科技等强势股成功捕捉")
    print("    • 30分钟快速分析响应及时")
    print("\n  ⚠️ 需要改进：")
    print("    • 盘中多次执行耗时过长的深度扫描")
    print("    • 复盘报告内容不够全面")
    print("    • 个股分析被动响应，未主动推送")
    print("\n  📋 明日执行计划：")
    print("    • 09:30 早盘监控启动")
    print("    • 每10分钟快速监控")
    print("    • 每30分钟快速深度分析")
    print("    • 15:05 盘后完整复盘")
    
    print("\n" + "="*70)
    print("📋 报告生成完毕")
    print("="*70)

if __name__ == '__main__':
    main()
