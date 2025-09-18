#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
使用Nuitka打包WeChatExporter为可执行文件
Nuitka通常能生成比PyInstaller更小更快的可执行文件
"""

import os
import sys
import subprocess
import shutil
import argparse
from wxManager.log import logger

def main():
    parser = argparse.ArgumentParser(description="使用Nuitka构建WeChat导出工具")
    parser.add_argument('--clean', action='store_true', help="清理之前的构建文件")
    parser.add_argument('--no-console', action='store_true', help="不显示控制台窗口")
    args = parser.parse_args()
    
    # 检查Nuitka是否已安装
    try:
        # 使用subprocess查询版本，而不是直接导入
        result = subprocess.run([sys.executable, "-m", "pip", "show", "nuitka"], 
                          capture_output=True, text=True)
        if "Version:" in result.stdout:
            version = result.stdout.split("Version:")[1].split("\n")[0].strip()
            logger.info("Nuitka已安装，版本:", version)
        else:
            raise ImportError("找不到Nuitka信息")
    except Exception:
        logger.info("未找到Nuitka，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "nuitka"])
    
    # 清理之前的构建
    if args.clean:
        logger.info("清理之前的构建文件...")
        build_dirs = [
            "run_wechat_export.build",
            "run_wechat_export.dist",
            "run_wechat_export.onefile-build"
        ]
        for dir_path in build_dirs:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
        
        # 清理可执行文件
        if os.path.exists("WeChatExporter.exe"):
            os.remove("WeChatExporter.exe")
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",  # 创建独立可执行文件
        "--onefile",  # 打包成单个文件
        "--include-package=wxManager",  # 包含wxManager包
        "--include-package=exporter",  # 包含exporter包
        "--include-data-dir=wxManager=wxManager",  # 添加数据目录
        "--include-data-dir=exporter=exporter",  # 添加数据目录
        "--include-data-files=config.py=config.py",  # 包含配置文件
        "--output-dir=.",  # 输出到当前目录
        "--output-filename=WeChatExporter.exe",  # 指定输出文件名
        "--disable-console-reports",  # 禁用控制台报告
        "--remove-output",  # 移除临时输出
        "--assume-yes-for-downloads",  # 自动下载依赖项
        "--plugin-enable=tk-inter",  # 启用tkinter插件
        "--include-module=PIL",  # 包含PIL模块
        "--include-module=tkcalendar",  # 包含tkcalendar模块
    ]
    
    # 图标设置
    if os.path.exists("resources/icon.ico"):
        cmd.append(f"--windows-icon-from-ico=resources/icon.ico")
    
    # 窗口模式设置
    if args.no_console:
        cmd.append("--windows-disable-console")
    
    # 添加主程序
    cmd.append("run_wechat_export.py")
    
    # 执行构建
    logger.info("开始构建...")
    logger.info(" ".join(cmd))
    subprocess.check_call(cmd)
    
    logger.info("\n构建完成! 可执行文件位于 WeChatExporter.exe")

if __name__ == "__main__":
    main() 