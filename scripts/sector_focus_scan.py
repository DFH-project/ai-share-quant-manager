#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重点板块专项监控脚本
监控华为算力、服务器等重点板块
"""
import sys
import argparse
sys.path.insert(0, '/root/.openclaw/workspace/skills/a-share-quant-manager')

from core.sector_tracker import get_sector_tracker
from core.data_fetcher import data_fetcher

def monitor_sectors(sector_names):
    """监控指定板块"""
    tracker = get_sector_tracker()
    
    print("=" * 60)
    print("🔴 重点板块专项监控")
    print("=" * 60)
    print(f"监控时间: {__import__('datetime').datetime.now().strftime('%H:%M:%S')}")
    print(f"重点板块: {', '.join(sector_names)}")
    print()
    
    has_alert = False
    alert_messages = []
    
    for sector_name in sector_names:
        stocks = tracker.get_sector_stocks(sector_name)
        if not stocks:
            print(f"⚠️ 板块 {sector_name} 不存在或为空")
            continue
        
        print(f"\n【{sector_name}】({len(stocks)}只成分股)")
        print("-" * 60)
        
        results = []
        for code in stocks:
            try:
                data = data_fetcher.get_stock_data(code)
                if data:
                    results.append({
                        'code': code,
                        'name': data.get('name', code),
                        'price': data.get('price', 0),
                        'change': data.get('change_percent', 0),
                        'volume': data.get('volume', 0)
                    })
            except:
                pass
        
        # 按涨幅排序
        results.sort(key=lambda x: x['change'], reverse=True)
        
        # 显示所有成分股
        for r in results:
            marker = ''
            if r['change'] > 5:
                marker = '🔥 强势'
                has_alert = True
                alert_messages.append(f"{r['name']}({r['code']}) 大涨{r['change']:+.2f}%")
            elif r['change'] > 3:
                marker = '📈 活跃'
            elif r['change'] < -3:
                marker = '📉 调整'
            elif r['change'] < -5:
                marker = '⚠️ 大跌'
                has_alert = True
                alert_messages.append(f"{r['name']}({r['code']}) 大跌{r['change']:+.2f}%")
            
            name = r['name'][:6].ljust(8)
            print(f"  {r['code']} {name} {r['price']:8.2f} {r['change']:+6.2f}% {marker}")
        
        # 显示板块龙头
        if results:
            leader = max(results, key=lambda x: x['change'])
            print(f"\n  🏆 板块龙头: {leader['name']} {leader['change']:+.2f}%")
        
        # 板块统计
        if results:
            avg_change = sum(r['change'] for r in results) / len(results)
            up_count = len([r for r in results if r['change'] > 0])
            print(f"  📊 平均: {avg_change:+.2f}% | 涨跌: {up_count}/{len(results)}")
    
    print()
    print("=" * 60)
    
    if has_alert:
        print("🚨 异动提醒:")
        for msg in alert_messages:
            print(f"  • {msg}")
    else:
        print("✅ 无异常波动")
    
    print("=" * 60)
    
    return has_alert, alert_messages

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='重点板块监控')
    parser.add_argument('--sectors', type=str, default='华为算力,服务器', 
                        help='监控的板块，用逗号分隔')
    args = parser.parse_args()
    
    sector_list = [s.strip() for s in args.sectors.split(',')]
    has_alert, alerts = monitor_sectors(sector_list)
    
    # 退出码：有异动返回1，方便shell脚本判断
    sys.exit(1 if has_alert else 0)
