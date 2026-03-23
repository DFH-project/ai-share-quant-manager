#!/usr/bin/env python3
"""
position_manager.py - 持仓管理模块
功能：
1. 管理实际持仓数据
2. 计算组合风险敞口
3. 生成仓位调整建议
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

@dataclass
class Position:
    """持仓数据"""
    code: str
    name: str
    shares: int  # 持股数量
    avg_cost: float  # 平均成本
    current_price: float = 0.0  # 当前价格
    market_value: float = 0.0  # 市值
    profit_loss: float = 0.0  # 盈亏金额
    profit_loss_pct: float = 0.0  # 盈亏比例
    weight: float = 0.0  # 组合权重
    
    def update_price(self, price: float):
        """更新当前价格"""
        self.current_price = price
        self.market_value = self.shares * price
        self.profit_loss = (price - self.avg_cost) * self.shares
        if self.avg_cost > 0:
            self.profit_loss_pct = (price - self.avg_cost) / self.avg_cost * 100


class PositionManager:
    """持仓管理器"""
    
    def __init__(self, data_dir: Path = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / 'data'
        
        self.data_dir = data_dir
        self.positions_file = data_dir / 'positions.json'
        self.history_file = data_dir / 'trade_history.json'
        
        self.positions: Dict[str, Position] = {}
        self.total_value: float = 0.0
        self.total_profit_loss: float = 0.0
        
        self._load_positions()
    
    def _load_positions(self):
        """加载持仓数据"""
        try:
            if self.positions_file.exists():
                with open(self.positions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for code, pos_data in data.get('positions', {}).items():
                        self.positions[code] = Position(**pos_data)
        except Exception as e:
            print(f"加载持仓失败: {e}")
    
    def _save_positions(self):
        """保存持仓数据"""
        try:
            data = {
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'positions': {code: asdict(pos) for code, pos in self.positions.items()}
            }
            with open(self.positions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存持仓失败: {e}")
    
    def update_position(self, code: str, name: str, shares: int, avg_cost: float):
        """更新持仓"""
        if code in self.positions:
            # 更新现有持仓
            pos = self.positions[code]
            total_cost = pos.shares * pos.avg_cost + shares * avg_cost
            total_shares = pos.shares + shares
            if total_shares > 0:
                pos.avg_cost = total_cost / total_shares
            pos.shares = total_shares
        else:
            # 新建持仓
            self.positions[code] = Position(
                code=code,
                name=name,
                shares=shares,
                avg_cost=avg_cost
            )
        
        self._save_positions()
    
    def close_position(self, code: str):
        """平仓"""
        if code in self.positions:
            del self.positions[code]
            self._save_positions()
    
    def update_prices(self, price_data: Dict[str, float]):
        """批量更新价格"""
        for code, price in price_data.items():
            if code in self.positions:
                self.positions[code].update_price(price)
        
        # 重新计算总市值和权重
        self.total_value = sum(pos.market_value for pos in self.positions.values())
        self.total_profit_loss = sum(pos.profit_loss for pos in self.positions.values())
        
        for pos in self.positions.values():
            if self.total_value > 0:
                pos.weight = pos.market_value / self.total_value * 100
    
    def get_position(self, code: str) -> Optional[Position]:
        """获取单个持仓"""
        return self.positions.get(code)
    
    def get_all_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self.positions.values())
    
    def get_portfolio_summary(self) -> Dict:
        """获取组合摘要"""
        return {
            'total_value': self.total_value,
            'total_profit_loss': self.total_profit_loss,
            'position_count': len(self.positions),
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'positions': [
                {
                    'code': p.code,
                    'name': p.name,
                    'shares': p.shares,
                    'avg_cost': p.avg_cost,
                    'current_price': p.current_price,
                    'market_value': p.market_value,
                    'profit_loss': p.profit_loss,
                    'profit_loss_pct': p.profit_loss_pct,
                    'weight': p.weight
                }
                for p in self.positions.values()
            ]
        }
    
    def get_risk_exposure(self) -> Dict:
        """获取风险敞口分析"""
        if not self.positions:
            return {'status': '无持仓'}
        
        # 计算集中度
        weights = [pos.weight for pos in self.positions.values()]
        max_weight = max(weights) if weights else 0
        avg_weight = sum(weights) / len(weights) if weights else 0
        
        # 盈亏分布
        profit_positions = [p for p in self.positions.values() if p.profit_loss > 0]
        loss_positions = [p for p in self.positions.values() if p.profit_loss < 0]
        
        return {
            'concentration': {
                'max_single_weight': max_weight,
                'average_weight': avg_weight,
                'concentration_risk': 'HIGH' if max_weight > 20 else 'MEDIUM' if max_weight > 10 else 'LOW'
            },
            'pnl_distribution': {
                'profit_count': len(profit_positions),
                'loss_count': len(loss_positions),
                'profit_amount': sum(p.profit_loss for p in profit_positions),
                'loss_amount': sum(p.profit_loss for p in loss_positions)
            },
            'total_value': self.total_value,
            'total_pnl': self.total_profit_loss
        }
    
    def generate_alert_with_position(self, code: str, alert_title: str, 
                                     risk_level: str, suggestion: str) -> str:
        """生成带持仓信息的警报"""
        position = self.get_position(code)
        
        report = []
        report.append(f"\n{'='*70}")
        report.append(f"🚨 持仓风险警报 - {code}")
        report.append(f"{'='*70}")
        report.append(f"📰 公告: {alert_title}")
        report.append(f"⚠️ 风险等级: {risk_level}")
        
        if position:
            report.append(f"\n📊 您的持仓:")
            report.append(f"   持股: {position.shares} 股")
            report.append(f"   成本: ¥{position.avg_cost:.2f}")
            report.append(f"   现价: ¥{position.current_price:.2f}")
            report.append(f"   市值: ¥{position.market_value:,.2f}")
            report.append(f"   盈亏: {position.profit_loss:+.2f} ({position.profit_loss_pct:+.2f}%)")
            report.append(f"   权重: {position.weight:.2f}%")
            
            # 计算潜在损失
            if risk_level in ['极高风险', '高风险']:
                potential_loss = position.market_value * 0.1  # 假设跌10%
                report.append(f"\n⚠️ 如果跌停，预计损失: ¥{potential_loss:,.2f}")
        else:
            report.append(f"\nℹ️ 您未持有该股票")
        
        report.append(f"\n💡 建议行动: {suggestion}")
        report.append(f"{'='*70}\n")
        
        return '\n'.join(report)


def main():
    """测试"""
    pm = PositionManager()
    
    # 添加测试持仓
    pm.update_position('603127', '昭衍新药', 1000, 25.0)
    pm.update_position('600519', '贵州茅台', 100, 1500.0)
    
    # 更新价格
    pm.update_prices({
        '603127': 20.0,  # 跌停价
        '600519': 1550.0
    })
    
    # 打印组合摘要
    print("组合摘要:")
    print(json.dumps(pm.get_portfolio_summary(), indent=2, ensure_ascii=False))
    
    print("\n风险敞口:")
    print(json.dumps(pm.get_risk_exposure(), indent=2, ensure_ascii=False))
    
    # 生成带持仓的警报
    print(pm.generate_alert_with_position(
        '603127',
        '股东拟合计减持公司不超4.1%股份',
        '高风险',
        '建议减仓30-50%，设置-5%止损位'
    ))


if __name__ == '__main__':
    main()
