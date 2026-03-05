"""
smart_trader.py - 智能交易模块
交易执行、风控和仓位管理
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum
import numpy as np


class OrderType(Enum):
    """订单类型"""
    BUY = "买入"
    SELL = "卖出"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "待执行"
    EXECUTED = "已执行"
    CANCELLED = "已取消"
    FAILED = "失败"


@dataclass
class Order:
    """交易订单"""
    id: str
    code: str
    name: str
    order_type: OrderType
    price: float
    quantity: int
    amount: float
    status: OrderStatus
    created_at: str
    executed_at: Optional[str] = None
    executed_price: Optional[float] = None
    notes: str = ""


@dataclass
class Position:
    """持仓"""
    code: str
    name: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    profit_loss: float
    profit_loss_pct: float
    updated_at: str


class SmartTrader:
    """智能交易管理器"""
    
    def __init__(self, data_fetcher, config_file: str = "./data/trader_config.json"):
        self.data_fetcher = data_fetcher
        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 配置参数
        self.config = {
            'initial_capital': 1000000,      # 初始资金
            'max_position_pct': 0.2,          # 单股最大仓位比例
            'max_total_positions': 10,        # 最大持仓数量
            'stop_loss_pct': 0.08,            # 止损比例
            'take_profit_pct': 0.15,          # 止盈比例
            'min_trade_amount': 10000,        # 最小交易金额
            'risk_level': 'medium'            # 风险等级
        }
        
        self._load_config()
        
        # 状态数据
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.cash = self.config['initial_capital']
        self.total_value = self.config['initial_capital']
        
        self._load_state()
    
    def _load_config(self) -> None:
        """加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
            except Exception as e:
                print(f"加载配置失败: {e}")
    
    def _save_config(self) -> None:
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def _load_state(self) -> None:
        """加载交易状态"""
        state_file = self.config_file.parent / "trader_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.cash = state.get('cash', self.config['initial_capital'])
                    
                    # 加载持仓
                    for pos_data in state.get('positions', []):
                        pos = Position(**pos_data)
                        self.positions[pos.code] = pos
                    
                    # 加载订单历史
                    for order_data in state.get('orders', []):
                        order_data['order_type'] = OrderType(order_data['order_type'])
                        order_data['status'] = OrderStatus(order_data['status'])
                        self.orders.append(Order(**order_data))
            except Exception as e:
                print(f"加载交易状态失败: {e}")
    
    def _save_state(self) -> None:
        """保存交易状态"""
        state_file = self.config_file.parent / "trader_state.json"
        try:
            state = {
                'cash': self.cash,
                'total_value': self.total_value,
                'positions': [asdict(p) for p in self.positions.values()],
                'orders': [
                    {
                        **asdict(o),
                        'order_type': o.order_type.value,
                        'status': o.status.value
                    }
                    for o in self.orders[-100:]  # 只保留最近100条
                ],
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存交易状态失败: {e}")
    
    def update_prices(self) -> None:
        """更新持仓价格"""
        if not self.positions:
            return
        
        codes = list(self.positions.keys())
        realtime_data = self.data_fetcher.get_multiple_realtime(codes)
        
        for code, pos in self.positions.items():
            stock_data = realtime_data[realtime_data['code'] == code]
            if not stock_data.empty:
                current_price = stock_data.iloc[0]['price']
                if not pd.isna(current_price):
                    pos.current_price = current_price
                    pos.market_value = pos.quantity * current_price
                    pos.profit_loss = pos.market_value - (pos.quantity * pos.avg_cost)
                    pos.profit_loss_pct = (current_price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
                    pos.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 计算总资产
        position_value = sum(p.market_value for p in self.positions.values())
        self.total_value = self.cash + position_value
        
        self._save_state()
    
    def check_risk(self, code: str, order_type: OrderType, 
                   price: float, quantity: int) -> Tuple[bool, str]:
        """检查交易风险"""
        amount = price * quantity
        
        # 检查最小交易金额
        if amount < self.config['min_trade_amount']:
            return False, f"交易金额 {amount:.2f} 小于最小金额 {self.config['min_trade_amount']}"
        
        if order_type == OrderType.BUY:
            # 检查资金
            if amount > self.cash:
                return False, f"资金不足: 需要 {amount:.2f}, 可用 {self.cash:.2f}"
            
            # 检查持仓数量限制
            if len(self.positions) >= self.config['max_total_positions'] and code not in self.positions:
                return False, f"已达到最大持仓数量 {self.config['max_total_positions']}"
            
            # 检查单股仓位限制
            max_position_value = self.total_value * self.config['max_position_pct']
            current_value = self.positions.get(code, Position(
                code=code, name="", quantity=0, avg_cost=0,
                current_price=price, market_value=0, profit_loss=0,
                profit_loss_pct=0, updated_at=""
            )).market_value
            new_value = current_value + amount
            if new_value > max_position_value:
                return False, f"超过单股最大仓位限制: 将持有 {new_value:.2f}, 限制 {max_position_value:.2f}"
        
        elif order_type == OrderType.SELL:
            # 检查持仓
            if code not in self.positions:
                return False, f"没有持仓 {code}"
            if quantity > self.positions[code].quantity:
                return False, f"持仓不足: 持有 {self.positions[code].quantity}, 卖出 {quantity}"
        
        return True, "通过"
    
    def create_order(self, code: str, name: str, order_type: OrderType,
                     price: float, quantity: int, notes: str = "") -> Optional[Order]:
        """创建订单"""
        # 风险检查
        passed, msg = self.check_risk(code, order_type, price, quantity)
        if not passed:
            print(f"风险检查未通过: {msg}")
            return None
        
        order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{len(self.orders):04d}"
        
        order = Order(
            id=order_id,
            code=code,
            name=name,
            order_type=order_type,
            price=price,
            quantity=quantity,
            amount=price * quantity,
            status=OrderStatus.PENDING,
            created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            notes=notes
        )
        
        self.orders.append(order)
        print(f"创建订单: {order_id} - {order_type.value} {code} {quantity}股 @ {price}")
        
        return order
    
    def execute_order(self, order_id: str, executed_price: Optional[float] = None) -> bool:
        """执行订单"""
        order = next((o for o in self.orders if o.id == order_id), None)
        if not order:
            print(f"订单 {order_id} 不存在")
            return False
        
        if order.status != OrderStatus.PENDING:
            print(f"订单 {order_id} 状态为 {order.status.value}, 无法执行")
            return False
        
        # 使用实际成交价或订单价格
        price = executed_price or order.price
        amount = price * order.quantity
        
        if order.order_type == OrderType.BUY:
            # 更新现金
            self.cash -= amount
            
            # 更新持仓
            if order.code in self.positions:
                pos = self.positions[order.code]
                total_cost = pos.avg_cost * pos.quantity + amount
                pos.quantity += order.quantity
                pos.avg_cost = total_cost / pos.quantity
            else:
                self.positions[order.code] = Position(
                    code=order.code,
                    name=order.name,
                    quantity=order.quantity,
                    avg_cost=price,
                    current_price=price,
                    market_value=amount,
                    profit_loss=0,
                    profit_loss_pct=0,
                    updated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        elif order.order_type == OrderType.SELL:
            # 更新现金
            self.cash += amount
            
            # 更新持仓
            if order.code in self.positions:
                pos = self.positions[order.code]
                pos.quantity -= order.quantity
                if pos.quantity <= 0:
                    del self.positions[order.code]
        
        # 更新订单状态
        order.status = OrderStatus.EXECUTED
        order.executed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        order.executed_price = price
        
        self._save_state()
        print(f"订单 {order_id} 已执行 @ {price}")
        
        return True
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        order = next((o for o in self.orders if o.id == order_id), None)
        if not order:
            return False
        
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            self._save_state()
            print(f"订单 {order_id} 已取消")
            return True
        
        return False
    
    def check_stop_loss_take_profit(self) -> List[Dict]:
        """检查止损止盈"""
        alerts = []
        
        for code, pos in self.positions.items():
            if pos.profit_loss_pct <= -self.config['stop_loss_pct'] * 100:
                alerts.append({
                    'code': code,
                    'name': pos.name,
                    'type': '止损',
                    'profit_loss_pct': pos.profit_loss_pct,
                    'suggestion': f'建议卖出，亏损 {pos.profit_loss_pct:.2f}%'
                })
            elif pos.profit_loss_pct >= self.config['take_profit_pct'] * 100:
                alerts.append({
                    'code': code,
                    'name': pos.name,
                    'type': '止盈',
                    'profit_loss_pct': pos.profit_loss_pct,
                    'suggestion': f'建议卖出，盈利 {pos.profit_loss_pct:.2f}%'
                })
        
        return alerts
    
    def get_portfolio_summary(self) -> Dict:
        """获取投资组合摘要"""
        self.update_prices()
        
        position_value = sum(p.market_value for p in self.positions.values())
        total_profit_loss = sum(p.profit_loss for p in self.positions.values())
        
        return {
            'cash': round(self.cash, 2),
            'position_value': round(position_value, 2),
            'total_value': round(self.total_value, 2),
            'total_return': round((self.total_value - self.config['initial_capital']) / self.config['initial_capital'] * 100, 2),
            'position_count': len(self.positions),
            'unrealized_pnl': round(total_profit_loss, 2),
            'cash_ratio': round(self.cash / self.total_value * 100, 2) if self.total_value > 0 else 0,
            'position_ratio': round(position_value / self.total_value * 100, 2) if self.total_value > 0 else 0
        }
    
    def display_portfolio(self) -> None:
        """显示投资组合"""
        self.update_prices()
        
        summary = self.get_portfolio_summary()
        
        print(f"\n{'='*100}")
        print(f"投资组合概览")
        print(f"{'='*100}")
        print(f"总资产: {summary['total_value']:,.2f}  现金: {summary['cash']:,.2f} ({summary['cash_ratio']:.1f}%)")
        print(f"持仓市值: {summary['position_value']:,.2f} ({summary['position_ratio']:.1f}%)")
        print(f"总收益: {summary['total_return']:.2f}%  未实现盈亏: {summary['unrealized_pnl']:,.2f}")
        print(f"{'-'*100}")
        
        if self.positions:
            print(f"{'代码':<10}{'名称':<12}{'数量':<10}{'成本价':<10}{'现价':<10}{'市值':<12}{'盈亏':<12}{'盈亏%':<8}")
            print(f"{'-'*100}")
            
            for pos in sorted(self.positions.values(), key=lambda x: x.market_value, reverse=True):
                pnl_color = "+" if pos.profit_loss >= 0 else ""
                print(f"{pos.code:<10}{pos.name:<12}{pos.quantity:<10}{pos.avg_cost:<10.2f}{pos.current_price:<10.2f}"
                      f"{pos.market_value:<12,.0f}{pnl_color}{pos.profit_loss:<12,.2f}{pos.profit_loss_pct:<8.2f}%")
        else:
            print("当前无持仓")
        
        print(f"{'='*100}")
    
    def execute_strategy_signals(self, signals, watchlist, max_orders: int = 3) -> List[str]:
        """执行策略信号"""
        executed_orders = []
        
        for signal in signals[:max_orders]:
            if signal.signal.value == "买入":
                # 计算购买数量（简单策略：每只最多投入10%资金）
                max_amount = self.total_value * 0.1
                price = signal.indicators.get('close', 0)
                
                if price > 0:
                    quantity = int(max_amount / price / 100) * 100  # 按手计算
                    if quantity >= 100:
                        order = self.create_order(
                            code=signal.code,
                            name=signal.name,
                            order_type=OrderType.BUY,
                            price=price,
                            quantity=quantity,
                            notes=f"策略信号: {', '.join(signal.reasons)}"
                        )
                        if order:
                            # 模拟执行
                            self.execute_order(order.id, price)
                            executed_orders.append(order.id)
        
        return executed_orders


# 导入pandas用于类型检查
import pandas as pd
