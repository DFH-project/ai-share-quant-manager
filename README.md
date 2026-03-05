# A-Share Quant Manager

A股投资量化管理工具 - 自选股管理与智能交易系统

## 项目结构

```
a-share-quant-manager/
├── core/                       # 核心模块
│   ├── __init__.py
│   ├── watchlist_memory.py     # 自选股记忆模块
│   ├── monthly_strategy.py     # 月度策略模块
│   ├── smart_trader.py         # 智能交易模块
│   └── data_fetcher_v2.py      # 数据获取模块V2
├── config/                     # 配置文件
│   ├── __init__.py
│   └── settings.py
├── utils/                      # 工具函数
│   ├── __init__.py
│   └── helpers.py
├── tests/                      # 测试文件
│   ├── __init__.py
│   └── test_modules.py
├── data/                       # 数据存储
│   └── watchlist.json
├── main.py                     # 主入口
├── requirements.txt            # 依赖
└── README.md                   # 项目说明
```

## 功能模块

### 1. watchlist_memory.py - 自选股记忆模块
- 管理用户自选股列表
- 持久化存储到本地JSON
- 支持增删改查操作
- 支持分类和标签管理

### 2. monthly_strategy.py - 月度策略模块
- 月度选股策略
- 策略回测与评估
- 生成月度交易信号
- 技术指标分析（MA, RSI, MACD, 布林带）

### 3. smart_trader.py - 智能交易模块
- 交易执行与风控
- 仓位管理
- 交易记录追踪
- 止损止盈检查

### 4. data_fetcher_v2.py - 数据获取模块
- A股实时数据获取（AKShare）
- 历史数据下载
- 数据清洗与缓存
- 指数和板块数据

## 模块联动关系

```
┌─────────────────┐
│  DataFetcherV2  │◄────── 真实数据源 (AKShare)
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ WatchlistMemory │────►│ MonthlyStrategy │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │                       ▼
         │              ┌─────────────────┐
         └─────────────►│   SmartTrader   │
                        └─────────────────┘
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 命令行交互模式
```bash
python main.py
```

### 作为库使用
```python
from core.data_fetcher_v2 import DataFetcherV2
from core.watchlist_memory import WatchlistMemory
from core.monthly_strategy import MonthlyStrategy
from core.smart_trader import SmartTrader

# 初始化模块
fetcher = DataFetcherV2()
watchlist = WatchlistMemory()
strategy = MonthlyStrategy(fetcher)
trader = SmartTrader(fetcher)

# 添加自选股
watchlist.add('000001', category='关注', data_fetcher=fetcher)

# 运行策略扫描
signals = strategy.scan_watchlist(watchlist)

# 执行交易
order_ids = trader.execute_strategy_signals(signals, watchlist)
```

## 数据说明

本项目使用真实数据源：
- **AKShare**: A股实时/历史数据（主要数据源）
- 所有数据均为真实市场数据，禁止AI生成假数据

## 测试

运行模块测试：
```bash
python tests/test_modules.py
```

或从主菜单选择选项9

## 更新日志

### 2024-03-05
- 完成Watchlist模块升级
- 修复模块间数据流转问题
- 统一接口命名规范
- 添加单例模式支持
