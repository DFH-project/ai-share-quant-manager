#!/usr/bin/env python3
"""
news_monitor.py - 个股新闻监控模块
功能：
1. 定时轮询自选股新闻
2. 关键词匹配（减持、增持、质押、解禁、业绩、重组等）
3. 发现重要公告立即推送
4. 与现有盘中监控整合
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import akshare as ak
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from core.risk_assessor import RiskAssessor, RiskLevel

# 关键词配置
ALERT_KEYWORDS = {
    '减持': ['减持', '清仓', '套现', '卖出'],
    '增持': ['增持', '回购', '买入'],
    '质押': ['质押', '平仓', '解押'],
    '解禁': ['解禁', '限售', '流通股'],
    '业绩': ['业绩', '预增', '预减', '亏损', '盈利'],
    '重组': ['重组', '并购', '收购', '借壳'],
    '监管': ['立案', '调查', '处罚', '问询', '警示'],
    '停牌': ['停牌', '复牌'],
    '分红': ['分红', '派息', '送转'],
    '高管变动': ['董事长', '总经理', '辞职', '离职']
}

class NewsMonitor:
    """新闻监控器"""
    
    def __init__(self, watchlist_path: str = None):
        if watchlist_path is None:
            base_dir = Path(__file__).parent.parent
            watchlist_path = base_dir / 'data' / 'watchlist_v2.json'
        
        self.watchlist_path = watchlist_path
        self.watchlist = self._load_watchlist()
        
        # 已处理新闻缓存（防止重复提醒）
        self.cache_file = Path(__file__).parent.parent / 'data' / 'news_alert_cache.json'
        self.alerted_news = self._load_alert_cache()
        
        # 风险评估器
        self.risk_assessor = RiskAssessor()
    
    def _load_watchlist(self) -> List[Dict]:
        """加载自选股列表"""
        try:
            with open(self.watchlist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('watchlist', [])
        except Exception as e:
            print(f"加载自选股失败: {e}")
            return []
    
    def _load_alert_cache(self) -> Dict:
        """加载已提醒缓存"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载缓存失败: {e}")
        return {}
    
    def _save_alert_cache(self):
        """保存提醒缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.alerted_news, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败: {e}")
    
    def _check_keywords(self, title: str, content: str = '') -> List[str]:
        """检查标题和内容中的关键词"""
        text = f"{title} {content}".lower()
        matched_categories = []
        
        for category, keywords in ALERT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    matched_categories.append(category)
                    break
        
        return matched_categories
    
    def _is_news_alerted(self, code: str, news_id: str) -> bool:
        """检查新闻是否已经提醒过"""
        key = f"{code}_{news_id}"
        return key in self.alerted_news
    
    def _mark_news_alerted(self, code: str, news_id: str):
        """标记新闻已提醒"""
        key = f"{code}_{news_id}"
        self.alerted_news[key] = {
            'alert_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'code': code
        }
    
    def fetch_stock_news(self, code: str, limit: int = 20) -> List[Dict]:
        """获取个股新闻"""
        try:
            df = ak.stock_news_em(symbol=code)
            if df is None or len(df) == 0:
                return []
            
            # 只取最近24小时的新闻
            cutoff_time = datetime.now() - timedelta(hours=24)
            recent_news = []
            
            for _, row in df.head(limit).iterrows():
                try:
                    pub_time = datetime.strptime(row['发布时间'], '%Y-%m-%d %H:%M:%S')
                    if pub_time >= cutoff_time:
                        recent_news.append({
                            'code': code,
                            'title': row['新闻标题'],
                            'content': row.get('新闻内容', '')[:200],
                            'pub_time': row['发布时间'],
                            'source': row.get('文章来源', '东方财富'),
                            'link': row.get('新闻链接', ''),
                            'news_id': f"{code}_{pub_time.strftime('%Y%m%d%H%M%S')}"
                        })
                except:
                    continue
            
            return recent_news
        except Exception as e:
            print(f"获取 {code} 新闻失败: {e}")
            return []
    
    def scan_all_stocks(self) -> List[Dict]:
        """扫描所有自选股新闻"""
        alerts = []
        
        print(f"\n🔍 开始扫描 {len(self.watchlist)} 只自选股新闻...")
        print("-" * 60)
        
        for item in self.watchlist:
            code = item.get('code')
            name = item.get('name', code)
            
            if not code:
                continue
            
            # 获取新闻
            news_list = self.fetch_stock_news(code)
            
            for news in news_list:
                # 检查是否已经提醒过
                if self._is_news_alerted(code, news['news_id']):
                    continue
                
                # 关键词匹配
                categories = self._check_keywords(news['title'], news['content'])
                
                if categories:
                    alert = {
                        'code': code,
                        'name': name,
                        'title': news['title'],
                        'pub_time': news['pub_time'],
                        'categories': categories,
                        'source': news['source'],
                        'link': news['link'],
                        'priority': 'HIGH' if '减持' in categories or '监管' in categories else 'MEDIUM'
                    }
                    alerts.append(alert)
                    
                    # 标记已提醒
                    self._mark_news_alerted(code, news['news_id'])
                    
                    # 打印
                    emoji = "🚨" if alert['priority'] == 'HIGH' else "⚠️"
                    print(f"{emoji} [{name}({code})] {', '.join(categories)}")
                    print(f"   📰 {news['title'][:60]}...")
                    print(f"   ⏰ {news['pub_time']}")
                    print()
        
        # 保存缓存
        self._save_alert_cache()
        
        return alerts
    
    def generate_alert_report(self, alerts: List[Dict]) -> str:
        """生成带风险评估的提醒报告"""
        if not alerts:
            return "📰 新闻监控：未发现重要公告（最近24小时）"
        
        report = []
        report.append("\n" + "=" * 70)
        report.append("🚨 个股新闻监控警报")
        report.append("=" * 70)
        report.append(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"发现 {len(alerts)} 条重要新闻\n")
        
        # 对所有警报进行风险评估
        critical_alerts = []
        high_alerts = []
        medium_alerts = []
        low_alerts = []
        
        for alert in alerts:
            # 进行风险评估
            assessment = self.risk_assessor.assess_news(alert['title'], alert['categories'])
            alert['assessment'] = assessment
            
            # 按风险等级分类
            if assessment.level == RiskLevel.CRITICAL:
                critical_alerts.append(alert)
            elif assessment.level == RiskLevel.HIGH:
                high_alerts.append(alert)
            elif assessment.level == RiskLevel.MEDIUM:
                medium_alerts.append(alert)
            else:
                low_alerts.append(alert)
        
        # 生成详细报告
        if critical_alerts:
            report.append("\n" + "🔴" * 20)
            report.append("【极高风险 - 必须立即行动】")
            report.append("🔴" * 20)
            for alert in critical_alerts:
                report.append(self.risk_assessor.format_alert(
                    alert['code'], alert['name'], alert['title'],
                    alert['categories'], alert['pub_time']
                ))
        
        if high_alerts:
            report.append("\n" + "🟠" * 20)
            report.append("【高风险 - 建议24小时内处理】")
            report.append("🟠" * 20)
            for alert in high_alerts:
                report.append(self.risk_assessor.format_alert(
                    alert['code'], alert['name'], alert['title'],
                    alert['categories'], alert['pub_time']
                ))
        
        if medium_alerts:
            report.append("\n" + "🟡" * 20)
            report.append("【中等风险 - 需要关注】")
            report.append("🟡" * 20)
            for alert in medium_alerts:
                report.append(self.risk_assessor.format_alert(
                    alert['code'], alert['name'], alert['title'],
                    alert['categories'], alert['pub_time']
                ))
        
        if low_alerts:
            report.append("\n" + "ℹ️" * 20)
            report.append("【低风险/信息 - 仅供参考】")
            report.append("ℹ️" * 20)
            for alert in low_alerts:
                report.append(self.risk_assessor.format_alert(
                    alert['code'], alert['name'], alert['title'],
                    alert['categories'], alert['pub_time']
                ))
        
        report.append("\n" + "=" * 70)
        
        return '\n'.join(report)


def main():
    """主函数"""
    monitor = NewsMonitor()
    alerts = monitor.scan_all_stocks()
    report = monitor.generate_alert_report(alerts)
    print(report)
    
    # 如果有高优先级警报，建议发送飞书通知
    high_alerts = [a for a in alerts if a['priority'] == 'HIGH']
    if high_alerts:
        print(f"\n⚠️ 发现 {len(high_alerts)} 条高优先级新闻，建议立即关注！")
        return 1  # 返回非0表示有重要警报
    
    return 0


if __name__ == '__main__':
    exit(main())
