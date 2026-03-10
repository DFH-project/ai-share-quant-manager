#!/usr/bin/env python3
"""
多维度股票分析引擎 - Multi-Dimension Stock Analyzer
综合：趋势、基本面、资金面、技术面、板块面
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.fundamental_service import get_fundamental_data
from core.enhanced_fundamental import get_fundamental_data as get_enhanced_fundamental
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
from dataclasses import dataclass

@dataclass
class StockAnalysisResult:
    """股票分析结果"""
    code: str
    name: str
    
    # 价格数据
    current_price: float
    change_pct: float
    
    # 趋势评分 (30%)
    trend_score: float  # 0-100
    trend_details: Dict
    
    # 基本面评分 (25%)
    fundamental_score: float  # 0-100
    fundamental_details: Dict
    
    # 资金面评分 (20%)
    fund_score: float  # 0-100
    fund_details: Dict
    
    # 技术面评分 (15%)
    technical_score: float  # 0-100
    technical_details: Dict
    
    # 板块面评分 (10%)
    sector_score: float  # 0-100
    sector_details: Dict
    
    # 综合评分
    total_score: float  # 0-100
    
    # 建议
    suggestion: str
    risk_level: str  # 低/中/高

class MultiDimensionAnalyzer:
    """多维度分析器"""
    
    # 权重配置
    WEIGHTS = {
        'trend': 0.30,
        'fundamental': 0.25,
        'fund': 0.20,
        'technical': 0.15,
        'sector': 0.10
    }
    
    def __init__(self):
        self.data_fetcher = data_fetcher
    
    def analyze_stock(self, code: str, name: str = "") -> Optional[StockAnalysisResult]:
        """综合分析单只股票"""
        try:
            # 获取实时数据
            stock_data = self.data_fetcher.get_stock_data([code])
            if code not in stock_data:
                return None
            
            data = stock_data[code]
            current = data.get('current', 0)
            change_pct = data.get('change_pct', 0)
            
            # 1. 趋势分析
            trend_score, trend_details = self._analyze_trend(code, data)
            
            # 2. 基本面分析
            fundamental_score, fundamental_details = self._analyze_fundamental(code)
            
            # 3. 资金面分析
            fund_score, fund_details = self._analyze_fund_flow(code, data)
            
            # 4. 技术面分析
            technical_score, technical_details = self._analyze_technical(code, data)
            
            # 5. 板块面分析
            sector_score, sector_details = self._analyze_sector(code, data)
            
            # 计算综合评分
            total_score = (
                trend_score * self.WEIGHTS['trend'] +
                fundamental_score * self.WEIGHTS['fundamental'] +
                fund_score * self.WEIGHTS['fund'] +
                technical_score * self.WEIGHTS['technical'] +
                sector_score * self.WEIGHTS['sector']
            )
            
            # 生成建议
            suggestion, risk_level = self._generate_suggestion(
                total_score, trend_score, fundamental_score, change_pct
            )
            
            return StockAnalysisResult(
                code=code,
                name=name or data.get('name', code),
                current_price=current,
                change_pct=change_pct,
                trend_score=trend_score,
                trend_details=trend_details,
                fundamental_score=fundamental_score,
                fundamental_details=fundamental_details,
                fund_score=fund_score,
                fund_details=fund_details,
                technical_score=technical_score,
                technical_details=technical_details,
                sector_score=sector_score,
                sector_details=sector_details,
                total_score=total_score,
                suggestion=suggestion,
                risk_level=risk_level
            )
            
        except Exception as e:
            print(f"分析股票 {code} 失败: {e}")
            return None
    
    def _analyze_trend(self, code: str, data: Dict) -> Tuple[float, Dict]:
        """
        趋势分析 (30%)
        - 股价位置（相对20日/60日/120日高低点）
        - 均线排列（5/10/20日均线）
        - 近期趋势方向
        """
        score = 50  # 基础分
        details = {}
        
        try:
            current = data.get('current', 0)
            
            # 获取历史高点数据
            high_20d = data.get('high_20d', current)
            low_20d = data.get('low_20d', current * 0.9)
            
            # 1. 股价位置评分 (0-40分)
            if high_20d > low_20d:
                position = (current - low_20d) / (high_20d - low_20d) * 100
                details['20日位置'] = f"{position:.1f}%"
                
                if position >= 80:
                    score += 20  # 接近新高，强势
                    details['位置评价'] = '接近20日新高，强势'
                elif position >= 60:
                    score += 10
                    details['位置评价'] = '位于20日高位'
                elif position >= 40:
                    score += 0
                    details['位置评价'] = '位于20日中位'
                elif position >= 20:
                    score -= 10
                    details['位置评价'] = '位于20日低位'
                else:
                    score -= 20
                    details['位置评价'] = '接近20日新低，弱势'
            
            # 2. 今日涨跌 (0-30分)
            change_pct = data.get('change_pct', 0)
            if change_pct > 5:
                score += 20
                details['今日表现'] = '强势上涨'
            elif change_pct > 2:
                score += 10
                details['今日表现'] = '温和上涨'
            elif change_pct > -2:
                score += 0
                details['今日表现'] = '横盘整理'
            elif change_pct > -5:
                score -= 10
                details['今日表现'] = '回调中'
            else:
                score -= 20
                details['今日表现'] = '大幅下跌'
            
            # 3. 量能配合 (0-30分)
            volume_ratio = data.get('volume_ratio', 1)
            if volume_ratio > 2:
                score += 15
                details['量能'] = '放量明显'
            elif volume_ratio > 1.5:
                score += 10
                details['量能'] = '温和放量'
            elif volume_ratio > 0.8:
                score += 0
                details['量能'] = '量能正常'
            else:
                score -= 10
                details['量能'] = '缩量明显'
            
        except Exception as e:
            details['error'] = str(e)
        
        return max(0, min(100, score)), details
    
    def _analyze_fundamental(self, code: str) -> Tuple[float, Dict]:
        """
        基本面分析 (25%) - 使用增强版基本面数据
        包含：PE/PB/ROE/营收增长/利润增长/毛利率/负债率/机构持仓/北向资金/研报
        优先使用缓存，每晚23:00自动更新
        """
        score = 50  # 基础分
        details = {}
        
        # 获取增强版基本面数据
        fundamental = get_enhanced_fundamental(code)
        
        if fundamental is None:
            # 获取失败，使用基础分
            details['数据来源'] = '获取失败'
            details['状态'] = '使用基础分50分'
            return 50, details
        
        details['数据来源'] = '增强版基本面数据'
        details['更新时间'] = fundamental.get('update_time', '')[:10]
        
        # 1. PE估值评分 (0-20分)
        pe = fundamental.get('pe', 0)
        if pe and pe > 0:
            details['PE'] = f"{pe:.2f}"
            if pe < 15:
                score += 20
                details['PE评价'] = '低估值(PE<15)'
            elif pe < 30:
                score += 15
                details['PE评价'] = '适中(PE<30)'
            elif pe < 50:
                score += 5
                details['PE评价'] = '偏高(PE<50)'
            else:
                score -= 10
                details['PE评价'] = '过高(PE>=50)'
        
        # 2. ROE盈利能力 (0-20分)
        roe = fundamental.get('roe', 0)
        if roe and roe > 0:
            details['ROE'] = f"{roe:.2f}%"
            if roe > 20:
                score += 20
                details['ROE评价'] = '优秀(>20%)'
            elif roe > 15:
                score += 15
                details['ROE评价'] = '良好(>15%)'
            elif roe > 10:
                score += 10
                details['ROE评价'] = '一般(>10%)'
            else:
                score -= 5
                details['ROE评价'] = '较低(<10%)'
        
        # 3. PB估值 (0-10分)
        pb = fundamental.get('pb', 0)
        if pb and pb > 0:
            details['PB'] = f"{pb:.2f}"
            if pb < 2:
                score += 10
                details['PB评价'] = '低PB(<2)'
            elif pb < 4:
                score += 5
                details['PB评价'] = '适中(<4)'
            elif pb < 8:
                score += 0
                details['PB评价'] = '偏高(<8)'
            else:
                score -= 5
                details['PB评价'] = '过高(>=8)'
        
        # 4. 营收增长 (0-15分) - 新增
        revenue_growth = fundamental.get('revenue_growth', 0)
        if revenue_growth:
            details['营收增长'] = f"{revenue_growth:.1f}%"
            if revenue_growth > 30:
                score += 15
                details['营收评价'] = '高增长(>30%)'
            elif revenue_growth > 15:
                score += 10
                details['营收评价'] = '稳健增长(>15%)'
            elif revenue_growth > 0:
                score += 5
                details['营收评价'] = '正增长'
            else:
                score -= 5
                details['营收评价'] = '负增长'
        
        # 5. 净利润增长 (0-15分) - 新增
        profit_growth = fundamental.get('profit_growth', 0)
        if profit_growth:
            details['利润增长'] = f"{profit_growth:.1f}%"
            if profit_growth > 30:
                score += 15
                details['利润评价'] = '高增长(>30%)'
            elif profit_growth > 15:
                score += 10
                details['利润评价'] = '稳健增长(>15%)'
            elif profit_growth > 0:
                score += 5
                details['利润评价'] = '正增长'
            else:
                score -= 10
                details['利润评价'] = '负增长'
        
        # 6. 毛利率 (0-10分) - 新增
        gross_margin = fundamental.get('gross_margin', 0)
        if gross_margin:
            details['毛利率'] = f"{gross_margin:.1f}%"
            if gross_margin > 40:
                score += 10
                details['毛利评价'] = '高毛利(>40%)'
            elif gross_margin > 25:
                score += 5
                details['毛利评价'] = '良好(>25%)'
            else:
                details['毛利评价'] = '一般'
        
        # 7. 负债率 (0-10分) - 新增
        debt_ratio = fundamental.get('debt_ratio', 0)
        if debt_ratio:
            details['负债率'] = f"{debt_ratio:.1f}%"
            if debt_ratio < 40:
                score += 10
                details['负债评价'] = '低负债(<40%)'
            elif debt_ratio < 60:
                score += 5
                details['负债评价'] = '适中(<60%)'
            else:
                score -= 5
                details['负债评价'] = '高负债(>=60%)'
        
        # 8. 机构持仓 (0-10分) - 新增
        inst_hold = fundamental.get('institutional_hold', 0)
        if inst_hold:
            details['机构持仓'] = f"{inst_hold:.1f}%"
            if inst_hold > 30:
                score += 10
                details['机构评价'] = '机构重仓(>30%)'
            elif inst_hold > 10:
                score += 5
                details['机构评价'] = '机构关注(>10%)'
            else:
                details['机构评价'] = '机构低配'
        
        # 9. 北向资金 (0-5分) - 新增
        northbound = fundamental.get('northbound_ratio', 0)
        if northbound:
            details['北向资金'] = f"{northbound:.2f}%"
            if northbound > 5:
                score += 5
                details['北向评价'] = '外资重仓(>5%)'
            elif northbound > 1:
                score += 3
                details['北向评价'] = '外资关注(>1%)'
        
        # 10. 研报覆盖 (0-5分) - 新增
        research_count = fundamental.get('research_count', 0)
        if research_count:
            details['研报数量'] = f"{research_count}份"
            if research_count > 10:
                score += 5
                details['研报评价'] = '高度关注(>10份)'
            elif research_count > 3:
                score += 3
                details['研报评价'] = '有一定关注'
        
        # 行业信息
        industry = fundamental.get('industry', '')
        if industry:
            details['所属行业'] = industry
        
        return max(0, min(100, score)), details
    
    def _analyze_fund_flow(self, code: str, data: Dict) -> Tuple[float, Dict]:
        """
        资金面分析 (20%)
        - 主力资金流向
        - 成交量变化
        - 大单买入情况
        """
        score = 50
        details = {}
        
        try:
            # 1. 主力资金 (0-50分)
            main_force = data.get('main_force_flow', 0)
            if main_force > 0:
                score += 25
                details['主力资金'] = '净流入'
            else:
                score -= 10
                details['主力资金'] = '净流出'
            
            # 2. 成交量比 (0-30分)
            volume_ratio = data.get('volume_ratio', 1)
            if volume_ratio > 2:
                score += 15
                details['量能'] = '显著放量'
            elif volume_ratio > 1.5:
                score += 10
                details['量能'] = '温和放量'
            elif volume_ratio > 0.8:
                score += 0
                details['量能'] = '量能正常'
            else:
                score -= 10
                details['量能'] = '缩量'
            
            # 3. 涨跌与资金配合 (0-20分)
            change_pct = data.get('change_pct', 0)
            if change_pct > 0 and main_force > 0:
                score += 10
                details['配合度'] = '量价齐升，配合良好'
            elif change_pct < 0 and main_force < 0:
                score -= 10
                details['配合度'] = '量价齐跌，资金出逃'
            else:
                details['配合度'] = '量价背离，需观察'
            
        except Exception as e:
            details['error'] = str(e)
        
        return max(0, min(100, score)), details
    
    def _analyze_technical(self, code: str, data: Dict) -> Tuple[float, Dict]:
        """
        技术面分析 (15%)
        - MACD状态
        - 支撑压力位
        - K线形态
        """
        score = 50
        details = {}
        
        try:
            # 简化技术分析
            current = data.get('current', 0)
            open_price = data.get('open', current)
            high = data.get('high', current)
            low = data.get('low', current)
            
            # 1. 日内走势 (0-40分)
            if current > open_price:
                score += 15
                details['日内走势'] = '上涨'
            elif current < open_price:
                score -= 10
                details['日内走势'] = '下跌'
            else:
                details['日内走势'] = '平盘'
            
            # 2. 上下影线 (0-30分)
            if high > low:
                upper_shadow = (high - max(current, open_price)) / (high - low) * 100
                lower_shadow = (min(current, open_price) - low) / (high - low) * 100
                
                if lower_shadow > 20:  # 有明显下影线
                    score += 15
                    details['K线形态'] = '有下影线，支撑有效'
                elif upper_shadow > 20:  # 有明显上影线
                    score -= 10
                    details['K线形态'] = '有上影线，压力明显'
                else:
                    details['K线形态'] = '实体K线'
            
            # 3. 涨跌幅技术评分 (0-30分)
            change_pct = data.get('change_pct', 0)
            if 0 < change_pct < 5:
                score += 10
                details['涨跌评价'] = '温和上涨，技术健康'
            elif change_pct >= 5:
                score += 5
                details['涨跌评价'] = '大涨，注意是否超买'
            elif -3 < change_pct < 0:
                score -= 5
                details['涨跌评价'] = '小幅回调，关注支撑'
            elif change_pct <= -3:
                score -= 15
                details['涨跌评价'] = '明显回调，技术走弱'
            
        except Exception as e:
            details['error'] = str(e)
        
        return max(0, min(100, score)), details
    
    def _analyze_sector(self, code: str, data: Dict) -> Tuple[float, Dict]:
        """
        板块面分析 (10%)
        - 所属板块强度
        - 板块内排名
        - 板块轮动位置
        """
        score = 50
        details = {}
        
        try:
            # 这里需要结合板块数据
            # 简化处理
            change_pct = data.get('change_pct', 0)
            
            if change_pct > 5:
                score += 30
                details['板块地位'] = '板块领涨'
            elif change_pct > 2:
                score += 15
                details['板块地位'] = '板块强势'
            elif change_pct > 0:
                score += 5
                details['板块地位'] = '跟随板块'
            elif change_pct > -2:
                score -= 5
                details['板块地位'] = '弱于板块'
            else:
                score -= 15
                details['板块地位'] = '板块落后'
            
            details['板块趋势'] = '需结合板块指数判断'
            
        except Exception as e:
            details['error'] = str(e)
        
        return max(0, min(100, score)), details
    
    def _generate_suggestion(self, total_score: float, trend_score: float, 
                            fundamental_score: float, change_pct: float) -> Tuple[str, str]:
        """生成投资建议"""
        
        if total_score >= 80:
            if change_pct > 0:
                return "强烈建议买入，多维度优秀", "低"
            else:
                return "优质标的，等待低吸机会", "低"
        elif total_score >= 65:
            if change_pct > 0:
                return "建议买入，整体向好", "中低"
            else:
                return "关注买入机会", "中"
        elif total_score >= 50:
            return "观望，等待更明确信号", "中"
        elif total_score >= 35:
            return "谨慎，存在风险因素", "中高"
        else:
            return "回避，多维度走弱", "高"
    
    def batch_analyze(self, codes: List[str]) -> List[StockAnalysisResult]:
        """批量分析"""
        results = []
        for code in codes:
            result = self.analyze_stock(code)
            if result:
                results.append(result)
        
        # 按综合评分排序
        results.sort(key=lambda x: x.total_score, reverse=True)
        return results
    
    def format_report(self, result: StockAnalysisResult) -> str:
        """格式化分析报告"""
        lines = [
            f"\n{'='*60}",
            f"📊 {result.name}({result.code}) 多维度分析报告",
            f"{'='*60}",
            f"当前价格: {result.current_price:.2f} ({result.change_pct:+.2f}%)",
            f"",
            f"【综合评分】{result.total_score:.1f}/100 | 风险等级: {result.risk_level}",
            f"建议: {result.suggestion}",
            f"",
            f"【各维度评分】",
            f"  趋势面(30%): {result.trend_score:.1f} - {result.trend_details.get('位置评价', 'N/A')}",
            f"  基本面(25%): {result.fundamental_score:.1f} - {result.fundamental_details.get('基本面评价', 'N/A')}",
            f"  资金面(20%): {result.fund_score:.1f} - {result.fund_details.get('主力资金', 'N/A')}",
            f"  技术面(15%): {result.technical_score:.1f} - {result.technical_details.get('K线形态', 'N/A')}",
            f"  板块面(10%): {result.sector_score:.1f} - {result.sector_details.get('板块地位', 'N/A')}",
            f"{'='*60}"
        ]
        return "\n".join(lines)


# 单例
_analyzer = None

def get_analyzer() -> MultiDimensionAnalyzer:
    """获取分析器单例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = MultiDimensionAnalyzer()
    return _analyzer


if __name__ == '__main__':
    analyzer = MultiDimensionAnalyzer()
    result = analyzer.analyze_stock('603019', '中科曙光')
    if result:
        print(analyzer.format_report(result))
