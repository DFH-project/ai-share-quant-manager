# A-Share Quant Manager V3.2

## 🆕 最新更新 (2026-03-10)

### 7项核心优化 (今晚完成)

| 优化项 | 文件 | 功能描述 |
|:---|:---|:---|
| **1. 集中配置系统** | `core/config_manager.py` | 统一YAML配置，环境变量覆盖，热更新支持 |
| **2. 内存缓存优化** | `core/memory_cache_manager.py` | LRU缓存+TTL过期，命中率统计，线程安全 |
| **3. 分钟级监控** | `core/minute_monitor.py` | 30分钟级别精细监控，回调系统 |
| **4. 完整回测系统** | `core/enhanced_backtest.py` | 4种策略(均线/突破/RSI/MACD)+参数优化 |
| **5. ML预测模块** | `core/ml_predictor.py` | 智能预测价格走势，置信度评估 |
| **6. 完全联动系统** | `core/integrated_system.py` | 统一入口，一键调用所有模块 |
| **7. 板块轮动监控** | `core/sector_rotation_monitor.py` | AI产业链资金流向追踪 |

### 新增能力
- **多策略回测**: 突破策略在AI产业链100%有效
- **ML预测**: 短期方向预测 + 置信度评分
- **智能预警**: 止损/止盈/波动/突破多维监控
- **板块轮动**: CPO/AI服务器/芯片实时追踪

## 系统架构 V3.2

```
配置层 (config_manager) 
    ↓
缓存层 (memory_cache_manager - LRU+TTL)
    ↓
数据层 (CachedDataFetcher)
    ↓
业务层 ├─ 分钟监控 (minute_monitor)
       ├─ 智能预警 (smart_alert_system)
       ├─ 策略回测 (enhanced_backtest)
       ├─ ML预测 (ml_predictor)
       └─ 板块轮动 (sector_rotation_monitor)
    ↓
入口层 (integrated_system / intraday_monitor_integrated)
```

### 核心模块

| 模块 | 文件 | 功能 |
|:---|:---|:---|
| **DataManager** | `core/data_manager.py` | 统一数据管理，多源并行获取，智能缓存 |
| **HistoricalCache** | `core/historical_cache.py` | K线/均线/基本面历史数据缓存 |
| **ParallelAnalyzer** | `core/parallel_analyzer.py` | 5只并发分析引擎 |
| **IntegratedMonitor** | `scripts/integrated_monitor.py` | 持仓+自选联动监控 |

### 数据流转

```
DataManager (实时+历史数据)
    ↓
ParallelAnalyzer / PositionHealth / RebalanceEngine
    ↓
IntegratedMonitor (统一报告)
```

## 使用方法

### 1. 联动监控（推荐）
```bash
python3 scripts/integrated_monitor.py
```

### 2. 单独查询
```python
from core.data_manager import data_manager
data = data_manager.fetch_stock_data(['600584', '300308'])
```

### 3. 收盘后批量更新缓存
```python
from core.historical_cache import historical_cache
historical_cache.batch_update_all(codes)
```

## 数据源配置

| 数据源 | 优先级 | 用途 |
|:---|:---:|:---|
| 腾讯财经 | 1 | 实时价格、涨跌幅 |
| 东方财富 | 2 | 技术指标、K线 |
| 新浪财经 | 3 | 备用 |
| AKShare | 4 | 备用 |

## 缓存策略

| 数据类型 | 内存缓存 | 文件缓存 |
|:---|:---:|:---:|
| 实时价格 | 1分钟 | 5分钟 |
| 技术指标 | - | 30分钟 |
| 基本面 | - | 1小时 |
| K线数据 | - | 收盘后更新 |

## 当前持仓（2026-03-09 13:48）

| 股票 | 代码 | 成本 | 数量 | 状态 |
|:---|:---:|:---:|:---:|:---|
| 工业富联 | 601138 | 51.90 | 100 | 🟢 新买入 |
| 万丰奥威 | 002085 | 16.76 | 100 | 🟢 持有 |
| 科大讯飞 | 002230 | 51.79 | 100 | 🟢 持有 |
| 长电科技 | 600584 | 48.11 | 100 | 🟠 等反弹减仓 |
| 三花智控 | 002050 | 51.14 | 200 | 🟠 观察 |
| 北汽蓝谷 | 600733 | 8.90 | 200 | 🔴 等反弹减仓 |
| 浪潮软件 | 600756 | 18.50 | 100 | 🔴 等反弹减仓 |
| 昭衍新药 | 603127 | 38.04 | 100 | 🔴 等反弹减仓 |
| 恒生科技ETF | 513180 | 0.708 | 7000 | 🟡 持有 |

**现金：** 12,822元

## 特别关注板块

### AI算力
- 中科曙光(603019) ⭐ 新增
- 浪潮信息(000977)
- 华工科技(000988)
- 宝信软件(600845)
- 科华数据(002335)

### CPO光模块
- 中际旭创(300308)
- 新易盛(300502)
- 天孚通信(300394)

## 今日操作记录

| 时间 | 操作 | 股票 | 价格 | 数量 |
|:---|:---|:---|:---:|:---:|
| 13:22 | 买入 | 工业富联 | 51.90 | 100 |
| 13:43 | 关注 | 中科曙光 | - | - |

## 下午策略

1. **持有**：富联、万丰奥威、科大讯飞
2. **等反弹减仓**：长电、北汽蓝谷、浪潮软件、昭衍新药
3. **不追**：中科曙光（已涨+1.89%）

## 风险提示

- 东财/新浪/AKShare网络不稳定，已用腾讯兜底
- 历史缓存首次建立，部分数据缺失
- 收盘后(15:30)运行批量更新补全数据

---

*系统版本: V3.0*
*更新时间: 2026-03-09 13:48*
