#!/usr/bin/env python3
"""
integrated_system.py - 完全联动的整合系统
将所有新模块集成到统一入口
- 配置管理
- 内存缓存
- 分钟级监控
- 回测验证
- ML预测
- 智能预警
所有模块联动运行
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Dict, List, Optional

# 导入所有模块
from core.config_manager import get_config, cfg
from core.memory_cache_manager import get_price_cache, get_data_cache, CachedDataFetcher
from core.minute_monitor import MinuteMonitor
from core.enhanced_backtest import EnhancedBacktester, quick_backtest, StrategyLibrary
from core.ml_predictor import MLPredictor
from core.smart_alert_system import SmartAlertSystem
from core.portfolio_optimizer import PortfolioOptimizer
from core.watchlist_memory_v2 import get_watchlist_memory_v2
from core.data_fetcher import data_fetcher


class IntegratedQuantSystem:
    """完全联动的量化系统"""
    
    def __init__(self):
        """初始化所有模块"""
        print("🚀 初始化联动量化系统...")
        
        # 配置
        self.config = get_config()
        print("✅ 配置管理")
        
        # 缓存
        self.price_cache = get_price_cache()
        self.data_cache = get_data_cache()
        print("✅ 内存缓存")
        
        # 监控
        self.minute_monitor = MinuteMonitor(
            interval_minutes=self.config.monitor.medium_frequency_interval
        )
        self.alert_system = SmartAlertSystem()
        print("✅ 监控系统")
        
        # 回测
        self.backtester = EnhancedBacktester()
        print("✅ 回测系统")
        
        # ML预测
        self.ml_predictor = MLPredictor()
        print("✅ ML预测")
        
        # 组合优化
        self.optimizer = PortfolioOptimizer()
        print("✅ 组合优化")
        
        # 自选股
        self.watchlist = get_watchlist_memory_v2()
        print("✅ 自选股管理")
        
        print("✅ 系统初始化完成\n")
    
    def analyze_stock(self, code: str) -> Dict:
        """
        全方位分析单只股票
        集成所有模块的分析能力
        """
        print(f"\n{'='*60}")
        print(f"📊 全方位分析: {code}")
        print(f"{'='*60}")
        
        result = {
            'code': code,
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. 回测验证 (使用均线策略)
        print("\n1️⃣ 策略回测验证...")
        backtest_result = quick_backtest(code, 'ma_cross', short=5, long=20)
        if backtest_result:
            result['backtest'] = {
                'total_return': backtest_result.total_return,
                'sharpe_ratio': backtest_result.sharpe_ratio,
                'win_rate': backtest_result.win_rate,
                'max_drawdown': backtest_result.max_drawdown
            }
            print(f"   回测收益: {backtest_result.total_return*100:+.2f}%")
            print(f"   夏普比率: {backtest_result.sharpe_ratio:.2f}")
        
        # 2. ML预测
        print("\n2️⃣ ML智能预测...")
        prediction = self.ml_predictor.predict(code)
        if prediction:
            result['prediction'] = {
                'direction': prediction.direction,
                'expected_return': prediction.expected_return,
                'confidence': prediction.confidence
            }
            emoji = "📈" if prediction.direction == 'UP' else "📉"
            print(f"   {emoji} 预测方向: {prediction.direction}")
            print(f"   预期收益: {prediction.expected_return*100:+.2f}%")
            print(f"   置信度: {prediction.confidence*100:.0f}%")
        
        # 3. 智能预警检查
        print("\n3️⃣ 预警条件检查...")
        alerts = self.alert_system.check_alerts([code])
        if alerts:
            result['alerts'] = [
                {'type': a.alert_type, 'level': a.level, 'message': a.message}
                for a in alerts
            ]
            for a in alerts:
                print(f"   🚨 {a.level}: {a.message}")
        else:
            print("   ✅ 无预警触发")
        
        # 4. 缓存统计
        print("\n4️⃣ 系统性能...")
        cache_stats = self.price_cache.get_stats()
        result['cache_stats'] = cache_stats
        print(f"   缓存命中率: {cache_stats['hit_rate']}")
        
        return result
    
    def optimize_portfolio(self) -> Optional[Dict]:
        """组合优化建议"""
        portfolio = {
            'positions': [
                {
                    'code': p.code,
                    'quantity': 100,
                    'cost_price': p.cost_price if hasattr(p, 'cost_price') else 0,
                    'current_price': 0
                }
                for p in self.watchlist.get_by_attention_level('特别关注')
            ],
            'cash': 100000
        }
        
        if len(portfolio['positions']) < 2:
            print("⚠️ 持仓少于2只，无法优化")
            return None
        
        print(f"\n{'='*60}")
        print("⚖️ 组合优化建议")
        print(f"{'='*60}")
        
        opt_result = self.optimizer.suggest_rebalance(portfolio, 'sharpe')
        
        if opt_result:
            print(f"\n策略: {opt_result.strategy}")
            print(f"预期收益: {opt_result.expected_return*100:.2f}%")
            print(f"预期风险: {opt_result.expected_risk*100:.2f}%")
            print(f"夏普比率: {opt_result.sharpe_ratio:.2f}")
            
            if opt_result.trades:
                print(f"\n调仓建议:")
                for t in opt_result.trades[:5]:
                    emoji = "📈" if t['action'] == 'BUY' else "📉"
                    print(f"   {emoji} {t['code']}: {t['action']} {abs(t['diff'])*100:.1f}%")
            
            return {
                'strategy': opt_result.strategy,
                'expected_return': opt_result.expected_return,
                'expected_risk': opt_result.expected_risk,
                'sharpe_ratio': opt_result.sharpe_ratio,
                'trades': opt_result.trades
            }
        
        return None
    
    def run_complete_monitoring(self, codes: List[str] = None):
        """
        完整监控流程
        集成所有模块
        """
        if codes is None:
            # 获取特别关注股票
            codes = [p.code for p in self.watchlist.get_by_attention_level('特别关注')]
        
        if not codes:
            print("⚠️ 无监控标的")
            return
        
        print(f"\n{'='*60}")
        print(f"🔍 完整联动监控 - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        print(f"监控标的: {', '.join(codes[:5])}{'...' if len(codes) > 5 else ''}")
        
        # 使用缓存获取数据
        cached_fetcher = CachedDataFetcher()
        stock_data = cached_fetcher.get_stock_data(codes)
        
        print(f"\n📈 实时行情:")
        for code in codes[:10]:
            if code in stock_data:
                d = stock_data[code]
                change = d.get('change_pct', 0)
                emoji = "🟢" if change > 0 else "🔴"
                print(f"   {emoji} {code}: {change:+.2f}%")
        
        # 1. 智能预警检查
        print(f"\n🚨 智能预警检查...")
        alerts = self.alert_system.check_alerts(codes)
        if alerts:
            for a in alerts:
                level_emoji = "🔴" if a.level == "CRITICAL" else ("🟡" if a.level == "WARNING" else "🔵")
                print(f"   {level_emoji} {a.message}")
        else:
            print("   ✅ 无预警")
        
        # 2. ML预测 (每30分钟一次)
        print(f"\n🤖 ML预测分析...")
        predictions = self.ml_predictor.batch_predict(codes[:5])  # 只预测前5只
        for p in predictions[:3]:
            emoji = "📈" if p.direction == 'UP' else ("📉" if p.direction == 'DOWN' else "➡️")
            print(f"   {emoji} {p.name}: {p.expected_return*100:+.2f}% (置信{p.confidence*100:.0f}%)")
        
        # 3. 缓存统计
        stats = cached_fetcher.get_stats()
        print(f"\n💾 缓存统计: 命中率 {stats['hit_rate']}, 条目数 {stats['size']}")
        
        print(f"{'='*60}")
    
    def display_system_status(self):
        """显示系统状态"""
        print(f"\n{'='*60}")
        print("📊 系统状态总览")
        print(f"{'='*60}")
        
        # 配置信息
        print(f"\n⚙️ 配置信息:")
        print(f"   止损线: {cfg('risk.stop_loss_pct')*100:.0f}%")
        print(f"   止盈线: {cfg('risk.take_profit_pct')*100:.0f}%")
        print(f"   监控间隔: {cfg('monitor.medium_frequency_interval')}分钟")
        
        # 缓存统计
        print(f"\n💾 缓存状态:")
        price_stats = self.price_cache.get_stats()
        data_stats = self.data_cache.get_stats()
        print(f"   价格缓存: {price_stats['size']}/{price_stats['max_size']}, 命中率 {price_stats['hit_rate']}")
        print(f"   数据缓存: {data_stats['size']}/{data_stats['max_size']}, 命中率 {data_stats['hit_rate']}")
        
        # 自选股统计
        wl_stats = self.watchlist.get_statistics()
        print(f"\n📋 自选股:")
        print(f"   总计: {wl_stats['total']}只")
        print(f"   特别关注: {wl_stats['by_attention'].get('特别关注', 0)}只")
        
        print(f"{'='*60}")


# 便捷函数
def run_full_analysis(code: str):
    """便捷函数：全方位分析"""
    system = IntegratedQuantSystem()
    return system.analyze_stock(code)


def run_portfolio_optimization():
    """便捷函数：组合优化"""
    system = IntegratedQuantSystem()
    return system.optimize_portfolio()


def run_monitoring():
    """便捷函数：完整监控"""
    system = IntegratedQuantSystem()
    system.run_complete_monitoring()


if __name__ == '__main__':
    # 测试
    print("🧪 测试完全联动的整合系统...")
    
    system = IntegratedQuantSystem()
    
    # 显示系统状态
    system.display_system_status()
    
    # 运行监控
    print("\n" + "="*60)
    system.run_complete_monitoring(['300750', '002594'])
    
    # 全方位分析
    print("\n" + "="*60)
    system.analyze_stock('300750')
    
    print("\n✅ 联动系统测试完成")
