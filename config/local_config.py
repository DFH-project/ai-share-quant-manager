"""
local_config.py - 本地配置管理器
加载隐私配置，不提交到git
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

class LocalConfig:
    """本地配置管理器（隐私配置）"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """加载本地配置文件"""
        config_path = BASE_DIR / "config" / "config.local.yaml"
        template_path = BASE_DIR / "config" / "config.local.template.yaml"
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            # 如果本地配置不存在，使用模板
            if template_path.exists():
                with open(template_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            else:
                self._config = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项，支持点号路径
        例如: get('user.id') 或 get('trading.stop_loss_pct')
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_user_id(self) -> str:
        """获取用户ID"""
        return self.get('user.id', '')
    
    def get_user_name(self) -> str:
        """获取用户名"""
        return self.get('user.name', '')
    
    def get_data_dir(self) -> Path:
        """获取数据目录"""
        custom_path = self.get('paths.data_dir', '')
        if custom_path:
            return Path(custom_path)
        return BASE_DIR / "data"
    
    def get_cache_dir(self) -> Path:
        """获取缓存目录"""
        custom_path = self.get('paths.cache_dir', '')
        if custom_path:
            return Path(custom_path)
        return self.get_data_dir() / "cache"
    
    def get_log_dir(self) -> Path:
        """获取日志目录"""
        custom_path = self.get('paths.log_dir', '')
        if custom_path:
            return Path(custom_path)
        return self.get_data_dir() / "logs"
    
    def get_trading_config(self) -> Dict[str, Any]:
        """获取交易配置"""
        return self.get('trading', {})
    
    def get_monitor_config(self) -> Dict[str, Any]:
        """获取监控配置"""
        return self.get('monitor', {})
    
    def is_notification_enabled(self) -> bool:
        """检查通知是否启用"""
        return self.get('notifications.enabled', False)
    
    def get_notification_channels(self) -> list:
        """获取通知渠道"""
        return self.get('notifications.channels', [])

# 全局单例
_local_config = None

def get_local_config() -> LocalConfig:
    """获取本地配置单例"""
    global _local_config
    if _local_config is None:
        _local_config = LocalConfig()
    return _local_config

# 便捷函数
def local_cfg(key: str, default: Any = None) -> Any:
    """快速获取本地配置"""
    return get_local_config().get(key, default)
