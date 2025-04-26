#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WeChat Export GUI Configuration
This module provides configuration management for the WeChat Export GUI application.
"""

import os
import json
import logging

# 配置文件的默认路径
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.wechat_exporter')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# 确保配置目录存在
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR, exist_ok=True)

# 默认配置
DEFAULT_CONFIG = {
    "db_dir": "",
    "db_version": 3,
    "output_dir": "./data/",
    "last_export_format": "HTML", 
    "recent_contacts": [],
    "recent_databases": [],
    "decrypt_history": []
}

def load_config():
    """加载配置文件"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 确保配置中包含所有默认值
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            # 如果配置文件不存在，返回默认配置
            return DEFAULT_CONFIG.copy()
    except Exception as e:
        logging.error(f"加载配置文件失败: {str(e)}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logging.error(f"保存配置文件失败: {str(e)}")
        return False

def add_recent_contact(config, contact_wxid):
    """添加最近使用的联系人到配置"""
    if not contact_wxid:
        return config
        
    # 检查是否已经在列表中
    if contact_wxid in config['recent_contacts']:
        # 将其移动到列表开头
        config['recent_contacts'].remove(contact_wxid)
    
    # 添加到列表开头
    config['recent_contacts'].insert(0, contact_wxid)
    
    # 保持列表长度不超过10
    if len(config['recent_contacts']) > 10:
        config['recent_contacts'] = config['recent_contacts'][:10]
    
    return config

def add_recent_database(config, db_dir, db_version):
    """添加最近使用的数据库到配置"""
    if not db_dir:
        return config
        
    # 创建一个包含目录和版本的项
    db_item = {"path": db_dir, "version": db_version}
    
    # 检查是否已经在列表中
    for item in config['recent_databases']:
        if item["path"] == db_dir:
            config['recent_databases'].remove(item)
            break
    
    # 添加到列表开头
    config['recent_databases'].insert(0, db_item)
    
    # 保持列表长度不超过5
    if len(config['recent_databases']) > 5:
        config['recent_databases'] = config['recent_databases'][:5]
    
    return config

def add_decrypt_history(config, wxid, name, db_path, version):
    """添加解密历史记录"""
    if not wxid or not db_path:
        return config
        
    # 创建一个新的解密记录
    decrypt_item = {
        "wxid": wxid,
        "name": name,
        "db_path": db_path,
        "version": version,
        "timestamp": os.path.getmtime(db_path) if os.path.exists(db_path) else 0
    }
    
    # 检查是否已经在列表中
    for i, item in enumerate(config['decrypt_history']):
        if item["wxid"] == wxid:
            config['decrypt_history'][i] = decrypt_item
            return config
    
    # 添加到列表
    config['decrypt_history'].append(decrypt_item)
    
    return config

# 加载初始配置
app_config = load_config() 