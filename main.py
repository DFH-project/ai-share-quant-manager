#!/usr/bin/env python3
"""
main.py - A-Share Quant Manager 主入口
A股量化投资管理工具
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data_fetcher_v2 import DataFetcherV2
from core.watchlist_memory import WatchlistMemory
from core.monthly_strategy import MonthlyStrategy, SignalType
from core.smart_trader import SmartTrader, OrderType


def print_menu():
    """打印主菜单"""
    print("\n" + "="*60)
    print("A-Share Quant Manager - A股量化投资管理")
    print("="*60)
    print("1. 查看自选股")
    print("2. 添加自选股")
    print("3. 删除自选股")
    print("4. 运行策略扫描")
    print("5. 查看交易信号")
    print("6. 查看投资组合")
    print("7. 执行交易")
    print("8. 查看市场概览")
    print("9. 运行测试")
    print("0. 退出")
    print("="*60)


def view_watchlist(watchlist):
    """查看自选股"""
    watchlist.display()


def add_stock(watchlist, fetcher):
    """添加自选股"""
    code = input("请输入股票代码: ").strip()
    if not code:
        print("股票代码不能为空")
        return
    
    category = input("请输入分类 (默认: 关注): ").strip() or "关注"
    notes = input("请输入备注: ").strip()
    tags_input = input("请输入标签 (用逗号分隔): ").strip()
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]
    
    watchlist.add(code, category=category, notes=notes, tags=tags, data_fetcher=fetcher)


def remove_stock(watchlist):
    """删除自选股"""
    code = input("请输入要删除的股票代码: ").strip()
    watchlist.remove(code)


def run_strategy_scan(strategy, watchlist):
    """运行策略扫描"""
    print("\n开始扫描自选股...")
    signals = strategy.scan_watchlist(watchlist)
    
    if signals:
        print(f"\n生成 {len(signals)} 个交易信号:")
        strategy.display_signals(signals[:10])
    else:
        print("未生成交易信号")
    
    return signals


def view_signals(strategy):
    """查看交易信号"""
    if not strategy.signals:
        print("暂无交易信号，请先运行策略扫描")
        return
    
    print("\n选择信号类型:")
    print("1. 全部")
    print("2. 买入")
    print("3. 关注")
    print("4. 卖出")
    
    choice = input("请选择: ").strip()
    
    if choice == "2":
        signals = strategy.get_top_signals(signal_type=SignalType.BUY)
    elif choice == "3":
        signals = strategy.get_top_signals(signal_type=SignalType.WATCH)
    elif choice == "4":
        signals = strategy.get_top_signals(signal_type=SignalType.SELL)
    else:
        signals = strategy.signals
    
    strategy.display_signals(signals)


def view_portfolio(trader):
    """查看投资组合"""
    trader.display_portfolio()
    
    # 检查止损止盈
    alerts = trader.check_stop_loss_take_profit()
    if alerts:
        print("\n⚠️ 风险预警:")
        for alert in alerts:
            print(f"  {alert['code']} ({alert['name']}): {alert['type']} - {alert['suggestion']}")


def execute_trade(trader, watchlist):
    """执行交易"""
    print("\n1. 买入")
    print("2. 卖出")
    
    choice = input("请选择: ").strip()
    
    code = input("请输入股票代码: ").strip()
    
    # 获取股票名称
    item = watchlist.get(code)
    name = item.name if item else code
    
    try:
        price = float(input("请输入价格: ").strip())
        quantity = int(input("请输入数量: ").strip())
    except ValueError:
        print("输入无效")
        return
    
    if choice == "1":
        order_type = OrderType.BUY
    else:
        order_type = OrderType.SELL
    
    order = trader.create_order(code, name, order_type, price, quantity)
    if order:
        confirm = input(f"确认执行订单 {order.id}? (y/n): ").strip().lower()
        if confirm == 'y':
            trader.execute_order(order.id)


def view_market(fetcher):
    """查看市场概览"""
    print("\n获取市场数据中...")
    
    # 获取指数
    indices = [
        ("000001", "上证指数"),
        ("399001", "深证成指"),
        ("399006", "创业板指")
    ]
    
    print(f"\n{'指数':<12}{'最新':<12}{'涨跌':<12}{'涨跌幅'}")
    print("-" * 50)
    
    for code, name in indices:
        try:
            df = fetcher.get_index_data(code)
            if not df.empty:
                latest = df.iloc[-1]
                change = latest.get('涨跌幅', 0)
                print(f"{name:<12}{latest['收盘']:<12.2f}{latest['涨跌额']:<12.2f}{change:.2f}%")
        except:
            pass
    
    # 获取热门板块
    print("\n热门行业板块:")
    try:
        boards = fetcher.get_industry_boards()
        if not boards.empty:
            top_boards = boards.nlargest(5, '涨跌幅')[['名称', '涨跌幅']]
            for _, row in top_boards.iterrows():
                print(f"  {row['名称']}: {row['涨跌幅']:.2f}%")
    except:
        print("  获取失败")


def run_tests():
    """运行测试"""
    print("\n运行模块测试...")
    try:
        from tests.test_modules import run_all_tests
        run_all_tests()
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("\n初始化 A-Share Quant Manager...")
    
    # 初始化模块
    fetcher = DataFetcherV2()
    watchlist = WatchlistMemory()
    strategy = MonthlyStrategy(fetcher)
    trader = SmartTrader(fetcher)
    
    print(f"✓ 已加载 {len(watchlist.get_all())} 只自选股")
    print(f"✓ 当前总资产: {trader.get_portfolio_summary()['total_value']:,.2f}")
    
    while True:
        print_menu()
        choice = input("请选择操作: ").strip()
        
        if choice == "1":
            view_watchlist(watchlist)
        elif choice == "2":
            add_stock(watchlist, fetcher)
        elif choice == "3":
            remove_stock(watchlist)
        elif choice == "4":
            run_strategy_scan(strategy, watchlist)
        elif choice == "5":
            view_signals(strategy)
        elif choice == "6":
            view_portfolio(trader)
        elif choice == "7":
            execute_trade(trader, watchlist)
        elif choice == "8":
            view_market(fetcher)
        elif choice == "9":
            run_tests()
        elif choice == "0":
            print("\n感谢使用 A-Share Quant Manager!")
            break
        else:
            print("无效选择，请重试")


if __name__ == "__main__":
    main()
