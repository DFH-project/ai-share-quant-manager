#!/usr/bin/env python3
"""
ai_portfolio_analyzer.py - AI持仓深度分析工具
整合风险评估、LLM理由生成、智能调仓建议
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from core.data_fetcher import data_fetcher
from core.ai_risk_manager import get_ai_risk_manager
from core.llm_strategy_reasoning import get_llm_reasoner
from core.smart_rebalance_advisor import get_rebalance_advisor
from core.watchlist_memory_v2 import get_watchlist_memory_v2
from core.auto_watchlist_manager import get_auto_manager
from pathlib import Path


def analyze_portfolio():
    """分析持仓并生成AI建议"""
    
    # 读取持仓
    portfolio_path = Path(__file__).parent.parent / 'data' / 'portfolio.json'
    with open(portfolio_path) as f:
        pf = json.load(f)
    
    holdings = pf['positions']
    cash = pf['cash']
    
    print("="*80)
    print("🤖 AI持仓深度分析")
    print("="*80)
    
    # 1. AI风险评估
    print("\n【1/4】AI风险评估中...")
    risk_mgr = get_ai_risk_manager(data_fetcher)
    
    # 更新持仓当前价格
    codes = [h['code'] for h in holdings]
    data = data_fetcher.get_stock_data(codes)
    
    for h in holdings:
        if h['code'] in data:
            h['current_price'] = data[h['code']].get('current', h['cost_price'])
            h['pnl_pct'] = (h['current_price'] - h['cost_price']) / h['cost_price']
        else:
            h['current_price'] = h['cost_price']
            h['pnl_pct'] = 0
    
    # 生成风险评估报告
    risk_report = risk_mgr.generate_full_report(holdings)
    print(risk_report)
    
    # 2. 获取优质候选股
    print("\n【2/4】扫描优质候选股...")
    auto_mgr = get_auto_manager()
    
    # 获取五策略信号
    dip_signals = auto_mgr.scan_dip_buy_opportunities()
    multi_signals = auto_mgr.scan_multi_dimension_opportunities()
    
    candidates = []
    for s in dip_signals[:3]:
        candidates.append({
            'code': s['code'],
            'name': s['name'],
            'score': s['score'],
            'price': s['price'],
            'change_pct': s.get('change_pct', 0),
            'strategy': '低吸'
        })
    for s in multi_signals[:3]:
        candidates.append({
            'code': s['code'],
            'name': s['name'],
            'score': s['score'],
            'price': s['price'],
            'change_pct': s.get('change_pct', 0),
            'strategy': '多维优选'
        })
    
    print(f"   发现 {len(candidates)} 只优质候选股:")
    for c in candidates:
        print(f"   • {c['name']}({c['code']}) {c['change_pct']:+.2f}% 评分{c['score']:.0f}")
    
    # 3. 智能调仓分析
    print("\n【3/4】AI调仓分析中...")
    advisor = get_rebalance_advisor()
    
    total_value = sum(h['current_price'] * h['quantity'] for h in holdings)
    
    rebalance_report = advisor.generate_full_rebalance_report(
        holdings, candidates, total_value, cash
    )
    print(rebalance_report)
    
    # 4. 生成LLM选股理由（前3名候选股）
    print("\n【4/4】生成深度选股分析...")
    llm = get_llm_reasoner()
    
    for c in candidates[:3]:
        print(f"\n📊 {c['name']}({c['code']}) 深度分析:")
        print("-"*80)
        
        signal = {
            'name': c['name'],
            'code': c['code'],
            'price': c['price'],
            'change_pct': c['change_pct'],
            'score': c['score'],
            'reasons': [c['strategy']],
            'sector': '热点板块',
            'volume_ratio': 1.0
        }
        
        reason = llm.generate_reason(signal, c['strategy'])
        # 只显示关键部分
        for line in reason.split('\n')[:30]:  # 限制行数
            print(line)
    
    # 保存完整报告
    report_path = Path(__file__).parent.parent / 'data' / 'ai_portfolio_analysis.txt'
    full_report = f"""
AI持仓分析报告
生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*80}
{risk_report}

{'='*80}
{rebalance_report}
"""
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(full_report)
    
    print(f"\n✅ 完整报告已保存: {report_path}")
    print("="*80)


if __name__ == '__main__':
    analyze_portfolio()
