#!/usr/bin/env python3
"""
A股早盘分析脚本 - Morning Routine
生成开盘前市场分析报告
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import WatchlistMemory
from datetime import datetime

def main():
    """早盘分析主函数"""
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n{'='*60}")
    print(f"📊 A股早盘分析报告 - {today}")
    print(f"{'='*60}\n")
    
    try:
        # 获取大盘数据
        print("【大盘概况】")
        market_data = data_fetcher.get_index_data()
        for name, data in market_data.items():
            if data.get('current'):
                emoji = "🟢" if data.get('change_pct', 0) >= 0 else "🔴"
                print(f"  {emoji} {name}: {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        # 获取自选股
        watchlist = WatchlistMemory()
        items = watchlist.get_all()
        
        # 优先显示特别关注
        focus_items = [i for i in items if '特别关注' in i.category]
        focus_items.sort(key=lambda x: x.priority, reverse=True)
        
        if focus_items:
            print(f"\n【⭐ 特别关注 - AI算力板块】")
            focus_codes = [i.code for i in focus_items]
            stock_data = data_fetcher.get_stock_data(focus_codes)
            
            for item in focus_items[:6]:
                if item.code in stock_data:
                    data = stock_data[item.code]
                    emoji = "🟢" if data['change_pct'] >= 0 else "🔴"
                    print(f"  {emoji} {data['name']}({item.code}): {data['current']:.2f} ({data['change_pct']:+.2f}%)")
                    if item.notes:
                        # 提取买入建议
                        if '买入价' in item.notes or '等待' in item.notes:
                            print(f"     💡 {item.notes.split('综合')[1] if '综合' in item.notes else item.notes}")
        
        # 其他自选股
        other_items = [i for i in items if '特别关注' not in i.category]
        if other_items:
            print(f"\n【自选股关注】")
            other_codes = [i.code for i in other_items[:5]]
            stock_data = data_fetcher.get_stock_data(other_codes)
            for code in other_codes:
                if code in stock_data:
                    data = stock_data[code]
                    emoji = "🟢" if data['change_pct'] >= 0 else "🔴"
                    print(f"  {emoji} {data['name']}({code}): {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        print(f"\n{'='*60}")
        print(f"✅ 早盘分析完成 - 祝交易顺利！")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        raise

if __name__ == '__main__':
    main()
