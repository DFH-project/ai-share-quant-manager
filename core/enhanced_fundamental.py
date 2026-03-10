#!/usr/bin/env python3
"""
增强版基本面数据服务 - Enhanced Fundamental Service
包含：PE/PB/ROE/营收增长/利润增长/毛利率/负债率/机构持仓/北向资金/研报评级
每晚23:00自动更新缓存
"""

import json
import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# 尝试导入akshare
import akshare as ak

class EnhancedFundamentalService:
    """增强版基本面数据服务"""
    
    def __init__(self):
        self.cache_dir = Path(__file__).parent.parent / 'data' / 'fundamental_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / 'enhanced_fundamental.pkl'
        self.cache_json = self.cache_dir / 'enhanced_fundamental.json'
    
    def _load_cache(self) -> Dict:
        """加载缓存"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
                # 检查缓存时间
                if 'update_time' in cache:
                    update_time = datetime.fromisoformat(cache['update_time'])
                    if (datetime.now() - update_time).days < 1:
                        return cache.get('data', {})
        except Exception as e:
            print(f"[基本面] 加载缓存失败: {e}")
        return {}
    
    def _save_cache(self, data: Dict):
        """保存缓存"""
        try:
            cache = {
                'data': data,
                'update_time': datetime.now().isoformat()
            }
            # 保存pickle格式
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache, f)
            # 同时保存JSON格式便于查看
            with open(self.cache_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"[基本面] 保存缓存失败: {e}")
    
    def get_fundamental_data(self, code: str, force_update: bool = False) -> Optional[Dict]:
        """
        获取完整基本面数据
        优先使用缓存，缓存无效时获取新数据
        """
        # 检查缓存
        if not force_update:
            cache = self._load_cache()
            if code in cache:
                print(f"  [基本面] {code} 使用缓存数据")
                return cache[code]
        
        # 获取新数据
        data = self._fetch_fundamental_data(code)
        if data:
            # 更新缓存
            cache = self._load_cache()
            cache[code] = data
            self._save_cache(cache)
        return data
    
    def _fetch_fundamental_data(self, code: str) -> Optional[Dict]:
        """从多个数据源获取基本面数据"""
        result = {
            'code': code,
            'update_time': datetime.now().isoformat()
        }
        
        try:
            # 1. 获取股票基本信息和财务指标
            print(f"  [基本面] {code} 获取财务指标...")
            
            # 使用akshare获取财务数据
            try:
                # 获取个股信息
                stock_info = ak.stock_individual_info_em(symbol=code)
                if not stock_info.empty:
                    info_dict = dict(zip(stock_info['item'], stock_info['value']))
                    result['name'] = info_dict.get('股票简称', code)
                    result['industry'] = info_dict.get('行业', '')
                    result['total_market_cap'] = info_dict.get('总市值', 0)
                    result['float_market_cap'] = info_dict.get('流通市值', 0)
            except Exception as e:
                print(f"    基本信息获取失败: {e}")
            
            # 2. 获取主要财务指标
            try:
                print(f"  [基本面] {code} 获取主要财务指标...")
                finance = ak.stock_financial_analysis_indicator(symbol=code)
                if not finance.empty:
                    latest = finance.iloc[0]
                    result['roe'] = float(latest.get('净资产收益率(ROE)', 0))
                    result['roa'] = float(latest.get('总资产报酬率(ROA)', 0))
                    result['gross_margin'] = float(latest.get('销售毛利率', 0))
                    result['net_margin'] = float(latest.get('销售净利率', 0))
                    result['debt_ratio'] = float(latest.get('资产负债率', 0))
            except Exception as e:
                print(f"    财务指标获取失败: {e}")
            
            # 3. 获取利润表数据（计算增长）
            try:
                print(f"  [基本面] {code} 获取利润数据...")
                profit = ak.stock_profit_sheet_by_report_em(symbol=code)
                if not profit.empty and len(profit) >= 2:
                    latest = profit.iloc[0]
                    prev = profit.iloc[1]
                    
                    # 营业收入增长
                    latest_revenue = float(latest.get('营业收入', 0))
                    prev_revenue = float(prev.get('营业收入', 0))
                    if prev_revenue > 0:
                        result['revenue_growth'] = (latest_revenue - prev_revenue) / prev_revenue * 100
                    
                    # 净利润增长
                    latest_profit = float(latest.get('净利润', 0))
                    prev_profit = float(prev.get('净利润', 0))
                    if prev_profit > 0:
                        result['profit_growth'] = (latest_profit - prev_profit) / prev_profit * 100
            except Exception as e:
                print(f"    利润数据获取失败: {e}")
            
            # 4. 获取估值数据
            try:
                print(f"  [基本面] {code} 获取估值数据...")
                # 使用实时行情获取PE/PB
                realtime = ak.stock_zh_a_spot_em()
                stock_row = realtime[realtime['代码'] == code]
                if not stock_row.empty:
                    result['pe'] = float(stock_row.iloc[0].get('市盈率-动态', 0))
                    result['pb'] = float(stock_row.iloc[0].get('市净率', 0))
                    result['ps'] = float(stock_row.iloc[0].get('市销率', 0))
            except Exception as e:
                print(f"    估值数据获取失败: {e}")
            
            # 5. 获取机构持仓数据
            try:
                print(f"  [基本面] {code} 获取机构持仓...")
                institutional = ak.stock_institutional_hold_info(symbol=code)
                if not institutional.empty:
                    latest = institutional.iloc[0]
                    result['institutional_hold'] = float(latest.get('机构持仓比例', 0))
                    result['fund_hold'] = float(latest.get('基金持仓比例', 0))
            except Exception as e:
                print(f"    机构持仓获取失败: {e}")
            
            # 6. 获取北向资金数据
            try:
                print(f"  [基本面] {code} 获取北向资金...")
                northbound = ak.stock_hsgt_hist_em(symbol=code)
                if not northbound.empty:
                    latest = northbound.iloc[0]
                    result['northbound_hold'] = float(latest.get('持股数量', 0))
                    result['northbound_ratio'] = float(latest.get('持股占比', 0))
            except Exception as e:
                print(f"    北向资金获取失败: {e}")
            
            # 7. 获取研报评级
            try:
                print(f"  [基本面] {code} 获取研报评级...")
                reports = ak.stock_research_report_em(symbol=code)
                if not reports.empty:
                    result['research_count'] = len(reports)
                    # 统计评级分布
                    ratings = reports['评级'].value_counts().to_dict()
                    result['research_ratings'] = ratings
            except Exception as e:
                print(f"    研报评级获取失败: {e}")
            
            print(f"  [基本面] {code} 获取完成")
            return result
            
        except Exception as e:
            print(f"[基本面] {code} 获取失败: {e}")
            return None
    
    def update_all_cache(self, codes: List[str]):
        """更新所有股票的缓存"""
        print(f"\n{'='*60}")
        print(f"📊 更新基本面数据缓存 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}\n")
        
        cache = {}
        success_count = 0
        
        for i, code in enumerate(codes, 1):
            print(f"[{i}/{len(codes)}] 处理 {code}...")
            data = self._fetch_fundamental_data(code)
            if data:
                cache[code] = data
                success_count += 1
            print()
        
        # 保存缓存
        self._save_cache(cache)
        
        print(f"{'='*60}")
        print(f"✅ 更新完成: {success_count}/{len(codes)} 只股票")
        print(f"{'='*60}\n")
        
        return success_count


# 单例实例
_fundamental_service = None

def get_enhanced_fundamental_service():
    """获取基本面服务单例"""
    global _fundamental_service
    if _fundamental_service is None:
        _fundamental_service = EnhancedFundamentalService()
    return _fundamental_service


def get_fundamental_data(code: str, force_update: bool = False) -> Optional[Dict]:
    """便捷函数：获取基本面数据"""
    service = get_enhanced_fundamental_service()
    return service.get_fundamental_data(code, force_update)


if __name__ == '__main__':
    # 测试
    service = get_enhanced_fundamental_service()
    
    # 测试单只股票
    # data = service.get_fundamental_data('300750', force_update=True)
    # print(json.dumps(data, ensure_ascii=False, indent=2))
    
    # 测试批量更新
    test_codes = ['300750', '002594', '601138', '603127']
    service.update_all_cache(test_codes)
