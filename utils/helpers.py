"""
utils/helpers.py - 工具函数
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any


def format_number(num: float, decimals: int = 2) -> str:
    """格式化数字"""
    if num is None:
        return "N/A"
    return f"{num:,.{decimals}f}"


def format_percent(num: float, decimals: int = 2) -> str:
    """格式化百分比"""
    if num is None:
        return "N/A"
    return f"{num:.{decimals}f}%"


def format_date(date_str: str, input_fmt: str = "%Y-%m-%d", output_fmt: str = "%Y年%m月%d日") -> str:
    """格式化日期"""
    try:
        dt = datetime.strptime(date_str, input_fmt)
        return dt.strftime(output_fmt)
    except:
        return date_str


def get_trading_days(start_date: str, end_date: str) -> List[str]:
    """获取交易日列表（简化版，实际应该使用交易日历）"""
    trading_days = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    current = start
    while current <= end:
        # 跳过周末
        if current.weekday() < 5:
            trading_days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    return trading_days


def calculate_position_size(capital: float, price: float, 
                            max_position_pct: float = 0.1) -> int:
    """计算仓位大小"""
    max_amount = capital * max_position_pct
    quantity = int(max_amount / price / 100) * 100  # 按手计算
    return max(quantity, 0)


def save_json(data: Any, filepath: str) -> bool:
    """保存JSON文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存JSON失败: {e}")
        return False


def load_json(filepath: str) -> Any:
    """加载JSON文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON失败: {e}")
        return None


def print_table(headers: List[str], rows: List[List[Any]], 
                col_widths: List[int] = None) -> None:
    """打印表格"""
    if not rows:
        print("无数据")
        return
    
    # 自动计算列宽
    if col_widths is None:
        col_widths = []
        for i in range(len(headers)):
            max_width = len(str(headers[i]))
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, len(str(row[i])))
            col_widths.append(max_width + 2)
    
    # 打印表头
    header_line = ""
    for i, h in enumerate(headers):
        header_line += f"{str(h):<{col_widths[i]}}"
    print(header_line)
    print("-" * sum(col_widths))
    
    # 打印数据
    for row in rows:
        row_line = ""
        for i, cell in enumerate(row):
            if i < len(col_widths):
                row_line += f"{str(cell):<{col_widths[i]}}"
        print(row_line)
