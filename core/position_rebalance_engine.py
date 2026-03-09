#!/usr/bin/env python3
"""
换仓机会分析引擎 - Position Rebalance Engine
对比持仓股 vs 策略选股，生成智能调仓建议
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import get_watchlist_memory
from core.auto_watchlist_manager import get_auto_manager
from core.position_health_analyzer import get_health_analyzer
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

@dataclass
class RebalanceOpportunity:
    """换仓机会"""
    # 卖出标的
    sell_code: str
    sell_name: str
    sell_price: float
    sell_pnl: float  # 卖出时的盈亏
    
    # 买入标的
    buy_code: str
    buy_name: str
    buy_price: float
    buy_score: float  # 策略评分
    buy_strategy: str  # 触发策略
    
    # 换仓分析
    opportunity_score: float  # 机会评分 0-100
    expected_gain_diff: float  # 预期收益差 (%)
    risk_reduction: float  # 风险降低幅度
    
    # 建议
    confidence: float  # 置信度
    reasoning: List[str]  # 理由
    urgency: str  # 紧急程度: HIGH/MEDIUM/LOW
    
    # 执行建议
    suggested_timing: str  # 执行时机
    position_size: str  # 建议仓位


@dataclass
class PositionSwitchAnalysis:
    """持仓换股分析"""
    current_position: Dict  # 当前持仓
    switch_candidates: List[RebalanceOpportunity]  # 换仓候选
    best_switch: Optional[RebalanceOpportunity]  # 最优换仓
    hold_recommendation: str  # 持有建议


class PositionRebalanceEngine:
    """持仓换仓引擎"""
    
    def __init__(self):
        self.health_analyzer = get_health_analyzer()
        self.auto_manager = get_auto_manager()
        self.watchlist = get_watchlist_memory()
        
    def load_portfolio(self) -> List[Dict]:
        """加载持仓"""
        try:
            portfolio_path = Path(__file__).parent.parent / 'data' / 'portfolio.json'
            if portfolio_path.exists():
                with open(portfolio_path, 'r', encoding='utf-8') as f:
                    portfolio = json.load(f)
                    positions = portfolio.get('positions', [])
                    # 计算仓位占比
                    total_value = sum(p.get('value', 0) for p in positions)
                    for p in positions:
                        p['position_pct'] = (p.get('value', 0) / total_value * 100) if total_value > 0 else 0
                    return positions
        except Exception as e:
            print(f"加载持仓失败: {e}")
        return []
    
    def get_strategy_signals(self) -> List[Dict]:
        """获取当前策略选股信号"""
        signals = []
        
        # 获取五策略信号
        dip_signals = self.auto_manager.scan_dip_buy_opportunities()
        chase_signals = self.auto_manager.scan_buy_signals()
        potential_signals = self.auto_manager.scan_potential_stocks()
        bottom_signals = self.auto_manager.scan_bottom_fishing()
        multi_signals = self.auto_manager.scan_multi_dimension_opportunities()
        
        # 合并所有信号
        for s in dip_signals:
            s['strategy_type'] = '强势股低吸'
            signals.append(s)
        for s in chase_signals:
            s['strategy_type'] = '追涨型'
            signals.append(s)
        for s in potential_signals:
            s['strategy_type'] = '潜力型'
            signals.append(s)
        for s in bottom_signals:
            s['strategy_type'] = '抄底型'
            signals.append(s)
        for s in multi_signals:
            s['strategy_type'] = '多维度优选'
            signals.append(s)
        
        # 去重，保留最高分的
        seen = {}
        for s in signals:
            code = s['code']
            if code not in seen or seen[code]['score'] < s['score']:
                seen[code] = s
        
        return list(seen.values())
    
    def analyze_switch_opportunity(self, position: Dict, signal: Dict,
                                   health_report=None) -> Optional[RebalanceOpportunity]:
        """分析单次换仓机会"""
        
        sell_code = position['code']
        buy_code = signal['code']
        
        # 如果已经在持仓中，跳过
        portfolio = self.load_portfolio()
        portfolio_codes = [p['code'] for p in portfolio]
        if buy_code in portfolio_codes:
            return None
        
        # 获取价格
        sell_price = health_report.current_price if health_report else position.get('current_price', position['cost_price'])
        buy_price = signal['price']
        
        # 计算卖出盈亏
        sell_pnl = (sell_price - position['cost_price']) / position['cost_price'] * 100
        
        # 计算机会评分
        opportunity_score = self._calculate_opportunity_score(
            position, signal, health_report, sell_pnl
        )
        
        # 预期收益差
        expected_gain_diff = self._estimate_gain_diff(
            sell_code, buy_code, health_report, signal
        )
        
        # 风险降低幅度
        risk_reduction = self._calculate_risk_reduction(
            health_report, signal
        )
        
        # 置信度和紧急度
        confidence, urgency = self._assess_confidence_urgency(
            position, signal, health_report, sell_pnl, opportunity_score
        )
        
        # 生成理由
        reasoning = self._generate_reasoning(
            position, signal, health_report, sell_pnl, expected_gain_diff
        )
        
        # 执行建议
        suggested_timing = self._suggest_timing(sell_pnl, signal)
        position_size = self._suggest_position_size(signal, opportunity_score)
        
        return RebalanceOpportunity(
            sell_code=sell_code,
            sell_name=position['name'],
            sell_price=sell_price,
            sell_pnl=sell_pnl,
            buy_code=buy_code,
            buy_name=signal['name'],
            buy_price=buy_price,
            buy_score=signal['score'],
            buy_strategy=signal['strategy_type'],
            opportunity_score=opportunity_score,
            expected_gain_diff=expected_gain_diff,
            risk_reduction=risk_reduction,
            confidence=confidence,
            reasoning=reasoning,
            urgency=urgency,
            suggested_timing=suggested_timing,
            position_size=position_size
        )
    
    def _calculate_opportunity_score(self, position: Dict, signal: Dict,
                                     health_report, sell_pnl: float) -> float:
        """计算换仓机会评分"""
        
        score = 50  # 基础分
        
        # 持仓健康度权重
        if health_report:
            if health_report.health_score < 40:
                score += 20  # 持仓不健康，换仓价值大
            elif health_report.health_score < 60:
                score += 10
        
        # 盈亏状态权重
        if sell_pnl < -10:
            score += 15  # 深度套牢，换仓止损价值大
        elif sell_pnl < -5:
            score += 8
        elif sell_pnl > 10:
            score -= 5  # 盈利丰厚，换仓动力小
        
        # 新标的质量权重
        buy_score = signal.get('score', 50)
        score += (buy_score - 50) * 0.4  # 新标的质量越高，分数越高
        
        # 策略类型权重
        strategy_bonus = {
            '强势股低吸': 10,
            '追涨型': 8,
            '多维度优选': 12,
            '潜力型': 5,
            '抄底型': 3
        }
        score += strategy_bonus.get(signal.get('strategy_type', ''), 0)
        
        return min(100, max(0, score))
    
    def _estimate_gain_diff(self, sell_code: str, buy_code: str,
                           health_report, signal: Dict) -> float:
        """估算收益差（换仓后的预期额外收益）"""
        
        # 持仓股的预期收益（基于健康度）
        if health_report:
            if health_report.rebound_target and health_report.pnl_pct < 0:
                # 等反弹后的收益
                hold_expected = (health_report.rebound_target - health_report.current_price) / health_report.current_price * 100
            else:
                hold_expected = (health_report.trend_score - 50) * 0.2  # 趋势分换算预期收益
        else:
            hold_expected = 0
        
        # 新标的的预期收益（基于策略评分）
        buy_score = signal.get('score', 60)
        switch_expected = (buy_score - 60) * 0.5  # 评分换算预期收益
        
        # 收益差
        gain_diff = switch_expected - hold_expected
        
        return gain_diff
    
    def _calculate_risk_reduction(self, health_report, signal: Dict) -> float:
        """计算风险降低幅度"""
        if not health_report:
            return 0
        
        current_risk = max(0, 100 - health_report.health_score)
        new_risk = max(0, 100 - signal.get('score', 70))
        
        return current_risk - new_risk
    
    def _assess_confidence_urgency(self, position: Dict, signal: Dict,
                                   health_report, sell_pnl: float,
                                   opportunity_score: float) -> Tuple[float, str]:
        """评估置信度和紧急度"""
        
        # 置信度
        confidence = 60
        if health_report:
            confidence += (health_report.health_score < 50) * 10  # 持仓不健康增加置信度
        confidence += (signal.get('score', 50) - 50) * 0.3  # 新标的质量
        confidence = min(95, max(40, confidence))
        
        # 紧急度
        if sell_pnl < -15 and health_report and health_report.health_score < 35:
            urgency = "HIGH"
        elif opportunity_score > 75:
            urgency = "HIGH"
        elif opportunity_score > 60:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"
        
        return confidence, urgency
    
    def _generate_reasoning(self, position: Dict, signal: Dict,
                           health_report, sell_pnl: float, gain_diff: float) -> List[str]:
        """生成换仓理由"""
        reasoning = []
        
        # 持仓问题
        if health_report:
            if health_report.health_score < 50:
                reasoning.append(f"持仓股健康度仅{health_report.health_score:.0f}分，表现不佳")
            if health_report.action == "EXIT":
                reasoning.append(f"持仓股建议{health_report.action}，应考虑调仓")
        
        if sell_pnl < -10:
            reasoning.append(f"当前亏损{sell_pnl:.1f}%，继续持有机会成本高")
        
        # 新标的优势
        reasoning.append(f"新标的评分{signal['score']}分，质量更优")
        reasoning.append(f"新标策略: {signal['strategy_type']}")
        
        # 收益预期
        if gain_diff > 5:
            reasoning.append(f"换仓预期可多赚{gain_diff:.1f}%")
        
        return reasoning
    
    def _suggest_timing(self, sell_pnl: float, signal: Dict) -> str:
        """建议执行时机"""
        if sell_pnl < -8:
            return "等反弹减仓后执行"
        elif signal.get('strategy_type') == '强势股低吸':
            return "今日回调时执行"
        else:
            return "盘中择机执行"
    
    def _suggest_position_size(self, signal: Dict, opportunity_score: float) -> str:
        """建议仓位大小"""
        if opportunity_score > 80:
            return "满仓换入"
        elif opportunity_score > 65:
            return "半仓换入"
        else:
            return "轻仓试水"
    
    def find_best_switches(self, top_n: int = 5) -> List[RebalanceOpportunity]:
        """找到最优的换仓机会"""
        
        print("\n🔍 扫描换仓机会...")
        
        # 获取持仓
        positions = self.load_portfolio()
        if not positions:
            print("暂无持仓")
            return []
        
        # 获取策略信号
        signals = self.get_strategy_signals()
        if not signals:
            print("暂无策略选股信号")
            return []
        
        print(f"  持仓: {len(positions)}只 | 策略信号: {len(signals)}个")
        
        # 获取持仓健康报告
        health_reports = {}
        for pos in positions:
            report = self.health_analyzer.analyze_position(pos)
            if report:
                health_reports[pos['code']] = report
        
        # 生成所有换仓机会
        opportunities = []
        for pos in positions:
            health_report = health_reports.get(pos['code'])
            
            # 只考虑健康度<70或亏损>5%的持仓进行换仓
            should_consider = False
            if health_report:
                if health_report.health_score < 70:
                    should_consider = True
                if health_report.pnl_pct < -5:
                    should_consider = True
            
            if not should_consider:
                continue
            
            for signal in signals:
                opp = self.analyze_switch_opportunity(pos, signal, health_report)
                if opp and opp.opportunity_score > 50:  # 只保留机会分>50的
                    opportunities.append(opp)
        
        # 排序并返回前N
        opportunities.sort(key=lambda x: x.opportunity_score, reverse=True)
        return opportunities[:top_n]
    
    def generate_rebalance_report(self, opportunities: List[RebalanceOpportunity]) -> str:
        """生成换仓建议报告"""
        if not opportunities:
            return "\n📊 换仓分析: 当前暂无优质换仓机会，建议持有观望"
        
        lines = ["\n🔄 智能调仓建议", "=" * 70]
        lines.append(f"发现 {len(opportunities)} 个换仓机会，按优先级排序:\n")
        
        for i, opp in enumerate(opportunities[:5], 1):
            urgency_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[opp.urgency]
            pnl_emoji = "📉" if opp.sell_pnl < 0 else "📈"
            
            lines.append(f"{urgency_emoji} 机会#{i}: {opp.sell_name} → {opp.buy_name}")
            lines.append(f"   {pnl_emoji} 卖出: {opp.sell_name}({opp.sell_code}) 盈亏{opp.sell_pnl:+.1f}%")
            lines.append(f"   🎯 买入: {opp.buy_name}({opp.buy_code}) {opp.buy_strategy} {opp.buy_score}分")
            lines.append(f"   📊 机会评分: {opp.opportunity_score:.0f}/100 | 置信度: {opp.confidence:.0f}%")
            lines.append(f"   💰 预期收益差: {opp.expected_gain_diff:+.1f}% | 风险降低: {opp.risk_reduction:+.0f}分")
            lines.append(f"   ⏰ 执行时机: {opp.suggested_timing} | 建议仓位: {opp.position_size}")
            lines.append(f"   💡 理由: {'; '.join(opp.reasoning[:3])}")
            lines.append("")
        
        # 最优换仓
        best = opportunities[0]
        lines.append("🏆 最优换仓方案")
        lines.append("-" * 70)
        lines.append(f"卖出: {best.sell_name}({best.sell_code}) {best.sell_price:.2f} ({best.sell_pnl:+.1f}%)")
        lines.append(f"买入: {best.buy_name}({best.buy_code}) {best.buy_price:.2f} ({best.buy_strategy})")
        lines.append(f"预期: 换仓后收益提升{best.expected_gain_diff:.1f}%，风险降低{best.risk_reduction:.0f}分")
        lines.append("=" * 70)
        
        return "\n".join(lines)


# 单例
_rebalance_engine = None

def get_rebalance_engine() -> PositionRebalanceEngine:
    """获取换仓引擎单例"""
    global _rebalance_engine
    if _rebalance_engine is None:
        _rebalance_engine = PositionRebalanceEngine()
    return _rebalance_engine


if __name__ == '__main__':
    engine = PositionRebalanceEngine()
    opportunities = engine.find_best_switches()
    print(engine.generate_rebalance_report(opportunities))
