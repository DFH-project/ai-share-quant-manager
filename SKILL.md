# A-Share Quant Manager

A股量化交易管理系统

## 功能模块

### 1. 数据获取 (core/data_fetcher.py)
- 多数据源：腾讯、东方财富、新浪、AKShare
- 自动切换，互为兜底
- 只使用真实数据，禁止AI生成假数据

### 2. 自选股管理 (core/watchlist_memory.py)
- 管理观察池股票
- 支持分类和标签
- 持久化存储

### 3. 月度策略 (core/monthly_strategy.py)
- 技术指标分析
- 买入/卖出信号生成

### 4. 智能交易 (core/smart_trader.py)
- 交易执行
- 风险控制
- 仓位管理

### 5. 盘中监控 (scripts/intraday_monitor.py)
- 定时监控大盘和自选股
- 生成交易信号

## 使用方式

```bash
python3 main.py
```

## 数据源

- 腾讯财经
- 东方财富
- 新浪财经
- AKShare

## 监控脚本

```bash
python3 scripts/intraday_monitor.py
```
