#!/usr/bin/env python3
"""
并行分析引擎 - ParallelAnalyzer
核心设计：
1. 复用DataManager已获取的数据，禁止重复API调用
2. 多线程并行分析（5只并发）
3. 结果缓存，避免重复计算
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from core.data_manager import data_manager

@dataclass
class AnalysisResult:
    """分析结果"""
    code: str
    name: str
    current_price: float
    change_pct: float
    
    # 多维度评分
    trend_score: float = 50      # 趋势分
    fundamental_score: float = 50 # 基本面分
    fund_score: float = 50       # 资金分
    technical_score: float = 50  # 技术分
    sector_score: float = 50     # 板块分
    total_score: float = 50      # 总分
    
    # 分析结论
    suggestion: str = ""
    risk_level: str = "中"
    
    # 策略匹配
    matched_strategies: List[str] = None
    
    def __post_init__(self):
        if self.matched_strategies is None:
            self.matched_strategies = []


class ParallelAnalyzer:
    """并行分析器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.data_manager = data_manager
    
    def analyze_stocks(self, codes: List[str], stock_data: Dict[str, Dict] = None) -> Dict[str, AnalysisResult]:
        """
        并行分析多只股票
        
        Args:
            codes: 股票代码列表
            stock_data: 已获取的股票数据（复用，不再调用API）
        
        Returns:
            Dict[str, AnalysisResult]: 分析结果字典
        """
        if not codes:
            return {}
        
        # 如果没有提供数据，先获取（只调用一次）
        if stock_data is None:
            stock_data = self.data_manager.fetch_stock_data(codes)
        
        results = {}
        
        # 并行分析（5只并发）
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            
            for code in codes:
                if code in stock_data:
                    future = executor.submit(self._analyze_single, code, stock_data[code])
                    futures[future] = code
            
            for future in as_completed(futures):
                code = futures[future]
                try:
                    result = future.result()
                    results[code] = result
                except Exception as e:
                    print(f"[分析] {code} 分析失败: {e}")
        
        return results
    
    def _analyze_single(self, code: str, data: Dict) -> AnalysisResult:
        """分析单只股票"""
        name = data.get('name', code)
        current = data.get('current', 0)
        change = data.get('change_pct', 0)
        
        # 初始化评分
        trend_score = 50
        fund_score = 50
        tech_score = 50
        fundamental_score = 50
        
        # 1. 趋势分析
        ma30 = data.get('ma30', 0)
        ma60 = data.get('ma60', 0)
        if ma30 > 0 and ma60 > 0:
            if current > ma30 > ma60:
                trend_score = 70  # 多头排列
            elif current > ma30:
                trend_score = 60  # 短期强势
            elif current > ma60:
                trend_score = 50  # 中期支撑
            else:
                trend_score = 40  # 弱势
        
        # 2. 资金面分析
        volume_ratio = data.get('volume_ratio', 1)
        if volume_ratio > 2:
            fund_score = 70  # 放量
        elif volume_ratio > 1.5:
            fund_score = 60  # 温和放量
        elif volume_ratio > 0.8:
            fund_score = 50  # 正常
        else:
            fund_score = 40  # 缩量
        
        # 3. 技术面分析
        high_20d = data.get('high_20d', 0)
        low_20d = data.get('low_20d', 0)
        if high_20d > low_20d > 0:
            position = (current - low_20d) / (high_20d - low_20d)
            if position > 0.7:
                tech_score = 65  # 接近新高
            elif position > 0.3:
                tech_score = 50  # 中位
            else:
                tech_score = 40  # 接近低点
        
        # 4. 基本面分析（简化版，使用已有数据）
        pe = data.get('pe', 0)
        pb = data.get('pb', 0)
        if 0 < pe < 30:
            fundamental_score = 65  # 合理估值
        elif 0 < pe < 50:
            fundamental_score = 50
        else:
            fundamental_score = 40
        
        # 计算总分
        total = (trend_score * 0.25 + 
                fundamental_score * 0.25 + 
                fund_score * 0.2 + 
                tech_score * 0.2 + 
                50 * 0.1)  # 板块分默认50
        
        # 生成建议
        if total >= 65:
            suggestion = "建议买入，整体向好"
            risk = "低"
        elif total >= 55:
            suggestion = "可以关注，等待更明确信号"
            risk = "中"
        else:
            suggestion = "观望，等待机会"
            risk = "高"
        
        # 匹配策略
        strategies = []
        if change < -5 and total > 50:
            strategies.append("急跌反弹")
        if change > 3 and volume_ratio > 1.5:
            strategies.append("追涨型")
        if -4 < change < -1 and trend_score > 55:
            strategies.append("强势股低吸")
        
        return AnalysisResult(
            code=code,
            name=name,
            current_price=current,
            change_pct=change,
            trend_score=trend_score,
            fundamental_score=fundamental_score,
            fund_score=fund_score,
            technical_score=tech_score,
            total_score=total,
            suggestion=suggestion,
            risk_level=risk,
            matched_strategies=strategies
        )


# 全局分析器实例
parallel_analyzer = ParallelAnalyzer()
