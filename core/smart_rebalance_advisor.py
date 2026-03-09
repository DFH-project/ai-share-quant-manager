#!/usr/bin/env python3
"""
智能调仓顾问 - Smart Rebalance Advisor
整合持仓健康分析 + 换仓机会分析，生成最终调仓方案
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.position_health_analyzer import get_health_analyzer
from core.position_rebalance_engine import get_rebalance_engine
from core.auto_watchlist_manager import get_auto_manager
from typing import Dict, List
from datetime import datetime
import json
from pathlib import Path


class SmartRebalanceAdvisor:
    """智能调仓顾问 - 生成完整的调仓方案"""
    
    def __init__(self):
        self.health_analyzer = get_health_analyzer()
        self.rebalance_engine = get_rebalance_engine()
        self.auto_manager = get_auto_manager()
    
    def generate_full_analysis(self) -> Dict:
        """生成完整的持仓分析和调仓建议"""
        
        print("\n" + "=" * 70)
        print("🤖 智能调仓分析系统启动")
        print("=" * 70)
        
        # 1. 持仓健康度分析
        print("\n📊 Step 1: 分析持仓健康度...")
        health_reports = self.health_analyzer.analyze_all_positions()
        
        # 2. 换仓机会扫描
        print("\n🔄 Step 2: 扫描换仓机会...")
        opportunities = self.rebalance_engine.find_best_switches(top_n=5)
        
        # 3. 策略选股汇总
        print("\n✨ Step 3: 汇总策略选股...")
        strategy_signals = self._get_strategy_summary()
        
        # 4. 生成综合建议
        print("\n💡 Step 4: 生成综合调仓方案...")
        recommendations = self._generate_recommendations(
            health_reports, opportunities
        )
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'health_reports': health_reports,
            'opportunities': opportunities,
            'strategy_signals': strategy_signals,
            'recommendations': recommendations
        }
    
    def _get_strategy_summary(self) -> Dict:
        """获取策略选股汇总"""
        signals = self.rebalance_engine.get_strategy_signals()
        
        by_strategy = {}
        for s in signals:
            strategy = s.get('strategy_type', '其他')
            if strategy not in by_strategy:
                by_strategy[strategy] = []
            by_strategy[strategy].append(s)
        
        # 取各策略前3名
        top_by_strategy = {}
        for strategy, sigs in by_strategy.items():
            sigs.sort(key=lambda x: x['score'], reverse=True)
            top_by_strategy[strategy] = sigs[:3]
        
        return top_by_strategy
    
    def _generate_recommendations(self, health_reports, opportunities) -> List[Dict]:
        """生成综合调仓建议"""
        recommendations = []
        
        # 分类持仓
        exit_list = []  # 建议清仓
        reduce_list = []  # 建议减仓
        hold_list = []  # 建议持有
        wait_rebound_list = []  # 建议等反弹
        
        for report in health_reports:
            if report.action == "EXIT":
                exit_list.append(report)
            elif report.action == "REDUCE":
                reduce_list.append(report)
            elif report.action == "WAIT_REBOUND":
                wait_rebound_list.append(report)
            else:
                hold_list.append(report)
        
        # 生成建议列表
        if exit_list:
            recommendations.append({
                'type': 'URGENT_EXIT',
                'title': '⚠️ 紧急止损',
                'stocks': [f"{r.name}({r.code}) 亏{r.pnl_pct:.1f}%" for r in exit_list],
                'action': '立即清仓',
                'reason': '深度套牢且趋势恶化，继续持有风险极高'
            })
        
        if wait_rebound_list:
            for r in wait_rebound_list:
                if r.rebound_target:
                    rebound_pnl = (r.rebound_target - r.cost_price) / r.cost_price * 100
                    recommendations.append({
                        'type': 'WAIT_REBOUND',
                        'title': f'⏳ 等反弹减仓 - {r.name}',
                        'stock': f"{r.name}({r.code})",
                        'current_pnl': f"{r.pnl_pct:.1f}%",
                        'target_price': f"{r.rebound_target:.2f}",
                        'target_pnl': f"{rebound_pnl:.1f}%",
                        'rebound_prob': f"{r.rebound_probability:.0f}%",
                        'action': f'等反弹到{r.rebound_target:.2f}（{rebound_pnl:.1f}%）减仓',
                        'reason': f'当前亏{r.pnl_pct:.1f}%，反弹概率{r.rebound_probability:.0f}%，建议减亏卖出'
                    })
        
        if opportunities:
            best = opportunities[0]
            recommendations.append({
                'type': 'SWITCH',
                'title': f'🔄 优先换仓 - {best.sell_name} → {best.buy_name}',
                'sell': f"{best.sell_name}({best.sell_code}) {best.sell_pnl:+.1f}%",
                'buy': f"{best.buy_name}({best.buy_code}) {best.buy_strategy}",
                'score': f"{best.opportunity_score:.0f}分",
                'expected_gain': f"{best.expected_gain_diff:+.1f}%",
                'action': f'卖出{best.sell_name}，买入{best.buy_name}',
                'reason': f'换仓预期多赚{best.expected_gain_diff:.1f}%，风险降低{best.risk_reduction:.0f}分'
            })
        
        if reduce_list:
            recommendations.append({
                'type': 'REDUCE',
                'title': '⚡ 建议减仓',
                'stocks': [f"{r.name}({r.code}) 亏{r.pnl_pct:.1f}%" for r in reduce_list[:3]],
                'action': '减仓观望',
                'reason': '趋势走弱，建议降低仓位'
            })
        
        # 持仓健康提醒
        healthy_count = len([r for r in health_reports if r.health_status == "健康"])
        if healthy_count == 0 and len(health_reports) > 0:
            recommendations.append({
                'type': 'PORTfolio_WARNING',
                'title': '🔴 持仓健康度警告',
                'action': '全面审视持仓结构',
                'reason': f'全部{len(health_reports)}只持仓健康度均不理想，建议大幅调整'
            })
        
        return recommendations
    
    def generate_comprehensive_report(self, analysis: Dict) -> str:
        """生成综合报告"""
        
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append(f"📋 智能调仓分析报告 - {analysis['timestamp']}")
        lines.append("=" * 70)
        
        # 持仓健康总览
        health_reports = analysis['health_reports']
        if health_reports:
            lines.append(self.health_analyzer.generate_health_summary(health_reports))
        
        # 核心调仓建议
        recommendations = analysis['recommendations']
        if recommendations:
            lines.append("\n🎯 核心调仓建议")
            lines.append("=" * 70)
            
            for i, rec in enumerate(recommendations[:5], 1):
                lines.append(f"\n{i}. {rec['title']}")
                lines.append("-" * 50)
                
                if 'stock' in rec:
                    lines.append(f"   股票: {rec['stock']}")
                if 'stocks' in rec:
                    for s in rec['stocks']:
                        lines.append(f"   • {s}")
                if 'sell' in rec:
                    lines.append(f"   卖出: {rec['sell']}")
                    lines.append(f"   买入: {rec['buy']}")
                if 'current_pnl' in rec:
                    lines.append(f"   当前: {rec['current_pnl']} → 目标: {rec['target_pnl']} @ {rec['target_price']}")
                    lines.append(f"   反弹概率: {rec['rebound_prob']}")
                if 'score' in rec:
                    lines.append(f"   机会评分: {rec['score']} | 预期收益差: {rec['expected_gain']}")
                
                lines.append(f"   💡 建议: {rec['action']}")
                lines.append(f"   📌 理由: {rec['reason']}")
        
        # 换仓机会详情
        opportunities = analysis['opportunities']
        if opportunities:
            lines.append(self.rebalance_engine.generate_rebalance_report(opportunities))
        
        # 策略选股参考
        strategy_signals = analysis['strategy_signals']
        if strategy_signals:
            lines.append("\n📈 当前策略选股参考")
            lines.append("=" * 70)
            for strategy, signals in list(strategy_signals.items())[:3]:
                lines.append(f"\n{strategy}:")
                for s in signals[:2]:
                    lines.append(f"  • {s['name']}({s['code']}) {s['score']}分")
        
        # 执行计划
        lines.append("\n📅 建议执行计划")
        lines.append("=" * 70)
        lines.append(self._generate_action_plan(recommendations))
        
        lines.append("\n" + "=" * 70)
        lines.append("💡 提示: 以上建议基于量化模型，请结合市场情绪和自身风险承受力决策")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def _generate_action_plan(self, recommendations: List[Dict]) -> str:
        """生成执行计划"""
        lines = []
        
        urgent = [r for r in recommendations if r.get('type') == 'URGENT_EXIT']
        wait_rebound = [r for r in recommendations if r.get('type') == 'WAIT_REBOUND']
        switch = [r for r in recommendations if r.get('type') == 'SWITCH']
        
        lines.append("【立即执行】")
        if urgent:
            lines.append(f"  • 止损清仓: {', '.join([u['stocks'][0] for u in urgent[:2]])}")
        else:
            lines.append("  • 暂无紧急操作")
        
        lines.append("\n【观察等待】")
        if wait_rebound:
            for r in wait_rebound[:2]:
                lines.append(f"  • {r['stock']}: 等反弹到{r['target_price']}减仓")
        
        lines.append("\n【择机执行】")
        if switch:
            r = switch[0]
            lines.append(f"  • {r['action']}")
        
        return "\n".join(lines)
    
    def save_report(self, report: str):
        """保存报告"""
        report_path = Path(__file__).parent.parent / 'data' / 'rebalance_report.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        return report_path


# 便捷函数
def run_rebalance_analysis() -> str:
    """运行完整的调仓分析"""
    advisor = SmartRebalanceAdvisor()
    analysis = advisor.generate_full_analysis()
    report = advisor.generate_comprehensive_report(analysis)
    advisor.save_report(report)
    return report


if __name__ == '__main__':
    print(run_rebalance_analysis())
