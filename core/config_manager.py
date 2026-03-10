#!/usr/bin/env python3
"""
config_manager.py - 统一配置管理系统
集中管理所有配置，支持热更新，环境变量覆盖
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class DataConfig:
    """数据配置"""
    cache_ttl_minutes: int = 5
    max_retry: int = 3
    timeout_seconds: int = 10
    sources: list = None
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = ['tencent', 'eastmoney', 'sina', 'akshare']


@dataclass
class MonitorConfig:
    """监控配置"""
    high_frequency_interval: int = 10  # 分钟
    medium_frequency_interval: int = 30  # 分钟  
    low_frequency_interval: int = 60  # 分钟
    alert_cooldown_minutes: int = 30
    price_change_threshold: float = 0.03  # 3%
    volume_ratio_threshold: float = 3.0
    drawdown_threshold: float = 0.08  # 8%


@dataclass
class RiskConfig:
    """风险控制配置"""
    stop_loss_pct: float = -0.08  # -8%
    take_profit_pct: float = 0.15  # +15%
    max_position_pct: float = 0.25  # 单股最大25%
    max_drawdown_pct: float = 0.15  # 组合最大回撤15%
    var_confidence: float = 0.95


@dataclass
class StrategyConfig:
    """策略配置"""
    enabled_strategies: list = None
    dip_buy_score_threshold: int = 50
    momentum_score_threshold: int = 60
    value_pe_threshold: float = 20.0
    value_roe_threshold: float = 15.0
    
    def __post_init__(self):
        if self.enabled_strategies is None:
            self.enabled_strategies = [
                'dip_buy', 'momentum', 'value', 'multi_dimension'
            ]


@dataclass
class AnalysisConfig:
    """分析配置"""
    trend_weight: float = 0.30
    fundamental_weight: float = 0.25
    fund_flow_weight: float = 0.20
    technical_weight: float = 0.15
    sector_weight: float = 0.10
    lookback_days: int = 60


@dataclass
class MLConfig:
    """机器学习配置"""
    enabled: bool = True
    prediction_horizon: int = 5  # 预测未来5天
    confidence_threshold: float = 0.6
    retrain_interval_days: int = 7
    features: list = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = [
                'price_change', 'volume_ratio', 'ma5', 'ma20', 
                'rsi', 'macd', 'volatility'
            ]


@dataclass
class SystemConfig:
    """系统配置"""
    debug: bool = False
    log_level: str = 'INFO'
    max_workers: int = 8
    data_dir: str = 'data'
    cache_dir: str = 'data/cache'


class ConfigManager:
    """配置管理器 - 单例模式"""
    
    _instance = None
    _config_file = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._config_file = Path(__file__).parent.parent / 'config' / 'system_config.yaml'
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 默认配置
        self.data = DataConfig()
        self.monitor = MonitorConfig()
        self.risk = RiskConfig()
        self.strategy = StrategyConfig()
        self.analysis = AnalysisConfig()
        self.ml = MLConfig()
        self.system = SystemConfig()
        
        # 加载配置
        self.load()
    
    def load(self):
        """从文件加载配置"""
        if not self._config_file.exists():
            self.save()  # 创建默认配置
            return
        
        try:
            with open(self._config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if data:
                # 更新各模块配置
                if 'data' in data:
                    self.data = DataConfig(**data['data'])
                if 'monitor' in data:
                    self.monitor = MonitorConfig(**data['monitor'])
                if 'risk' in data:
                    self.risk = RiskConfig(**data['risk'])
                if 'strategy' in data:
                    self.strategy = StrategyConfig(**data['strategy'])
                if 'analysis' in data:
                    self.analysis = AnalysisConfig(**data['analysis'])
                if 'ml' in data:
                    self.ml = MLConfig(**data['ml'])
                if 'system' in data:
                    self.system = SystemConfig(**data['system'])
            
            # 环境变量覆盖
            self._override_from_env()
            
        except Exception as e:
            print(f"⚠️ 加载配置失败，使用默认配置: {e}")
    
    def save(self):
        """保存配置到文件"""
        try:
            data = {
                'data': asdict(self.data),
                'monitor': asdict(self.monitor),
                'risk': asdict(self.risk),
                'strategy': asdict(self.strategy),
                'analysis': asdict(self.analysis),
                'ml': asdict(self.ml),
                'system': asdict(self.system),
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self._config_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            
        except Exception as e:
            print(f"⚠️ 保存配置失败: {e}")
    
    def _override_from_env(self):
        """从环境变量覆盖配置"""
        # 数据配置
        if os.getenv('CACHE_TTL'):
            self.data.cache_ttl_minutes = int(os.getenv('CACHE_TTL'))
        
        # 监控配置
        if os.getenv('ALERT_COOLDOWN'):
            self.monitor.alert_cooldown_minutes = int(os.getenv('ALERT_COOLDOWN'))
        
        # 风险配置
        if os.getenv('STOP_LOSS'):
            self.risk.stop_loss_pct = float(os.getenv('STOP_LOSS'))
        
        # 系统配置
        if os.getenv('DEBUG'):
            self.system.debug = os.getenv('DEBUG').lower() == 'true'
        if os.getenv('LOG_LEVEL'):
            self.system.log_level = os.getenv('LOG_LEVEL')
    
    def get(self, path: str, default=None):
        """
        获取配置项
        
        Args:
            path: 配置路径，如 'monitor.price_change_threshold'
            default: 默认值
        """
        try:
            parts = path.split('.')
            obj = self
            for part in parts:
                obj = getattr(obj, part)
            return obj
        except:
            return default
    
    def set(self, path: str, value):
        """
        设置配置项
        
        Args:
            path: 配置路径
            value: 配置值
        """
        try:
            parts = path.split('.')
            obj = self
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)
            self.save()
        except Exception as e:
            print(f"⚠️ 设置配置失败: {e}")
    
    def display(self):
        """显示当前配置"""
        print("\n" + "="*60)
        print("📋 系统配置")
        print("="*60)
        
        print(f"\n数据配置:")
        print(f"  缓存TTL: {self.data.cache_ttl_minutes}分钟")
        print(f"  数据源: {', '.join(self.data.sources)}")
        
        print(f"\n监控配置:")
        print(f"  高频监控: {self.monitor.high_frequency_interval}分钟")
        print(f"  价格阈值: {self.monitor.price_change_threshold*100:.0f}%")
        print(f"  量比阈值: {self.monitor.volume_ratio_threshold}")
        
        print(f"\n风险控制:")
        print(f"  止损线: {self.risk.stop_loss_pct*100:.0f}%")
        print(f"  止盈线: {self.risk.take_profit_pct*100:.0f}%")
        print(f"  最大仓位: {self.risk.max_position_pct*100:.0f}%")
        
        print(f"\n分析权重:")
        print(f"  趋势: {self.analysis.trend_weight*100:.0f}%")
        print(f"  基本面: {self.analysis.fundamental_weight*100:.0f}%")
        print(f"  资金面: {self.analysis.fund_flow_weight*100:.0f}%")
        
        print("="*60)


# 全局配置实例
_config = None

def get_config() -> ConfigManager:
    """获取配置管理器实例"""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config


# 便捷函数
def cfg(path: str, default=None):
    """快速获取配置"""
    return get_config().get(path, default)


if __name__ == '__main__':
    # 测试
    config = get_config()
    config.display()
    
    # 测试获取配置
    print(f"\n止损线: {cfg('risk.stop_loss_pct')}")
    print(f"监控间隔: {cfg('monitor.high_frequency_interval')}分钟")
