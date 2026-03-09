#!/usr/bin/env python3
"""
深度扫描脚本 - Deep Scan Script
板块轮动 + 五策略选股 + 持仓股标记
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sector_tracker import get_sector_tracker
from core.auto_watchlist_manager import get_auto_manager
from core.watchlist_memory import get_watchlist_memory
import json
from pathlib import Path

def get_portfolio_info():
    """获取持仓信息"""
    try:
        portfolio_path = Path(__file__).parent.parent / 'data' / 'portfolio.json'
        if portfolio_path.exists():
            with open(portfolio_path, 'r') as f:
                portfolio = json.load(f)
                positions = portfolio.get('positions', [])
                return {
                    'codes': [p['code'] for p in positions],
                    'details': {p['code']: p for p in positions}
                }
    except Exception:
        pass
    return {'codes': [], 'details': {}}

def generate_scan_report(result, portfolio_info):
    """生成带持仓标记的扫描报告"""
    portfolio_codes = portfolio_info['codes']
    portfolio_details = portfolio_info['details']
    
    report_lines = []
    report_lines.append("🔥 **A股深度扫描完成** 🔥")
    report_lines.append(f"扫描时间: {__import__('datetime').datetime.now().strftime('%H:%M')}")
    report_lines.append("")
    
    # 持仓股中的信号
    report_lines.append("📊 **持仓股策略命中**")
    report_lines.append("-" * 40)
    
    hit_positions = []
    for strategy_key in ['dip', 'chase', 'potential', 'bottom', 'multi']:
        strategy_name = {
            'dip': '💧低吸', 'chase': '🚀追涨', 'potential': '💎潜力', 
            'bottom': '🎯抄底', 'multi': '⭐优选'
        }.get(strategy_key, strategy_key)
        
        signals = result.get(strategy_key, {}).get('signals', [])
        for signal in signals:
            if signal['code'] in portfolio_codes:
                pos = portfolio_details[signal['code']]
                pnl = (signal['price'] - pos['cost_price']) / pos['cost_price'] * 100
                hit_positions.append({
                    'name': signal['name'],
                    'code': signal['code'],
                    'strategy': strategy_name,
                    'score': signal['score'],
                    'price': signal['price'],
                    'change': signal.get('change_pct', 0),
                    'cost': pos['cost_price'],
                    'pnl': pnl
                })
    
    if hit_positions:
        for hit in hit_positions:
            emoji = "🟢" if hit['pnl'] >= 0 else "🔴"
            report_lines.append(f"{emoji} **{hit['name']}({hit['code']})** [持仓]")
            report_lines.append(f"   命中策略: {hit['strategy']} | 评分:{hit['score']}分")
            report_lines.append(f"   现价:{hit['price']:.2f} ({hit['change']:+.2f}%) | 成本:{hit['cost']:.2f} | 盈亏:{hit['pnl']:+.2f}%")
            report_lines.append("")
    else:
        report_lines.append("暂无持仓股被策略选中")
        report_lines.append("")
    
    # 各策略信号汇总
    report_lines.append("📈 **五策略信号汇总**")
    report_lines.append("-" * 40)
    
    strategy_summary = [
        ('💧 强势股低吸', result.get('dip', {})),
        ('🚀 追涨型', result.get('chase', {})),
        ('💎 潜力型', result.get('potential', {})),
        ('🎯 抄底型', result.get('bottom', {})),
        ('⭐ 多维度优选', result.get('multi', {})),
    ]
    
    for name, data in strategy_summary:
        found = data.get('found', 0)
        added = data.get('added', 0)
        report_lines.append(f"{name}: 发现{found}个 | 新增{added}只到自选")
    
    report_lines.append("")
    report_lines.append("🏆 **重点标的详情**")
    report_lines.append("-" * 40)
    
    # 多维度优选详细展示
    multi_signals = result.get('multi', {}).get('signals', [])
    if multi_signals:
        report_lines.append("⭐ **多维度优选 (趋势+基本面+资金+技术+板块)**")
        for s in multi_signals[:5]:
            pos_marker = " **[持仓]**" if s['code'] in portfolio_codes else ""
            report_lines.append(f"  • {s['name']}({s['code']}){pos_marker}")
            report_lines.append(f"    综合{s['score']:.0f}分 | 趋势{s.get('trend_score', 0):.0f} 资金{s.get('fund_score', 0):.0f} 技术{s.get('technical_score', 0):.0f}")
            report_lines.append(f"    价格:{s['price']:.2f} ({s.get('change_pct', 0):+.2f}%) | {s.get('suggestion', '')}")
    
    # 低吸机会
    dip_signals = result.get('dip', {}).get('signals', [])
    if dip_signals:
        report_lines.append("")
        report_lines.append("💧 **强势股低吸机会**")
        for s in dip_signals[:3]:
            pos_marker = " [持仓]" if s['code'] in portfolio_codes else ""
            report_lines.append(f"  • {s['name']}({s['code']}){pos_marker}")
            report_lines.append(f"    评分:{s['score']}分 | {s.get('suggestion', '')}")
    
    report_lines.append("")
    report_lines.append("✅ 扫描结果已同步到自选管理，可查看每只股票的具体策略触发原因")
    
    return "\n".join(report_lines)

def main():
    print("="*60)
    print("🔥 板块轮动扫描")
    print("="*60)
    
    # 获取持仓信息
    portfolio_info = get_portfolio_info()
    print(f"\n📊 当前持仓: {len(portfolio_info['codes'])}只")
    if portfolio_info['codes']:
        for code, detail in portfolio_info['details'].items():
            print(f"   📈 {detail['name']}({code}) 成本:{detail['cost_price']:.2f}")
    
    # 板块扫描
    sector = get_sector_tracker()
    sector.run_sector_scan()
    print(sector.get_sector_summary())
    
    print("\n" + "="*60)
    print("✨ 五策略选股扫描")
    print("="*60)
    
    # 五策略扫描
    manager = get_auto_manager()
    result = manager.run_full_scan()
    
    print("\n" + "="*60)
    print("📊 扫描结果汇总")
    print("="*60)
    print(f"💧 低吸型: {result['dip']['found']} 个")
    print(f"🚀 追涨型: {result['chase']['found']} 个")
    print(f"💎 潜力型: {result['potential']['found']} 个")
    print(f"🎯 抄底型: {result['bottom']['found']} 个")
    print(f"⭐ 多维度: {result['multi']['found']} 个")
    
    # 显示持仓股命中情况
    print("\n" + "="*60)
    print("📈 持仓股策略命中检查")
    print("="*60)
    hit_count = 0
    for strategy_key in ['dip', 'chase', 'potential', 'bottom', 'multi']:
        signals = result.get(strategy_key, {}).get('signals', [])
        for signal in signals:
            if signal['code'] in portfolio_info['codes']:
                hit_count += 1
                pos = portfolio_info['details'][signal['code']]
                pnl = (signal['price'] - pos['cost_price']) / pos['cost_price'] * 100
                print(f"🎯 {signal['name']}({signal['code']}) 命中【{strategy_key}】策略!")
                print(f"   现价:{signal['price']:.2f} 成本:{pos['cost_price']:.2f} 盈亏:{pnl:+.2f}%")
    
    if hit_count == 0:
        print("暂无持仓股被策略选中")
    
    # 显示重点监控股票
    if result['multi']['signals']:
        print("\n⭐ 多维度优选标的：")
        for s in result['multi']['signals']:
            pos_marker = " [📈持仓]" if s['code'] in portfolio_info['codes'] else ""
            print(f"  {s['name']}({s['code']}){pos_marker} 综合{s['score']:.0f}分 - {s['suggestion']}")
    
    # 生成飞书报告
    report = generate_scan_report(result, portfolio_info)
    
    # 保存报告到文件，供飞书发送使用
    report_path = Path(__file__).parent.parent / 'data' / 'last_scan_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📋 扫描报告已保存到: {report_path}")
    
    return result, report

if __name__ == '__main__':
    main()
