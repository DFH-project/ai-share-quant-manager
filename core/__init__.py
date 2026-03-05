"""
A-Share Quant Manager - 核心模块包
"""

from .data_fetcher_v2 import DataFetcherV2
from .watchlist_memory import WatchlistMemory
from .monthly_strategy import MonthlyStrategy
from .smart_trader import SmartTrader

__all__ = ['DataFetcherV2', 'WatchlistMemory', 'MonthlyStrategy', 'SmartTrader']
