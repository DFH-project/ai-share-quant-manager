"""
config/settings.py - 配置文件
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# AKShare配置
AKSHARE_CONFIG = {
    'timeout': 30,
    'retries': 3
}

# 策略参数
STRATEGY_CONFIG = {
    'scan_limit': 100,           # 扫描股票数量限制
    'min_score': 60,             # 最小信号分数
    'signal_valid_days': 7       # 信号有效期（天）
}

# 交易配置
TRADE_CONFIG = {
    'initial_capital': 1000000,  # 初始资金
    'commission_rate': 0.0003,   # 佣金率
    'min_commission': 5,         # 最低佣金
    'stamp_duty': 0.001,         # 印花税
    'max_position_pct': 0.2,     # 单股最大仓位
    'stop_loss_pct': 0.08,       # 止损比例
    'take_profit_pct': 0.15      # 止盈比例
}

# 日志配置
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': DATA_DIR / 'app.log'
}
