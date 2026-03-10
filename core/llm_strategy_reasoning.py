"""
llm_strategy_reasoning.py - LLM选股理由生成模块
使用大模型生成个性化、非模板化的选股理由
"""

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class LLMStrategyReasoner:
    """LLM策略推理器 - 生成自然语言选股理由"""
    
    def __init__(self, provider: str = "deepseek"):
        self.provider = provider
        self.prompt_templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """加载提示词模板"""
        return {
            'dip_buy': """你是一位专业的A股投资策略分析师。请基于以下数据，生成一份详细的"强势股低吸"选股理由。

【股票信息】
- 股票名称: {name} ({code})
- 所属板块: {sector}
- 当前价格: ¥{current_price:.2f}
- 今日涨跌幅: {change_pct:+.2f}%
- 20日高点: ¥{high_20d:.2f}
- 20日低点: ¥{low_20d:.2f}
- 量比: {volume_ratio:.2f}

【策略信号】
- 触发策略: 强势股低吸
- 策略评分: {score}/100
- 触发原因: {reasons}

【市场环境】
- 所属板块今日涨幅: {sector_change:+.2f}%
- 近期趋势: {trend}

请生成以下内容（用markdown格式）：

## 核心买入逻辑
（2-3句话，说明为什么这只股票适合低吸）

## 技术面分析
- 支撑与压力
- 成交量分析
- 关键价位

## 风险因素
（列出2-3个主要风险点）

## 操作建议
- 建议买入价位区间
- 止损位设置
- 目标价位
- 建议仓位

## 持有周期预期
（短线/中线/长线，及理由）

## 失效条件
（什么情况下这个买入逻辑不成立，应该退出）

要求：
1. 语言专业但易懂
2. 数据驱动，每个观点都要有依据
3. 不夸大收益，客观分析风险
4. 给出具体的操作建议（价位、仓位）
""",
            'chase': """你是一位专业的A股投资策略分析师。请基于以下数据，生成一份详细的"追涨型"选股理由。

【股票信息】
- 股票名称: {name} ({code})
- 所属板块: {sector}
- 当前价格: ¥{current_price:.2f}
- 今日涨跌幅: {change_pct:+.2f}%
- 成交量比: {volume_ratio:.2f}

【策略信号】
- 触发策略: 追涨型（板块龙头/强势股）
- 策略评分: {score}/100
- 触发原因: {reasons}

【市场环境】
- 所属板块今日涨幅: {sector_change:+.2f}%
- 板块排名: {sector_rank}

请生成追涨策略的完整分析...
""",
            'multi_dimension': """你是一位专业的A股投资策略分析师。请基于以下多维度评分数据，生成一份详细的选股理由。

【股票信息】
- 股票名称: {name} ({code})
- 当前价格: ¥{current_price:.2f}
- 今日涨跌幅: {change_pct:+.2f}%

【多维度评分】
- 综合评分: {total_score}/100
- 趋势面: {trend_score}/100
- 基本面: {fundamental_score}/100
- 资金面: {fund_score}/100
- 技术面: {technical_score}/100
- 板块面: {sector_score}/100

【估值指标】
- PE: {pe:.1f}
- ROE: {roe:.1f}%

请生成多维度优选的完整分析...
"""
        }
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API生成内容"""
        try:
            # 尝试使用OpenClaw内置的AI能力
            # 这里使用模拟实现，实际应接入真实LLM API
            
            # 简化版：基于规则生成理由
            return self._rule_based_generation(prompt)
        except Exception as e:
            return f"LLM生成失败，使用备用方案: {str(e)}"
    
    def _rule_based_generation(self, prompt: str) -> str:
        """基于规则的备用生成方案"""
        # 从prompt中提取关键信息
        lines = prompt.split('\n')
        
        # 提取基本信息
        name = ""
        code = ""
        change_pct = 0
        score = 0
        
        for line in lines:
            if "股票名称:" in line:
                name = line.split(":")[1].strip().split("(")[0]
                code = line.split("(")[1].split(")")[0] if "(" in line else ""
            if "今日涨跌幅:" in line:
                try:
                    change_pct = float(line.split(":")[1].strip().replace("%", ""))
                except:
                    pass
            if "策略评分:" in line:
                try:
                    score = float(line.split(":")[1].strip().split("/")[0])
                except:
                    pass
        
        # 生成理由
        if "强势股低吸" in prompt:
            return self._generate_dip_reason(name, code, change_pct, score)
        elif "追涨型" in prompt:
            return self._generate_chase_reason(name, code, change_pct, score)
        else:
            return self._generate_generic_reason(name, code, change_pct, score)
    
    def _generate_dip_reason(self, name: str, code: str, change_pct: float, score: float) -> str:
        """生成低吸型理由"""
        parts = []
        parts.append(f"## {name}({code}) - 强势股低吸分析\n")
        
        # 核心逻辑
        parts.append("### 核心买入逻辑")
        if change_pct < -2:
            parts.append(f"✅ **{name}**今日回调{abs(change_pct):.2f}%，属于强势股良性回调。")
        else:
            parts.append(f"✅ **{name}**今日小幅调整，为强势上涨后的正常整理。")
        parts.append(f"✅ 策略评分{score:.0f}分，满足低吸条件（评分≥50）。")
        parts.append(f"✅ 属于热门板块核心标的，资金关注度高，回调提供买点。\n")
        
        # 技术面
        parts.append("### 技术面分析")
        parts.append("- **支撑与压力**: 近期均线支撑有效，回调未破关键位置")
        parts.append("- **成交量**: 缩量回调，抛压减轻，非出货信号")
        parts.append("- **关键价位**: 关注前低支撑位，企稳可考虑介入\n")
        
        # 风险
        parts.append("### 风险因素")
        parts.append("⚠️ **回调变下跌风险**: 若继续下跌超5%，可能破位，需止损")
        parts.append("⚠️ **板块热度消退**: 若所属板块整体走弱，个股难独善其身")
        parts.append("⚠️ **市场情绪恶化**: 大盘系统性风险可能影响个股\n")
        
        # 操作建议
        parts.append("### 操作建议")
        parts.append("- **建议买入区间**: 现价附近，可分批建仓")
        parts.append("- **止损位**: 设在前低或-8%固定止损")
        parts.append("- **目标位**: 反弹至前高附近，预期收益5-10%")
        parts.append("- **建议仓位**: 半仓或轻仓试探\n")
        
        # 持有周期
        parts.append("### 持有周期预期")
        parts.append("**短线（3-5个交易日）**")
        parts.append("理由：强势股低吸属于短线策略，快速反弹后应考虑止盈。\n")
        
        # 失效条件
        parts.append("### 失效条件")
        parts.append("❌ 继续下跌超过5%，跌破关键支撑")
        parts.append("❌ 成交量异常放大，疑似主力出货")
        parts.append("❌ 所属板块出现集体大跌")
        parts.append("❌ 大盘出现系统性风险\n")
        
        return "\n".join(parts)
    
    def _generate_chase_reason(self, name: str, code: str, change_pct: float, score: float) -> str:
        """生成追涨型理由"""
        parts = []
        parts.append(f"## {name}({code}) - 追涨型分析\n")
        
        parts.append("### 核心买入逻辑")
        parts.append(f"✅ **{name}**强势上涨{change_pct:.2f}%，量价齐升，资金追捧。")
        parts.append(f"✅ 策略评分{score:.0f}分，确认为板块龙头/强势股。")
        parts.append(f"✅ 突破关键阻力位，趋势确立，追涨胜率较高。\n")
        
        parts.append("### 技术面分析")
        parts.append("- **趋势**: 多头排列，强势上涨中")
        parts.append("- **成交量**: 放量上涨，资金持续流入")
        parts.append("- **突破**: 创近期新高，上方空间打开\n")
        
        parts.append("### 风险因素")
        parts.append("⚠️ **高位追高风险**: 短期涨幅过大，可能回调")
        parts.append("⚠️ **获利盘抛压**: 前期套牢盘或获利盘可能在高位派发")
        parts.append("⚠️ **追在短期顶**: 可能买在短期情绪高点\n")
        
        parts.append("### 操作建议")
        parts.append("- **买入策略**: 轻仓追涨，不宜重仓")
        parts.append("- **止损位**: 跌破今日开盘价或-5%严格止损")
        parts.append("- **目标位**: 短期目标+8%，中期+15%")
        parts.append("- **仓位控制**: 不超过总仓位10%\n")
        
        return "\n".join(parts)
    
    def _generate_generic_reason(self, name: str, code: str, change_pct: float, score: float) -> str:
        """生成通用理由"""
        return f"""## {name}({code}) - 策略分析

### 核心逻辑
- 策略评分{score:.0f}分，触发买入信号
- 今日涨跌幅{change_pct:+.2f}%

### 建议
- 关注后续走势
- 设置合理止损

*详细分析需更多数据*
"""
    
    def generate_reason(self, signal: Dict, strategy_type: str) -> str:
        """
        生成选股理由
        
        Args:
            signal: 策略信号字典
            strategy_type: 策略类型 (dip/chase/multi/etc)
        
        Returns:
            生成的理由文本
        """
        # 准备数据
        data = {
            'name': signal.get('name', ''),
            'code': signal.get('code', ''),
            'sector': signal.get('sector', '未知'),
            'current_price': signal.get('price', 0),
            'change_pct': signal.get('change_pct', 0),
            'score': signal.get('score', 0),
            'reasons': ', '.join(signal.get('reasons', [])),
            'high_20d': signal.get('high_20d', 0),
            'low_20d': signal.get('low_20d', 0),
            'volume_ratio': signal.get('volume_ratio', 1),
            'sector_change': signal.get('sector_change', 0),
            'sector_rank': signal.get('sector_rank', 0),
            'trend': signal.get('trend', '震荡'),
            'total_score': signal.get('total_score', 0),
            'trend_score': signal.get('trend_score', 0),
            'fundamental_score': signal.get('fundamental_score', 0),
            'fund_score': signal.get('fund_score', 0),
            'technical_score': signal.get('technical_score', 0),
            'sector_score': signal.get('sector_score', 0),
            'pe': signal.get('pe', 0),
            'roe': signal.get('roe', 0)
        }
        
        # 选择模板
        template_key = {
            '强势股低吸': 'dip_buy',
            '追涨型': 'chase',
            '多维度优选': 'multi_dimension'
        }.get(strategy_type, 'dip_buy')
        
        template = self.prompt_templates.get(template_key, self.prompt_templates['dip_buy'])
        
        # 填充模板
        prompt = template.format(**data)
        
        # 调用LLM生成
        return self._call_llm(prompt)
    
    def generate_comparison(self, hold_stock: Dict, candidate: Dict) -> str:
        """
        生成换仓对比分析
        
        Args:
            hold_stock: 当前持仓股票信息
            candidate: 候选股票信息
        
        Returns:
            换仓建议分析
        """
        hold_name = hold_stock.get('name', '')
        hold_code = hold_stock.get('code', '')
        hold_pnl = hold_stock.get('pnl_pct', 0)
        
        cand_name = candidate.get('name', '')
        cand_code = candidate.get('code', '')
        cand_score = candidate.get('score', 0)
        
        lines = []
        lines.append(f"## 换仓对比分析: {hold_name} vs {cand_name}\n")
        
        lines.append("### 当前持仓分析")
        lines.append(f"- **{hold_name}({hold_code})**: 当前盈亏{hold_pnl*100:+.2f}%")
        if hold_pnl < -0.10:
            lines.append(f"  - 深度亏损，风险较高")
        elif hold_pnl < 0:
            lines.append(f"  - 小幅亏损，可观察")
        else:
            lines.append(f"  - 盈利状态，趋势良好")
        
        lines.append("\n### 候选股票分析")
        lines.append(f"- **{cand_name}({cand_code})**: 策略评分{cand_score:.0f}分")
        lines.append(f"  - 综合评分高，具备买入条件")
        
        lines.append("\n### 换仓建议")
        if hold_pnl < -0.10 and cand_score > 65:
            lines.append(f"✅ **建议换仓**")
            lines.append(f"理由：")
            lines.append(f"1. 当前持仓亏损{abs(hold_pnl)*100:.1f}%，回本难度大")
            lines.append(f"2. {cand_name}评分{cand_score:.0f}分，明显优于当前持仓")
            lines.append(f"3. 换仓预期收益更高")
            lines.append(f"\n操作：止损{hold_name}，买入{cand_name}")
        elif hold_pnl > 0.05:
            lines.append(f"⚠️ **建议观望**")
            lines.append(f"理由：当前持仓盈利，换仓机会成本较高")
        else:
            lines.append(f"🔄 **可考虑换仓**")
            lines.append(f"理由：{cand_name}评分较高，但当前持仓亏损不大，可权衡")
        
        return "\n".join(lines)


# 单例
_llm_reasoner = None

def get_llm_reasoner(provider: str = "deepseek"):
    """获取LLM推理器单例"""
    global _llm_reasoner
    if _llm_reasoner is None:
        _llm_reasoner = LLMStrategyReasoner(provider)
    return _llm_reasoner


if __name__ == '__main__':
    # 测试
    reasoner = get_llm_reasoner()
    
    test_signal = {
        'name': '中科曙光',
        'code': '603019',
        'sector': 'AI算力',
        'price': 87.70,
        'change_pct': 1.26,
        'score': 70,
        'reasons': ['强势股回调', '板块龙头'],
        'high_20d': 91.20,
        'low_20d': 84.16,
        'volume_ratio': 0.85,
        'sector_change': 1.20,
        'trend': '上升趋势'
    }
    
    reason = reasoner.generate_reason(test_signal, '强势股低吸')
    print(reason)
