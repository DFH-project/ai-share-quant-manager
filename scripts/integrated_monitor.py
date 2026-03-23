#!/usr/bin/env python3
"""
integrated_monitor.py - 整合监控入口
整合：盘中监控 + 新闻监控
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.news_monitor import NewsMonitor
from core.watchlist_memory_v2 import get_watchlist_memory_v2
from core.data_fetcher import data_fetcher
from datetime import datetime
import json


def run_integrated_monitoring():
    """运行整合监控"""
    print("\n" + "=" * 80)
    print(f"🤖 A股智能监控系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. 新闻监控（新增）
    print("\n📰 第一步：新闻公告监控")
    print("-" * 60)
    news_monitor = NewsMonitor()
    news_alerts = news_monitor.scan_all_stocks()
    
    if news_alerts:
        print(f"\n⚠️ 发现 {len(news_alerts)} 条重要新闻！")
        high_priority = [a for a in news_alerts if a['priority'] == 'HIGH']
        if high_priority:
            print(f"🚨 其中 {len(high_priority)} 条高优先级，需要立即关注！")
            for alert in high_priority[:3]:
                print(f"\n   🔴 [{alert['name']}] {', '.join(alert['categories'])}")
                print(f"      {alert['title'][:50]}...")
    else:
        print("✅ 最近24小时无重要公告")
    
    # 2. 价格监控
    print("\n\n📈 第二步：价格异动监控")
    print("-" * 60)
    
    price_alerts = []
    watchlist = get_watchlist_memory_v2()
    high_attention = watchlist.get_by_attention_level('特别关注')
    
    if not high_attention:
        print("⚠️ 暂无特别关注股票（检查watchlist配置）")
    else:
        print(f"监控 {len(high_attention)} 只特别关注股...")
        
        codes = [item.code for item in high_attention]
        stock_data = data_fetcher.get_stock_data(codes)
        
        for item in high_attention:
            if item.code not in stock_data:
                continue
            
            data = stock_data[item.code]
            change_pct = data.get('change_pct', 0)
            current_price = data.get('current', 0)
            
            # 检查价格异动
            if abs(change_pct) >= 5:
                price_alerts.append({
                    'code': item.code,
                    'name': item.name,
                    'change_pct': change_pct,
                    'price': current_price,
                    'reason': '大幅波动'
                })
                emoji = "📈" if change_pct > 0 else "📉"
                print(f"{emoji} {item.name}({item.code}): {change_pct:+.2f}% ¥{current_price}")
            
            # 检查止损价
            if item.entry_plan and item.entry_plan.stop_loss > 0:
                if current_price <= item.entry_plan.stop_loss:
                    price_alerts.append({
                        'code': item.code,
                        'name': item.name,
                        'change_pct': change_pct,
                        'price': current_price,
                        'reason': f'跌破止损价¥{item.entry_plan.stop_loss}'
                    })
                    print(f"🚨 {item.name}({item.code}): 跌破止损价！当前¥{current_price}")
        
        if not price_alerts:
            print("✅ 价格无异常波动")
    
    # 3. 综合报告
    print("\n" + "=" * 80)
    print("📊 监控总结")
    print("=" * 80)
    
    total_alerts = len(news_alerts) + len(price_alerts)
    
    if total_alerts == 0:
        print("✅ 一切正常，无警报")
        return 0
    else:
        print(f"⚠️ 共发现 {total_alerts} 个警报：")
        print(f"   - 新闻公告: {len(news_alerts)} 条")
        print(f"   - 价格异动: {len(price_alerts)} 条")
        
        # 生成详细报告
        report = news_monitor.generate_alert_report(news_alerts)
        print(report)
        
        # 建议行动
        high_news = [a for a in news_alerts if a['priority'] == 'HIGH']
        if high_news:
            print("\n" + "=" * 80)
            print("🎯 建议行动：")
            print("=" * 80)
            for alert in high_news:
                if '减持' in alert['categories']:
                    print(f"\n🔴 [{alert['name']}] 出现减持公告！")
                    print(f"   建议：评估持仓，考虑减仓或止损")
                if '监管' in alert['categories']:
                    print(f"\n🔴 [{alert['name']}] 监管相关公告！")
                    print(f"   建议：关注风险，谨慎操作")
        
        return 1  # 有警报


if __name__ == '__main__':
    exit(run_integrated_monitoring())
