#!/usr/bin/env python3
"""
自动选股并添加完整分析到自选V2
这个脚本演示如何将股票按分级管理添加到自选股，并记录完整的选股原因
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.watchlist_memory_v2 import (
    get_watchlist_memory_v2, 
    SelectionReason, 
    EntryPlan,
    migrate_from_v1
)
from core.data_fetcher import data_fetcher
from core.multi_dimension_analyzer import get_analyzer
from datetime import datetime


def create_selection_reason(
    primary_reason: str,
    secondary_reasons: list = None,
    key_indicators: dict = None,
    market_context: str = "",
    sector_context: str = "",
    risk_factors: list = None,
    expected_scenario: str = "",
    invalidation_conditions: list = None
) -> SelectionReason:
    """
    创建完整的选股原因记录
    
    Args:
        primary_reason: 主要选股原因
        secondary_reasons: 次要原因列表
        key_indicators: 关键指标（评分、估值等）
        market_context: 市场环境描述
        sector_context: 板块情况描述
        risk_factors: 风险因素列表
        expected_scenario: 预期走势
        invalidation_conditions: 选股逻辑失效条件
    """
    return SelectionReason(
        primary_reason=primary_reason,
        secondary_reasons=secondary_reasons or [],
        key_indicators=key_indicators or {},
        market_context=market_context,
        sector_context=sector_context,
        risk_factors=risk_factors or [],
        selection_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
        expected_scenario=expected_scenario,
        invalidation_conditions=invalidation_conditions or []
    )


def create_entry_plan(
    entry_price: float = 0.0,
    stop_loss: float = 0.0,
    target_price: float = 0.0,
    position_size: str = "",
    holding_period: str = ""
) -> EntryPlan:
    """
    创建买入计划
    
    Args:
        entry_price: 计划买入价
        stop_loss: 止损价
        target_price: 目标价
        position_size: 建议仓位（轻仓/半仓/重仓）
        holding_period: 持有周期（短线/中线/长线）
    """
    return EntryPlan(
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,
        position_size=position_size,
        holding_period=holding_period
    )


def add_dip_buy_stock(
    code: str,
    name: str,
    current_price: float,
    change_pct: float,
    sector: str = "",
    confidence: str = "中等"
):
    """
    添加强势股低吸标的
    
    示例场景：昨天强势上涨，今天回调1-3%，给出买点
    """
    wl = get_watchlist_memory_v2()
    
    # 构建完整选股原因
    selection_reason = create_selection_reason(
        primary_reason=f"强势股回调买入机会，今日回调{change_pct:.2f}%",
        secondary_reasons=[
            "昨日强势上涨，证明有资金关注",
            "今日良性回调，未出现恐慌抛售",
            "属于热门板块核心标的"
        ],
        key_indicators={
            '回调幅度': change_pct,
            '当前价格': current_price,
            '板块': sector,
            '信心度': confidence
        },
        market_context="大盘震荡，热点轮动，适合低吸策略",
        sector_context=f"{sector}板块今日表现活跃，龙头股有资金关注",
        risk_factors=[
            "回调可能演变为下跌趋势",
            "板块热度可能快速消退",
            "大盘系统性风险"
        ],
        expected_scenario="短期企稳反弹，目标3-5%收益",
        invalidation_conditions=[
            "继续下跌超过5%，破位止损",
            "板块出现集体大跌",
            "成交量异常放大，疑似出货"
        ]
    )
    
    # 构建买入计划
    entry_price = current_price * 0.99  # 计划买入价略低于当前
    stop_loss = current_price * 0.95    # 止损价5%
    target_price = current_price * 1.05  # 目标价5%
    
    entry_plan = create_entry_plan(
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,
        position_size="半仓",
        holding_period="短线（3-5天）"
    )
    
    # 添加到自选
    success = wl.add_with_full_analysis(
        code=code,
        name=name,
        attention_level="特别关注" if confidence == "高" else "一般关注",
        strategy_type="低吸型",
        selection_reason=selection_reason,
        entry_plan=entry_plan,
        linked_sectors=[sector] if sector else [],
        notes=f"💧强势股低吸 | 回调{change_pct:.2f}% | 计划买入{entry_price:.2f} | {confidence}信心"
    )
    
    return success


def add_chase_stock(
    code: str,
    name: str,
    current_price: float,
    change_pct: float,
    sector: str = "",
    is_sector_leader: bool = False
):
    """
    添加追涨型标的（板块龙头、强势股）
    
    示例场景：板块龙头强势突破，量价齐升
    """
    wl = get_watchlist_memory_v2()
    
    leader_tag = "板块龙头" if is_sector_leader else "强势股"
    
    selection_reason = create_selection_reason(
        primary_reason=f"{leader_tag}强势突破，量价齐升",
        secondary_reasons=[
            f"今日涨幅{change_pct:.2f}%，强势明显" if change_pct > 0 else "技术形态良好",
            "成交量放大，资金持续流入",
            "板块效应明显，有持续性"
        ],
        key_indicators={
            '涨幅': change_pct,
            '当前价格': current_price,
            '板块': sector,
            '龙头地位': is_sector_leader
        },
        market_context="市场情绪积极，热点板块有持续性",
        sector_context=f"{sector}板块领涨，{leader_tag}获得资金追捧",
        risk_factors=[
            "高位追涨风险",
            "可能出现冲高回落",
            "板块轮动导致掉队"
        ],
        expected_scenario="延续强势，短期目标5-10%",
        invalidation_conditions=[
            "次日低开超过2%",
            "放量滞涨",
            "跌破今日开盘价"
        ]
    )
    
    # 追涨型通常不预设买入价（追涨买入），但设止损
    stop_loss = current_price * 0.97  # 3%止损
    target_price = current_price * 1.08  # 8%目标
    
    entry_plan = create_entry_plan(
        entry_price=current_price,  # 现价追入
        stop_loss=stop_loss,
        target_price=target_price,
        position_size="轻仓",
        holding_period="短线（2-3天）"
    )
    
    attention = "特别关注" if is_sector_leader else "一般关注"
    
    success = wl.add_with_full_analysis(
        code=code,
        name=name,
        attention_level=attention,
        strategy_type="追涨型",
        selection_reason=selection_reason,
        entry_plan=entry_plan,
        linked_sectors=[sector] if sector else [],
        notes=f"🚀{leader_tag}追涨 | 涨幅{change_pct:.2f}% | 止损{stop_loss:.2f} | 轻仓短线"
    )
    
    return success


def add_value_stock(
    code: str,
    name: str,
    current_price: float,
    pe: float,
    roe: float,
    sector: str = ""
):
    """
    添加价值型标的（低PE高ROE）
    
    示例场景：PE<20，ROE>15%的优质公司
    """
    wl = get_watchlist_memory_v2()
    
    selection_reason = create_selection_reason(
        primary_reason=f"低估值高盈利价值股，PE{pe:.1f}，ROE{roe:.1f}%",
        secondary_reasons=[
            "估值低于行业平均",
            "盈利能力稳定优秀",
            "适合中长期持有",
            "下跌空间有限"
        ],
        key_indicators={
            'PE': pe,
            'ROE': roe,
            '当前价格': current_price,
            '板块': sector
        },
        market_context="市场震荡，价值股提供安全边际",
        sector_context=f"{sector}板块估值合理，基本面稳健",
        risk_factors=[
            "价值股可能长期不涨",
            "行业景气度下行",
            "市场风格不在价值股"
        ],
        expected_scenario="中长期稳健上涨，年化收益15-20%",
        invalidation_conditions=[
            "ROE连续两季度下滑",
            "PE上升到30以上（估值过高）",
            "基本面恶化"
        ]
    )
    
    entry_plan = create_entry_plan(
        entry_price=current_price,
        stop_loss=current_price * 0.90,  # 价值股止损放宽到10%
        target_price=current_price * 1.30,  # 30%目标（中长期）
        position_size="重仓",
        holding_period="长线（3-6个月）"
    )
    
    success = wl.add_with_full_analysis(
        code=code,
        name=name,
        attention_level="一般关注",  # 价值股不需要高频监控
        strategy_type="价值型",
        selection_reason=selection_reason,
        entry_plan=entry_plan,
        linked_sectors=[sector] if sector else [],
        notes=f"💰价值投资 | PE{pe:.1f} ROE{roe:.1f}% | 长线持有 | 分批建仓"
    )
    
    return success


def add_multi_dimension_stock(
    code: str,
    name: str,
    total_score: float,
    trend_score: float,
    fund_score: float,
    technical_score: float,
    suggestion: str,
    sector: str = ""
):
    """
    添加多维度优选标的
    
    综合评分≥65分的优质标的
    """
    wl = get_watchlist_memory_v2()
    
    selection_reason = create_selection_reason(
        primary_reason=f"多维度综合评分{total_score:.0f}分，全面优秀",
        secondary_reasons=[
            f"趋势面{trend_score:.0f}分：走势良好",
            f"资金面{fund_score:.0f}分：资金关注",
            f"技术面{technical_score:.0f}分：技术形态佳",
            "多维度共振，确定性较高"
        ],
        key_indicators={
            '综合评分': total_score,
            '趋势评分': trend_score,
            '资金评分': fund_score,
            '技术评分': technical_score,
            '板块': sector
        },
        market_context="结构性行情，优选多维度共振标的",
        sector_context=f"{sector}板块内有综合优势",
        risk_factors=[
            "高评分不代表必然上涨",
            "系统性风险影响",
            "评分可能快速变化"
        ],
        expected_scenario=suggestion,
        invalidation_conditions=[
            "综合评分下降到55以下",
            "任一维度评分大幅下降",
            "出现重大利空"
        ]
    )
    
    success = wl.add_with_full_analysis(
        code=code,
        name=name,
        attention_level="特别关注",
        strategy_type="多维优选型",
        selection_reason=selection_reason,
        entry_plan=EntryPlan(),  # 多维优选根据具体情况设置
        linked_sectors=[sector] if sector else [],
        notes=f"⭐多维优选 | 综合{total_score:.0f}分 | 趋势{trend_score:.0f}资金{fund_score:.0f} | {suggestion[:20]}"
    )
    
    return success


def display_all_watchlist():
    """显示所有自选股"""
    wl = get_watchlist_memory_v2()
    wl.display()
    
    # 显示统计
    stats = wl.get_statistics()
    print(f"\n📊 统计:")
    print(f"  总计: {stats['total']}只")
    print(f"  按关注级别: 🔴特别关注:{stats['by_attention'].get('特别关注',0)} "
          f"🟡一般关注:{stats['by_attention'].get('一般关注',0)} "
          f"🟢观察:{stats['by_attention'].get('观察',0)}")
    print(f"  按策略类型:")
    for strategy, count in sorted(stats['by_strategy'].items(), key=lambda x: -x[1]):
        print(f"    {strategy}: {count}只")


def view_stock_detail(code: str):
    """查看股票详细分析"""
    wl = get_watchlist_memory_v2()
    item = wl.get(code)
    
    if not item:
        print(f"股票 {code} 不在自选股中")
        return
    
    print(f"\n{'='*80}")
    print(f"📋 {item.name}({item.code}) 详细分析")
    print(f"{'='*80}")
    
    # 基础信息
    print(f"\n【基础信息】")
    print(f"  关注级别: {item.get_attention_emoji()} {item.attention_level}")
    print(f"  策略类型: {item.get_strategy_emoji()} {item.strategy_type}")
    print(f"  关联板块: {', '.join(item.linked_sectors) if item.linked_sectors else '无'}")
    print(f"  添加日期: {item.added_date}")
    
    # 选股原因
    if item.selection_reason:
        sr = item.selection_reason
        print(f"\n【选股原因】")
        print(f"  主要原因: {sr.primary_reason}")
        if sr.secondary_reasons:
            print(f"  次要原因:")
            for r in sr.secondary_reasons:
                print(f"    • {r}")
        if sr.key_indicators:
            print(f"  关键指标:")
            for k, v in sr.key_indicators.items():
                print(f"    • {k}: {v}")
        if sr.market_context:
            print(f"  市场环境: {sr.market_context}")
        if sr.sector_context:
            print(f"  板块情况: {sr.sector_context}")
        if sr.expected_scenario:
            print(f"  预期走势: {sr.expected_scenario}")
        if sr.risk_factors:
            print(f"  风险因素:")
            for r in sr.risk_factors:
                print(f"    ⚠️ {r}")
        if sr.invalidation_conditions:
            print(f"  失效条件:")
            for c in sr.invalidation_conditions:
                print(f"    ❌ {c}")
    
    # 买入计划
    if item.entry_plan:
        ep = item.entry_plan
        print(f"\n【买入计划】")
        if ep.entry_price > 0:
            print(f"  买入价: {ep.entry_price:.2f}")
        if ep.stop_loss > 0:
            print(f"  止损价: {ep.stop_loss:.2f}")
        if ep.target_price > 0:
            print(f"  目标价: {ep.target_price:.2f}")
        if ep.position_size:
            print(f"  建议仓位: {ep.position_size}")
        if ep.holding_period:
            print(f"  持有周期: {ep.holding_period}")
    
    print(f"{'='*80}")


def main():
    """主函数 - 演示功能"""
    print("="*80)
    print("自选股V2管理 - 分级+策略+深度分析")
    print("="*80)
    
    # 1. 从V1迁移数据
    print("\n1. 从V1迁移数据...")
    migrated = migrate_from_v1()
    
    # 2. 显示当前自选股
    print("\n2. 当前自选股列表")
    display_all_watchlist()
    
    # 3. 查看某只股票的详细分析
    print("\n3. 查看详细分析示例")
    print("-" * 80)
    wl = get_watchlist_memory_v2()
    items = wl.get_all()
    if items:
        view_stock_detail(items[0].code)
    
    print("\n✅ 完成")
    print("\n使用说明:")
    print("  - 使用 add_dip_buy_stock() 添加强势股低吸标的")
    print("  - 使用 add_chase_stock() 添加追涨型标的")
    print("  - 使用 add_value_stock() 添加价值型标的")
    print("  - 使用 add_multi_dimension_stock() 添加多维优选标的")
    print("  - 使用 view_stock_detail(code) 查看股票详细分析")


if __name__ == '__main__':
    main()
