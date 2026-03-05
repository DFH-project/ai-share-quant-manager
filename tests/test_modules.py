"""
tests/test_modules.py - 测试模块
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher_v2 import DataFetcherV2
from core.watchlist_memory import WatchlistMemory
from core.monthly_strategy import MonthlyStrategy
from core.smart_trader import SmartTrader, OrderType


def test_data_fetcher():
    """测试数据获取模块"""
    print("\n" + "="*60)
    print("测试数据获取模块 (DataFetcherV2)")
    print("="*60)
    
    fetcher = DataFetcherV2()
    
    # 测试获取股票列表
    print("\n1. 获取股票列表样本...")
    stocks = fetcher.get_stock_list()
    if not stocks.empty:
        print(f"   ✓ 成功获取 {len(stocks)} 只股票")
        print(f"   样本: {stocks[['code', 'name']].head(3).to_dict('records')}")
    else:
        print("   ✗ 获取失败")
    
    # 测试获取个股数据
    print("\n2. 获取个股日线数据 (000001 平安银行)...")
    df = fetcher.get_daily_data("000001", days=30)
    if not df.empty:
        print(f"   ✓ 成功获取 {len(df)} 条数据")
        print(f"   最新数据: 收盘 {df.iloc[-1]['close']}, 涨跌 {df.iloc[-1]['change_pct']}%")
    else:
        print("   ✗ 获取失败")
    
    # 测试获取实时数据
    print("\n3. 获取实时数据...")
    realtime = fetcher.get_realtime_data("000001")
    if realtime:
        print(f"   ✓ 成功获取: {realtime.get('name')} 当前价 {realtime.get('price')}")
    else:
        print("   ✗ 获取失败")
    
    return fetcher


def test_watchlist(fetcher):
    """测试自选股模块"""
    print("\n" + "="*60)
    print("测试自选股模块 (WatchlistMemory)")
    print("="*60)
    
    # 使用测试数据文件
    watchlist = WatchlistMemory(data_file="./data/test_watchlist.json")
    
    # 清空测试数据
    watchlist.clear()
    
    # 测试添加
    print("\n1. 添加自选股...")
    watchlist.add("000001", name="平安银行", category="关注", tags=["银行", "蓝筹"], data_fetcher=fetcher)
    watchlist.add("000858", name="五粮液", category="关注", tags=["白酒", "消费"], data_fetcher=fetcher)
    watchlist.add("002594", name="比亚迪", category="观察", tags=["新能源", "汽车"], data_fetcher=fetcher)
    
    # 测试重复添加
    result = watchlist.add("000001", data_fetcher=fetcher)
    if not result:
        print("   ✓ 重复添加检测正常")
    
    # 测试查询
    print("\n2. 查询自选股...")
    all_items = watchlist.get_all()
    print(f"   ✓ 共 {len(all_items)} 只自选股")
    
    item = watchlist.get("000858")
    if item:
        print(f"   ✓ 查询 000858: {item.name}, 分类: {item.category}")
    
    # 测试分类
    print("\n3. 按分类查询...")
    watch_items = watchlist.get_by_category("关注")
    print(f"   ✓ '关注' 分类有 {len(watch_items)} 只股票")
    
    # 测试标签
    print("\n4. 按标签查询...")
    tag_items = watchlist.get_by_tag("白酒")
    print(f"   ✓ '白酒' 标签有 {len(tag_items)} 只股票")
    
    # 测试统计
    print("\n5. 统计信息...")
    stats = watchlist.get_statistics()
    print(f"   ✓ 总计: {stats['total']}, 分类: {stats['by_category']}")
    
    # 显示列表
    print("\n6. 显示自选股列表:")
    watchlist.display()
    
    return watchlist


def test_strategy(fetcher, watchlist):
    """测试策略模块"""
    print("\n" + "="*60)
    print("测试策略模块 (MonthlyStrategy)")
    print("="*60)
    
    strategy = MonthlyStrategy(fetcher)
    
    # 测试单股分析
    print("\n1. 分析单只股票 (000001)...")
    signal = strategy.analyze_stock("000001", "平安银行")
    if signal:
        print(f"   ✓ 信号: {signal.signal.value}, 评分: {signal.score}")
        print(f"   原因: {', '.join(signal.reasons[:3])}")
    
    # 测试扫描自选股
    print("\n2. 扫描自选股列表...")
    signals = strategy.scan_watchlist(watchlist)
    print(f"   ✓ 生成 {len(signals)} 个信号")
    
    if signals:
        print("\n3. 显示信号:")
        strategy.display_signals(signals[:5])
        
        # 测试报告
        print("\n4. 生成策略报告...")
        report = strategy.generate_monthly_report()
        print(f"   ✓ 买入信号: {report['buy_count']}, 关注信号: {report['watch_count']}")
    
    return strategy


def test_trader(fetcher, strategy):
    """测试交易模块"""
    print("\n" + "="*60)
    print("测试交易模块 (SmartTrader)")
    print("="*60)
    
    trader = SmartTrader(fetcher, config_file="./data/test_trader_config.json")
    
    # 显示初始状态
    print("\n1. 初始投资组合:")
    trader.display_portfolio()
    
    # 测试创建订单
    print("\n2. 创建买入订单...")
    order1 = trader.create_order(
        code="000001",
        name="平安银行",
        order_type=OrderType.BUY,
        price=10.5,
        quantity=1000,
        notes="测试买入"
    )
    
    if order1:
        print(f"   ✓ 创建订单: {order1.id}")
        
        # 执行订单
        print("\n3. 执行订单...")
        trader.execute_order(order1.id, executed_price=10.45)
    
    # 创建第二个订单
    order2 = trader.create_order(
        code="000858",
        name="五粮液",
        order_type=OrderType.BUY,
        price=150.0,
        quantity=500,
        notes="测试买入2"
    )
    if order2:
        trader.execute_order(order2.id, executed_price=149.5)
    
    # 显示持仓
    print("\n4. 执行后的投资组合:")
    trader.display_portfolio()
    
    # 测试风控检查
    print("\n5. 风险检查...")
    passed, msg = trader.check_risk("000001", OrderType.BUY, 10.5, 100000)
    print(f"   {'✓' if passed else '✗'} {msg}")
    
    # 测试止损止盈检查
    print("\n6. 检查止损止盈...")
    alerts = trader.check_stop_loss_take_profit()
    print(f"   ✓ 发现 {len(alerts)} 个预警")
    
    # 测试卖出
    print("\n7. 创建卖出订单...")
    order3 = trader.create_order(
        code="000001",
        name="平安银行",
        order_type=OrderType.SELL,
        price=11.0,
        quantity=500,
        notes="测试卖出"
    )
    if order3:
        trader.execute_order(order3.id, executed_price=11.05)
    
    print("\n8. 最终投资组合:")
    trader.display_portfolio()
    
    return trader


def test_integration():
    """集成测试 - 测试模块间联动"""
    print("\n" + "="*60)
    print("集成测试 - 模块间联动")
    print("="*60)
    
    # 初始化模块
    print("\n1. 初始化所有模块...")
    fetcher = DataFetcherV2()
    watchlist = WatchlistMemory(data_file="./data/test_watchlist.json")
    strategy = MonthlyStrategy(fetcher)
    trader = SmartTrader(fetcher, config_file="./data/test_trader_config.json")
    print("   ✓ 所有模块初始化完成")
    
    # 清空测试数据
    watchlist.clear()
    
    # 添加自选股
    print("\n2. 添加自选股...")
    test_codes = ["000001", "000858", "002594", "600519", "300750"]
    for code in test_codes:
        watchlist.add(code, data_fetcher=fetcher)
    print(f"   ✓ 添加 {len(test_codes)} 只自选股")
    
    # 策略扫描
    print("\n3. 策略扫描自选股...")
    signals = strategy.scan_watchlist(watchlist)
    print(f"   ✓ 生成 {len(signals)} 个交易信号")
    
    # 执行交易信号
    print("\n4. 执行交易信号...")
    if signals:
        order_ids = trader.execute_strategy_signals(signals, watchlist, max_orders=2)
        print(f"   ✓ 执行 {len(order_ids)} 个订单")
    
    # 显示结果
    print("\n5. 最终状态:")
    print(f"   自选股数量: {len(watchlist.get_all())}")
    print(f"   交易信号数量: {len(signals)}")
    trader.display_portfolio()
    
    print("\n" + "="*60)
    print("集成测试完成!")
    print("="*60)


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("# A-Share Quant Manager 模块测试")
    print("#"*60)
    
    try:
        # 测试数据获取
        fetcher = test_data_fetcher()
        
        # 测试自选股
        watchlist = test_watchlist(fetcher)
        
        # 测试策略
        strategy = test_strategy(fetcher, watchlist)
        
        # 测试交易
        trader = test_trader(fetcher, strategy)
        
        # 集成测试
        test_integration()
        
        print("\n" + "#"*60)
        print("# 所有测试通过!")
        print("#"*60)
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
