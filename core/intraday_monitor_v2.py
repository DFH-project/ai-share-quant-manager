"""
intraday_monitor_v2.py - 盘中监控V2
核心功能：
1. 自选股分级监控 - 特别关注高频，一般关注常规，观察低频
2. 策略类型联动 - 不同策略给出不同买卖建议
3. 选股原因追踪 - 持续验证选股逻辑
4. 买入计划提醒 - 到达买入价时提醒
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory_v2 import get_watchlist_memory_v2, WatchlistItemV2, SelectionReason, EntryPlan
from core.sector_tracker import get_sector_tracker
from core.multi_dimension_analyzer import get_analyzer
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json


class IntradayMonitorV2:
    """盘中监控V2 - 分级精准监控"""
    
    def __init__(self):
        self.watchlist = get_watchlist_memory_v2()
        self.sector_tracker = get_sector_tracker()
        self.analyzer = get_analyzer()
        self.alert_history = []  # 报警历史
        
    def monitor_high_attention(self) -> List[Dict]:
        """
        特别关注股票监控 - 高频、详细
        每10分钟检查一次
        """
        alerts = []
        high_items = self.watchlist.get_by_attention_level('特别关注')
        
        if not high_items:
            return alerts
        
        print(f"\n🔴 特别关注监控 ({len(high_items)}只) - 高频")
        print("-" * 80)
        
        codes = [item.code for item in high_items]
        stock_data = data_fetcher.get_stock_data(codes)
        
        for item in high_items:
            code = item.code
            if code not in stock_data:
                continue
            
            data = stock_data[code]
            current_price = data.get('current', 0)
            change_pct = data.get('change_pct', 0)
            
            # 更新表现追踪
            item.update_performance(current_price, change_pct)
            
            # 策略特定监控逻辑
            strategy_alerts = self._check_strategy_specific(item, data)
            
            # 买入计划监控
            if item.entry_plan and item.entry_plan.entry_price > 0:
                entry_alert = self._check_entry_plan(item, current_price, change_pct)
                if entry_alert:
                    strategy_alerts.append(entry_alert)
            
            # 选股原因验证
            validation = self._validate_selection_reason(item, data)
            
            if strategy_alerts or validation.get('alert', False):
                alert = {
                    'code': code,
                    'name': item.name,
                    'strategy': item.strategy_type,
                    'price': current_price,
                    'change_pct': change_pct,
                    'alerts': strategy_alerts,
                    'validation': validation,
                    'priority': 'HIGH'
                }
                alerts.append(alert)
                
                # 显示
                emoji = item.get_strategy_emoji()
                print(f"  {emoji} {item.name}({code}) {change_pct:+.2f}% {current_price:.2f}")
                for sa in strategy_alerts:
                    print(f"     ⚠️ {sa['type']}: {sa['message']}")
        
        return alerts
    
    def monitor_medium_attention(self) -> List[Dict]:
        """
        一般关注股票监控 - 常规
        每30分钟检查一次
        """
        alerts = []
        medium_items = self.watchlist.get_by_attention_level('一般关注')
        
        if not medium_items:
            return alerts
        
        print(f"\n🟡 一般关注监控 ({len(medium_items)}只) - 常规")
        print("-" * 80)
        
        codes = [item.code for item in medium_items]
        stock_data = data_fetcher.get_stock_data(codes)
        
        for item in medium_items:
            code = item.code
            if code not in stock_data:
                continue
            
            data = stock_data[code]
            current_price = data.get('current', 0)
            change_pct = data.get('change_pct', 0)
            
            # 只监控重要信号（大涨大跌）
            if abs(change_pct) >= 3:
                alert = {
                    'code': code,
                    'name': item.name,
                    'strategy': item.strategy_type,
                    'price': current_price,
                    'change_pct': change_pct,
                    'message': f"波动较大 {change_pct:+.2f}%",
                    'priority': 'MEDIUM'
                }
                alerts.append(alert)
                emoji = item.get_strategy_emoji()
                print(f"  {emoji} {item.name}({code}) {change_pct:+.2f}% - 波动较大")
        
        return alerts
    
    def monitor_low_attention(self) -> List[Dict]:
        """
        观察级股票监控 - 低频
        每60分钟检查一次，只监控极端情况
        """
        alerts = []
        low_items = self.watchlist.get_by_attention_level('观察')
        
        if not low_items:
            return alerts
        
        print(f"\n🟢 观察级监控 ({len(low_items)}只) - 低频")
        print("-" * 80)
        
        codes = [item.code for item in low_items]
        stock_data = data_fetcher.get_stock_data(codes)
        
        for item in low_items:
            code = item.code
            if code not in stock_data:
                continue
            
            data = stock_data[code]
            current_price = data.get('current', 0)
            change_pct = data.get('change_pct', 0)
            
            # 只监控极端情况
            if abs(change_pct) >= 5:
                alert = {
                    'code': code,
                    'name': item.name,
                    'price': current_price,
                    'change_pct': change_pct,
                    'message': f"极端波动 {change_pct:+.2f}%",
                    'priority': 'LOW'
                }
                alerts.append(alert)
                print(f"  {item.name}({code}) {change_pct:+.2f}% - 极端波动")
        
        return alerts
    
    def _check_strategy_specific(self, item: WatchlistItemV2, data: Dict) -> List[Dict]:
        """根据策略类型进行特定检查"""
        alerts = []
        strategy = item.strategy_type
        change_pct = data.get('change_pct', 0)
        current = data.get('current', 0)
        
        if strategy == '追涨型':
            # 追涨型：涨幅超5%提醒，跌破-3%止损
            if change_pct > 5:
                alerts.append({
                    'type': '追涨确认',
                    'message': f'强势上涨 {change_pct:+.2f}%，追涨信号确认',
                    'action': '可考虑追涨'
                })
            elif change_pct < -3:
                alerts.append({
                    'type': '止损提醒',
                    'message': f'跌破止损线 {change_pct:+.2f}%',
                    'action': '建议止损'
                })
        
        elif strategy == '低吸型':
            # 低吸型：回调到位提醒，继续大跌提醒
            if -4 <= change_pct <= -1:
                alerts.append({
                    'type': '低吸机会',
                    'message': f'回调 {change_pct:.2f}%，低吸机会',
                    'action': '可考虑低吸'
                })
            elif change_pct < -5:
                alerts.append({
                    'type': '低吸失败',
                    'message': f'深度回调 {change_pct:.2f}%，可能破位',
                    'action': '观望或止损'
                })
        
        elif strategy == '抄底型':
            # 抄底型：止跌信号，继续探底
            if -2 <= change_pct <= 1:
                alerts.append({
                    'type': '止跌信号',
                    'message': f'跌幅收窄 {change_pct:+.2f}%，可能止跌',
                    'action': '关注反弹'
                })
        
        elif strategy == '板块龙头':
            # 板块龙头：领涨确认，领跌提醒
            if change_pct > 3:
                alerts.append({
                    'type': '龙头领涨',
                    'message': f'龙头强势 {change_pct:+.2f}%',
                    'action': '持有或追涨'
                })
        
        elif strategy == '价值型':
            # 价值型：大跌加仓机会
            if change_pct < -3:
                alerts.append({
                    'type': '价值加仓',
                    'message': f'价值股回调 {change_pct:.2f}%，加仓机会',
                    'action': '可考虑加仓'
                })
        
        return alerts
    
    def _check_entry_plan(self, item: WatchlistItemV2, current_price: float, change_pct: float) -> Optional[Dict]:
        """检查买入计划"""
        entry_price = item.entry_plan.entry_price
        stop_loss = item.entry_plan.stop_loss
        target = item.entry_plan.target_price
        
        # 到达买入价
        if entry_price > 0 and abs(current_price - entry_price) / entry_price < 0.02:
            return {
                'type': '买入提醒',
                'message': f'到达计划买入价 {entry_price:.2f} (当前{current_price:.2f})',
                'action': '执行买入计划'
            }
        
        # 跌破止损
        if stop_loss > 0 and current_price <= stop_loss:
            return {
                'type': '止损提醒',
                'message': f'跌破止损价 {stop_loss:.2f}',
                'action': '执行止损'
            }
        
        # 到达目标
        if target > 0 and current_price >= target:
            return {
                'type': '目标到达',
                'message': f'到达目标价 {target:.2f}',
                'action': '可考虑止盈'
            }
        
        return None
    
    def _validate_selection_reason(self, item: WatchlistItemV2, data: Dict) -> Dict:
        """验证选股原因是否仍然成立"""
        result = {'valid': True, 'alert': False, 'issues': []}
        
        if not item.selection_reason:
            return result
        
        change_pct = data.get('change_pct', 0)
        
        # 检查失效条件
        invalidation_conditions = item.selection_reason.invalidation_conditions
        for condition in invalidation_conditions:
            # 简单判断：如果包含"跌幅"等关键词
            if '跌幅' in condition and change_pct < -5:
                result['valid'] = False
                result['issues'].append(f'触发失效条件: {condition}')
        
        # 大幅偏离预期
        if '大跌' in item.selection_reason.expected_scenario and change_pct > 0:
            result['issues'].append('预期大跌但实际上涨，逻辑可能变化')
        
        if result['issues']:
            result['alert'] = True
        
        return result
    
    def generate_monitoring_report(self) -> Dict:
        """生成完整监控报告"""
        print("\n" + "="*80)
        print("📊 盘中监控V2 - 分级精准监控")
        print("="*80)
        
        # 大盘概况
        try:
            index_data = data_fetcher.get_index_data()
            print(f"\n大盘: 上证 {index_data.get('sh_index', 0):.2f} "
                  f"{index_data.get('sh_change_pct', 0):+.2f}%")
        except:
            pass
        
        # 分级监控
        high_alerts = self.monitor_high_attention()
        medium_alerts = self.monitor_medium_attention()
        low_alerts = self.monitor_low_attention()
        
        # 板块监控
        print("\n📈 板块轮动监控")
        print("-" * 80)
        sector_data = self.sector_tracker.calculate_sector_performance()
        for sector_name, perf in sorted(sector_data.items(), 
                                       key=lambda x: x[1]['avg_change'], reverse=True)[:5]:
            avg_change = perf['avg_change']
            emoji = "🔥" if avg_change > 2 else ("📈" if avg_change > 0 else "📉")
            print(f"  {emoji} {sector_name}: {avg_change:+.2f}% "
                  f"({perf['up_count']}/{perf['total']}上涨)")
        
        # 汇总
        all_alerts = high_alerts + medium_alerts + low_alerts
        
        print("\n" + "="*80)
        print(f"监控完成: {len(high_alerts)}个高优先级 | {len(medium_alerts)}个中优先级 | {len(low_alerts)}个低优先级")
        print("="*80)
        
        return {
            'high_alerts': high_alerts,
            'medium_alerts': medium_alerts,
            'low_alerts': low_alerts,
            'total_alerts': len(all_alerts),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def check_buy_signals(self) -> List[Dict]:
        """检查买入信号 - 基于自选股"""
        buy_signals = []
        
        print("\n✳️ 买入信号检查")
        print("-" * 80)
        
        # 只检查特别关注
        high_items = self.watchlist.get_by_attention_level('特别关注')
        
        for item in high_items:
            data = data_fetcher.get_stock_data([item.code])
            if item.code not in data:
                continue
            
            stock = data[item.code]
            change_pct = stock.get('change_pct', 0)
            current_price = stock.get('current', 0)
            
            # 根据策略判断买入信号
            signal = None
            
            if item.strategy_type == '低吸型' and -3 <= change_pct <= -1:
                signal = {
                    'code': item.code,
                    'name': item.name,
                    'strategy': '低吸型',
                    'price': current_price,
                    'change_pct': change_pct,
                    'strength': '中等',
                    'reason': f'回调{change_pct:.2f}%，符合低吸条件'
                }
            
            elif item.strategy_type == '追涨型' and change_pct > 3:
                signal = {
                    'code': item.code,
                    'name': item.name,
                    'strategy': '追涨型',
                    'price': current_price,
                    'change_pct': change_pct,
                    'strength': '强' if change_pct > 5 else '中等',
                    'reason': f'强势上涨{change_pct:.2f}%，追涨信号'
                }
            
            elif item.strategy_type == '抄底型' and -2 <= change_pct < 1:
                signal = {
                    'code': item.code,
                    'name': item.name,
                    'strategy': '抄底型',
                    'price': current_price,
                    'change_pct': change_pct,
                    'strength': '中等',
                    'reason': '止跌信号，可考虑抄底'
                }
            
            if signal:
                buy_signals.append(signal)
                emoji = item.get_strategy_emoji()
                print(f"  {emoji} {signal['name']}({signal['code']}) "
                      f"{signal['change_pct']:+.2f}% - {signal['reason']}")
        
        return buy_signals
    
    def run_full_monitoring(self) -> Dict:
        """运行完整监控"""
        report = self.generate_monitoring_report()
        buy_signals = self.check_buy_signals()
        
        return {
            'monitoring_report': report,
            'buy_signals': buy_signals,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


def main():
    """主函数"""
    monitor = IntradayMonitorV2()
    result = monitor.run_full_monitoring()
    
    print("\n监控结果:")
    print(f"  总提醒数: {result['monitoring_report']['total_alerts']}")
    print(f"  买入信号: {len(result['buy_signals'])}个")


if __name__ == '__main__':
    main()
