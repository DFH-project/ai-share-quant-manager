#!/usr/bin/env python3
"""
持仓健康度分析引擎 - Position Health Analyzer
评估每只持仓股的健康状况，给出继续持有/减仓/清仓建议
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.multi_dimension_analyzer import get_analyzer
from core.fundamental_service import get_fundamental_data
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

@dataclass
class PositionHealthReport:
    """持仓健康度报告"""
    code: str
    name: str
    current_price: float
    cost_price: float
    position_pct: float  # 仓位占比
    pnl_pct: float  # 盈亏比例
    
    # 健康度评估
    health_score: float  # 0-100分
    health_status: str  # 健康/亚健康/病态/濒死
    
    # 多维度评分
    trend_score: float
    fund_score: float
    technical_score: float
    fundamental_score: float
    
    # 分析结论
    outlook: str  # 短期展望
    rebound_probability: float  # 反弹概率 0-100
    rebound_target: Optional[float]  # 预计反弹目标价
    
    # 建议
    action: str  # HOLD/REDUCE/EXIT/WAIT_REBOUND
    action_confidence: float  # 建议置信度
    reasoning: List[str]  # 建议理由
    
    # 动态止损/止盈
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]


class PositionHealthAnalyzer:
    """持仓健康度分析器"""
    
    def __init__(self):
        self.analyzer = get_analyzer()
        
    def load_portfolio(self) -> List[Dict]:
        """加载持仓数据"""
        try:
            portfolio_path = Path(__file__).parent.parent / 'data' / 'portfolio.json'
            if portfolio_path.exists():
                with open(portfolio_path, 'r', encoding='utf-8') as f:
                    portfolio = json.load(f)
                    return portfolio.get('positions', [])
        except Exception as e:
            print(f"加载持仓失败: {e}")
        return []
    
    def analyze_position(self, position: Dict) -> PositionHealthReport:
        """分析单只持仓股的健康度"""
        code = position['code']
        name = position['name']
        cost_price = position['cost_price']
        shares = position.get('shares', 0)
        position_pct = position.get('position_pct', 0)
        
        # 获取实时数据
        stock_data = data_fetcher.get_stock_data([code])
        if code not in stock_data:
            return None
        
        data = stock_data[code]
        current_price = data.get('current', cost_price)
        pnl_pct = (current_price - cost_price) / cost_price * 100
        
        # 多维度分析
        multi_result = self.analyzer.analyze_stock(code)
        
        if multi_result:
            trend_score = multi_result.trend_score
            fund_score = multi_result.fund_score
            technical_score = multi_result.technical_score
            fundamental_score = multi_result.fundamental_score
            total_score = multi_result.total_score
        else:
            trend_score = fund_score = technical_score = fundamental_score = 50
            total_score = 50
        
        # 计算健康度分数（加权）
        # 盈亏状态影响健康度：亏损越多，健康度越低
        pnl_factor = max(0, min(100, 50 + pnl_pct * 2))  # 盈亏因子
        health_score = (total_score * 0.6 + pnl_factor * 0.4)
        
        # 确定健康状态
        if health_score >= 70:
            health_status = "健康"
        elif health_score >= 50:
            health_status = "亚健康"
        elif health_score >= 30:
            health_status = "病态"
        else:
            health_status = "濒死"
        
        # 预测反弹概率和目标
        rebound_probability, rebound_target = self._predict_rebound(
            code, current_price, cost_price, pnl_pct, trend_score, technical_score
        )
        
        # 生成建议
        action, action_confidence, reasoning = self._generate_action(
            code, pnl_pct, health_score, health_status, 
            trend_score, fund_score, rebound_probability,
            multi_result.suggestion if multi_result else ""
        )
        
        # 计算动态止损/止盈
        stop_loss, take_profit = self._calculate_exit_points(
            current_price, cost_price, pnl_pct, trend_score, technical_score
        )
        
        # 展望
        outlook = self._generate_outlook(trend_score, fund_score, pnl_pct)
        
        return PositionHealthReport(
            code=code,
            name=name,
            current_price=current_price,
            cost_price=cost_price,
            position_pct=position_pct,
            pnl_pct=pnl_pct,
            health_score=health_score,
            health_status=health_status,
            trend_score=trend_score,
            fund_score=fund_score,
            technical_score=technical_score,
            fundamental_score=fundamental_score,
            outlook=outlook,
            rebound_probability=rebound_probability,
            rebound_target=rebound_target,
            action=action,
            action_confidence=action_confidence,
            reasoning=reasoning,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit
        )
    
    def _predict_rebound(self, code: str, current: float, cost: float, 
                         pnl_pct: float, trend: float, tech: float) -> Tuple[float, Optional[float]]:
        """预测反弹概率和目标价"""
        
        # 深度套牢情况
        if pnl_pct < -15:
            # 技术分高，反弹概率大
            if tech > 60:
                probability = 45 + (tech - 60) * 0.5
                target = cost * 0.92  # 预计反弹到成本下8%
            else:
                probability = 25
                target = current * 1.05  # 预计5%反弹
        
        # 中度亏损
        elif pnl_pct < -8:
            if trend > 50 and tech > 55:
                probability = 55 + (trend - 50)
                target = cost * 0.95
            else:
                probability = 40
                target = cost * 0.97
        
        # 轻度亏损或盈利
        else:
            if trend > 60:
                probability = 70
                target = cost * 1.08
            else:
                probability = 50
                target = cost * 1.02
        
        probability = min(90, max(10, probability))
        return probability, target
    
    def _generate_action(self, code: str, pnl_pct: float, health_score: float,
                        health_status: str, trend: float, fund: float,
                        rebound_prob: float, suggestion: str) -> Tuple[str, float, List[str]]:
        """生成操作建议"""
        
        reasoning = []
        
        # 深度套牢 (-15%以下)
        if pnl_pct < -15:
            if health_score < 35 and trend < 40:
                action = "EXIT"
                confidence = 75
                reasoning.append(f"深度套牢({pnl_pct:.1f}%)且趋势走弱，建议止损")
            elif rebound_prob > 50:
                action = "WAIT_REBOUND"
                confidence = 60
                reasoning.append(f"深度套牢但反弹概率{rebound_prob:.0f}%，建议等反弹减仓")
            else:
                action = "REDUCE"
                confidence = 65
                reasoning.append(f"深度套牢，建议减仓降低风险")
        
        # 中度亏损 (-8%到-15%)
        elif pnl_pct < -8:
            if trend > 55 and fund > 50:
                action = "HOLD"
                confidence = 60
                reasoning.append(f"中度亏损但资金/趋势尚可，建议持有观察")
            elif rebound_prob > 55:
                action = "WAIT_REBOUND"
                confidence = 55
                reasoning.append(f"中度亏损，等反弹至{pnl_pct*0.6:.1f}%附近减仓")
            else:
                action = "REDUCE"
                confidence = 70
                reasoning.append(f"趋势走弱，建议减仓止损")
        
        # 轻度亏损 (-8%以内)
        elif pnl_pct < 0:
            if health_score > 60:
                action = "HOLD"
                confidence = 70
                reasoning.append(f"轻度亏损但健康度良好，建议持有")
            else:
                action = "REDUCE"
                confidence = 60
                reasoning.append(f"轻度亏损且健康度一般，考虑调仓")
        
        # 盈利状态
        else:
            if pnl_pct > 15 and trend < 50:
                action = "TAKE_PROFIT"
                confidence = 65
                reasoning.append(f"盈利{pnl_pct:.1f}%但趋势转弱，建议止盈")
            elif pnl_pct > 8:
                action = "HOLD"
                confidence = 75
                reasoning.append(f"盈利状态良好，建议持有")
            else:
                action = "HOLD"
                confidence = 60
                reasoning.append(f"微盈，继续观察")
        
        # 添加多维度建议
        if suggestion and len(suggestion) > 3:
            reasoning.append(f"系统建议: {suggestion[:30]}")
        
        return action, confidence, reasoning
    
    def _calculate_exit_points(self, current: float, cost: float, pnl_pct: float,
                               trend: float, tech: float) -> Tuple[Optional[float], Optional[float]]:
        """计算动态止损/止盈点"""
        
        # 止损：根据技术支撑位或固定比例
        if pnl_pct < -10:
            stop_loss = cost * 0.85  # 最大亏损15%强制止损
        elif pnl_pct < -5:
            stop_loss = cost * 0.92
        else:
            stop_loss = current * 0.95  # 浮动止损5%
        
        # 止盈：根据趋势强度
        if trend > 70:
            take_profit = cost * 1.20  # 强趋势，目标20%
        elif trend > 55:
            take_profit = cost * 1.12
        else:
            take_profit = cost * 1.08
        
        return stop_loss, take_profit
    
    def _generate_outlook(self, trend: float, fund: float, pnl_pct: float) -> str:
        """生成短期展望"""
        if trend > 65 and fund > 60:
            return "看涨"
        elif trend > 55 or fund > 55:
            return "震荡偏强"
        elif trend > 40 and fund > 40:
            return "震荡"
        elif trend < 35:
            return "看跌"
        else:
            return "震荡偏弱"
    
    def analyze_all_positions(self) -> List[PositionHealthReport]:
        """分析所有持仓股"""
        positions = self.load_portfolio()
        reports = []
        
        print(f"\n🔍 分析 {len(positions)} 只持仓股健康度...")
        
        for pos in positions:
            report = self.analyze_position(pos)
            if report:
                reports.append(report)
        
        # 按健康度排序
        reports.sort(key=lambda x: x.health_score, reverse=True)
        return reports
    
    def generate_health_summary(self, reports: List[PositionHealthReport]) -> str:
        """生成健康度汇总报告"""
        if not reports:
            return "暂无持仓"
        
        lines = ["\n📊 持仓健康度总览", "=" * 60]
        
        # 统计
        total = len(reports)
        healthy = len([r for r in reports if r.health_status == "健康"])
        subhealthy = len([r for r in reports if r.health_status == "亚健康"])
        sick = len([r for r in reports if r.health_status == "病态"])
        dying = len([r for r in reports if r.health_status == "濒死"])
        
        lines.append(f"总持仓: {total}只 | 🟢健康{healthy} 🟡亚健康{subhealthy} 🟠病态{sick} 🔴濒死{dying}")
        lines.append("")
        
        # 按健康状态分组展示
        status_order = ["健康", "亚健康", "病态", "濒死"]
        for status in status_order:
            status_reports = [r for r in reports if r.health_status == status]
            if status_reports:
                emoji = {"健康": "🟢", "亚健康": "🟡", "病态": "🟠", "濒死": "🔴"}[status]
                lines.append(f"\n{emoji} {status} ({len(status_reports)}只)")
                lines.append("-" * 40)
                
                for r in status_reports:
                    pnl_emoji = "📈" if r.pnl_pct >= 0 else "📉"
                    lines.append(f"  {pnl_emoji} {r.name}({r.code}) 健康度:{r.health_score:.0f}分")
                    lines.append(f"     盈亏:{r.pnl_pct:+.1f}% | 趋势:{r.trend_score:.0f} | 展望:{r.outlook}")
                    lines.append(f"     建议: {r.action} (置信度{r.action_confidence:.0f}%)")
                    lines.append(f"     理由: {'; '.join(r.reasoning[:2])}")
                    
                    if r.rebound_target and r.pnl_pct < 0:
                        lines.append(f"     预计反弹: {r.rebound_target:.2f} (概率{r.rebound_probability:.0f}%)")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# 单例
_health_analyzer = None

def get_health_analyzer() -> PositionHealthAnalyzer:
    """获取持仓健康度分析器单例"""
    global _health_analyzer
    if _health_analyzer is None:
        _health_analyzer = PositionHealthAnalyzer()
    return _health_analyzer


if __name__ == '__main__':
    analyzer = PositionHealthAnalyzer()
    reports = analyzer.analyze_all_positions()
    print(analyzer.generate_health_summary(reports))
