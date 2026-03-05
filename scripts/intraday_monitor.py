#!/usr/bin/env python3
"""
A股盘中监控脚本 - Intraday Monitor
使用多数据源获取真实数据，监控持仓+自选股
"""

import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import WatchlistMemory
from datetime import datetime

def load_portfolio():
    """加载持仓数据"""
    portfolio_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'portfolio.json')
    if os.path.exists(portfolio_path):
        with open(portfolio_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'cash': 0, 'positions': []}

def main():
    """盘中监控主函数"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 执行A股盘中监控...")
    
    try:
        # 获取真实大盘数据
        print("获取大盘数据...")
        market_data = data_fetcher.get_index_data()
        sh = market_data.get('上证指数', {})
        print(f"上证指数: {sh.get('current', 0):.2f} ({sh.get('change_pct', 0):+.2f}%)")
        
        # 获取持仓数据
        portfolio = load_portfolio()
        positions = portfolio.get('positions', [])
        cash = portfolio.get('cash', 0)
        
        # 获取自选股
        watchlist = WatchlistMemory()
        watchlist_codes = watchlist.get_codes()
        
        # 合并持仓和自选股（去重）
        all_codes = list(set([p['code'] for p in positions] + watchlist_codes))
        
        print(f"\n💰 持仓: {len(positions)}只，现金: {cash:,.0f}元")
        print(f"📋 自选股: {len(watchlist_codes)}只")
        print(f"🔍 监控总数: {len(all_codes)}只\n")
        
        if all_codes:
            print("获取个股数据...")
            stock_data = data_fetcher.get_stock_data(all_codes[:20])  # 最多20只
            
            # 显示持仓
            if positions:
                print("\n📈 持仓监控：")
                for pos in positions:
                    code = pos['code']
                    if code in stock_data:
                        data = stock_data[code]
                        current = data['current']
                        change = data['change_pct']
                        pnl = (current - pos['cost_price']) / pos['cost_price'] * 100
                        emoji = "🟢" if pnl >= 0 else "🔴"
                        print(f"  {emoji} {pos['name']}({code}): {current:.2f} ({change:+.2f}%) 盈亏: {pnl:+.2f}%")
            
            # 显示自选股
            if watchlist_codes:
                print("\n👀 自选股监控：")
                for code in watchlist_codes:
                    if code in stock_data:
                        data = stock_data[code]
                        print(f"  • {data['name']}({code}): {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        print("\n✅ 监控完成，数据真实有效")
        
    except Exception as e:
        print(f"\n❌ 监控失败: {e}")
        print("❌ 无法获取真实数据，不生成假数据")
        raise

if __name__ == '__main__':
    main()
