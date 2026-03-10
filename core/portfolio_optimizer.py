#!/usr/bin/env python3
"""
portfolio_optimizer.py - 组合优化器
核心功能:
1. 马科维茨均值-方差优化 (Markowitz MPT)
2. 风险平价配置 (Risk Parity)
3. 最大夏普比率组合
4. 目标收益率下的最小风险组合

设计原则:
- 与现有持仓系统兼容
- 提供多种优化目标选择
- 输出明确的调仓建议
- 考虑交易成本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from core.data_fetcher import data_fetcher
from core.historical_cache import HistoricalDataCache


@dataclass
class OptimizationResult:
    """优化结果"""
    strategy: str  # 优化策略名称
    target_return: float  # 目标收益率
    expected_return: float  # 预期收益率
    expected_risk: float  # 预期风险(标准差)
    sharpe_ratio: float  # 夏普比率
    weights: Dict[str, float]  # 各股票权重
    current_weights: Dict[str, float]  # 当前权重
    trades: List[Dict]  # 调仓建议
    risk_contribution: Dict[str, float]  # 风险贡献度


class PortfolioOptimizer:
    """组合优化器 - 马科维茨均值-方差优化"""
    
    def __init__(self, risk_free_rate: float = 0.03):
        """
        Args:
            risk_free_rate: 无风险利率，默认3%
        """
        self.risk_free_rate = risk_free_rate
        self.cache = HistoricalDataCache()
    
    def get_historical_returns(self, codes: List[str], days: int = 60) -> Tuple[np.ndarray, List[str], Dict]:
        """
        获取历史收益率矩阵
        
        Returns:
            returns_matrix: (n_days, n_stocks) 收益率矩阵
            codes: 成功获取的股票代码列表
            prices_dict: 价格数据字典
        """
        prices_dict = {}
        
        for code in codes:
            try:
                klines = data_fetcher._get_kline_eastmoney(code, days=days+5)
                if len(klines) >= days:
                    closes = [k['close'] for k in klines[-days:]]
                    prices_dict[code] = closes
            except:
                pass
        
        if not prices_dict:
            return None, [], {}
        
        # 计算日收益率
        valid_codes = list(prices_dict.keys())
        returns_list = []
        
        for code in valid_codes:
            prices = prices_dict[code]
            returns = [(prices[i] - prices[i-1]) / prices[i-1] 
                      for i in range(1, len(prices))]
            returns_list.append(returns)
        
        returns_matrix = np.array(returns_list).T  # (n_days, n_stocks)
        
        return returns_matrix, valid_codes, prices_dict
    
    def optimize_sharpe_ratio(self, codes: List[str], 
                             current_weights: Dict[str, float] = None) -> Optional[OptimizationResult]:
        """
        最大夏普比率优化
        
        Args:
            codes: 股票代码列表
            current_weights: 当前权重
        
        Returns:
            OptimizationResult: 优化结果
        """
        returns_matrix, valid_codes, prices_dict = self.get_historical_returns(codes)
        
        if returns_matrix is None or len(valid_codes) < 2:
            print("❌ 数据不足，无法优化")
            return None
        
        n = len(valid_codes)
        
        # 计算预期收益率和协方差矩阵
        expected_returns = np.mean(returns_matrix, axis=0) * 252  # 年化
        cov_matrix = np.cov(returns_matrix.T) * 252  # 年化协方差
        
        # 蒙特卡洛模拟寻找最大夏普比率
        n_portfolios = 5000
        best_sharpe = -np.inf
        best_weights = None
        
        np.random.seed(42)
        for _ in range(n_portfolios):
            # 随机权重
            weights = np.random.random(n)
            weights /= np.sum(weights)
            
            # 计算组合收益和风险
            port_return = np.dot(weights, expected_returns)
            port_risk = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            # 夏普比率
            if port_risk > 0:
                sharpe = (port_return - self.risk_free_rate) / port_risk
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_weights = weights
        
        if best_weights is None:
            return None
        
        # 计算最优组合指标
        opt_return = np.dot(best_weights, expected_returns)
        opt_risk = np.sqrt(np.dot(best_weights.T, np.dot(cov_matrix, best_weights)))
        
        # 构建结果
        weights_dict = {valid_codes[i]: best_weights[i] for i in range(n)}
        current_weights_dict = current_weights or {code: 1/n for code in valid_codes}
        
        # 风险贡献度
        marginal_risk = np.dot(cov_matrix, best_weights)
        risk_contrib = {valid_codes[i]: best_weights[i] * marginal_risk[i] / opt_risk 
                       for i in range(n)}
        
        # 生成调仓建议
        trades = []
        for code in valid_codes:
            target = weights_dict.get(code, 0)
            current = current_weights_dict.get(code, 0)
            diff = target - current
            
            if abs(diff) > 0.02:  # 超过2%才建议调仓
                action = 'BUY' if diff > 0 else 'SELL'
                trades.append({
                    'code': code,
                    'action': action,
                    'current_weight': current,
                    'target_weight': target,
                    'diff': diff
                })
        
        return OptimizationResult(
            strategy='最大夏普比率',
            target_return=opt_return,
            expected_return=opt_return,
            expected_risk=opt_risk,
            sharpe_ratio=best_sharpe,
            weights=weights_dict,
            current_weights=current_weights_dict,
            trades=trades,
            risk_contribution=risk_contrib
        )
    
    def optimize_min_risk(self, codes: List[str], 
                         target_return: float = None) -> Optional[OptimizationResult]:
        """
        最小风险优化
        
        Args:
            codes: 股票代码列表
            target_return: 目标收益率，None则为全局最小风险
        """
        returns_matrix, valid_codes, prices_dict = self.get_historical_returns(codes)
        
        if returns_matrix is None or len(valid_codes) < 2:
            return None
        
        n = len(valid_codes)
        expected_returns = np.mean(returns_matrix, axis=0) * 252
        cov_matrix = np.cov(returns_matrix.T) * 252
        
        # 蒙特卡洛模拟
        n_portfolios = 5000
        best_risk = np.inf
        best_weights = None
        best_return = 0
        
        np.random.seed(42)
        for _ in range(n_portfolios):
            weights = np.random.random(n)
            weights /= np.sum(weights)
            
            port_return = np.dot(weights, expected_returns)
            port_risk = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            # 如果有目标收益，检查是否满足
            if target_return is not None and port_return < target_return:
                continue
            
            if port_risk < best_risk:
                best_risk = port_risk
                best_weights = weights
                best_return = port_return
        
        if best_weights is None:
            return None
        
        weights_dict = {valid_codes[i]: best_weights[i] for i in range(n)}
        sharpe = (best_return - self.risk_free_rate) / best_risk if best_risk > 0 else 0
        
        return OptimizationResult(
            strategy='最小风险' + (f'(目标{target_return*100:.0f}%)' if target_return else ''),
            target_return=target_return or 0,
            expected_return=best_return,
            expected_risk=best_risk,
            sharpe_ratio=sharpe,
            weights=weights_dict,
            current_weights={},
            trades=[],
            risk_contribution={}
        )
    
    def optimize_risk_parity(self, codes: List[str]) -> Optional[OptimizationResult]:
        """
        风险平价优化 - 各资产风险贡献相等
        """
        returns_matrix, valid_codes, prices_dict = self.get_historical_returns(codes)
        
        if returns_matrix is None or len(valid_codes) < 2:
            return None
        
        n = len(valid_codes)
        expected_returns = np.mean(returns_matrix, axis=0) * 252
        cov_matrix = np.cov(returns_matrix.T) * 252
        
        # 简化版风险平价：基于波动率反比配置
        volatilities = np.sqrt(np.diag(cov_matrix))
        inv_vol = 1 / volatilities
        weights = inv_vol / np.sum(inv_vol)
        
        port_return = np.dot(weights, expected_returns)
        port_risk = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        
        weights_dict = {valid_codes[i]: weights[i] for i in range(n)}
        
        # 风险贡献度
        marginal_risk = np.dot(cov_matrix, weights)
        risk_contrib = {valid_codes[i]: weights[i] * marginal_risk[i] / port_risk 
                       for i in range(n)}
        
        sharpe = (port_return - self.risk_free_rate) / port_risk if port_risk > 0 else 0
        
        return OptimizationResult(
            strategy='风险平价',
            target_return=port_return,
            expected_return=port_return,
            expected_risk=port_risk,
            sharpe_ratio=sharpe,
            weights=weights_dict,
            current_weights={},
            trades=[],
            risk_contribution=risk_contrib
        )
    
    def suggest_rebalance(self, portfolio: Dict, 
                         optimization_type: str = 'sharpe') -> Optional[OptimizationResult]:
        """
        为持仓提供调仓建议
        
        Args:
            portfolio: 持仓数据 {'positions': [...], 'cash': ...}
            optimization_type: 'sharpe'/'min_risk'/'risk_parity'
        """
        positions = portfolio.get('positions', [])
        if len(positions) < 2:
            print("❌ 持仓少于2只，无法优化")
            return None
        
        codes = [p['code'] for p in positions]
        
        # 计算当前权重
        total_value = sum(p['current_price'] * p['quantity'] 
                         for p in positions if 'current_price' in p)
        
        if total_value == 0:
            # 获取当前价格
            data = data_fetcher.get_stock_data(codes)
            for p in positions:
                if p['code'] in data:
                    p['current_price'] = data[p['code']].get('current', p['cost_price'])
            
            total_value = sum(p['current_price'] * p['quantity'] for p in positions)
        
        current_weights = {p['code']: p['current_price'] * p['quantity'] / total_value 
                          for p in positions}
        
        # 执行优化
        if optimization_type == 'sharpe':
            return self.optimize_sharpe_ratio(codes, current_weights)
        elif optimization_type == 'min_risk':
            return self.optimize_min_risk(codes)
        elif optimization_type == 'risk_parity':
            return self.optimize_risk_parity(codes)
        else:
            return self.optimize_sharpe_ratio(codes, current_weights)


def print_optimization_result(result: OptimizationResult):
    """打印优化结果"""
    print("\n" + "="*70)
    print(f"📊 组合优化结果 - {result.strategy}")
    print("="*70)
    
    print(f"\n💰 收益风险指标:")
    print(f"   预期年化收益: {result.expected_return*100:.2f}%")
    print(f"   预期年化风险: {result.expected_risk*100:.2f}%")
    print(f"   夏普比率: {result.sharpe_ratio:.2f}")
    
    print(f"\n⚖️ 最优权重配置:")
    for code, weight in sorted(result.weights.items(), key=lambda x: -x[1]):
        print(f"   {code}: {weight*100:.1f}%")
    
    if result.trades:
        print(f"\n🔄 调仓建议:")
        for t in result.trades:
            emoji = "📈" if t['action'] == 'BUY' else "📉"
            print(f"   {emoji} {t['code']}: {t['action']} {abs(t['diff'])*100:.1f}%")
            print(f"      当前: {t['current_weight']*100:.1f}% → 目标: {t['target_weight']*100:.1f}%")
    
    print("="*70)


if __name__ == '__main__':
    # 测试
    print("🧪 测试组合优化器...")
    
    optimizer = PortfolioOptimizer()
    
    # 测试股票
    test_codes = ['300750', '002594', '601138']
    
    # 最大夏普优化
    result = optimizer.optimize_sharpe_ratio(test_codes)
    if result:
        print_optimization_result(result)
    else:
        print("❌ 优化失败")
