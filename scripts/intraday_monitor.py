#!/usr/bin/env python3
"""
A股盘中监控脚本 - Intraday Monitor (并行优化版)
使用多数据源获取真实数据，监控持仓+自选股
交易时间: 9:00-15:00
新增：五策略选股（低吸+追涨+潜力+抄底+多维度优选）、板块跟踪、重点监控
优化：并行数据获取，减少重复计算
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import WatchlistMemory
from core.auto_watchlist_manager import get_auto_manager
from core.sector_tracker import get_sector_tracker
from core.smart_rebalance_advisor import SmartRebalanceAdvisor
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

def print_strategy_items(items, stock_data, strategy_name, strategy_emoji, status_func):
    """统一打印策略监控项"""
    if not items:
        return
    
    print(f"\n{'='*60}")
    print(f"{strategy_emoji} 重点监控-{strategy_name}")
    print("="*60)
    
    for item in sorted(items, key=lambda x: x.priority, reverse=True)[:5]:
        code = item.code
        if code in stock_data:
            data = stock_data[code]
            current = data['current']
            change = data['change_pct']
            status = status_func(change)
            print(f"{strategy_emoji} {item.name}({code}): {current:.2f} ({change:+.2f}%)")
            print(f"   {status} | {item.notes[:50] if item.notes else ''}")

def main():
    """盘中监控主函数"""
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S')}] 执行A股盘中监控...")
    
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
        
        # ===== 2. 加载账户数据 =====
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
        
        # ===== 3. 并行获取所有股票数据（核心优化）=====
        stock_data = {}
        if all_codes:
            print(f"\n📡 正在并行获取 {len(all_codes)} 只股票数据...")
            stock_data = data_fetcher.get_stock_data(all_codes[:40], max_workers=10)
        
        # ===== 4. 板块轮动（每30分钟扫描） =====
        scan_results = None
        if should_run_full_scan():
            print("\n" + "="*60)
            print("🔥 板块轮动扫描")
            print("="*60)
            sector_tracker = get_sector_tracker()
            sector_result = sector_tracker.run_sector_scan()
            print(sector_tracker.get_sector_summary())
            
            # ===== 5. 三策略选股扫描（每30分钟） =====
            print("\n" + "="*60)
            print("✨ 三策略选股扫描")
            print("="*60)
            auto_manager = get_auto_manager()
            scan_results = auto_manager.run_full_scan()
            
            # ===== 6. 智能调仓分析（每30分钟，全量扫描时）=====
            if positions:
                print("\n" + "="*60)
                print("🤖 智能调仓分析")
                print("="*60)
                try:
                    advisor = SmartRebalanceAdvisor()
                    analysis = advisor.generate_full_analysis()
                    rebalance_report = advisor.generate_comprehensive_report(analysis)
                    # 只显示核心建议
                    print(f"  已分析 {len(analysis['health_reports'])} 只持仓股")
                    print(f"  发现 {len(analysis['opportunities'])} 个换仓机会")
                    if analysis['recommendations']:
                        print("\n  核心建议:")
                        for rec in analysis['recommendations'][:3]:
                            print(f"    • {rec['title']}")
                            print(f"      建议: {rec['action'][:50]}")
                except Exception as e:
                    print(f"  调仓分析跳过: {e}")
        
        # ===== 7. 获取所有自选股并按策略分类（只获取一次）=====
        all_items = watchlist.get_all()
        
        # 按策略分类
        dip_items = [item for item in all_items if '低吸' in item.category]
        chase_items = [item for item in all_items if '追涨' in item.category]
        potential_items = [item for item in all_items if '潜力' in item.category]
        bottom_items = [item for item in all_items if '抄底' in item.category]
        multi_items = [item for item in all_items if '优选' in item.category]
        sector_items = watchlist.get_by_category("板块龙头")
        
        # ===== 8. 策略0: 强势股低吸（最优先） =====
        print_strategy_items(
            dip_items, stock_data, "强势股低吸（昨日强势，今日回调）", "💧",
            lambda change: "✅ 理想买点（回调适中）" if -3 <= change <= -1 else 
                          "⚠️ 偏深回调（谨慎）" if -4 <= change < -3 else 
                          "📝 微回调（可等）" if -1 < change < 0 else "❌ 不符预期"
        )
        
        # ===== 9. 策略1: 追涨型（板块龙头+强势股） =====
        print_strategy_items(
            chase_items, stock_data, "追涨型（板块龙头+强势股）", "🚀",
            lambda change: "✅ 强势-可考虑追涨" if change > 3 else 
                          "⚠️ 温和-继续观察" if change > 0 else "❌ 转弱-放弃追涨"
        )
        
        # ===== 10. 策略2: 潜力型（热门板块核心标的） =====
        print_strategy_items(
            potential_items, stock_data, "潜力型（热门板块核心标的）", "💎",
            lambda change: "✅ 启动-开始上涨" if change > 2 else 
                          "⏳ 蓄势-等待放量" if 0 < change <= 2 else "📝 观察-暂未启动"
        )
        
        # ===== 11. 策略3: 抄底型（调整后低位企稳） =====
        print_strategy_items(
            bottom_items, stock_data, "抄底型（热门板块调整后的低位机会）", "🎯",
            lambda change: "✅ 企稳-开始反弹" if change > 1 else 
                          "⏳ 筑底-观察确认" if -1 <= change <= 1 else "❌ 弱势-继续等待"
        )
        
        # ===== 12. 策略4: 多维度综合优选 =====
        print_strategy_items(
            multi_items, stock_data, "多维度优选（趋势+基本面+资金+技术+板块）", "⭐",
            lambda change: "✅ 强势上涨，综合评分有效" if change > 3 else 
                          "🟢 温和上涨，符合预期" if change > 0 else 
                          "⏳ 小幅调整，观察中" if change > -2 else "⚠️ 跌幅较大，重新评估"
        )
        
        # ===== 13. 板块龙头监控 =====
        if sector_items:
            print(f"\n{'='*60}")
            print("🏆 板块龙头监控")
            print("="*60)
            
            for item in sorted(sector_items, key=lambda x: x.priority, reverse=True)[:5]:
                code = item.code
                if code in stock_data:
                    data = stock_data[code]
                    print(f"📈 {item.name}({code}): {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        # ===== 14. 持仓监控 =====
        if positions:
            print(f"\n{'='*60}")
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
        
        # ===== 15. 形态走坏降级提示 =====
        degraded_items = [item for item in all_items if "❌已降级" in (item.notes or "")]
        if degraded_items:
            print(f"\n{'='*60}")
            print("⚠️ 已取消重点监控（形态走坏）")
            print("="*60)
            for item in degraded_items[:3]:
                code = item.code
                if code in stock_data:
                    data = stock_data[code]
                    print(f"❌ {item.name}({code}): {data['current']:.2f} ({data['change_pct']:+.2f}%)")
        
        # ===== 16. 买入建议总结 =====
        print(f"\n{'='*60}")
        print("💡 买入建议总结")
        print("="*60)
        
        # 强势股低吸优先
        dip_buy = []
        for item in dip_items:
            code = item.code
            if code in stock_data:
                data = stock_data[code]
                change = data['change_pct']
                if -4 <= change <= -1:  # 回调适中
                    dip_buy.append(f"💧{item.name}({code}) {change:.2f}%")
        
        if dip_buy:
            print("✅ 强势股低吸机会（昨日强势，今日回调）：")
            for b in dip_buy[:5]:
                print(f"   {b}")
        
        # 其他策略
        other_buy = []
        for item in all_items:
            code = item.code
            if code in stock_data:
                data = stock_data[code]
                change = data['change_pct']
                if change > 3:
                    if '追涨' in item.category:
                        other_buy.append(f"🚀{item.name}({code}) +{change:.2f}%")
                    elif '潜力' in item.category:
                        other_buy.append(f"💎{item.name}({code}) +{change:.2f}%")
                    elif '抄底' in item.category:
                        other_buy.append(f"🎯{item.name}({code}) +{change:.2f}%")
                    elif '优选' in item.category:
                        other_buy.append(f"⭐{item.name}({code}) +{change:.2f}%")
        
        if other_buy:
            print("\n🚀 其他强势信号：" + ", ".join(other_buy[:5]))
        
        if not dip_buy and not other_buy:
            print("⏳ 暂无明确买入信号")
            print("   💧 低吸型：等待昨日强势股今日回调")
            print("   🚀 追涨型：等待板块龙头放量突破")
            print("   💎 潜力型：等待热门股启动信号")
            print("   🎯 抄底型：等待调整企稳确认")
            print("   ⭐ 多维度：等待高综合评分标的")
        
        # 计算运行时间
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n{'='*60}")
        print(f"✅ 监控完成 [{datetime.now().strftime('%H:%M:%S')}] (耗时{elapsed:.1f}秒)")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 监控失败: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == '__main__':
    main()
