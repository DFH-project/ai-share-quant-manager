"""
data_fetcher_v2.py - 数据获取模块V2
使用AKShare获取A股真实数据
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Union
import json
import os


class DataFetcherV2:
    """A股数据获取器 - 使用AKShare获取真实市场数据"""
    
    def __init__(self, cache_dir: str = "./data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
    def get_stock_list(self) -> pd.DataFrame:
        """获取A股所有股票列表"""
        try:
            # 使用AKShare获取上海和深圳股票列表
            sh_df = ak.stock_sh_a_spot_em()
            sz_df = ak.stock_sz_a_spot_em()
            
            # 合并两个市场的数据
            all_stocks = pd.concat([sh_df, sz_df], ignore_index=True)
            
            # 标准化列名
            if '代码' in all_stocks.columns and '名称' in all_stocks.columns:
                all_stocks = all_stocks.rename(columns={
                    '代码': 'code',
                    '名称': 'name',
                    '最新价': 'price',
                    '涨跌幅': 'change_pct',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '总市值': 'market_cap',
                    '市盈率': 'pe',
                    '市净率': 'pb'
                })
            
            return all_stocks
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def get_stock_name(self, code: str) -> str:
        """根据股票代码获取股票名称"""
        try:
            stock_list = self.get_stock_list()
            if not stock_list.empty:
                stock = stock_list[stock_list['code'] == code]
                if not stock.empty:
                    return stock.iloc[0]['name']
            return code
        except Exception as e:
            print(f"获取股票名称失败: {e}")
            return code
    
    def get_daily_data(self, code: str, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """获取股票日线数据"""
        try:
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            if end_date is None:
                end_date = datetime.now().strftime('%Y%m%d')
            
            # 使用AKShare获取历史行情数据
            df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                    start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df is not None and not df.empty:
                # 标准化列名
                df = df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '振幅': 'amplitude',
                    '涨跌幅': 'change_pct',
                    '涨跌额': 'change',
                    '换手率': 'turnover'
                })
                df['code'] = code
                df['name'] = self.get_stock_name(code)
            
            return df
        except Exception as e:
            print(f"获取股票{code}日线数据失败: {e}")
            return pd.DataFrame()
    
    def get_realtime_data(self, code: str) -> Dict:
        """获取股票实时数据"""
        try:
            df = ak.stock_zh_a_spot_em()
            stock = df[df['代码'] == code]
            if not stock.empty:
                return {
                    'code': code,
                    'name': stock.iloc[0]['名称'],
                    'price': stock.iloc[0]['最新价'],
                    'change_pct': stock.iloc[0]['涨跌幅'],
                    'volume': stock.iloc[0]['成交量'],
                    'amount': stock.iloc[0]['成交额'],
                    'high': stock.iloc[0]['最高'],
                    'low': stock.iloc[0]['最低'],
                    'open': stock.iloc[0]['今开'],
                    'prev_close': stock.iloc[0]['昨收'],
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            return {}
        except Exception as e:
            print(f"获取股票{code}实时数据失败: {e}")
            return {}
    
    def get_multiple_realtime(self, codes: List[str]) -> pd.DataFrame:
        """获取多只股票实时数据"""
        try:
            df = ak.stock_zh_a_spot_em()
            filtered = df[df['代码'].isin(codes)]
            return filtered.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_pct',
                '成交量': 'volume',
                '成交额': 'amount'
            })
        except Exception as e:
            print(f"获取多只股票实时数据失败: {e}")
            return pd.DataFrame()
    
    def get_index_data(self, index_code: str = "000001") -> pd.DataFrame:
        """获取指数数据"""
        try:
            if index_code == "000001":  # 上证指数
                df = ak.index_zh_a_hist(symbol="000001", period="daily")
            elif index_code == "399001":  # 深证成指
                df = ak.index_zh_a_hist(symbol="399001", period="daily")
            elif index_code == "399006":  # 创业板指
                df = ak.index_zh_a_hist(symbol="399006", period="daily")
            else:
                df = ak.index_zh_a_hist(symbol=index_code, period="daily")
            
            return df
        except Exception as e:
            print(f"获取指数{index_code}数据失败: {e}")
            return pd.DataFrame()
    
    def get_fundamental_data(self, code: str) -> Dict:
        """获取股票基本面数据"""
        try:
            # 获取个股信息
            df = ak.stock_individual_info_em(symbol=code)
            if df is not None and not df.empty:
                info = dict(zip(df['item'], df['value']))
                return {
                    'code': code,
                    'name': info.get('股票简称', ''),
                    'industry': info.get('行业', ''),
                    'market_cap': info.get('总市值', ''),
                    'pe': info.get('市盈率', ''),
                    'pb': info.get('市净率', ''),
                    'roe': info.get('净资产收益率', ''),
                    'total_shares': info.get('总股本', '')
                }
            return {}
        except Exception as e:
            print(f"获取股票{code}基本面数据失败: {e}")
            return {}
    
    def get_concept_boards(self) -> pd.DataFrame:
        """获取概念板块列表"""
        try:
            df = ak.stock_board_concept_name_em()
            return df
        except Exception as e:
            print(f"获取概念板块失败: {e}")
            return pd.DataFrame()
    
    def get_industry_boards(self) -> pd.DataFrame:
        """获取行业板块列表"""
        try:
            df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            print(f"获取行业板块失败: {e}")
            return pd.DataFrame()
    
    def get_realtime_quote(self, symbol: str) -> Dict:
        """获取个股实时行情（兼容接口）"""
        return self.get_realtime_data(symbol)
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息（兼容接口）"""
        return self.get_fundamental_data(symbol)
    
    def search_stock(self, keyword: str) -> List[Dict]:
        """搜索股票"""
        try:
            df = self.get_stock_list()
            if df.empty:
                return []
            
            # 按代码或名称搜索
            matches = df[
                df['code'].str.contains(keyword, na=False) |
                df['name'].str.contains(keyword, na=False)
            ]
            
            return matches.head(10).rename(columns={
                'code': '代码',
                'name': '名称',
                'price': '最新价',
                'change_pct': '涨跌幅'
            }).to_dict('records')
        except Exception as e:
            print(f"[ERROR] 搜索股票失败: {e}")
            return []
    
    def get_market_overview(self) -> Dict:
        """获取市场概览"""
        try:
            df = ak.stock_zh_a_spot_em()
            if df.empty:
                return {}
            
            # 计算市场统计
            up_count = len(df[df['涨跌幅'] > 0])
            down_count = len(df[df['涨跌幅'] < 0])
            flat_count = len(df[df['涨跌幅'] == 0])
            
            return {
                'total_stocks': len(df),
                'up_count': up_count,
                'down_count': down_count,
                'flat_count': flat_count,
                'limit_up_count': len(df[df['涨跌幅'] >= 9.5]),
                'limit_down_count': len(df[df['涨跌幅'] <= -9.5]),
                'avg_change': df['涨跌幅'].mean(),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            print(f"[ERROR] 获取市场概览失败: {e}")
            return {}


# 单例模式
_data_fetcher = None

def get_data_fetcher() -> DataFetcherV2:
    """获取数据获取器单例"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcherV2()
    return _data_fetcher
