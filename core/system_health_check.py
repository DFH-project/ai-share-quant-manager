#!/usr/bin/env python3
"""
system_health_check.py - 系统健康检查模块
功能：
1. 检查各模块运行状态
2. 检查数据文件完整性
3. 检查API可用性
4. 生成健康报告
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import subprocess


class SystemHealthChecker:
    """系统健康检查器"""
    
    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        
        self.base_dir = base_dir
        self.data_dir = base_dir / 'data'
        self.scripts_dir = base_dir / 'scripts'
        self.core_dir = base_dir / 'core'
        
        self.check_results = []
    
    def check_file_exists(self, file_path: Path, description: str) -> Dict:
        """检查文件是否存在"""
        exists = file_path.exists()
        result = {
            'check': f'文件检查: {description}',
            'status': '✅ 正常' if exists else '❌ 缺失',
            'path': str(file_path),
            'critical': False
        }
        self.check_results.append(result)
        return result
    
    def check_critical_files(self) -> List[Dict]:
        """检查关键文件"""
        critical_files = [
            (self.data_dir / 'watchlist_v2.json', '自选股列表'),
            (self.core_dir / 'watchlist_memory_v2.py', '持仓记忆模块'),
            (self.core_dir / 'data_fetcher.py', '数据获取模块'),
            (self.core_dir / 'risk_assessor.py', '风险评估模块'),
            (self.scripts_dir / 'news_monitor.py', '新闻监控脚本'),
            (self.scripts_dir / 'integrated_monitor.py', '整合监控脚本'),
        ]
        
        results = []
        for file_path, desc in critical_files:
            result = self.check_file_exists(file_path, desc)
            result['critical'] = True
            results.append(result)
        
        return results
    
    def check_data_freshness(self) -> Dict:
        """检查数据新鲜度"""
        try:
            watchlist_file = self.data_dir / 'watchlist_v2.json'
            if not watchlist_file.exists():
                result = {
                    'check': '数据新鲜度',
                    'status': '❌ 无法检查',
                    'message': '自选股文件不存在',
                    'critical': True
                }
            else:
                mtime = datetime.fromtimestamp(watchlist_file.stat().st_mtime)
                age = datetime.now() - mtime
                
                if age < timedelta(hours=1):
                    status = '✅ 正常'
                elif age < timedelta(days=1):
                    status = '⚠️ 较旧'
                else:
                    status = '❌ 过期'
                
                result = {
                    'check': '数据新鲜度',
                    'status': status,
                    'last_update': mtime.strftime('%Y-%m-%d %H:%M:%S'),
                    'age_hours': age.total_seconds() / 3600,
                    'critical': age > timedelta(days=7)
                }
            
            self.check_results.append(result)
            return result
            
        except Exception as e:
            result = {
                'check': '数据新鲜度',
                'status': '❌ 检查失败',
                'error': str(e),
                'critical': True
            }
            self.check_results.append(result)
            return result
    
    def check_api_availability(self) -> Dict:
        """检查API可用性"""
        try:
            # 尝试导入akshare并获取数据
            import akshare as ak
            
            # 获取一只测试股票的数据
            test_code = '000001'  # 平安银行
            df = ak.stock_zh_a_hist(symbol=test_code, period="daily", start_date=None, end_date=None, adjust="qfq")
            
            if df is not None and len(df) > 0:
                result = {
                    'check': '数据API可用性',
                    'status': '✅ 正常',
                    'message': f'成功获取{test_code}数据，{len(df)}条记录',
                    'critical': False
                }
            else:
                result = {
                    'check': '数据API可用性',
                    'status': '❌ 异常',
                    'message': '获取数据为空',
                    'critical': True
                }
                
        except Exception as e:
            result = {
                'check': '数据API可用性',
                'status': '❌ 失败',
                'error': str(e),
                'critical': True
            }
        
        self.check_results.append(result)
        return result
    
    def check_news_api(self) -> Dict:
        """检查新闻API"""
        try:
            import akshare as ak
            
            # 尝试获取新闻
            news_df = ak.stock_news_em(symbol='000001')
            
            if news_df is not None:
                result = {
                    'check': '新闻API可用性',
                    'status': '✅ 正常',
                    'message': f'成功获取新闻，{len(news_df)}条记录',
                    'critical': False
                }
            else:
                result = {
                    'check': '新闻API可用性',
                    'status': '❌ 异常',
                    'message': '获取新闻为空',
                    'critical': True
                }
                
        except Exception as e:
            result = {
                'check': '新闻API可用性',
                'status': '❌ 失败',
                'error': str(e),
                'critical': True
            }
        
        self.check_results.append(result)
        return result
    
    def check_cron_jobs(self) -> Dict:
        """检查定时任务状态"""
        try:
            # 这里假设可以通过某种方式获取cron状态
            # 实际实现可能需要调用openclaw API
            result = {
                'check': '定时任务状态',
                'status': '⚠️ 需手动检查',
                'message': '运行: openclaw cron list 查看任务状态',
                'critical': False
            }
        except Exception as e:
            result = {
                'check': '定时任务状态',
                'status': '❌ 检查失败',
                'error': str(e),
                'critical': False
            }
        
        self.check_results.append(result)
        return result
    
    def check_disk_space(self) -> Dict:
        """检查磁盘空间"""
        try:
            import shutil
            stat = shutil.disk_usage(self.base_dir)
            
            free_gb = stat.free / (1024**3)
            total_gb = stat.total / (1024**3)
            used_pct = (stat.used / stat.total) * 100
            
            if free_gb > 10:
                status = '✅ 正常'
            elif free_gb > 5:
                status = '⚠️ 空间紧张'
            else:
                status = '❌ 空间不足'
            
            result = {
                'check': '磁盘空间',
                'status': status,
                'free_gb': round(free_gb, 2),
                'total_gb': round(total_gb, 2),
                'used_percent': round(used_pct, 1),
                'critical': free_gb < 1
            }
            
        except Exception as e:
            result = {
                'check': '磁盘空间',
                'status': '❌ 检查失败',
                'error': str(e),
                'critical': False
            }
        
        self.check_results.append(result)
        return result
    
    def run_all_checks(self) -> Dict:
        """运行所有检查"""
        self.check_results = []
        
        print("🔍 开始系统健康检查...")
        print("=" * 70)
        
        # 关键文件检查
        self.check_critical_files()
        
        # 数据新鲜度
        self.check_data_freshness()
        
        # API可用性
        self.check_api_availability()
        self.check_news_api()
        
        # 定时任务
        self.check_cron_jobs()
        
        # 磁盘空间
        self.check_disk_space()
        
        # 汇总
        critical_issues = [r for r in self.check_results if r.get('critical') and '❌' in r['status']]
        warnings = [r for r in self.check_results if '⚠️' in r['status']]
        
        summary = {
            'total_checks': len(self.check_results),
            'passed': len([r for r in self.check_results if '✅' in r['status']]),
            'warnings': len(warnings),
            'critical_issues': len(critical_issues),
            'overall_status': '❌ 严重问题' if critical_issues else '⚠️ 有警告' if warnings else '✅ 健康'
        }
        
        return {
            'summary': summary,
            'details': self.check_results,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def generate_report(self, results: Dict) -> str:
        """生成健康报告"""
        report = []
        report.append("\n" + "=" * 70)
        report.append("🩺 系统健康检查报告")
        report.append("=" * 70)
        report.append(f"检查时间: {results['timestamp']}")
        report.append(f"总体状态: {results['summary']['overall_status']}")
        report.append("")
        
        summary = results['summary']
        report.append(f"📊 检查结果汇总:")
        report.append(f"   总检查项: {summary['total_checks']}")
        report.append(f"   ✅ 通过: {summary['passed']}")
        report.append(f"   ⚠️ 警告: {summary['warnings']}")
        report.append(f"   ❌ 严重问题: {summary['critical_issues']}")
        report.append("")
        
        # 详细结果
        report.append("📋 详细检查结果:")
        report.append("-" * 70)
        
        for result in results['details']:
            report.append(f"\n{result['check']}")
            report.append(f"   状态: {result['status']}")
            
            if 'path' in result:
                report.append(f"   路径: {result['path']}")
            if 'message' in result:
                report.append(f"   信息: {result['message']}")
            if 'error' in result:
                report.append(f"   错误: {result['error']}")
            if 'free_gb' in result:
                report.append(f"   空间: {result['free_gb']}GB / {result['total_gb']}GB (已用{result['used_percent']}%)")
        
        report.append("\n" + "=" * 70)
        
        # 如果有严重问题，给出建议
        if summary['critical_issues'] > 0:
            report.append("\n🚨 严重问题及修复建议:")
            report.append("-" * 70)
            for r in results['details']:
                if r.get('critical') and '❌' in r['status']:
                    report.append(f"\n• {r['check']}")
                    if '文件检查' in r['check']:
                        report.append("  建议: 检查文件路径，重新初始化系统")
                    elif 'API' in r['check']:
                        report.append("  建议: 检查网络连接，确认AKShare版本")
                    elif '数据新鲜度' in r['check']:
                        report.append("  建议: 运行数据更新脚本")
        
        report.append("\n" + "=" * 70)
        
        return '\n'.join(report)


def main():
    """主函数"""
    checker = SystemHealthChecker()
    results = checker.run_all_checks()
    report = checker.generate_report(results)
    print(report)
    
    # 返回码：0=健康，1=有警告，2=严重问题
    if results['summary']['critical_issues'] > 0:
        return 2
    elif results['summary']['warnings'] > 0:
        return 1
    else:
        return 0


if __name__ == '__main__':
    exit(main())
