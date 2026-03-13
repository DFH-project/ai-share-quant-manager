#!/usr/bin/env python3
"""
飞书消息推送工具
"""
import os
import json
import urllib.request
import urllib.parse

def send_feishu_message(message, user_id="ou_ba471bbf9d1107134a390c3befc4dd57"):
    """
    发送消息到飞书
    
    使用OpenClaw的message工具实际推送
    """
    # 构建命令
    cmd = f'openclaw message send --target "{user_id}" --message "{message}"'
    
    # 执行命令
    result = os.system(cmd)
    
    if result == 0:
        print("✅ 消息推送成功")
    else:
        print(f"⚠️ 推送返回码: {result}")
    
    return result == 0


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        message = sys.argv[1]
        send_feishu_message(message)
    else:
        print("用法: python3 feishu_sender.py '消息内容'")
