"""
ai_risk_manager.py - AI风险控制模块
基于最新AI能力：波动率预测、组合VaR、黑天鹅预警
"""

import numpy as np
import pandas as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path


@dataclass
class RiskAssessment:
    """风险评估结果"""
    code: str
    name: str
    current_price: float
    cost_price: float
    pnl_pct: float
    volatility_20d: float  # 20日波动率
    var_95: float  # 95%置信度VaR
    tail_risk_score: float  # 尾部风险评分 0-100
    stop_loss_suggestion: str  # 止损建议
    action: str  # 建议操作: HOLD/STOP_LOSS/ADD/AVERAGE
    confidence: float  # 建议置信度
    reasoning: str  # AI推理理由


@dataclass
class PortfolioRisk:
    """组合风险"""
    total_value: float
    total_cost: float
    total_pnl_pct: float
    portfolio_var_95: float  # 组合VaR
    max_drawdown_risk: float  # 最大回撤风险
    concentration_risk: float  # 集中度风险
    correlation_risk: float  # 相关性风险
    overall_risk_level: str  # 整体风险等级
    suggestions: List[str]  # 组合层面建议


class AIRiskManager:
    """AI风险控制管理器"""
    
    def __init__(self, data_fetcher):
        self.data_fetcher = data_fetcher
        self.cache_dir = Path(__file__).parent.parent / 'data' / 'risk_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 风险阈值配置
        self.config = {
            'stop_loss_fixed': -0.08,  # 固定止损线
            'stop_loss_volatility_multiplier': 2.0,  # 波动率倍数止损
            'tail_risk_threshold': 70,  # 尾部风险阈值
            'max_position_concentration': 0.25,  # 最大集中度
            'var_warning_threshold': 0.05,  # VaR警告阈值（5%）
        }
    
    def calculate_volatility(self, code: str, days: int = 20) -> float:
        """计算历史波动率（年化）"""
        try:
            # 获取历史K线数据
            klines = self.data_fetcher._get_kline_eastmoney(code, days=days+5)
            if len(klines) < days:
                return 0.25  # 默认25%波动率
            
            # 计算日收益率
            closes = [k['close'] for k in klines[-days:]]
            returns = [(closes[i] - closes[i-1]) / closes[i-1] 
                      for i in range(1, len(closes))]
            
            # 计算标准差（年化）
            daily_vol = np.std(returns)
            annual_vol = daily_vol * np.sqrt(252)
            
            return annual_vol
        except Exception as e:
            return 0.25  # 出错返回默认值
    
    def calculate_var(self, code: str, confidence: float = 0.95) -> float:
        """计算VaR（历史模拟法）"""
        try:
            klines = self.data_fetcher._get_kline_eastmoney(code, days=60)
            if len(klines) < 20:
                return -0.05  # 默认5%VaR
            
            closes = [k['close'] for k in klines]
            returns = [(closes[i] - closes[i-1]) / closes[i-1] 
                      for i in range(1, len(closes))]
            
            # 计算指定置信度的VaR
            var = np.percentile(returns, (1 - confidence) * 100)
            return var
        except:
            return -0.05
    
    def assess_tail_risk(self, code: str) -> float:
        """评估尾部风险（0-100分，越高越危险）"""
        try:
            klines = self.data_fetcher._get_kline_eastmoney(code, days=40)
            if len(klines) < 20:
                return 50
            
            closes = [k['close'] for k in klines]
            returns = [(closes[i] - closes[i-1]) / closes[i-1] 
                      for i in range(1, len(closes))]
            
            # 计算偏度和峰度
            skewness = np.mean([(r - np.mean(returns))**3 for r in returns]) / (np.std(returns)**3 + 1e-8)
            kurtosis = np.mean([(r - np.mean(returns))**4 for r in returns]) / (np.std(returns)**4 + 1e-8) - 3
            
            # 计算最大连续下跌天数
            consecutive_drops = 0
            max_drops = 0
            for r in returns:
                if r < 0:
                    consecutive_drops += 1
                    max_drops = max(max_drops, consecutive_drops)
                else:
                    consecutive_drops = 0
            
            # 综合评分
            tail_risk = 50
            if skewness < -0.5:  # 左偏，下跌风险大
                tail_risk += 15
            if kurtosis > 3:  # 肥尾
                tail_risk += 10
            if max_drops >= 5:  # 连续大跌
                tail_risk += 20
            
            return min(100, tail_risk)
        except:
            return 50
    
    def generate_stop_loss_suggestion(self, position: Dict, 
                                     volatility: float, 
                                     var: float,
                                     tail_risk: float) -> Tuple[str, str]:
        """生成止损建议和行动"""
        code = position['code']
        name = position['name']
        cost = position['cost_price']
        current = position.get('current_price', cost)
        pnl = (current - cost) / cost if cost > 0 else 0
        
        # 自适应止损价格
        vol_stop = cost * (1 - volatility * self.config['stop_loss_volatility_multiplier'])
        fixed_stop = cost * (1 + self.config['stop_loss_fixed'])
        
        # 选择更宽松的止损（保护利润，给波动空间）
        suggested_stop = max(vol_stop, fixed_stop)
        
        reasoning_parts = []
        
        # 深度亏损情况
        if pnl < -0.10:
            if tail_risk > 70:
                action = "STOP_LOSS"
                reasoning_parts.append(f"深度亏损({pnl*100:.1f}%)且尾部风险高({tail_risk}分)")
                reasoning_parts.append(f"建议止损，避免进一步下跌")
            else:
                action = "HOLD_WATCH"
                reasoning_parts.append(f"深度亏损但尾部风险可控")
                reasoning_parts.append(f"建议持有观察，设置严格止损在¥{suggested_stop:.2f}")
        
        # 中度亏损
        elif pnl < -0.05:
            if var < -0.03:  # 日VaR大于3%
                action = "AVERAGE_DOWN" if tail_risk < 60 else "HOLD"
                reasoning_parts.append(f"中度亏损，波动率{'适中' if volatility < 0.3 else '较高'}")
                if action == "AVERAGE_DOWN":
                    reasoning_parts.append(f"建议逢低补仓摊低成本")
                else:
                    reasoning_parts.append(f"建议持有，等待反弹")
            else:
                action = "HOLD"
                reasoning_parts.append(f"亏损可控，风险较低，建议持有")
        
        # 小幅亏损或盈利
        elif pnl < 0.05:
            action = "HOLD"
            reasoning_parts.append(f"小幅波动，建议持有观察")
        
        # 盈利
        else:
            if pnl > 0.15:
                action = "PROFIT_PROTECT"
                reasoning_parts.append(f"盈利可观({pnl*100:.1f}%)，建议止盈保护")
                suggested_stop = cost * 1.10  # 保护10%利润
            else:
                action = "HOLD"
                reasoning_parts.append(f"盈利中，继续持有")
                suggested_stop = cost * 1.02  # 保护成本
        
        suggestion = f"建议止损价: ¥{suggested_stop:.2f} | 操作: {action}"
        reasoning = "; ".join(reasoning_parts)
        
        return suggestion, action, reasoning
    
    def assess_position(self, position: Dict) -> RiskAssessment:
        """评估单个持仓风险"""
        code = position['code']
        name = position['name']
        cost = position['cost_price']
        
        # 获取当前价格
        data = self.data_fetcher.get_stock_data([code])
        current = data.get(code, {}).get('current', cost)
        
        pnl = (current - cost) / cost if cost > 0 else 0
        
        # 计算各项指标
        volatility = self.calculate_volatility(code)
        var = self.calculate_var(code)
        tail_risk = self.assess_tail_risk(code)
        
        # 生成建议
        suggestion, action, reasoning = self.generate_stop_loss_suggestion(
            position, volatility, var, tail_risk
        )
        
        # 计算置信度
        confidence = 0.7
        if abs(pnl) > 0.10:
            confidence += 0.15
        if tail_risk > 70 or tail_risk < 30:
            confidence += 0.10
        confidence = min(0.95, confidence)
        
        return RiskAssessment(
            code=code,
            name=name,
            current_price=current,
            cost_price=cost,
            pnl_pct=pnl,
            volatility_20d=volatility,
            var_95=var,
            tail_risk_score=tail_risk,
            stop_loss_suggestion=suggestion,
            action=action,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def assess_portfolio(self, positions: List[Dict]) -> PortfolioRisk:
        """评估组合风险"""
        if not positions:
            return PortfolioRisk(0, 0, 0, 0, 0, 0, 0, "无持仓", [])
        
        # 计算组合价值
        total_cost = sum(p['cost_price'] * p['quantity'] for p in positions)
        
        # 获取当前价格
        codes = [p['code'] for p in positions]
        data = self.data_fetcher.get_stock_data(codes)
        
        total_value = 0
        position_values = []
        for p in positions:
            current = data.get(p['code'], {}).get('current', p['cost_price'])
            value = current * p['quantity']
            total_value += value
            position_values.append(value)
        
        total_pnl_pct = (total_value - total_cost) / total_cost if total_cost > 0 else 0
        
        # 计算集中度风险
        max_position = max(position_values) / total_value if total_value > 0 else 0
        concentration_risk = max_position
        
        # 简化计算组合VaR（假设独立性）
        individual_vars = []
        for p in positions:
            var = self.calculate_var(p['code'])
            weight = (p['cost_price'] * p['quantity']) / total_cost if total_cost > 0 else 0
            individual_vars.append(var * weight)
        
        portfolio_var = sum(individual_vars) if individual_vars else -0.05
        
        # 风险等级判断
        if total_pnl_pct < -0.15 or portfolio_var < -0.08:
            risk_level = "高风险"
        elif total_pnl_pct < -0.08 or portfolio_var < -0.05:
            risk_level = "中高风险"
        elif total_pnl_pct < 0 or portfolio_var < -0.03:
            risk_level = "中等风险"
        else:
            risk_level = "低风险"
        
        # 生成建议
        suggestions = []
        if concentration_risk > self.config['max_position_concentration']:
            suggestions.append(f"集中度风险: 最大持仓占比{concentration_risk*100:.1f}%，建议分散")
        
        if total_pnl_pct < -0.10:
            suggestions.append(f"组合亏损{total_pnl_pct*100:.1f}%，建议减仓止损或换仓")
        
        if portfolio_var < -0.05:
            suggestions.append(f"组合VaR为{portfolio_var*100:.1f}%，日亏损风险较高")
        
        return PortfolioRisk(
            total_value=total_value,
            total_cost=total_cost,
            total_pnl_pct=total_pnl_pct,
            portfolio_var_95=portfolio_var,
            max_drawdown_risk=abs(total_pnl_pct),
            concentration_risk=concentration_risk,
            correlation_risk=0.5,  # 简化处理
            overall_risk_level=risk_level,
            suggestions=suggestions
        )
    
    def generate_full_report(self, positions: List[Dict]) -> str:
        """生成完整风险评估报告"""
        lines = []
        lines.append("="*80)
        lines.append("🛡️ AI风险评估报告 | " + datetime.now().strftime("%H:%M:%S"))
        lines.append("="*80)
        
        # 组合风险评估
        portfolio = self.assess_portfolio(positions)
        lines.append("\n📊 组合风险概览")
        lines.append("-"*80)
        lines.append(f"总资产: ¥{portfolio.total_value:,.0f} | 成本: ¥{portfolio.total_cost:,.0f}")
        lines.append(f"总盈亏: {portfolio.total_pnl_pct*100:+.2f}% | 组合VaR: {portfolio.portfolio_var_95*100:.2f}%")
        lines.append(f"风险等级: {portfolio.overall_risk_level}")
        lines.append(f"集中度风险: {portfolio.concentration_risk*100:.1f}%")
        
        if portfolio.suggestions:
            lines.append("\n⚠️ 组合层面建议:")
            for sug in portfolio.suggestions:
                lines.append(f"  • {sug}")
        
        # 个股风险评估
        lines.append("\n" + "="*80)
        lines.append("📈 个股风险评估")
        lines.append("-"*80)
        
        for position in positions:
            assessment = self.assess_position(position)
            
            emoji = "🔴" if assessment.pnl_pct < -0.10 else (
                "⚠️" if assessment.pnl_pct < -0.05 else (
                "🟢" if assessment.pnl_pct > 0.05 else "⚪"))
            
            lines.append(f"\n{emoji} {assessment.name}({assessment.code})")
            lines.append(f"   成本: ¥{assessment.cost_price:.2f} → 现价: ¥{assessment.current_price:.2f}")
            lines.append(f"   盈亏: {assessment.pnl_pct*100:+.2f}% | 波动率: {assessment.volatility_20d*100:.1f}%")
            lines.append(f"   VaR(95%): {assessment.var_95*100:.2f}% | 尾部风险: {assessment.tail_risk_score}/100")
            lines.append(f"   🎯 建议: {assessment.stop_loss_suggestion}")
            lines.append(f"   💡 理由: {assessment.reasoning}")
            lines.append(f"   📊 置信度: {assessment.confidence*100:.0f}%")
        
        lines.append("\n" + "="*80)
        return "\n".join(lines)


# 单例
_ai_risk_manager = None

def get_ai_risk_manager(data_fetcher=None):
    """获取AI风险管理器单例"""
    global _ai_risk_manager
    if _ai_risk_manager is None:
        if data_fetcher is None:
            from core.data_fetcher import data_fetcher
        _ai_risk_manager = AIRiskManager(data_fetcher)
    return _ai_risk_manager


if __name__ == '__main__':
    # 测试
    from core.data_fetcher import data_fetcher
    import json
    
    with open('../data/portfolio.json') as f:
        pf = json.load(f)
    
    risk_mgr = get_ai_risk_manager(data_fetcher)
    report = risk_mgr.generate_full_report(pf['positions'])
    print(report)
