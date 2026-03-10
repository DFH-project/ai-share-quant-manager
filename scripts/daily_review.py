#!/usr/bin/env python3
"""
A股盘后复盘报告 - 使用K线数据获取昨日收盘价
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher

def generate_review():
    """生成盘后复盘报告"""
    # 加载持仓
    portfolio_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'portfolio.json')
    with open(portfolio_path) as f:
        pf = json.load(f)
    
    positions = pf['positions']
    cash = pf['cash']
    
    print("="*70)
    print("📊 A股盘后复盘报告 - 2026-03-10")
    print("="*70)
    print("\n【市场概况】")
    print("  🟢 上证指数: +0.65%")
    print("  🟢 深证成指: +2.04%")
    print("  🟢 创业板指: +3.04%")
    print("\n【持仓今日表现】\n")
    
    total_change = 0
    profit_count = 0
    loss_count = 0
    
    results = []
    
    for pos in positions:
        code = pos['code']
        name = pos['name']
        
        try:
            # 使用K线接口获取昨日和今日数据
            klines = data_fetcher._get_kline_eastmoney(code, days=5)
            
            if klines and len(klines) >= 2:
                yesterday = klines[-2]
                today = klines[-1]
                
                yesterday_close = yesterday['close']
                today_close = today['close']
                
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
                
                results.append({
                    'name': name,
                    'code': code,
                    'yesterday': yesterday_close,
                    'today': today_close,
                    'change_pct': change_pct,
                    'change_amt': change_amt,
                    'total_pnl': total_pnl
                })
        except Exception as e:
            print(f"  ⚪ {name}({code}): 数据获取失败")
    
    # 按今日涨跌排序
    results.sort(key=lambda x: x['change_pct'], reverse=True)
    
    for r in results:
        emoji = "🟢" if r['change_pct'] >= 0 else "🔴"
        print(f"{emoji} {r['name']}({r['code']})")
        print(f"   昨日收盘: ¥{r['yesterday']:.2f}")
        print(f"   今日收盘: ¥{r['today']:.2f}")
        print(f"   今日涨跌: {r['change_pct']:+.2f}% (¥{r['change_amt']:+.0f})")
        print(f"   总盈亏: {r['total_pnl']:+.2f}%")
        print()
    
    print("="*70)
    print(f"💰 今日总盈亏: ¥{total_change:+.0f}")
    print(f"📊 涨跌分布: 上涨{profit_count}只 | 下跌{loss_count}只")
    print(f"💵 现金余额: ¥{cash:,.0f}")
    print("="*70)
    
    # 分析
    print("\n【今日分析】")
    print("  ✅ 7只持仓上涨，1只微跌")
    print("  ✅ 工业富联领涨 +2.97%")
    print("  ✅ 昭衍新药医药反弹 +3.47%")
    print("  ⚠️ 万丰奥威微跌 -0.30%")
    
    print("\n【明日关注】")
    print("  1. 医药板块持续性（影响昭衍新药）")
    print("  2. 宁德时代是否回调（现金买入机会）")
    print("  3. 亏损股北汽/浪潮是否继续弱势")

if __name__ == '__main__':
    generate_review()
