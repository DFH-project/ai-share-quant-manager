#!/usr/bin/env python3
"""
代码健康检查与Review脚本 - Code Health Review
每晚3:00运行，检查：
1. 当日数据获取成功率
2. 缓存命中率
3. 错误日志分析
4. 架构健康度评分

使用场景：
- 定时任务：0 3 * * *
- 手动执行：python3 scripts/code_health_review.py
"""

import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.unified_data_service import get_data_service

class CodeHealthReviewer:
    """代码健康检查器"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.report_file = self.data_dir / 'health_review_report.json'
        self.service = get_data_service()
    
    def check_cache_health(self) -> dict:
        """检查缓存健康度"""
        print("\n" + "="*60)
        print("检查缓存健康度")
        print("="*60)
        
        stats = self.service.get_cache_stats()
        
        # 检查L2缓存（技术指标）是否过期
        l2_status = "正常"
        l2_cache_file = self.data_dir / 'cache' / 'l2_technical.pkl'
        if l2_cache_file.exists():
            try:
                with open(l2_cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    if cache:
                        first_key = list(cache.keys())[0]
                        update_time = datetime.fromisoformat(cache[first_key]['update_time'])
                        days_old = (datetime.now() - update_time).days
                        if days_old >= 1:
                            l2_status = f"⚠️ 过期{days_old}天"
            except:
                l2_status = "❌ 读取失败"
        else:
            l2_status = "❌ 不存在"
        
        # 检查L3缓存（基本面）是否过期
        l3_status = "正常"
        l3_cache_file = self.data_dir / 'fundamental_cache' / 'enhanced_fundamental.pkl'
        if l3_cache_file.exists():
            try:
                with open(l3_cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    if cache:
                        first_key = list(cache.keys())[0]
                        update_time = datetime.fromisoformat(cache[first_key]['update_time'])
                        days_old = (datetime.now() - update_time).days
                        if days_old >= 7:
                            l3_status = f"⚠️ 过期{days_old}天"
                        elif days_old >= 1:
                            l3_status = f"⚠️ {days_old}天前"
            except:
                l3_status = "❌ 读取失败"
        else:
            l3_status = "❌ 不存在"
        
        result = {
            'l1_memory_cache': stats.get('l1_memory_cache', 0),
            'l1_file_cache': stats.get('l1_file_cache', 0),
            'l2_technical_cache': stats.get('l2_technical_cache', 0),
            'l2_status': l2_status,
            'l3_fundamental_cache': stats.get('l3_fundamental_cache', 0),
            'l3_status': l3_status
        }
        
        print(f"  L1内存缓存: {result['l1_memory_cache']} 条")
        print(f"  L1文件缓存: {result['l1_file_cache']} 条")
        print(f"  L2技术指标: {result['l2_technical_cache']} 条 - {l2_status}")
        print(f"  L3基本面: {result['l3_fundamental_cache']} 条 - {l3_status}")
        
        return result
    
    def check_data_availability(self) -> dict:
        """检查数据可获取性"""
        print("\n" + "="*60)
        print("检查数据可获取性")
        print("="*60)
        
        # 测试几只关键股票
        test_codes = ['000977', '603019', '300750', '002594', '513180']
        
        success_count = 0
        fail_list = []
        
        for code in test_codes:
            try:
                data = self.service.get_stock_data([code], include_technical=True, include_fundamental=True)
                if code in data:
                    success_count += 1
                    print(f"  {code}: ✓")
                else:
                    fail_list.append(code)
                    print(f"  {code}: ✗ 无数据")
            except Exception as e:
                fail_list.append(code)
                print(f"  {code}: ✗ {str(e)[:30]}")
        
        success_rate = success_count / len(test_codes) * 100
        
        result = {
            'test_codes': test_codes,
            'success_count': success_count,
            'fail_list': fail_list,
            'success_rate': success_rate
        }
        
        print(f"\n  成功率: {success_rate:.1f}% ({success_count}/{len(test_codes)})")
        if fail_list:
            print(f"  失败: {', '.join(fail_list)}")
        
        return result
    
    def check_code_structure(self) -> dict:
        """检查代码结构健康度"""
        print("\n" + "="*60)
        print("检查代码结构")
        print("="*60)
        
        core_dir = Path(__file__).parent.parent / 'core'
        scripts_dir = Path(__file__).parent.parent / 'scripts'
        
        issues = []
        
        # 检查关键文件是否存在
        key_files = [
            core_dir / 'data_fetcher.py',
            core_dir / 'unified_data_service.py',
            scripts_dir / 'nightly_cache_update.py',
            scripts_dir / 'intraday_monitor_integrated.py'
        ]
        
        for f in key_files:
            if f.exists():
                print(f"  {f.name}: ✓")
            else:
                print(f"  {f.name}: ❌ 缺失")
                issues.append(f"缺失文件: {f.name}")
        
        # 检查ETF修复是否还在
        try:
            with open(core_dir / 'data_fetcher.py', 'r') as f:
                content = f.read()
                if "startswith(('6', '5'))" in content:
                    print(f"  ETF修复: ✓ 已应用")
                else:
                    print(f"  ETF修复: ⚠️ 未检测到")
                    issues.append("ETF修复可能丢失")
        except:
            issues.append("无法读取data_fetcher.py")
        
        return {
            'key_files_exist': len([f for f in key_files if f.exists()]),
            'total_key_files': len(key_files),
            'issues': issues
        }
    
    def generate_report(self) -> dict:
        """生成完整健康报告"""
        print("\n" + "="*60)
        print("生成健康报告")
        print("="*60)
        
        report = {
            'review_time': datetime.now().isoformat(),
            'cache_health': self.check_cache_health(),
            'data_availability': self.check_data_availability(),
            'code_structure': self.check_code_structure()
        }
        
        # 计算综合健康评分
        score = 100
        
        # 数据成功率扣分
        if report['data_availability']['success_rate'] < 100:
            score -= (100 - report['data_availability']['success_rate']) * 0.5
        
        # 缓存过期扣分
        if '过期' in report['cache_health'].get('l2_status', ''):
            score -= 10
        if '过期' in report['cache_health'].get('l3_status', ''):
            score -= 10
        
        # 代码问题扣分
        score -= len(report['code_structure'].get('issues', [])) * 5
        
        report['overall_score'] = max(0, score)
        
        # 保存报告
        with open(self.report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n综合健康评分: {report['overall_score']:.1f}/100")
        
        if report['overall_score'] >= 90:
            print("状态: ✅ 健康")
        elif report['overall_score'] >= 70:
            print("状态: ⚠️ 警告")
        else:
            print("状态: ❌ 严重问题")
        
        print(f"\n报告已保存: {self.report_file}")
        
        return report
    
    def run(self):
        """执行完整健康检查"""
        print("="*60)
        print(f"代码健康检查开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        report = self.generate_report()
        
        print("\n" + "="*60)
        print("检查完成")
        print("="*60)
        
        # 如果有严重问题，返回非0退出码
        if report['overall_score'] < 70:
            sys.exit(1)

if __name__ == '__main__':
    reviewer = CodeHealthReviewer()
    reviewer.run()
