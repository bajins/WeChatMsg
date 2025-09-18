#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WeChat Export GUI Configuration
This module provides configuration management for the WeChat Export GUI application.
"""

import os
import json
import logging
import ctypes
from ctypes import wintypes

# 配置文件的默认路径
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.wechat_exporter')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# 确保配置目录存在
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR, exist_ok=True)

def get_documents_path():
    """
    获取 Windows 系统的“文档”文件夹路径
    """
    # CSIDL https://learn.microsoft.com/zh-cn/windows/win32/shell/csidl
    CSIDL_PERSONAL = 5       # 文档文件夹
    SHGFP_TYPE_CURRENT = 0   # 获取当前路径
    # CSIDL_DESKTOP=0x0000 # 桌面
    # CSIDL_PERSONAL=0x0005 # 我的文档
    # CSIDL_APPDATA=0x001A # Roaming AppData
    # CSIDL_LOCAL_APPDATA=0x001C # Local AppData
    # CSIDL_WINDOWS=0x0024 # Windows 目录
    # CSIDL_SYSTEM=0x0025 # System32
    # CSIDL_PROGRAM_FILES=0x0026 # Program Files
    # CSIDL_PROGRAM_FILESX86=0x002A # Program Files (x86)

    # KNOWNFOLDERID https://learn.microsoft.com/zh-cn/windows/win32/shell/knownfolderid
    # https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath
    # FOLDERID_Desktop=uuid.UUID("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}") # 桌面
    # FOLDERID_Documents=uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}") # 文档
    # FOLDERID_Downloads=uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}") # 下载
    # FOLDERID_Pictures=uuid.UUID("{33E28130-4E1E-4676-835A-98395C3BC3BB}") # 图片
    # FOLDERID_Music=uuid.UUID("{4BD8D571-6D19-48D3-BE97-422220080E43}") # 音乐
    # FOLDERID_Videos=uuid.UUID("{18989B1D-99B5-455B-841C-AB7C74E4DDFC}") # 视频
    # FOLDERID_RoamingAppData=uuid.UUID("{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}") # %APPDATA%
    # FOLDERID_LocalAppData=uuid.UUID("{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}") # %LOCALAPPDATA%
    # FOLDERID_ProgramFiles=uuid.UUID("{905E63B6-C1BF-494E-B29C-65B732D3D21A}") # C:\Program Files
    # FOLDERID_ProgramFilesX86=uuid.UUID("{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}") # C:\Program Files (x86)

    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)

    return buf.value


# 默认配置
DEFAULT_CONFIG = {
    "db_dir": os.path.join(get_documents_path(), "WeChat Files"),
    "db_version": 3,
    "output_dir": "./data/",
    "last_export_format": "HTML", 
    "recent_contacts": [],
    "recent_databases": [],
    "decrypt_history": []
}

def is_empty(v):
    return v is None or (hasattr(v, '__len__') and len(v) == 0)

def merge_dicts_deep(target, source):
    result = {}
    keys = set(target) | set(source)
    for k in keys:
        tv = target.get(k)
        sv = source.get(k)
        if isinstance(tv, dict) and isinstance(sv, dict):
            result[k] = merge_dicts_deep(tv, sv)
        elif sv is not None and not is_empty(sv) and (k not in target or is_empty(tv)):
            result[k] = sv
        else:
            result[k] = tv if k in target else sv
    return result

def load_config():
    """加载配置文件"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 确保配置中包含所有默认值
                # for key, value in DEFAULT_CONFIG.items():
                #     if key not in config:
                #         config[key] = value
                result = merge_dicts_deep(DEFAULT_CONFIG, config)
                return result
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