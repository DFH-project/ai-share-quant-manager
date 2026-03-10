#!/usr/bin/env python3
"""
A股盘后总结分析脚本 - Post-Market Summary
生成当日交易总结和分析报告
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import WatchlistMemory
from datetime import datetime, time

def load_portfolio():
    """加载持仓数据"""
    portfolio_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'portfolio.json')
    if os.path.exists(portfolio_path):
        with open(portfolio_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'cash': 0, 'positions': []}

def is_after_market_close():
    """检查是否已收盘 (15:00后)"""
    now = datetime.now().time()
    close_time = time(15, 0)
    return now >= close_time

def generate_summary():
    """生成盘后总结"""
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n{'='*60}")
    print(f"📊 A股盘后总结报告 - {today}")
    print(f"{'='*60}\n")
    
    try:
        # 获取大盘数据
        print("【大盘概况】")
        market_data = data_fetcher.get_index_data()
        for name, data in market_data.items():
            if data.get('current'):
                emoji = "🟢" if data.get('change_pct', 0) >= 0 else "🔴"
                print(f"  {emoji} {name}: {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        # 获取持仓数据
        portfolio = load_portfolio()
        positions = portfolio.get('positions', [])
        cash = portfolio.get('cash', 0)
        
        if positions:
            print(f"\n【持仓分析】")
            print(f"  持仓数量: {len(positions)}只")
            print(f"  现金余额: {cash:,.0f}元")
            
            all_codes = [p['code'] for p in positions]
            stock_data = data_fetcher.get_stock_data(all_codes)
            
            total_change = 0  # 今日总盈亏金额
            profit_count = 0
            loss_count = 0
            
            for pos in positions:
                code = pos['code']
                name = pos['name']
                try:
                    # 获取K线数据计算昨日和今日价格
                    klines = data_fetcher._get_kline_eastmoney(code, days=5)
                    if len(klines) >= 2:
                        yesterday_close = klines[-2]['close']
                        today_close = klines[-1]['close']
                        
                        # 计算今日涨跌（基于昨日收盘价）
                        change_pct = (today_close - yesterday_close) / yesterday_close * 100
                        change_amt = (today_close - yesterday_close) * pos['quantity']
                        
                        # 计算总盈亏（基于成本价）
                        total_pnl = (today_close - pos['cost_price']) / pos['cost_price'] * 100
                        
                        total_change += change_amt
                        if change_pct >= 0:
                            profit_count += 1
                        else:
                            loss_count += 1
                        
                        emoji = "🟢" if change_pct >= 0 else "🔴"
                        print(f"  {emoji} {name}({code}): {today_close:.2f}")
                        print(f"     今日涨跌: {change_pct:+.2f}% ({change_amt:+.0f}元) | 总盈亏: {total_pnl:+.2f}%")
                except Exception as e:
                    print(f"  ⚪ {name}({code}): 数据获取失败")
            
            print(f"\n  💰 今日总盈亏: {total_change:+.0f}元")
            print(f"  📊 今日涨跌: 盈利{profit_count}只 | 亏损{loss_count}只")
        
        print(f"\n{'='*60}")
        print(f"✅ 盘后总结生成完成")
        print(f"⏰ 下次监控: 次日 9:00")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ 生成总结失败: {e}")
        raise

def main():
    """盘后总结主函数"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 执行A股盘后总结...")
    
    # 检查是否已收盘
    if not is_after_market_close():
        print("⏰ 市场尚未收盘 (15:00后生成总结)")
        return
    
    generate_summary()

if __name__ == '__main__':
    main()
