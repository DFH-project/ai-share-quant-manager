#!/usr/bin/env python3
"""
A股盘中监控脚本 - Intraday Monitor
使用多数据源获取真实数据，监控持仓+自选股
交易时间: 9:00-15:00
新增：三策略选股（追涨+潜力+抄底）、板块跟踪、重点监控
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import WatchlistMemory
from core.auto_watchlist_manager import get_auto_manager
from core.sector_tracker import get_sector_tracker
from datetime import datetime, time

def load_portfolio():
    """加载持仓数据"""
    portfolio_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'portfolio.json')
    if os.path.exists(portfolio_path):
        with open(portfolio_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'cash': 0, 'positions': []}

def is_trading_time():
    """检查是否在A股交易时间 (9:00-15:00)"""
    now = datetime.now().time()
    start_time = time(9, 0)
    end_time = time(15, 0)
    return start_time <= now <= end_time

def get_minute_of_day():
    """获取当天分钟数（用于判断扫描频率）"""
    now = datetime.now()
    return now.hour * 60 + now.minute

def should_run_full_scan():
    """判断是否运行全量扫描（每30分钟一次）"""
    minute = get_minute_of_day()
    # 9:00, 9:30, 10:00, 10:30, 11:00, 11:30, 13:00, 13:30, 14:00, 14:30
    return minute in [540, 570, 600, 630, 660, 690, 780, 810, 840, 870]

def main():
    """盘中监控主函数"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 执行A股盘中监控...")
    
    # 检查是否在交易时间
    if not is_trading_time():
        print("⏰ 当前不在A股交易时间 (9:00-15:00)，跳过监控")
        return
    
    try:
        # ===== 1. 大盘数据 =====
        print("\n" + "="*60)
        print("📊 大盘概况")
        print("="*60)
        market_data = data_fetcher.get_index_data()
        sh = market_data.get('上证指数', {})
        print(f"上证指数: {sh.get('current', 0):.2f} ({sh.get('change_pct', 0):+.2f}%)")
        
        # 显示其他指数
        for name in ['深证成指', '创业板指', '科创50']:
            if name in market_data:
                data = market_data[name]
                emoji = "🟢" if data.get('change_pct', 0) >= 0 else "🔴"
                print(f"{emoji} {name}: {data.get('current', 0):.2f} ({data.get('change_pct', 0):+.2f}%)")
        
        # ===== 2. 板块轮动（每30分钟扫描） =====
        scan_results = None
        if should_run_full_scan():
            print("\n" + "="*60)
            print("🔥 板块轮动扫描")
            print("="*60)
            sector_tracker = get_sector_tracker()
            sector_result = sector_tracker.run_sector_scan()
            print(sector_tracker.get_sector_summary())
            
            # ===== 3. 三策略选股扫描（每30分钟） =====
            print("\n" + "="*60)
            print("✨ 三策略选股扫描")
            print("="*60)
            auto_manager = get_auto_manager()
            scan_results = auto_manager.run_full_scan()
        
        # ===== 4. 获取数据 =====
        portfolio = load_portfolio()
        positions = portfolio.get('positions', [])
        cash = portfolio.get('cash', 0)
        
        watchlist = WatchlistMemory()
        watchlist_codes = watchlist.get_codes()
        
        # 合并监控列表
        all_codes = list(set([p['code'] for p in positions] + watchlist_codes))
        
        print(f"\n" + "="*60)
        print(f"💼 账户概况")
        print("="*60)
        print(f"💰 持仓: {len(positions)}只 | 现金: {cash:,.0f}元")
        print(f"📋 自选股: {len(watchlist_codes)}只 | 🔍 监控总数: {len(all_codes)}只")
        
        if all_codes:
            stock_data = data_fetcher.get_stock_data(all_codes[:40])
            
            # ===== 5. 策略1: 追涨型（板块龙头+强势股） =====
            chase_items = [item for item in watchlist.get_all() if '追涨' in item.category]
            if chase_items:
                print("\n" + "="*60)
                print("🚀 重点监控-追涨型（板块龙头+强势股）")
                print("="*60)
                
                for item in sorted(chase_items, key=lambda x: x.priority, reverse=True)[:5]:
                    code = item.code
                    if code in stock_data:
                        data = stock_data[code]
                        current = data['current']
                        change = data['change_pct']
                        
                        # 判断买入建议
                        if change > 3:
                            status = "✅ 强势-可考虑追涨"
                        elif change > 0:
                            status = "⚠️ 温和-继续观察"
                        else:
                            status = "❌ 转弱-放弃追涨"
                        
                        print(f"🚀 {item.name}({code}): {current:.2f} ({change:+.2f}%)")
                        print(f"   {status} | {item.notes[:50]}")
            
            # ===== 6. 策略2: 潜力型（热门板块核心标的） =====
            potential_items = [item for item in watchlist.get_all() if '潜力' in item.category]
            if potential_items:
                print("\n" + "="*60)
                print("💎 重点监控-潜力型（热门板块核心标的）")
                print("="*60)
                
                for item in sorted(potential_items, key=lambda x: x.priority, reverse=True)[:5]:
                    code = item.code
                    if code in stock_data:
                        data = stock_data[code]
                        current = data['current']
                        change = data['change_pct']
                        
                        # 判断启动信号
                        if change > 2:
                            status = "✅ 启动-开始上涨"
                        elif 0 < change <= 2:
                            status = "⏳ 蓄势-等待放量"
                        else:
                            status = "📝 观察-暂未启动"
                        
                        print(f"💎 {item.name}({code}): {current:.2f} ({change:+.2f}%)")
                        print(f"   {status} | {item.notes[:50]}")
            
            # ===== 7. 策略3: 抄底型（调整后低位企稳） =====
            bottom_items = [item for item in watchlist.get_all() if '抄底' in item.category]
            if bottom_items:
                print("\n" + "="*60)
                print("🎯 重点监控-抄底型（热门板块调整后的低位机会）")
                print("="*60)
                
                for item in sorted(bottom_items, key=lambda x: x.priority, reverse=True)[:5]:
                    code = item.code
                    if code in stock_data:
                        data = stock_data[code]
                        current = data['current']
                        change = data['change_pct']
                        
                        # 判断企稳信号
                        if change > 1:
                            status = "✅ 企稳-开始反弹"
                        elif -1 <= change <= 1:
                            status = "⏳ 筑底-观察确认"
                        else:
                            status = "❌ 弱势-继续等待"
                        
                        print(f"🎯 {item.name}({code}): {current:.2f} ({change:+.2f}%)")
                        print(f"   {status} | {item.notes[:50]}")
            
            # ===== 8. 板块龙头监控（兼容旧分类） =====
            sector_items = watchlist.get_by_category("板块龙头")
            if sector_items:
                print("\n" + "="*60)
                print("🏆 板块龙头监控")
                print("="*60)
                
                for item in sorted(sector_items, key=lambda x: x.priority, reverse=True)[:5]:
                    code = item.code
                    if code in stock_data:
                        data = stock_data[code]
                        print(f"📈 {item.name}({code}): {data['current']:.2f} ({data['change_pct']:+.2f}%)")
            
            # ===== 9. 持仓监控 =====
            if positions:
                print("\n" + "="*60)
                print("📈 持仓监控")
                print("="*60)
                
                for pos in positions:
                    code = pos['code']
                    if code in stock_data:
                        data = stock_data[code]
                        current = data['current']
                        change = data['change_pct']
                        pnl = (current - pos['cost_price']) / pos['cost_price'] * 100
                        emoji = "🟢" if pnl >= 0 else "🔴"
                        print(f"{emoji} {pos['name']}({code}): {current:.2f} ({change:+.2f}%) 盈亏: {pnl:+.2f}%")
            
            # ===== 10. 形态走坏降级提示 =====
            degraded_items = [item for item in watchlist.get_all() if "❌已降级" in item.notes]
            if degraded_items:
                print("\n" + "="*60)
                print("⚠️ 已取消重点监控（形态走坏）")
                print("="*60)
                for item in degraded_items[:3]:
                    code = item.code
                    if code in stock_data:
                        data = stock_data[code]
                        print(f"❌ {item.name}({code}): {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        # ===== 11. 买入建议总结 =====
        print("\n" + "="*60)
        print("💡 买入建议总结")
        print("="*60)
        
        buy_recommendations = []
        for item in watchlist.get_all():
            code = item.code
            if code in stock_data and ('追涨' in item.category or '潜力' in item.category or '抄底' in item.category):
                data = stock_data[code]
                change = data['change_pct']
                if change > 3:
                    strategy = '🚀' if '追涨' in item.category else '💎' if '潜力' in item.category else '🎯'
                    buy_recommendations.append(f"{strategy}{item.name}({code}) +{change:.2f}%")
        
        if buy_recommendations:
            print("✅ 强势信号（涨幅>3%）：" + ", ".join(buy_recommendations[:5]))
        else:
            print("⏳ 暂无强势买入信号，继续观察三策略监控池")
            print("   追涨型：等待板块龙头放量突破")
            print("   潜力型：等待热门股启动信号")
            print("   抄底型：等待调整企稳确认")
        
        print("\n" + "="*60)
        print(f"✅ 监控完成 [{datetime.now().strftime('%H:%M:%S')}]")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 监控失败: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == '__main__':
    main()
