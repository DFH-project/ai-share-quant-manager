#!/usr/bin/env python3
"""
risk_assessor.py - 风险评估模块
功能：
1. 根据公告类型和程度评估风险等级
2. 生成操作建议
3. 预估对持仓的影响
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = "极高风险"  # 必须立即行动
    HIGH = "高风险"        # 建议24小时内处理
    MEDIUM = "中等风险"    # 需要关注
    LOW = "低风险"         # 正常监控
    INFO = "信息"          # 仅供参考

@dataclass
class RiskAssessment:
    """风险评估结果"""
    level: RiskLevel
    score: int  # 0-100
    reasons: List[str]
    suggested_action: str
    urgency: str  # 立即/24小时内/本周内/正常
    estimated_impact: str  # 预估影响

class RiskAssessor:
    """风险评估器"""
    
    def __init__(self):
        # 风险评分规则
        self.risk_rules = {
            '减持': {
                '清仓式': {'score': 95, 'level': RiskLevel.CRITICAL, 'keywords': ['清仓', '全额', '全部']},
                '大比例': {'score': 85, 'level': RiskLevel.HIGH, 'keywords': ['5%', '4%', '3%', '大幅']},
                '一般': {'score': 60, 'level': RiskLevel.MEDIUM, 'keywords': ['减持']},
            },
            '监管': {
                '立案': {'score': 100, 'level': RiskLevel.CRITICAL, 'keywords': ['立案', '调查', '涉嫌']},
                '处罚': {'score': 90, 'level': RiskLevel.HIGH, 'keywords': ['处罚', '罚款', '警示']},
                '问询': {'score': 70, 'level': RiskLevel.MEDIUM, 'keywords': ['问询', '关注函']},
            },
            '业绩': {
                '预减': {'score': 80, 'level': RiskLevel.HIGH, 'keywords': ['预减', '亏损', '大幅下滑']},
                '预增': {'score': 30, 'level': RiskLevel.LOW, 'keywords': ['预增', '增长']},
            },
            '质押': {
                '平仓风险': {'score': 90, 'level': RiskLevel.CRITICAL, 'keywords': ['平仓', '违约', '强制']},
                '高比例': {'score': 70, 'level': RiskLevel.MEDIUM, 'keywords': ['质押', '冻结']},
            },
            '解禁': {
                '大额': {'score': 75, 'level': RiskLevel.HIGH, 'keywords': ['解禁', '限售']},
            },
            '停牌': {
                'default': {'score': 50, 'level': RiskLevel.MEDIUM, 'keywords': ['停牌']},
            },
            '重组': {
                'default': {'score': 40, 'level': RiskLevel.LOW, 'keywords': ['重组', '并购']},
            },
            '增持': {
                'default': {'score': 20, 'level': RiskLevel.INFO, 'keywords': ['增持', '回购']},
            },
            '分红': {
                'default': {'score': 10, 'level': RiskLevel.INFO, 'keywords': ['分红', '派息']},
            },
            '高管变动': {
                '核心离职': {'score': 65, 'level': RiskLevel.MEDIUM, 'keywords': ['董事长', '总经理', '辞职']},
                '一般': {'score': 30, 'level': RiskLevel.LOW, 'keywords': ['高管', '离职']},
            },
        }
    
    def assess_news(self, title: str, categories: List[str]) -> RiskAssessment:
        """评估单条新闻的风险"""
        max_score = 0
        matched_rules = []
        matched_level = RiskLevel.LOW
        
        for category in categories:
            if category not in self.risk_rules:
                continue
            
            category_rules = self.risk_rules[category]
            
            for rule_name, rule in category_rules.items():
                if rule_name == 'default':
                    # 检查是否匹配该类别的任何关键词
                    keywords = rule.get('keywords', [])
                else:
                    keywords = rule.get('keywords', [])
                
                # 检查标题是否包含关键词
                title_lower = title.lower()
                for keyword in keywords:
                    if keyword in title_lower:
                        score = rule.get('score', 50)
                        if score > max_score:
                            max_score = score
                            matched_level = rule.get('level', RiskLevel.LOW)
                            matched_rules.append(f"{category}-{rule_name}: {keyword}")
                        break
        
        # 如果没有匹配到具体规则，给默认分
        if max_score == 0:
            max_score = 30
            matched_level = RiskLevel.LOW
            matched_rules.append("默认评估")
        
        # 生成建议
        assessment = self._generate_assessment(
            level=matched_level,
            score=max_score,
            reasons=matched_rules,
            title=title,
            categories=categories
        )
        
        return assessment
    
    def _generate_assessment(self, level: RiskLevel, score: int, 
                            reasons: List[str], title: str, 
                            categories: List[str]) -> RiskAssessment:
        """生成完整的评估结果"""
        
        # 根据风险等级生成建议
        if level == RiskLevel.CRITICAL:
            if '减持' in categories and '清仓' in title:
                suggested_action = "建议立即挂单卖出50-100%仓位，清仓式减持通常导致连续跌停"
                urgency = "立即"
                estimated_impact = "预计次日低开3-5%，甚至可能跌停"
            elif '监管' in categories:
                suggested_action = "建议立即减仓或清仓，监管风险不确定性极高"
                urgency = "立即"
                estimated_impact = "预计短期下跌10-20%，可能停牌"
            elif '质押' in categories and '平仓' in title:
                suggested_action = "建议立即卖出，质押平仓会导致踩踏式下跌"
                urgency = "立即"
                estimated_impact = "预计连续跌停，流动性枯竭"
            else:
                suggested_action = "建议立即评估持仓，考虑减仓避险"
                urgency = "立即"
                estimated_impact = "预计短期大幅下跌"
                
        elif level == RiskLevel.HIGH:
            if '减持' in categories:
                suggested_action = "建议减仓30-50%，设置-5%止损位"
                urgency = "24小时内"
                estimated_impact = "预计短期下跌5-10%"
            elif '业绩' in categories and '预减' in title:
                suggested_action = "建议减仓或调低目标价，业绩下滑影响估值"
                urgency = "本周内"
                estimated_impact = "预计下跌5-15%"
            elif '解禁' in categories:
                suggested_action = "建议减仓20-30%，解禁抛压通常持续数日"
                urgency = "24小时内"
                estimated_impact = "预计下跌3-8%"
            else:
                suggested_action = "建议减仓避险，密切关注后续发展"
                urgency = "24小时内"
                estimated_impact = "预计短期下跌5-10%"
                
        elif level == RiskLevel.MEDIUM:
            suggested_action = "建议关注，若已持仓可设-3%止损，未持仓暂时观望"
            urgency = "本周内"
            estimated_impact = "预计波动加大，下跌风险3-5%"
            
        elif level == RiskLevel.LOW:
            suggested_action = "正常持有，按原计划操作"
            urgency = "正常"
            estimated_impact = "预计影响有限"
            
        else:  # INFO
            suggested_action = "仅供参考，不影响操作"
            urgency = "正常"
            estimated_impact = "无显著影响"
        
        return RiskAssessment(
            level=level,
            score=score,
            reasons=reasons,
            suggested_action=suggested_action,
            urgency=urgency,
            estimated_impact=estimated_impact
        )
    
    def format_alert(self, code: str, name: str, title: str, 
                    categories: List[str], pub_time: str) -> str:
        """格式化警报消息"""
        assessment = self.assess_news(title, categories)
        
        # 根据风险等级选择表情
        emoji_map = {
            RiskLevel.CRITICAL: "🚨",
            RiskLevel.HIGH: "⚠️",
            RiskLevel.MEDIUM: "⚡",
            RiskLevel.LOW: "ℹ️",
            RiskLevel.INFO: "📌"
        }
        emoji = emoji_map.get(assessment.level, "⚠️")
        
        report = []
        report.append(f"\n{emoji} 【{assessment.level.value}】{name}({code})")
        report.append(f"{'='*60}")
        report.append(f"📰 公告标题: {title}")
        report.append(f"📂 类型: {', '.join(categories)}")
        report.append(f"⏰ 发布时间: {pub_time}")
        report.append(f"📊 风险评分: {assessment.score}/100")
        report.append(f"🎯 紧急程度: {assessment.urgency}")
        report.append(f"📉 预估影响: {assessment.estimated_impact}")
        report.append(f"")
        report.append(f"💡 建议行动: {assessment.suggested_action}")
        report.append(f"{'='*60}")
        
        return '\n'.join(report)


def test_assessor():
    """测试风险评估器"""
    assessor = RiskAssessor()
    
    test_cases = [
        {
            'code': '603127',
            'name': '昭衍新药',
            'title': '股东拟合计减持公司不超4.1%股份',
            'categories': ['减持'],
            'pub_time': '2026-03-16 19:08:27'
        },
        {
            'code': '600519',
            'name': '贵州茅台',
            'title': '股东拟清仓式减持公司股份',
            'categories': ['减持'],
            'pub_time': '2026-03-17 10:00:00'
        },
        {
            'code': '000001',
            'name': '平安银行',
            'title': '公司收到监管问询函',
            'categories': ['监管'],
            'pub_time': '2026-03-17 14:00:00'
        },
        {
            'code': '300001',
            'name': '特锐德',
            'title': '公司发布2025年业绩预增公告',
            'categories': ['业绩'],
            'pub_time': '2026-03-17 09:00:00'
        }
    ]
    
    print("风险评估测试\n")
    print("="*70)
    
    for case in test_cases:
        alert = assessor.format_alert(
            case['code'],
            case['name'],
            case['title'],
            case['categories'],
            case['pub_time']
        )
        print(alert)
        print()


if __name__ == '__main__':
    test_assessor()
