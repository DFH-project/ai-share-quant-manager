"""
smart_rebalance_advisor.py - 智能调仓建议系统
基于机会成本计算和组合优化，给出换仓/加仓/止损建议
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class RebalanceOpportunity:
    """调仓机会"""
    hold_code: str
    hold_name: str
    hold_pnl_pct: float
    candidate_code: str
    candidate_name: str
    candidate_score: float
    opportunity_cost: float  # 机会成本（年化预期收益差）
    swap_confidence: float  # 换仓置信度 0-100
    recommendation: str  # HOLD/SWAP/ADD/STOP
    reasoning: str  # 详细理由


@dataclass
class PositionAdvice:
    """持仓建议"""
    code: str
    name: str
    current_pnl: float
    action: str  # HOLD/ADD/REDUCE/STOP
    target_weight: float  # 目标仓位占比
    confidence: float
    reasoning: str


class SmartRebalanceAdvisor:
    """智能调仓顾问"""
    
    def __init__(self, data_fetcher, risk_manager, llm_reasoner):
        self.data_fetcher = data_fetcher
        self.risk_manager = risk_manager
        self.llm_reasoner = llm_reasoner
        
        # 配置
        self.config = {
            'swap_threshold': 0.10,  # 换仓阈值（预期收益差>10%）
            'stop_loss_threshold': -0.10,  # 止损阈值
            'take_profit_threshold': 0.15,  # 止盈阈值
            'max_position_weight': 0.20,  # 单股最大仓位
            'min_position_weight': 0.05,  # 单股最小仓位
        }
    
    def calculate_opportunity_cost(self, hold_stock: Dict, candidate: Dict) -> float:
        """
        计算换仓机会成本
        
        机会成本 = (候选股预期收益 - 持仓股预期收益) × 时间权重
        """
        # 持仓股预期收益（基于当前趋势和基本面）
        hold_expected_return = self._estimate_expected_return(hold_stock)
        
        # 候选股预期收益（基于策略评分）
        cand_expected_return = self._estimate_expected_return(candidate)
        
        # 计算收益差
        return_diff = cand_expected_return - hold_expected_return
        
        # 考虑换仓成本（手续费+滑点，约0.2%）
        transaction_cost = 0.002
        
        # 净机会成本
        opportunity_cost = return_diff - transaction_cost * 2  # 买卖各一次
        
        return opportunity_cost
    
    def _estimate_expected_return(self, stock: Dict) -> float:
        """估算预期收益（年化）"""
        # 基于策略评分估算
        score = stock.get('score', 50)
        
        # 评分转换为预期收益（简化模型）
        # 假设：50分对应5%预期收益，每增加1分增加0.3%
        base_return = 0.05
        score_contribution = (score - 50) * 0.003
        
        expected = base_return + score_contribution
        
        # 考虑当前盈亏（均值回归效应）
        pnl = stock.get('pnl_pct', 0)
        if pnl > 0.20:  # 已涨20%以上，预期收益降低
            expected *= 0.7
        elif pnl < -0.15:  # 已跌15%以上，预期收益提升（反弹）
            expected *= 1.3
        
        return max(-0.10, min(0.30, expected))  # 限制在-10%到30%
    
    def analyze_swap_opportunities(self, holdings: List[Dict], 
                                   candidates: List[Dict]) -> List[RebalanceOpportunity]:
        """分析换仓机会"""
        opportunities = []
        
        for hold in holdings:
            hold_code = hold['code']
            hold_name = hold['name']
            hold_pnl = hold.get('pnl_pct', 0)
            
            for cand in candidates:
                cand_code = cand['code']
                
                # 跳过已持仓的股票
                if cand_code == hold_code:
                    continue
                
                # 计算机会成本
                opp_cost = self.calculate_opportunity_cost(hold, cand)
                
                # 只有机会成本为正才考虑换仓
                if opp_cost > self.config['swap_threshold']:
                    # 计算置信度
                    confidence = self._calculate_swap_confidence(hold, cand, opp_cost)
                    
                    # 生成建议
                    if hold_pnl < -0.10 and confidence > 70:
                        recommendation = "SWAP"
                    elif hold_pnl < 0 and confidence > 80:
                        recommendation = "SWAP"
                    else:
                        recommendation = "CONSIDER"
                    
                    # 生成理由
                    reasoning = self.llm_reasoner.generate_comparison(hold, cand)
                    
                    opp = RebalanceOpportunity(
                        hold_code=hold_code,
                        hold_name=hold_name,
                        hold_pnl_pct=hold_pnl,
                        candidate_code=cand_code,
                        candidate_name=cand['name'],
                        candidate_score=cand.get('score', 0),
                        opportunity_cost=opp_cost,
                        swap_confidence=confidence,
                        recommendation=recommendation,
                        reasoning=reasoning
                    )
                    opportunities.append(opp)
        
        # 按机会成本排序
        opportunities.sort(key=lambda x: x.opportunity_cost, reverse=True)
        return opportunities[:5]  # 返回前5个最佳机会
    
    def _calculate_swap_confidence(self, hold: Dict, cand: Dict, opp_cost: float) -> float:
        """计算换仓置信度"""
        confidence = 50.0
        
        # 机会成本因素（权重30%）
        confidence += min(30, opp_cost * 200)  # 每1%机会成本加20分
        
        # 持仓亏损程度（权重25%）
        hold_pnl = hold.get('pnl_pct', 0)
        if hold_pnl < -0.15:
            confidence += 25
        elif hold_pnl < -0.10:
            confidence += 15
        elif hold_pnl < -0.05:
            confidence += 5
        
        # 候选股评分（权重25%）
        cand_score = cand.get('score', 50)
        confidence += min(25, (cand_score - 50) * 0.8)
        
        # 风险因素（权重20%，扣分项）
        cand_tail_risk = cand.get('tail_risk', 50)
        if cand_tail_risk > 70:
            confidence -= 20
        elif cand_tail_risk > 60:
            confidence -= 10
        
        return max(0, min(100, confidence))
    
    def optimize_portfolio_weights(self, holdings: List[Dict], 
                                   total_value: float) -> List[PositionAdvice]:
        """
        优化组合仓位权重
        
        使用简化版MPT（均值-方差优化）
        """
        advices = []
        
        # 计算每只股票的评分（用于确定目标权重）
        scores = []
        for h in holdings:
            # 综合评分 = 策略评分 + 盈亏调整 + 风险调整
            strategy_score = h.get('strategy_score', 50)
            pnl = h.get('pnl_pct', 0)
            risk_score = h.get('risk_score', 50)
            
            # 盈亏调整：盈利股降低权重（止盈），亏损股根据程度调整
            pnl_adjust = 0
            if pnl > 0.15:
                pnl_adjust = -10  # 盈利超15%，降低配置
            elif pnl < -0.10:
                pnl_adjust = -15  # 深度亏损，降低配置
            elif pnl < -0.05:
                pnl_adjust = 5  # 轻度亏损，增加配置博反弹
            
            # 风险调整
            risk_adjust = (50 - risk_score) * 0.2
            
            final_score = strategy_score + pnl_adjust + risk_adjust
            scores.append(final_score)
        
        # 归一化权重
        total_score = sum(scores) if sum(scores) > 0 else 1
        target_weights = [s / total_score for s in scores]
        
        # 生成建议
        for i, hold in enumerate(holdings):
            code = hold['code']
            name = hold['name']
            current_value = hold.get('current_price', hold['cost_price']) * hold['quantity']
            current_weight = current_value / total_value if total_value > 0 else 0
            target_weight = target_weights[i]
            pnl = hold.get('pnl_pct', 0)
            
            # 确定操作
            weight_diff = target_weight - current_weight
            
            if weight_diff > 0.03:
                action = "ADD"
            elif weight_diff < -0.03:
                action = "REDUCE"
            else:
                action = "HOLD"
            
            # 特殊情况：深度亏损
            if pnl < -0.12:
                action = "STOP"
                target_weight = 0
            
            # 生成理由
            if action == "ADD":
                reasoning = f"目标仓位{target_weight*100:.1f}%高于当前{current_weight*100:.1f}%，建议加仓"
            elif action == "REDUCE":
                reasoning = f"目标仓位{target_weight*100:.1f}%低于当前{current_weight*100:.1f}%，建议减仓"
            elif action == "STOP":
                reasoning = f"深度亏损{pnl*100:.1f}%，建议止损"
            else:
                reasoning = f"当前仓位合理，维持持有"
            
            advice = PositionAdvice(
                code=code,
                name=name,
                current_pnl=pnl,
                action=action,
                target_weight=target_weight,
                confidence=min(95, 60 + abs(weight_diff) * 100),
                reasoning=reasoning
            )
            advices.append(advice)
        
        return advices
    
    def generate_full_rebalance_report(self, holdings: List[Dict], 
                                       candidates: List[Dict],
                                       total_value: float,
                                       cash: float) -> str:
        """生成完整调仓报告"""
        lines = []
        lines.append("="*80)
        lines.append("🔄 AI智能调仓分析报告 | " + datetime.now().strftime("%H:%M:%S"))
        lines.append("="*80)
        
        # 组合现状
        lines.append("\n📊 组合现状")
        lines.append("-"*80)
        lines.append(f"总资产: ¥{total_value + cash:,.0f} (持仓¥{total_value:,.0f} + 现金¥{cash:,.0f})")
        
        # 换仓机会
        lines.append("\n🔄 换仓机会分析")
        lines.append("-"*80)
        
        opportunities = self.analyze_swap_opportunities(holdings, candidates)
        if opportunities:
            for i, opp in enumerate(opportunities[:3], 1):
                emoji = "🔴" if opp.recommendation == "SWAP" else "🟡"
                lines.append(f"\n{emoji} 机会{i}: {opp.hold_name} → {opp.candidate_name}")
                lines.append(f"   当前持仓盈亏: {opp.hold_pnl_pct*100:+.2f}%")
                lines.append(f"   候选股评分: {opp.candidate_score:.0f}分")
                lines.append(f"   预期收益差: {opp.opportunity_cost*100:+.1f}% (年化)")
                lines.append(f"   换仓置信度: {opp.swap_confidence:.0f}%")
                lines.append(f"   建议: {opp.recommendation}")
                # 简化显示理由
                lines.append(f"   理由: {opp.reasoning.split('### 换仓建议')[1].strip() if '### 换仓建议' in opp.reasoning else '详见分析'}")
        else:
            lines.append("\n⚪ 未发现显著换仓机会")
            lines.append("   当前持仓与候选股机会成本相近，建议维持现状")
        
        # 仓位优化建议
        lines.append("\n" + "="*80)
        lines.append("⚖️ 仓位优化建议")
        lines.append("-"*80)
        
        advices = self.optimize_portfolio_weights(holdings, total_value)
        for advice in advices:
            emoji = {"ADD": "📈", "REDUCE": "📉", "HOLD": "➡️", "STOP": "❌"}.get(advice.action, "➡️")
            lines.append(f"\n{emoji} {advice.name}({advice.code})")
            lines.append(f"   当前盈亏: {advice.current_pnl*100:+.2f}%")
            lines.append(f"   建议操作: {advice.action}")
            lines.append(f"   目标仓位: {advice.target_weight*100:.1f}%")
            lines.append(f"   置信度: {advice.confidence:.0f}%")
            lines.append(f"   理由: {advice.reasoning}")
        
        # 综合建议
        lines.append("\n" + "="*80)
        lines.append("🎯 综合调仓建议")
        lines.append("-"*80)
        
        # 找出最优先的操作
        urgent_stops = [a for a in advices if a.action == "STOP"]
        good_swaps = [o for o in opportunities if o.recommendation == "SWAP"]
        
        if urgent_stops:
            lines.append("\n🔴 优先操作（止损）:")
            for s in urgent_stops:
                lines.append(f"   • 止损 {s.name}({s.code})，亏损{s.current_pnl*100:.1f}%")
        
        if good_swaps:
            lines.append("\n🟢 优先操作（换仓）:")
            for s in good_swaps[:2]:
                lines.append(f"   • {s.hold_name} → {s.candidate_name}")
                lines.append(f"     预期收益提升{s.opportunity_cost*100:.1f}%")
        
        if cash > total_value * 0.2 and opportunities:
            lines.append("\n💰 现金配置建议:")
            lines.append(f"   当前现金比例{cash/(total_value+cash)*100:.1f}%较高")
            lines.append(f"   建议买入: {opportunities[0].candidate_name}({opportunities[0].candidate_code})")
        
        lines.append("\n" + "="*80)
        return "\n".join(lines)


# 单例
_rebalance_advisor = None

def get_rebalance_advisor(data_fetcher=None, risk_manager=None, llm_reasoner=None):
    """获取智能调仓顾问单例"""
    global _rebalance_advisor
    if _rebalance_advisor is None:
        from core.data_fetcher import data_fetcher as df
        from core.ai_risk_manager import get_ai_risk_manager
        from core.llm_strategy_reasoning import get_llm_reasoner
        
        _rebalance_advisor = SmartRebalanceAdvisor(
            data_fetcher or df,
            risk_manager or get_ai_risk_manager(df),
            llm_reasoner or get_llm_reasoner()
        )
    return _rebalance_advisor


if __name__ == '__main__':
    # 测试
    advisor = get_rebalance_advisor()
    
    # 模拟持仓
    holdings = [
        {'code': '600733', 'name': '北汽蓝谷', 'cost_price': 8.90, 'current_price': 7.81, 'quantity': 200, 'pnl_pct': -0.1225, 'strategy_score': 45, 'risk_score': 75},
        {'code': '600756', 'name': '浪潮软件', 'cost_price': 18.50, 'current_price': 16.33, 'quantity': 100, 'pnl_pct': -0.1173, 'strategy_score': 48, 'risk_score': 70},
    ]
    
    # 模拟候选股
    candidates = [
        {'code': '300750', 'name': '宁德时代', 'score': 85, 'tail_risk': 40},
        {'code': '300308', 'name': '中际旭创', 'score': 80, 'tail_risk': 45},
    ]
    
    report = advisor.generate_full_rebalance_report(holdings, candidates, 50000, 12000)
    print(report)
