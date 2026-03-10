#!/usr/bin/env python3
"""
setup_v2_demo.py - V2系统完整演示
将部分股票升级为特别关注，展示分级监控功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.watchlist_memory_v2 import get_watchlist_memory_v2, SelectionReason, EntryPlan
from core.intraday_monitor_v2 import IntradayMonitorV2


def upgrade_to_high_attention():
    """将核心股票升级为特别关注"""
    wl = get_watchlist_memory_v2()
    
    # 定义核心股票及其详细分析
    core_stocks = [
        {
            'code': '300308',
            'name': '中际旭创',
            'strategy': '板块龙头',
            'sector': 'CPO',
            'reason': 'CPO全球龙头，800G光模块核心供应商，DeepSeek催化受益',
            'entry': 120.0,
            'stop': 110.0,
            'target': 140.0
        },
        {
            'code': '300502',
            'name': '新易盛',
            'strategy': '板块龙头',
            'sector': 'CPO',
            'reason': '高速光模块龙头，DeepSeek推理需求爆发直接受益',
            'entry': 90.0,
            'stop': 82.0,
            'target': 105.0
        },
        {
            'code': '603019',
            'name': '中科曙光',
            'strategy': '低吸型',
            'sector': 'AI算力',
            'reason': 'AI服务器龙头，昨日强势今日回调给出买点',
            'entry': 28.5,
            'stop': 27.0,
            'target': 32.0
        },
        {
            'code': '002594',
            'name': '比亚迪',
            'strategy': '板块龙头',
            'sector': '新能源',
            'reason': '新能源车龙头，基本面稳健，回调是机会',
            'entry': 95.0,
            'stop': 88.0,
            'target': 110.0
        },
        {
            'code': '300750',
            'name': '宁德时代',
            'strategy': '多维优选型',
            'sector': '新能源',
            'reason': '多维度综合优选，趋势+基本面+资金共振',
            'entry': 180.0,
            'stop': 165.0,
            'target': 210.0
        },
        {
            'code': '600276',
            'name': '恒瑞医药',
            'strategy': '多维优选型',
            'sector': '医药',
            'reason': '创新药龙头，综合评分高，长期配置价值',
            'entry': 48.0,
            'stop': 44.0,
            'target': 55.0
        },
        {
            'code': '300124',
            'name': '汇川技术',
            'strategy': '板块龙头',
            'sector': '机器人',
            'reason': '工控龙头，机器人赛道核心标的',
            'entry': 70.0,
            'stop': 64.0,
            'target': 80.0
        },
        {
            'code': '600584',
            'name': '长电科技',
            'strategy': '低吸型',
            'sector': '半导体',
            'reason': '封测龙头，强势股低吸策略标的',
            'entry': 47.0,
            'stop': 44.0,
            'target': 52.0
        }
    ]
    
    print("="*80)
    print("🔄 升级核心股票到特别关注")
    print("="*80)
    
    for stock in core_stocks:
        item = wl.get(stock['code'])
        if item:
            # 更新为特别关注
            item.attention_level = '特别关注'
            item.strategy_type = stock['strategy']
            item.linked_sectors = [stock['sector']]
            
            # 添加详细选股原因
            item.selection_reason = SelectionReason(
                primary_reason=stock['reason'],
                secondary_reasons=[
                    f"属于{stock['sector']}板块核心标的",
                    "市场关注度高，流动性好",
                    "技术形态符合策略要求"
                ],
                key_indicators={
                    '策略类型': stock['strategy'],
                    '所属板块': stock['sector'],
                    '信心度': '高'
                },
                expected_scenario='按策略预期运行，达到目标价止盈',
                invalidation_conditions=[
                    f'跌破止损价{stock["stop"]:.2f}',
                    '板块出现系统性风险',
                    '基本面恶化'
                ]
            )
            
            # 添加买入计划
            item.entry_plan = EntryPlan(
                entry_price=stock['entry'],
                stop_loss=stock['stop'],
                target_price=stock['target'],
                position_size='半仓',
                holding_period='短线' if stock['strategy'] == '低吸型' else '中线'
            )
            
            item.priority = 90
            item.notes = f"🔴特别关注 | {stock['strategy']} | {stock['reason'][:30]}"
            
            print(f"  ✅ {stock['name']}({stock['code']}) -> 特别关注 [{stock['strategy']}]")
    
    wl._save()
    
    # 将部分股票设为一般关注
    medium_codes = ['000977', '300394', '002085', '000099', '002371', '601138', '300775']
    for code in medium_codes:
        item = wl.get(code)
        if item:
            item.attention_level = '一般关注'
            item.priority = 50
            item.notes = f"🟡一般关注 | {item.strategy_type}"
    
    wl._save()
    
    print(f"\n✅ 升级完成！")
    print(f"  🔴 特别关注: {len([i for i in wl.get_all() if i.attention_level=='特别关注'])}只")
    print(f"  🟡 一般关注: {len([i for i in wl.get_all() if i.attention_level=='一般关注'])}只")
    print(f"  🟢 观察: {len([i for i in wl.get_all() if i.attention_level=='观察'])}只")


def run_full_demo():
    """运行完整演示"""
    print("\n" + "="*80)
    print("🎯 A股量化系统V2 - 完整演示")
    print("="*80)
    
    # 1. 升级核心股票
    upgrade_to_high_attention()
    
    # 2. 显示升级后的列表
    print("\n" + "="*80)
    print("📋 升级后的自选股列表")
    print("="*80)
    
    wl = get_watchlist_memory_v2()
    wl.display()
    
    # 3. 显示某只股票的详细分析
    print("\n" + "="*80)
    print("🔍 详细分析示例：中际旭创")
    print("="*80)
    
    item = wl.get('300308')
    if item:
        print(f"\n【基础信息】")
        print(f"  关注级别: {item.get_attention_emoji()} {item.attention_level}")
        print(f"  策略类型: {item.get_strategy_emoji()} {item.strategy_type}")
        print(f"  关联板块: {', '.join(item.linked_sectors)}")
        
        print(f"\n【选股原因】")
        if item.selection_reason:
            print(f"  主要原因: {item.selection_reason.primary_reason}")
            if item.selection_reason.secondary_reasons:
                print(f"  次要原因:")
                for r in item.selection_reason.secondary_reasons[:3]:
                    print(f"    • {r}")
        
        print(f"\n【买入计划】")
        if item.entry_plan:
            print(f"  计划买入价: {item.entry_plan.entry_price:.2f}")
            print(f"  止损价: {item.entry_plan.stop_loss:.2f}")
            print(f"  目标价: {item.entry_plan.target_price:.2f}")
            print(f"  仓位建议: {item.entry_plan.position_size}")
            print(f"  持有周期: {item.entry_plan.holding_period}")
        
        if item.selection_reason and item.selection_reason.invalidation_conditions:
            print(f"\n【失效条件】")
            for c in item.selection_reason.invalidation_conditions:
                print(f"  ❌ {c}")
    
    # 4. 运行分级监控
    print("\n" + "="*80)
    print("📡 运行分级监控演示")
    print("="*80)
    
    monitor = IntradayMonitorV2()
    report = monitor.run_full_monitoring()
    
    print("\n" + "="*80)
    print("✅ V2系统演示完成！")
    print("="*80)
    print("\n核心功能：")
    print("  1. ✅ 自选分级管理（特别关注/一般关注/观察）")
    print("  2. ✅ 策略类型标记（追涨/低吸/抄底/价值/多维优选等）")
    print("  3. ✅ 选股原因深度记录")
    print("  4. ✅ 买入计划管理")
    print("  5. ✅ 分级精准监控")
    print("  6. ✅ 策略联动提醒")
    print("\n使用命令：")
    print("  • 快速监控: python3 scripts/intraday_monitor_integrated.py --quick")
    print("  • 完整监控: python3 scripts/intraday_monitor_integrated.py --full")
    print("  • 查看列表: python3 scripts/intraday_monitor_integrated.py --v2-list")
    print("  • 查看详情: python3 scripts/intraday_monitor_integrated.py --detail 300308")


if __name__ == '__main__':
    run_full_demo()
