#!/usr/bin/env python3
"""
smart_alert_system.py - 智能预警系统
核心功能:
1. 关键价位突破预警 (支撑/压力/成本价)
2. 异动检测 (放量/急跌/异动)
3. 板块热点切换预警
4. 与现有监控完全兼容，零侵入

设计原则:
- 事件驱动，非轮询
- 可配置阈值
- 不重复报警
- 支持飞书推送
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict

from core.data_fetcher import data_fetcher
from core.historical_cache import HistoricalDataCache


@dataclass
class AlertRule:
    """预警规则"""
    code: str
    rule_type: str  # price_break/volume_surge/sector_change/drawdown
    condition: str  # >/</>=/<=/cross_up/cross_down
    threshold: float
    message_template: str
    enabled: bool = True
    last_triggered: str = None
    cooldown_minutes: int = 30  # 冷却时间，避免重复报警


@dataclass
class AlertEvent:
    """预警事件"""
    timestamp: str
    code: str
    name: str
    alert_type: str
    level: str  # INFO/WARNING/CRITICAL
    message: str
    current_price: float
    trigger_value: float


class SmartAlertSystem:
    """智能预警系统 - 零侵入设计"""
    
    def __init__(self):
        self.cache = HistoricalDataCache()
        self.alert_rules: Dict[str, List[AlertRule]] = defaultdict(list)
        self.alert_history: List[AlertEvent] = []
        self.callbacks: List[Callable] = []
        
        # 加载已保存的规则
        self._load_rules()
    
    def _get_rules_file(self) -> Path:
        """获取规则文件路径"""
        rules_dir = Path(__file__).parent.parent / 'data' / 'alerts'
        rules_dir.mkdir(parents=True, exist_ok=True)
        return rules_dir / 'alert_rules.json'
    
    def _load_rules(self):
        """加载预警规则"""
        try:
            rules_file = self._get_rules_file()
            if rules_file.exists():
                with open(rules_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for code, rules_data in data.items():
                        self.alert_rules[code] = [AlertRule(**r) for r in rules_data]
                print(f"✅ 已加载 {sum(len(rules) for rules in self.alert_rules.values())} 条预警规则")
        except Exception as e:
            print(f"⚠️ 加载规则失败: {e}")
    
    def _save_rules(self):
        """保存预警规则"""
        try:
            rules_file = self._get_rules_file()
            data = {}
            for code, rules in self.alert_rules.items():
                data[code] = [asdict(r) for r in rules]
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存规则失败: {e}")
    
    def add_price_alert(self, code: str, price: float, direction: str = 'above'):
        """
        添加价格突破预警
        
        Args:
            code: 股票代码
            price: 目标价格
            direction: 'above'(突破上方) / 'below'(跌破下方)
        """
        condition = 'cross_up' if direction == 'above' else 'cross_down'
        template = f"🚨 {code} 价格{direction}突破 ¥{price}"
        
        rule = AlertRule(
            code=code,
            rule_type='price_break',
            condition=condition,
            threshold=price,
            message_template=template,
            cooldown_minutes=60
        )
        
        self.alert_rules[code].append(rule)
        self._save_rules()
        print(f"✅ 已添加价格预警: {code} {direction} ¥{price}")
    
    def add_volume_alert(self, code: str, volume_ratio: float = 3.0):
        """
        添加放量预警
        
        Args:
            code: 股票代码
            volume_ratio: 量比阈值，默认3倍
        """
        rule = AlertRule(
            code=code,
            rule_type='volume_surge',
            condition='>=',
            threshold=volume_ratio,
            message_template=f"📈 {code} 异常放量，量比突破 {volume_ratio}",
            cooldown_minutes=30
        )
        
        self.alert_rules[code].append(rule)
        self._save_rules()
        print(f"✅ 已添加放量预警: {code} 量比>={volume_ratio}")
    
    def add_drawdown_alert(self, code: str, drawdown_pct: float = 0.08):
        """
        添加回撤预警
        
        Args:
            code: 股票代码
            drawdown_pct: 回撤阈值，默认8%
        """
        rule = AlertRule(
            code=code,
            rule_type='drawdown',
            condition='>=',
            threshold=drawdown_pct,
            message_template=f"🔴 {code} 从高点回撤 {drawdown_pct*100:.0f}%，注意风险",
            cooldown_minutes=120
        )
        
        self.alert_rules[code].append(rule)
        self._save_rules()
        print(f"✅ 已添加回撤预警: {code} 回撤>={drawdown_pct*100:.0f}%")
    
    def check_alerts(self, codes: List[str] = None) -> List[AlertEvent]:
        """
        检查预警触发
        
        Args:
            codes: 指定检查的股票，None则检查所有有规则的股票
        
        Returns:
            List[AlertEvent]: 触发的预警事件
        """
        triggered = []
        
        if codes is None:
            codes = list(self.alert_rules.keys())
        
        # 批量获取实时数据
        stock_data = data_fetcher.get_stock_data(codes)
        
        for code in codes:
            if code not in self.alert_rules or not self.alert_rules[code]:
                continue
            
            if code not in stock_data:
                continue
            
            data = stock_data[code]
            current_price = data.get('current', 0)
            name = data.get('name', code)
            
            for rule in self.alert_rules[code]:
                if not rule.enabled:
                    continue
                
                # 检查冷却时间
                if rule.last_triggered:
                    last_time = datetime.fromisoformat(rule.last_triggered)
                    if (datetime.now() - last_time).total_seconds() / 60 < rule.cooldown_minutes:
                        continue
                
                # 检查规则触发
                event = self._check_rule(rule, code, name, current_price, data)
                if event:
                    triggered.append(event)
                    self.alert_history.append(event)
                    rule.last_triggered = datetime.now().isoformat()
                    
                    # 执行回调
                    for callback in self.callbacks:
                        try:
                            callback(event)
                        except:
                            pass
        
        # 保存更新后的规则状态
        if triggered:
            self._save_rules()
        
        return triggered
    
    def _check_rule(self, rule: AlertRule, code: str, name: str, 
                   current_price: float, data: Dict) -> Optional[AlertEvent]:
        """检查单个规则是否触发"""
        
        if rule.rule_type == 'price_break':
            return self._check_price_break(rule, code, name, current_price, data)
        elif rule.rule_type == 'volume_surge':
            return self._check_volume_surge(rule, code, name, current_price, data)
        elif rule.rule_type == 'drawdown':
            return self._check_drawdown(rule, code, name, current_price, data)
        
        return None
    
    def _check_price_break(self, rule: AlertRule, code: str, name: str,
                          current_price: float, data: Dict) -> Optional[AlertEvent]:
        """检查价格突破"""
        prev_close = data.get('prev_close', current_price)
        
        if rule.condition == 'cross_up':
            # 突破上方
            if prev_close < rule.threshold <= current_price:
                return AlertEvent(
                    timestamp=datetime.now().isoformat(),
                    code=code,
                    name=name,
                    alert_type='price_break_up',
                    level='INFO',
                    message=f"🚀 {name}({code}) 突破 ¥{rule.threshold}，当前 ¥{current_price}",
                    current_price=current_price,
                    trigger_value=rule.threshold
                )
        
        elif rule.condition == 'cross_down':
            # 跌破下方
            if prev_close > rule.threshold >= current_price:
                return AlertEvent(
                    timestamp=datetime.now().isoformat(),
                    code=code,
                    name=name,
                    alert_type='price_break_down',
                    level='WARNING',
                    message=f"🔴 {name}({code}) 跌破 ¥{rule.threshold}，当前 ¥{current_price}",
                    current_price=current_price,
                    trigger_value=rule.threshold
                )
        
        return None
    
    def _check_volume_surge(self, rule: AlertRule, code: str, name: str,
                           current_price: float, data: Dict) -> Optional[AlertEvent]:
        """检查放量"""
        volume_ratio = data.get('volume_ratio', 1)
        
        if volume_ratio >= rule.threshold:
            return AlertEvent(
                timestamp=datetime.now().isoformat(),
                code=code,
                name=name,
                alert_type='volume_surge',
                level='INFO',
                message=f"📈 {name}({code}) 异常放量，量比 {volume_ratio:.2f}",
                current_price=current_price,
                trigger_value=volume_ratio
            )
        
        return None
    
    def _check_drawdown(self, rule: AlertRule, code: str, name: str,
                       current_price: float, data: Dict) -> Optional[AlertEvent]:
        """检查回撤"""
        high_20d = data.get('high_20d', current_price)
        
        if high_20d > 0:
            drawdown = (high_20d - current_price) / high_20d
            if drawdown >= rule.threshold:
                return AlertEvent(
                    timestamp=datetime.now().isoformat(),
                    code=code,
                    name=name,
                    alert_type='drawdown',
                    level='CRITICAL',
                    message=f"⚠️ {name}({code}) 从高点回撤 {drawdown*100:.1f}%",
                    current_price=current_price,
                    trigger_value=drawdown
                )
        
        return None
    
    def register_callback(self, callback: Callable):
        """注册预警回调函数"""
        self.callbacks.append(callback)
    
    def get_alert_summary(self) -> Dict:
        """获取预警统计"""
        summary = {
            'total_rules': sum(len(rules) for rules in self.alert_rules.values()),
            'total_alerts': len(self.alert_history),
            'today_alerts': len([
                a for a in self.alert_history 
                if datetime.fromisoformat(a.timestamp).date() == datetime.now().date()
            ]),
            'stocks_with_rules': len(self.alert_rules)
        }
        return summary
    
    def auto_setup_alerts_for_portfolio(self, portfolio: Dict):
        """
        为持仓自动设置预警
        - 成本价±8%预警
        - 20日高点回撤8%预警
        """
        for pos in portfolio.get('positions', []):
            code = pos['code']
            cost = pos['cost_price']
            
            # 止盈预警
            self.add_price_alert(code, cost * 1.15, 'above')
            # 止损预警
            self.add_price_alert(code, cost * 0.92, 'below')
            # 回撤预警
            self.add_drawdown_alert(code, 0.08)
        
        print(f"✅ 已为 {len(portfolio.get('positions', []))} 只持仓自动设置预警")


# 便捷函数
def create_default_alerts(codes: List[str]) -> SmartAlertSystem:
    """为股票列表创建默认预警"""
    alert_system = SmartAlertSystem()
    
    for code in codes:
        # 默认放量预警
        alert_system.add_volume_alert(code, volume_ratio=3.0)
    
    return alert_system


if __name__ == '__main__':
    # 测试
    print("🧪 测试智能预警系统...")
    
    alert_system = SmartAlertSystem()
    
    # 添加测试预警
    alert_system.add_price_alert('300750', 380, 'above')
    alert_system.add_volume_alert('300750', 2.5)
    
    # 检查预警
    events = alert_system.check_alerts(['300750'])
    
    if events:
        print(f"\n🚨 触发 {len(events)} 个预警:")
        for e in events:
            print(f"   {e.level}: {e.message}")
    else:
        print("\n✅ 无预警触发")
    
    # 显示统计
    summary = alert_system.get_alert_summary()
    print(f"\n📊 预警统计: {summary}")
