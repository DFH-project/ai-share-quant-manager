#!/usr/bin/env python3
"""
A股自动选股管理器 - Auto Watchlist Manager
三种策略动态管理自选池：
1. 追涨型：板块龙头，强势股（已有）
2. 潜力型：热门板块核心标的
3. 抄底型：调整后低位企稳的热门股
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_fetcher import data_fetcher
from core.watchlist_memory import WatchlistMemory, get_watchlist_memory
from core.multi_dimension_analyzer import get_analyzer, StockAnalysisResult
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path

# 热门板块核心标的（潜力股池 + 强势股低吸池）
HOT_SECTOR_CORE = {
    'AI算力': ['603019', '000938', '600756', '300418', '002230', '601138'],
    '半导体': ['600584', '603160', '002371', '688981', '600460', '002156'],
    '新能源': ['300750', '601012', '600438', '002594', '300014', '002466'],
    '机器人': ['002050', '300124', '002747', '603486', '688169', '002896'],
    '医药': ['600276', '000538', '300760', '603259', '600196', '603127'],
    '低空经济': ['002151', '300900', '002097', '000099', '300775', '002085'],
    '固态电池': ['300073', '002709', '603659', '300450', '002074', '300769'],
    'CPO光模块': ['300308', '300502', '002281', '300394', '000988'],
}

class AutoWatchlistManager:
    """自动选股管理器 - 三策略选股"""
    
    def __init__(self):
        self.watchlist = get_watchlist_memory()
        self.buy_signals = []  # 买入信号池
        self.potential_stocks = []  # 潜力股池
        self.bottom_fishing = []  # 抄底池
        
    def scan_dip_buy_opportunities(self) -> List[Dict]:
        """
        策略4: 强势股低吸型 - 关键策略
        特征：
        1. 属于热门板块核心标的
        2. 近期有强势表现（昨天或前天涨>2%，证明是强势股）
        3. 今天回调（跌1-4%，给出买点）
        4. 不是破位（没有跌破关键支撑）
        
        举例：昨天中科曙光+2.5%，今天-1.5% → 低吸机会
        """
        dip_opportunities = []
        
        try:
            # 收集所有热门板块核心标的
            all_hot_stocks = set()
            for sector, codes in HOT_SECTOR_CORE.items():
                all_hot_stocks.update(codes)
            
            stock_list = list(all_hot_stocks)
            stock_data = data_fetcher.get_stock_data(stock_list)
            
            for code, data in stock_data.items():
                current = data.get('current', 0)
                change_pct = data.get('change_pct', 0)
                prev_close = data.get('prev_close', 0)
                
                # 条件1: 今天回调（跌1-4%，给出买点但不过度悲观）
                if -4 <= change_pct < -0.5:
                    score = 0
                    reasons = []
                    
                    # 条件2: 昨天涨得好（证明是强势股）
                    # 通过昨收和今开判断昨日表现
                    open_price = data.get('open', 0)
                    if open_price > 0 and prev_close > 0:
                        # 如果今天高开，说明昨天收盘强势
                        gap_pct = (open_price - prev_close) / prev_close * 100
                        if gap_pct > 0.5:  # 高开说明昨天强势
                            score += 25
                            reasons.append("昨日强势")
                    
                    # 条件3: 热门板块属性（核心逻辑）
                    sector_name = self._get_stock_sector(code)
                    if sector_name:
                        score += 30
                        reasons.append(f"热门板块-{sector_name}")
                    
                    # 条件4: 回调幅度适中（1-4%是良性回调）
                    if -3 <= change_pct < -1:
                        score += 20
                        reasons.append("良性回调")
                    elif -4 <= change_pct < -3:
                        score += 10
                        reasons.append("深度回调")
                    
                    # 条件5: 未跌破关键支撑（简化判断：未跌破今日开盘太多）
                    if open_price > 0:
                        drop_from_open = (current - open_price) / open_price * 100
                        if drop_from_open > -2:  # 从开盘跌幅不大
                            score += 15
                            reasons.append("支撑有效")
                    
                    # 条件6: 成交量未过度放大（不是出货）
                    volume_ratio = data.get('volume_ratio', 1)
                    if volume_ratio < 1.5:  # 缩量或正常量
                        score += 10
                        reasons.append("未放量恐慌")
                    
                    if score >= 50:
                        dip_opportunities.append({
                            'code': code,
                            'name': data.get('name', code),
                            'price': current,
                            'change_pct': change_pct,
                            'score': score,
                            'reasons': reasons,
                            'sector': sector_name or '',
                            'strategy': '强势股低吸',
                            'time': datetime.now().strftime('%H:%M'),
                            'suggestion': f'昨日强势，今日回调{change_pct:.1f}%，可考虑低吸'
                        })
            
            dip_opportunities.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            print(f"扫描低吸机会失败: {e}")
        
        return dip_opportunities[:10]  # 保留前10
    
    def _get_stock_sector(self, code: str) -> Optional[str]:
        """获取股票所属的热门板块"""
        for sector, codes in HOT_SECTOR_CORE.items():
            if code in codes:
                return sector
        return None
    
    def scan_buy_signals(self, stock_pool: List[str] = None) -> List[Dict]:
        """
        策略1: 追涨型 - 扫描买入信号
        检测条件：
        1. 量价齐升（成交量>5日均量1.5倍 + 涨幅>3%）
        2. 强势上涨（涨幅>5%）
        3. 突破新高
        4. 资金流入
        """
        signals = []
        
        if stock_pool is None:
            stock_pool = self._get_default_scan_pool()
        
        try:
            stock_data = data_fetcher.get_stock_data(stock_pool[:50])
            
            for code, data in stock_data.items():
                signal_score = 0
                reasons = []
                
                # 条件1: 量价齐升
                if data.get('volume_ratio', 0) > 1.5 and data.get('change_pct', 0) > 3:
                    signal_score += 30
                    reasons.append("量价齐升")
                
                # 条件2: 强势上涨
                if data.get('change_pct', 0) > 5:
                    signal_score += 25
                    reasons.append("强势上涨")
                
                # 条件3: 突破新高
                if data.get('high_20d', 0) > 0 and data.get('current', 0) >= data.get('high_20d', 0) * 0.98:
                    signal_score += 20
                    reasons.append("接近20日新高")
                
                # 条件4: 资金流入
                if data.get('main_force_flow', 0) > 0:
                    signal_score += 15
                    reasons.append("主力流入")
                
                if signal_score >= 50:
                    signals.append({
                        'code': code,
                        'name': data.get('name', code),
                        'price': data.get('current', 0),
                        'change_pct': data.get('change_pct', 0),
                        'score': signal_score,
                        'reasons': reasons,
                        'sector': data.get('sector', ''),
                        'strategy': '追涨型',
                        'time': datetime.now().strftime('%H:%M')
                    })
            
            signals.sort(key=lambda x: x['score'], reverse=True)
            self.buy_signals = signals[:10]
            
        except Exception as e:
            print(f"扫描买入信号失败: {e}")
        
        return self.buy_signals
    
    def scan_potential_stocks(self) -> List[Dict]:
        """
        策略2: 潜力型 - 扫描热门板块核心标的
        特征：
        1. 属于热门板块核心标的
        2. 尚未大幅上涨（涨幅<3%）
        3. 有资金关注迹象
        4. 技术形态良好（均线多头排列初期）
        """
        potentials = []
        
        try:
            # 收集所有热门板块核心标的
            all_core_stocks = []
            for sector, codes in HOT_SECTOR_CORE.items():
                all_core_stocks.extend([(code, sector) for code in codes])
            
            # 去重
            unique_stocks = list(set(all_core_stocks))
            codes = [item[0] for item in unique_stocks]
            code_to_sector = {item[0]: item[1] for item in unique_stocks}
            
            stock_data = data_fetcher.get_stock_data(codes)
            
            for code, data in stock_data.items():
                change_pct = data.get('change_pct', 0)
                
                # 条件：尚未大涨但有潜力
                if 0 < change_pct < 3:  # 微涨，有启动迹象
                    score = 0
                    reasons = []
                    
                    # 热门板块加分
                    score += 20
                    reasons.append(f"热门板块-{code_to_sector.get(code, '')}")
                    
                    # 资金流入加分
                    if data.get('main_force_flow', 0) > 0:
                        score += 15
                        reasons.append("资金关注")
                    
                    # 成交量温和放大
                    if data.get('volume_ratio', 0) > 1.2:
                        score += 10
                        reasons.append("量能温和")
                    
                    if score >= 30:
                        potentials.append({
                            'code': code,
                            'name': data.get('name', code),
                            'price': data.get('current', 0),
                            'change_pct': change_pct,
                            'score': score,
                            'reasons': reasons,
                            'sector': code_to_sector.get(code, ''),
                            'strategy': '潜力型',
                            'time': datetime.now().strftime('%H:%M')
                        })
            
            potentials.sort(key=lambda x: x['score'], reverse=True)
            self.potential_stocks = potentials[:8]
            
        except Exception as e:
            print(f"扫描潜力股失败: {e}")
        
        return self.potential_stocks
    
    def scan_bottom_fishing(self, stock_pool: List[str] = None) -> List[Dict]:
        """
        策略3: 抄底型 - 扫描调整后低位企稳的热门股
        特征：
        1. 属于热门板块
        2. 近期调整充分（从高点回调>10%）
        3. 出现企稳信号（缩量十字星、下影线）
        4. 今日微涨或止跌（跌幅<2%）
        """
        bottoms = []
        
        if stock_pool is None:
            # 扫描热门板块核心标的
            stock_pool = []
            for codes in HOT_SECTOR_CORE.values():
                stock_pool.extend(codes)
        
        try:
            stock_data = data_fetcher.get_stock_data(stock_pool[:40])
            
            for code, data in stock_data.items():
                change_pct = data.get('change_pct', 0)
                high_20d = data.get('high_20d', 0)
                current = data.get('current', 0)
                
                # 条件1: 有前期高点且回调充分
                if high_20d > 0 and current < high_20d * 0.90:  # 从20日高点回调>10%
                    score = 0
                    reasons = []
                    
                    # 止跌信号
                    if -2 < change_pct < 2:  # 跌幅收窄或微涨
                        score += 25
                        reasons.append("止跌企稳")
                    
                    # 缩量（抛压减轻）
                    if data.get('volume_ratio', 0) < 0.8:
                        score += 20
                        reasons.append("缩量惜售")
                    
                    # 下影线（支撑有效）
                    if data.get('low', 0) > 0:
                        lower_shadow = (current - data.get('low', current)) / data.get('low', 1) * 100
                        if lower_shadow > 1:  # 有下影线
                            score += 15
                            reasons.append("下方支撑")
                    
                    # 热门板块属性
                    score += 10
                    reasons.append("热门板块调整")
                    
                    if score >= 40:
                        pullback_pct = (high_20d - current) / high_20d * 100
                        bottoms.append({
                            'code': code,
                            'name': data.get('name', code),
                            'price': current,
                            'change_pct': change_pct,
                            'pullback_pct': pullback_pct,
                            'score': score,
                            'reasons': reasons,
                            'strategy': '抄底型',
                            'time': datetime.now().strftime('%H:%M')
                        })
            
            bottoms.sort(key=lambda x: x['score'], reverse=True)
            self.bottom_fishing = bottoms[:8]
            
        except Exception as e:
            print(f"扫描抄底机会失败: {e}")
        
        return self.bottom_fishing
    
    def auto_add_to_watchlist(self, signals: List[Dict] = None, strategy_type: str = "追涨型") -> int:
        """自动将信号股加入自选，按策略分类"""
        if signals is None:
            signals = self.buy_signals
        
        category_map = {
            '强势股低吸': '重点监控-低吸',
            '追涨型': '重点监控-追涨',
            '潜力型': '重点监控-潜力',
            '抄底型': '重点监控-抄底',
            '多维度优选': '重点监控-优选',
            '震荡整理': '重点监控-震荡',
            '板块补涨': '重点监控-补涨',
            '基本面价值': '重点监控-价值',
            '重点-AI算力': '重点监控-AI算力',
            '重点-半导体': '重点监控-半导体',
            '重点-新能源': '重点监控-新能源',
            '重点-机器人': '重点监控-机器人'
        }
        
        priority_map = {
            '强势股低吸': 10,
            '追涨型': 9,
            '潜力型': 8,
            '抄底型': 7,
            '多维度优选': 9,
            '震荡整理': 8,  # 新策略优先级
            '板块补涨': 9,  # 新策略优先级
            '基本面价值': 7,  # 新策略优先级
            '重点-AI算力': 9,
            '重点-半导体': 9,
            '重点-新能源': 9,
            '重点-机器人': 9
        }
        
        emoji_map = {
            '强势股低吸': '💧',
            '追涨型': '🚀',
            '潜力型': '💎',
            '抄底型': '🎯',
            '多维度优选': '⭐',
            '震荡整理': '⏳',  # 新策略emoji
            '板块补涨': '📈',  # 新策略emoji
            '基本面价值': '💰',  # 新策略emoji
            '重点-AI算力': '🤖',
            '重点-半导体': '🔌',
            '重点-新能源': '🔋',
            '重点-机器人': '🦾'
        }
        
        category = category_map.get(strategy_type, '重点监控')
        priority = priority_map.get(strategy_type, 8)
        emoji = emoji_map.get(strategy_type, '✳️')
        
        added_count = 0
        for signal in signals:
            code = signal['code']
            
            # 如果已存在，更新
            if self.watchlist.exists(code):
                self.watchlist.update(
                    code,
                    category=category,
                    priority=priority,
                    notes=f"{emoji}{strategy_type}:{signal['score']}分 {' '.join(signal['reasons'])} {signal['time']}"
                )
            else:
                # 新加入自选
                self.watchlist.add(
                    code=code,
                    name=signal['name'],
                    category=category,
                    priority=priority,
                    tags=["自动发现", strategy_type],
                    notes=f"{emoji}{strategy_type} {signal['score']}分 {' '.join(signal['reasons'])} 价格:{signal['price']:.2f}"
                )
                added_count += 1
        
        return added_count
    
    def auto_remove_from_watchlist(self) -> int:
        """自动移除走坏的股票"""
        removed_count = 0
        watchlist_items = self.watchlist.get_all()
        
        codes = [item.code for item in watchlist_items]
        if not codes:
            return 0
        
        try:
            stock_data = data_fetcher.get_stock_data(codes)
            
            for item in watchlist_items:
                code = item.code
                if code not in stock_data:
                    continue
                
                data = stock_data[code]
                change_pct = data.get('change_pct', 0)
                
                # 不同策略不同止损条件
                should_remove = False
                remove_reason = ""
                
                if '低吸' in item.category and change_pct < -4:
                    # 低吸失败，继续下跌
                    should_remove = True
                    remove_reason = f"低吸失败跌{change_pct:.2f}%"
                
                elif '追涨' in item.category and change_pct < -5:
                    should_remove = True
                    remove_reason = f"追涨股大跌{change_pct:.2f}%"
                
                elif '优选' in item.category and change_pct < -5:
                    # 多维度优选股大跌，评分失效
                    should_remove = True
                    remove_reason = f"优选股大跌{change_pct:.2f}%，重新评估"
                
                elif '抄底' in item.category and change_pct < -3:
                    # 抄底失败，继续探底
                    should_remove = True
                    remove_reason = f"抄底失败跌{change_pct:.2f}%"
                
                elif '潜力' in item.category and change_pct < -4:
                    should_remove = True
                    remove_reason = f"潜力股破位跌{change_pct:.2f}%"
                
                if should_remove:
                    self.watchlist.update(
                        code,
                        category="观察",
                        priority=0,
                        notes=f"❌已降级-{remove_reason} {datetime.now().strftime('%H:%M')}"
                    )
                    removed_count += 1
        
        except Exception as e:
            print(f"自动移除检查失败: {e}")
        
        return removed_count
    
    def scan_multi_dimension_opportunities(self) -> List[Dict]:
        """
        策略5: 多维度综合选股 - 使用多维度分析引擎
        综合考虑：趋势、基本面、资金面、技术面、板块面
        """
        opportunities = []
        
        try:
            # 收集扫描池
            scan_pool = self._get_default_scan_pool()
            
            # 使用多维度分析器
            analyzer = get_analyzer()
            
            print(f"\n  正在对 {len(scan_pool)} 只股票进行多维度分析...")
            
            for code in scan_pool[:30]:  # 最多分析30只
                result = analyzer.analyze_stock(code)
                if result and result.total_score >= 65:  # 综合评分65分以上
                    opportunities.append({
                        'code': result.code,
                        'name': result.name,
                        'price': result.current_price,
                        'change_pct': result.change_pct,
                        'score': result.total_score,
                        'trend_score': result.trend_score,
                        'fund_score': result.fund_score,
                        'technical_score': result.technical_score,
                        'reasons': [
                            f"综合评分{result.total_score:.0f}",
                            f"趋势{result.trend_score:.0f}",
                            f"资金{result.fund_score:.0f}",
                            result.suggestion[:20]
                        ],
                        'suggestion': result.suggestion,
                        'risk_level': result.risk_level,
                        'strategy': '多维度优选',
                        'time': datetime.now().strftime('%H:%M')
                    })
            
            # 按综合评分排序
            opportunities.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            print(f"多维度扫描失败: {e}")
        
        return opportunities[:10]
    
    def get_strategy_summary(self) -> Dict[str, List[Dict]]:
        """获取三策略汇总"""
        return {
            '追涨型': self.buy_signals[:5],
            '潜力型': self.potential_stocks[:5],
            '抄底型': self.bottom_fishing[:5]
        }
    
    def run_full_scan(self) -> Dict:
        """完整四策略扫描"""
        print("\n" + "="*60)
        print("🔍 启动四策略全量扫描")
        print("="*60)
        
        # 0. 强势股低吸扫描（最优先）
        print("\n【策略0: 强势股低吸型 - 昨日强势，今日回调】")
        print("   核心逻辑：昨天涨得好证明强势，今天回调给出买点")
        dip_signals = self.scan_dip_buy_opportunities()
        dip_added = self.auto_add_to_watchlist(dip_signals, '强势股低吸')
        print(f"  发现 {len(dip_signals)} 个低吸机会，新增 {dip_added} 只")
        if dip_signals:
            print("  今日低吸标的：")
            for s in dip_signals[:3]:
                print(f"    💧 {s['name']}({s['code']}) {s['change_pct']:+.2f}% - {s['suggestion']}")
        
        # 1. 追涨型扫描
        print("\n【策略1: 追涨型 - 板块龙头+强势股】")
        chase_signals = self.scan_buy_signals()
        chase_added = self.auto_add_to_watchlist(chase_signals, '追涨型')
        print(f"  发现 {len(chase_signals)} 个追涨信号，新增 {chase_added} 只")
        
        # 2. 潜力型扫描
        print("\n【策略2: 潜力型 - 热门板块核心标的】")
        potential_signals = self.scan_potential_stocks()
        potential_added = self.auto_add_to_watchlist(potential_signals, '潜力型')
        print(f"  发现 {len(potential_signals)} 个潜力标的，新增 {potential_added} 只")
        
        # 3. 抄底型扫描
        print("\n【策略3: 抄底型 - 热门板块调整后的低位机会】")
        bottom_signals = self.scan_bottom_fishing()
        bottom_added = self.auto_add_to_watchlist(bottom_signals, '抄底型')
        print(f"  发现 {len(bottom_signals)} 个抄底机会，新增 {bottom_added} 只")
        
        # 4. 多维度综合选股
        print("\n【策略4: 多维度综合优选 - 趋势+基本面+资金+技术+板块】")
        multi_signals = self.scan_multi_dimension_opportunities()
        multi_added = self.auto_add_to_watchlist(multi_signals, '多维度优选')
        print(f"  发现 {len(multi_signals)} 只多维度优选标的，新增 {multi_added} 只")
        if multi_signals:
            print("  综合评分最高的标的：")
            for s in multi_signals[:3]:
                print(f"    ⭐ {s['name']}({s['code']}) 综合{s['score']:.0f}分 - {s['suggestion']}")
        
        # 5. 震荡股票池（新增）
        print("\n【策略5: 震荡整理 - 评分60-64分，今日涨幅-1%~+1%】")
        print("   核心逻辑：震荡整理中，等待突破信号")
        consolidation_signals = self.scan_consolidation_stocks()
        consolidation_added = self.auto_add_to_watchlist(consolidation_signals, '震荡整理')
        print(f"  发现 {len(consolidation_signals)} 只震荡整理标的，新增 {consolidation_added} 只")
        if consolidation_signals:
            print("  震荡整理标的：")
            for s in consolidation_signals[:3]:
                print(f"    ⏳ {s['name']}({s['code']}) {s['change_pct']:+.2f}% 综合{s['score']:.0f}分")
        
        # 6. 板块补涨机会（新增）
        print("\n【策略6: 板块补涨 - 板块涨但个股没涨】")
        print("   核心逻辑：板块效应扩散，滞涨个股补涨")
        laggard_signals = self.scan_sector_laggards()
        laggard_added = self.auto_add_to_watchlist(laggard_signals, '板块补涨')
        print(f"  发现 {len(laggard_signals)} 个补涨机会，新增 {laggard_added} 只")
        if laggard_signals:
            print("  补涨标的：")
            for s in laggard_signals[:3]:
                print(f"    📈 {s['name']}({s['code']}) 板块{s['sector_change']:+.2f}% 个股{s['change_pct']:+.2f}%")
        
        # 7. 基本面价值筛选（新增）
        print("\n【策略7: 基本面价值 - PE<20 + ROE>15%，不管今日涨跌】")
        print("   核心逻辑：低估值+高盈利，价值投资视角")
        value_signals = self.scan_fundamental_value()
        value_added = self.auto_add_to_watchlist(value_signals, '基本面价值')
        print(f"  发现 {len(value_signals)} 只价值标的，新增 {value_added} 只")
        if value_signals:
            print("  价值标的：")
            for s in value_signals[:3]:
                print(f"    💰 {s['name']}({s['code']}) PE{s['pe']:.1f} ROE{s['roe']:.1f}%")
        
        # 8. 重点板块标的筛选（新增）
        print("\n【策略8: 重点板块 - AI算力/半导体/新能源/机器人】")
        focus_signals = self.scan_focus_sectors(['AI算力', '半导体', '新能源', '机器人'])
        focus_added = 0
        for s in focus_signals:
            added = self.auto_add_to_watchlist([s], s['strategy'])
            focus_added += added
        print(f"  发现 {len(focus_signals)} 只重点板块标的，新增 {focus_added} 只")
        if focus_signals:
            print("  重点板块标的：")
            current_sector = ""
            for s in focus_signals[:6]:
                if s['sector'] != current_sector:
                    current_sector = s['sector']
                    print(f"    【{current_sector}】")
                print(f"      {s['name']}({s['code']}) 综合{s['score']:.0f}分")
        
        # 9. 清理走坏的股票
        removed = self.auto_remove_from_watchlist()
        print(f"\n  降级 {removed} 只走坏的股票")
        
        print("="*60)
        
        return {
            'dip': {'found': len(dip_signals), 'added': dip_added, 'signals': dip_signals[:3]},
            'chase': {'found': len(chase_signals), 'added': chase_added, 'signals': chase_signals[:3]},
            'potential': {'found': len(potential_signals), 'added': potential_added, 'signals': potential_signals[:3]},
            'bottom': {'found': len(bottom_signals), 'added': bottom_added, 'signals': bottom_signals[:3]},
            'multi': {'found': len(multi_signals), 'added': multi_added, 'signals': multi_signals[:3]},
            'consolidation': {'found': len(consolidation_signals), 'added': consolidation_added, 'signals': consolidation_signals[:3]},
            'laggard': {'found': len(laggard_signals), 'added': laggard_added, 'signals': laggard_signals[:3]},
            'value': {'found': len(value_signals), 'added': value_added, 'signals': value_signals[:3]},
            'focus': {'found': len(focus_signals), 'added': focus_added, 'signals': focus_signals[:6]},
            'removed': removed
        }
    
    def scan_consolidation_stocks(self) -> List[Dict]:
        """
        新增策略6: 震荡股票池 - 评分60-64分，今日涨幅-1%~+1%
        特征：
        1. 综合评分60-64分（中等偏上，但未达到优选标准）
        2. 今日涨幅-1%~+1%（震荡整理，未启动）
        3. 基本面尚可（PE<30或ROE>10%）
        4. 等待突破信号（震荡后可能向上突破）
        """
        consolidation = []
        
        try:
            # 扫描热门板块核心标的
            scan_pool = []
            for codes in HOT_SECTOR_CORE.values():
                scan_pool.extend(codes)
            scan_pool = list(set(scan_pool))
            
            stock_data = data_fetcher.get_stock_data(scan_pool[:40])
            analyzer = get_analyzer()
            
            for code in scan_pool[:40]:
                if code not in stock_data:
                    continue
                
                data = stock_data[code]
                change_pct = data.get('change_pct', 0)
                
                # 条件1: 今日震荡（-1%~+1%）
                if -1 <= change_pct <= 1:
                    # 多维度分析
                    result = analyzer.analyze_stock(code)
                    if result and 60 <= result.total_score < 65:
                        consolidation.append({
                            'code': result.code,
                            'name': result.name,
                            'price': result.current_price,
                            'change_pct': change_pct,
                            'score': result.total_score,
                            'trend_score': result.trend_score,
                            'fundamental_score': result.fundamental_score,
                            'reasons': [
                                f"震荡整理{change_pct:+.2f}%",
                                f"综合{result.total_score:.0f}分",
                                f"趋势{result.trend_score:.0f}",
                                "等待突破"
                            ],
                            'strategy': '震荡整理',
                            'time': datetime.now().strftime('%H:%M')
                        })
            
            consolidation.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            print(f"扫描震荡股票失败: {e}")
        
        return consolidation[:10]
    
    def scan_sector_laggards(self) -> List[Dict]:
        """
        新增策略7: 板块补涨机会 - 板块涨但个股没涨
        特征：
        1. 所属板块今日涨幅>1.5%（板块强势）
        2. 个股今日涨幅<0.5%（滞涨）
        3. 个股属于板块核心标的
        4. 有补涨潜力（板块效应会扩散）
        """
        laggards = []
        
        try:
            # 先计算各板块平均涨幅
            sector_performance = {}
            sector_stocks = {}
            
            for sector, codes in HOT_SECTOR_CORE.items():
                stock_data = data_fetcher.get_stock_data(codes)
                total_change = 0
                count = 0
                stocks_info = []
                
                for code in codes:
                    if code in stock_data:
                        change = stock_data[code].get('change_pct', 0)
                        total_change += change
                        count += 1
                        stocks_info.append({
                            'code': code,
                            'name': stock_data[code].get('name', code),
                            'price': stock_data[code].get('current', 0),
                            'change_pct': change
                        })
                
                if count > 0:
                    sector_performance[sector] = total_change / count
                    sector_stocks[sector] = stocks_info
            
            # 找出强势板块中的滞涨个股
            for sector, avg_change in sector_performance.items():
                if avg_change > 1.5:  # 板块强势
                    for stock in sector_stocks[sector]:
                        if stock['change_pct'] < 0.5:  # 个股滞涨
                            laggards.append({
                                'code': stock['code'],
                                'name': stock['name'],
                                'price': stock['price'],
                                'change_pct': stock['change_pct'],
                                'sector_change': avg_change,
                                'sector': sector,
                                'score': int(50 + (avg_change - stock['change_pct']) * 10),
                                'reasons': [
                                    f"板块{avg_change:+.2f}%",
                                    f"个股{stock['change_pct']:+.2f}%",
                                    "补涨潜力",
                                    sector
                                ],
                                'strategy': '板块补涨',
                                'time': datetime.now().strftime('%H:%M')
                            })
            
            laggards.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            print(f"扫描补涨机会失败: {e}")
        
        return laggards[:10]
    
    def scan_fundamental_value(self) -> List[Dict]:
        """
        新增策略8: 基本面价值筛选 - PE<20 + ROE>15%，不管今日涨跌
        特征：
        1. PE<20（低估值）
        2. ROE>15%（优秀盈利能力）
        3. 不关注今日涨跌（价值投资视角）
        4. 适合中长期持有
        """
        value_stocks = []
        
        try:
            # 扫描热门板块中的价值股
            scan_pool = []
            for codes in HOT_SECTOR_CORE.values():
                scan_pool.extend(codes)
            scan_pool = list(set(scan_pool))
            
            stock_data = data_fetcher.get_stock_data(scan_pool[:40])
            analyzer = get_analyzer()
            
            for code in scan_pool[:40]:
                if code not in stock_data:
                    continue
                
                data = stock_data[code]
                change_pct = data.get('change_pct', 0)
                
                # 多维度分析获取基本面数据
                result = analyzer.analyze_stock(code)
                if result:
                    # 从基本面服务获取详细数据
                    from core.fundamental_service import get_fundamental_data
                    fund_data = get_fundamental_data(code)
                    
                    if fund_data:
                        pe = fund_data.get('pe', 999)
                        roe = fund_data.get('roe', 0)
                        
                        # 条件: PE<20 且 ROE>15%
                        if pe < 20 and roe > 15:
                            score = int(60 + (20 - pe) * 2 + (roe - 15))
                            value_stocks.append({
                                'code': code,
                                'name': result.name,
                                'price': result.current_price,
                                'change_pct': change_pct,
                                'pe': pe,
                                'roe': roe,
                                'score': min(score, 90),
                                'reasons': [
                                    f"PE {pe:.1f}",
                                    f"ROE {roe:.1f}%",
                                    f"今日{change_pct:+.2f}%",
                                    "低估值+高盈利"
                                ],
                                'strategy': '基本面价值',
                                'time': datetime.now().strftime('%H:%M')
                            })
            
            value_stocks.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            print(f"扫描价值股失败: {e}")
        
        return value_stocks[:10]
    
    def scan_focus_sectors(self, focus_sectors: List[str] = None) -> List[Dict]:
        """
        新增策略9: 重点关注板块标的筛选
        用户可以指定重点关注的板块，深度扫描其中的优质标的
        
        Args:
            focus_sectors: 重点板块列表，如 ['AI算力', '半导体', '新能源']
        """
        if focus_sectors is None:
            # 默认关注当前热点板块
            focus_sectors = ['AI算力', '半导体', '新能源', '机器人']
        
        focus_stocks = []
        
        try:
            analyzer = get_analyzer()
            
            for sector in focus_sectors:
                if sector not in HOT_SECTOR_CORE:
                    continue
                
                codes = HOT_SECTOR_CORE[sector]
                sector_best = []
                
                for code in codes:
                    result = analyzer.analyze_stock(code)
                    if result and result.total_score >= 55:
                        sector_best.append({
                            'code': result.code,
                            'name': result.name,
                            'price': result.current_price,
                            'change_pct': result.change_pct,
                            'score': result.total_score,
                            'sector': sector,
                            'reasons': [
                                f"重点板块-{sector}",
                                f"综合{result.total_score:.0f}分",
                                result.suggestion[:15]
                            ],
                            'strategy': f'重点-{sector}',
                            'time': datetime.now().strftime('%H:%M')
                        })
                
                # 每个板块取前3
                sector_best.sort(key=lambda x: x['score'], reverse=True)
                focus_stocks.extend(sector_best[:3])
            
            focus_stocks.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            print(f"扫描重点板块失败: {e}")
        
        return focus_stocks[:15]


# 单例
_auto_manager = None

def get_auto_manager() -> AutoWatchlistManager:
    """获取自动管理器单例"""
    global _auto_manager
    if _auto_manager is None:
        _auto_manager = AutoWatchlistManager()
    return _auto_manager


if __name__ == '__main__':
    manager = AutoWatchlistManager()
    result = manager.run_full_scan()
    print("\n扫描结果:", result)
