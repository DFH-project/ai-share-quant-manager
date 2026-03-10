#!/usr/bin/env python3
"""
ml_predictor.py - 机器学习预测模块 v1.0 (简化版)
不依赖sklearn，使用numpy实现简单预测模型
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from core.data_fetcher import data_fetcher
from core.memory_cache_manager import get_data_cache


@dataclass
class PredictionResult:
    """预测结果"""
    code: str
    name: str
    current_price: float
    predicted_price: float
    confidence: float
    direction: str
    expected_return: float
    prediction_date: str


class SimpleLinearModel:
    """简单线性回归模型 (numpy实现)"""
    
    def __init__(self):
        self.weights = None
        self.bias = 0
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """训练模型"""
        # 添加偏置项
        X_with_bias = np.column_stack([np.ones(X.shape[0]), X])
        
        # 最小二乘法求解
        try:
            params = np.linalg.lstsq(X_with_bias, y, rcond=None)[0]
            self.bias = params[0]
            self.weights = params[1:]
        except:
            # 如果求解失败，使用简单平均
            self.weights = np.zeros(X.shape[1])
            self.bias = np.mean(y)
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测"""
        if self.weights is None:
            return np.zeros(X.shape[0])
        return np.dot(X, self.weights) + self.bias


class MLPredictor:
    """机器学习预测器 (简化版)"""
    
    def __init__(self):
        self.cache = get_data_cache()
        self.models = {}
        self.scaler_mean = None
        self.scaler_std = None
    
    def _extract_features(self, klines: List[Dict]) -> np.ndarray:
        """提取特征"""
        if len(klines) < 30:
            return None
        
        closes = [k['close'] for k in klines]
        volumes = [k['volume'] for k in klines]
        
        features = []
        
        # 价格变化特征
        features.append((closes[-1] - closes[-2]) / closes[-2] if len(closes) >= 2 else 0)
        features.append((closes[-1] - closes[-5]) / closes[-5] if len(closes) >= 5 else 0)
        features.append((closes[-1] - closes[-20]) / closes[-20] if len(closes) >= 20 else 0)
        
        # 量比
        avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]
        features.append(volumes[-1] / avg_volume if avg_volume > 0 else 1)
        
        # 波动率
        if len(closes) >= 20:
            returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(-20, 0)]
            features.append(np.std(returns))
        else:
            features.append(0)
        
        # 均线比率
        ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else closes[-1]
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        
        features.append(closes[-1] / ma5 if ma5 > 0 else 1)
        features.append(closes[-1] / ma20 if ma20 > 0 else 1)
        
        return np.array(features)
    
    def _prepare_training_data(self, code: str, days: int = 180) -> Tuple[np.ndarray, np.ndarray]:
        """准备训练数据"""
        klines = data_fetcher._get_kline_eastmoney(code, days=days+10)
        
        if len(klines) < 40:
            return None, None
        
        X = []
        y = []
        
        for i in range(30, len(klines) - 5):
            window = klines[i-30:i]
            features = self._extract_features(window)
            
            if features is not None:
                future_return = (klines[i+5]['close'] - klines[i]['close']) / klines[i]['close']
                X.append(features)
                y.append(future_return)
        
        return np.array(X), np.array(y)
    
    def _normalize(self, X: np.ndarray) -> np.ndarray:
        """标准化"""
        if self.scaler_mean is None:
            self.scaler_mean = np.mean(X, axis=0)
            self.scaler_std = np.std(X, axis=0) + 1e-8
        return (X - self.scaler_mean) / self.scaler_std
    
    def train(self, code: str) -> bool:
        """训练模型"""
        X, y = self._prepare_training_data(code)
        
        if X is None or len(X) < 30:
            return False
        
        # 标准化
        X_normalized = self._normalize(X)
        
        # 训练简单线性模型
        model = SimpleLinearModel()
        model.fit(X_normalized, y)
        
        self.models[code] = model
        return True
    
    def predict(self, code: str) -> Optional[PredictionResult]:
        """预测价格"""
        klines = data_fetcher._get_kline_eastmoney(code, days=40)
        
        if len(klines) < 30:
            return None
        
        if code not in self.models:
            success = self.train(code)
            if not success:
                return None
        
        features = self._extract_features(klines)
        if features is None:
            return None
        
        # 标准化
        X = self._normalize(features.reshape(1, -1))
        
        # 预测
        model = self.models[code]
        predicted_return = model.predict(X)[0]
        
        # 限制预测范围
        predicted_return = max(-0.1, min(0.1, predicted_return))
        
        # 计算置信度
        confidence = min(0.8, max(0.4, 1 - abs(predicted_return) * 5))
        
        # 判断方向
        if predicted_return > 0.01:
            direction = 'UP'
        elif predicted_return < -0.01:
            direction = 'DOWN'
        else:
            direction = 'SIDEWAYS'
        
        current_price = klines[-1]['close']
        predicted_price = current_price * (1 + predicted_return)
        
        name = code
        try:
            data = data_fetcher.get_stock_data([code])
            if code in data:
                name = data[code].get('name', code)
        except:
            pass
        
        return PredictionResult(
            code=code,
            name=name,
            current_price=current_price,
            predicted_price=predicted_price,
            confidence=confidence,
            direction=direction,
            expected_return=predicted_return,
            prediction_date=datetime.now().strftime('%Y-%m-%d')
        )
    
    def batch_predict(self, codes: List[str]) -> List[PredictionResult]:
        """批量预测"""
        results = []
        for code in codes:
            result = self.predict(code)
            if result:
                results.append(result)
        
        results.sort(key=lambda x: x.expected_return, reverse=True)
        return results


def print_prediction(result: PredictionResult):
    """打印预测结果"""
    emoji = "📈" if result.direction == 'UP' else ("📉" if result.direction == 'DOWN' else "➡️")
    print(f"{emoji} {result.name}({result.code})")
    print(f"   预测收益: {result.expected_return*100:+.2f}%")
    print(f"   置信度: {result.confidence*100:.0f}%")


if __name__ == '__main__':
    print("🧪 测试ML预测模块...")
    
    predictor = MLPredictor()
    
    result = predictor.predict('300750')
    if result:
        print_prediction(result)
    
    print("\n批量预测:")
    results = predictor.batch_predict(['300750', '002594'])
    for r in results:
        print_prediction(r)
