#!/usr/bin/env python3
"""
update_fundamental_cache.py - 更新基本面数据缓存
每晚23:00自动运行，更新所有自选股和持仓股的基本面数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from core.enhanced_fundamental import get_enhanced_fundamental_service

def load_all_codes():
    """加载所有需要更新的股票代码"""
    codes = set()
    
    # 1. 加载持仓股
    portfolio_path = Path(__file__).parent.parent / 'data' / 'portfolio.json'
    if portfolio_path.exists():
        with open(portfolio_path) as f:
            pf = json.load(f)
        for pos in pf.get('positions', []):
            codes.add(pos['code'])
    
    # 2. 加载自选股
    watchlist_path = Path(__file__).parent.parent / 'data' / 'watchlist_v2.json'
    if watchlist_path.exists():
        with open(watchlist_path) as f:
            wl = json.load(f)
        for code in wl.get('stocks', {}).keys():
            codes.add(code)
    
    # 3. 加载观察池
    watchlist_old = Path(__file__).parent.parent / 'data' / 'watchlist.json'
    if watchlist_old.exists():
        with open(watchlist_old) as f:
            wl = json.load(f)
        for item in wl.get('stocks', []):
            codes.add(item.get('code', ''))
    
    return list(codes)

def main():
    """主函数"""
    print("\n" + "="*70)
    print("📊 基本面数据缓存更新")
    print("="*70 + "\n")
    
    # 加载所有股票代码
    codes = load_all_codes()
    print(f"共需更新 {len(codes)} 只股票的基本面数据\n")
    
    if not codes:
        print("⚠️ 未找到任何股票代码")
        return
    
    # 更新缓存
    service = get_enhanced_fundamental_service()
    success_count = service.update_all_cache(codes)
    
    print(f"✅ 成功更新 {success_count}/{len(codes)} 只股票的基本面数据")
    print(f"📁 缓存文件: data/fundamental_cache/enhanced_fundamental.json\n")

if __name__ == '__main__':
    main()
