#!/usr/bin/env python3
"""
快速深度分析 - 30分钟版
并发分析自选股池（最多50只），输出得分靠前的股票
跳过耗时的基本面数据获取，专注技术面+资金面+趋势评分
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import DataFetcher
from core.watchlist_memory_v2 import get_watchlist_memory_v2
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
from pathlib import Path

def analyze_single_stock(code, name, fetcher):
    """分析单只股票 - 快速版（跳过多维基本面）"""
    try:
        data = fetcher.get_stock_data([code])
        if not data or code not in data:
            return None
        
        d = data[code]
        current = d.get('current', 0)
        change_pct = d.get('change_pct', 0)
        volume_ratio = d.get('volume_ratio', 1)
        
        # 简单评分（技术面为主）
        score = 50  # 基础分
        
        # 趋势分（股价相对20日高低点位置）
        high_20d = d.get('high_20d', current)
        low_20d = d.get('low_20d', current)
        if high_20d > low_20d:
            position = (current - low_20d) / (high_20d - low_20d)
            score += position * 20  # 0-20分
        
        # 涨幅分
        if change_pct > 5:
            score += 15
        elif change_pct > 3:
            score += 10
        elif change_pct > 1:
            score += 5
        elif change_pct < -3:
            score -= 10
        
        # 量能分
        if volume_ratio > 2:
            score += 10
        elif volume_ratio > 1.5:
            score += 5
        
        # 均线分
        ma5 = d.get('ma5', current)
        ma20 = d.get('ma20', current)
        if current > ma5 > ma20:
            score += 5
        elif current < ma5 < ma20:
            score -= 5
        
        return {
            'code': code,
            'name': name,
            'price': current,
            'change_pct': change_pct,
            'volume_ratio': volume_ratio,
            'score': min(100, max(0, score)),
            'ma5': ma5,
            'ma20': ma20
        }
    except Exception as e:
        return None

def main():
    fetcher = DataFetcher()
    
    # 获取自选股池
    wl = get_watchlist_memory_v2()
    watchlist_dict = wl.watchlist
    
    # 转换为列表并最多取50只
    stocks = []
    for code, info in list(watchlist_dict.items())[:50]:
        stocks.append({
            'code': code,
            'name': info.name if hasattr(info, 'name') else code
        })
    
    print(f"🔍 快速深度分析 | {datetime.now().strftime('%H:%M')}")
    print(f"分析股票数: {len(stocks)}只\n")
    
    # 并发分析
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(analyze_single_stock, s['code'], s['name'], fetcher): s 
            for s in stocks
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    # 按得分排序
    results.sort(key=lambda x: -x['score'])
    
    # 输出报告
    print("="*60)
    print("📊 自选股评分排名（前15名）")
    print("="*60)
    print(f"{'排名':<4} {'名称':<10} {'代码':<8} {'价格':<8} {'涨幅':<8} {'量能':<6} {'得分':<6}")
    print("-"*60)
    
    top15 = results[:15]
    for i, r in enumerate(top15, 1):
        change_str = f"{r['change_pct']:+.2f}%"
        vol_str = f"{r['volume_ratio']:.2f}"
        print(f"{i:<4} {r['name']:<10} {r['code']:<8} {r['price']:<8.2f} {change_str:<8} {vol_str:<6} {r['score']:<6.0f}")
    
    print("\n" + "="*60)
    print("🔥 重点推荐（得分≥70）")
    print("="*60)
    
    high_score = [r for r in results if r['score'] >= 70]
    if high_score:
        for r in high_score[:5]:
            trend = "🟢多头" if r['price'] > r['ma5'] > r['ma20'] else "🔴调整"
            print(f"⭐ {r['name']}({r['code']}) {r['price']:.2f} {r['change_pct']:+.2f}% | 得分{r['score']:.0f} | {trend}")
    else:
        print("暂无得分≥70的股票")
    
    print("\n" + "="*60)
    print("💧 低吸关注（跌幅>-3%且得分≥55）")
    print("="*60)
    
    dip_candidates = [r for r in results if -3 < r['change_pct'] < 0 and r['score'] >= 55]
    if dip_candidates:
        for r in dip_candidates[:3]:
            print(f"💧 {r['name']}({r['code']}) {r['price']:.2f} {r['change_pct']:+.2f}% | 得分{r['score']:.0f}")
    else:
        print("暂无符合条件的低吸标的")
    
    # 保存报告
    report_path = Path(__file__).parent.parent / 'data' / 'quick_analysis_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"🔍 快速深度分析 | {datetime.now().strftime('%H:%M')}\n\n")
        f.write("="*60 + "\n")
        f.write("📊 自选股评分排名（前15名）\n")
        f.write("="*60 + "\n")
        for i, r in enumerate(top15, 1):
            f.write(f"{i}. {r['name']}({r['code']}) {r['price']:.2f} {r['change_pct']:+.2f}% 得分{r['score']:.0f}\n")
        
        f.write("\n" + "="*60 + "\n")
        f.write("🔥 重点推荐（得分≥70）\n")
        f.write("="*60 + "\n")
        if high_score:
            for r in high_score[:5]:
                f.write(f"⭐ {r['name']}({r['code']}) {r['price']:.2f} {r['change_pct']:+.2f}% 得分{r['score']:.0f}\n")
        else:
            f.write("暂无得分≥70的股票\n")
    
    print(f"\n📋 报告已保存: {report_path}")
    return results

if __name__ == '__main__':
    main()
