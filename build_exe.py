#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WeChat Exporter打包工具
用于将Python应用打包成可执行文件
支持--onefile(单文件)和--onedir(文件夹)两种模式
"""

import os
import sys
import shutil
import platform
import subprocess
import argparse
import glob
import zipfile
from pathlib import Path
import logging
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('build_exe')

# 确定是否在虚拟环境中运行
in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def check_venv_type():
    """检查虚拟环境类型"""
    venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
    
    if not os.path.exists(venv_path):
        logger.warning(f"未找到虚拟环境目录: {venv_path}")
        return "none"
    
    # 检查是标准venv还是uv环境
    if os.path.exists(os.path.join(venv_path, "Scripts", "activate.bat")):
        logger.info("检测到标准venv环境")
        return "venv"
    elif os.path.exists(os.path.join(venv_path, "Scripts", "python.exe")):
        logger.info("检测到uv管理的环境")
        return "uv"
    else:
        logger.warning("未能确定虚拟环境类型")
        return "unknown"

def check_pyinstaller():
    """检查PyInstaller是否已安装"""
    try:
        import PyInstaller
        logger.info(f"检测到PyInstaller版本: {PyInstaller.__version__}")
        return True
    except ImportError:
        logger.error("未找到PyInstaller，请先安装: pip install pyinstaller")
        logger.info("正在尝试安装PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        return False

def clean_build_dir():
    """清理之前的构建文件"""
    logger.info("清理之前的构建文件...")
    dirs_to_clean = ['build', 'dist']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            logger.info(f"删除目录: {dir_name}")
            shutil.rmtree(dir_name, ignore_errors=True)
    
    # 删除spec文件
    for spec_file in glob.glob("*.spec"):
        logger.info(f"删除spec文件: {spec_file}")
        os.remove(spec_file)

def check_upx():
    """检查UPX是否可用"""
    # 首先检查是否有本地的UPX目录
    upx_paths = ["upx", "./upx", "./tools/upx"]
    for path in upx_paths:
        if os.path.exists(path) and os.path.isdir(path):
            upx_exe = os.path.join(path, "upx.exe" if sys.platform == "win32" else "upx")
            if os.path.exists(upx_exe):
                logger.info(f"找到本地UPX: {upx_exe}")
                return upx_exe
    
    # 其次检查PATH中是否有UPX
    try:
        result = subprocess.run(
            ["upx", "--version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            shell=True
        )
        if result.returncode == 0:
            logger.info("在系统PATH中找到UPX")
            return "upx"
    except:
        pass
    
    logger.warning("未找到UPX，将不使用UPX压缩")
    logger.info("如果需要使用UPX压缩，请从 https://github.com/upx/upx/releases 下载并安装")
    return None

def collect_dlls():
    """确保_temp_dlls目录存在并包含DLL文件"""
    dll_dir = "_temp_dlls"
    
    if not os.path.exists(dll_dir):
        os.makedirs(dll_dir)
    
    if not os.listdir(dll_dir):
        if sys.platform == "win32":
            if os.path.exists("collect_dlls.bat"):
                logger.info("运行collect_dlls.bat收集DLL文件...")
                subprocess.run(["collect_dlls.bat"], shell=True)
                if not os.listdir(dll_dir):
                    logger.warning(f"DLL收集完成，但{dll_dir}目录仍为空")
            else:
                logger.warning("未找到collect_dlls.bat脚本，跳过DLL收集")
        else:
            logger.info("非Windows平台，跳过DLL收集")
        
    return dll_dir

def create_version_info(args):
    """创建版本信息文件"""
    version_file = "file_version_info.txt"
    version = args.version if hasattr(args, 'version') and args.version else "1.0.0"
    
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(f"""
# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=({','.join(version.split('.')+['0']*(4-len(version.split('.'))))}),
    prodvers=({','.join(version.split('.')+['0']*(4-len(version.split('.'))))}),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x40004,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'080404b0',
        [StringStruct(u'CompanyName', u'WeChatExporter'),
        StringStruct(u'FileDescription', u'WeChat聊天记录导出工具'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'WeChatExporter'),
        StringStruct(u'LegalCopyright', u'© 2021-2024 WeChatExporter'),
        StringStruct(u'OriginalFilename', u'WeChatExporter.exe'),
        StringStruct(u'ProductName', u'WeChat聊天记录导出工具'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
        """)
    return version_file

def build_executable(args):
    """构建可执行文件"""
    # 检查PyInstaller是否已安装
    if not check_pyinstaller():
        sys.exit(1)
    
    # 清理先前的构建文件
    if args.clean:
        clean_build_dir()
    
    # 确保DLL目录存在
    dll_dir = collect_dlls()
    
    # 创建目录
    os.makedirs("dist", exist_ok=True)
    
    # 检查UPX
    upx_path = check_upx() if args.upx else None
    
    # 创建版本信息文件
    version_file = create_version_info(args)
    
    # 设置图标
    icon_path = args.icon if args.icon and os.path.exists(args.icon) else None
    if not icon_path:
        for icon in ["icons/app.ico", "resources/icons/app.ico", "app.ico"]:
            if os.path.exists(icon):
                icon_path = icon
                break
    
    # 确定入口文件
    entry_point = args.entry
    if not os.path.exists(entry_point):
        logger.error(f"入口文件不存在: {entry_point}")
        sys.exit(1)
    
    # 构建命令
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
    ]
    
    # 选择单文件或目录模式
    if args.onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    
    # Windows下添加不显示控制台窗口的选项
    if sys.platform == "win32" and not args.debug:
        cmd.append("--windowed")
    
    # 添加图标
    if icon_path:
        cmd.extend(["--icon", icon_path])
    
    # 添加版本信息文件
    if os.path.exists(version_file):
        cmd.extend(["--version-file", version_file])
    
    # 添加UPX设置
    if upx_path:
        cmd.extend(["--upx-dir", os.path.dirname(upx_path) if os.path.dirname(upx_path) else "."])
    
    # 设置输出文件名
    output_name = args.name if args.name else "WeChatExporter"
    cmd.extend(["--name", output_name])
    
    # 排除不需要的模块
    excluded_modules = [
        "matplotlib", "numpy", "scipy", "pandas", "PyQt5", "PySide2", "PySide6", "PyQt6",
        "IPython", "ipykernel", "jupyter", "notebook", "pytest", "sphinx", "streamlit",
        "cv2", "bokeh", "seaborn", "plotly", "sympy", "tensorflow", "torch", "torchvision",
        "sklearn", "scikit-learn", "spacy", "nltk", "gensim", "keras", "theano", "caffe",
        "openpyxl", "pydot", "networkx", "xml"
    ]
    for module in excluded_modules:
        cmd.extend(["--exclude-module", module])
    
    # 确保包含需要的包
    included_packages = [
        "tkinter", "tkcalendar", "PIL", "Crypto"
    ]
    for package in included_packages:
        try:
            __import__(package)
            logger.info(f"包含包: {package}")
        except ImportError:
            logger.warning(f"未找到包: {package}，可能会导致打包问题")
    
    # 添加数据文件
    data_files = []
    
    # 添加DLL文件
    if os.path.exists(dll_dir) and os.listdir(dll_dir):
        data_files.append((f"{dll_dir}/*", "."))
    
    # 添加资源文件
    for res_dir in ["resources", "icons", "assets"]:
        if os.path.exists(res_dir):
            data_files.append((f"{res_dir}/*", res_dir))
    
    # 添加数据文件到命令
    for src, dst in data_files:
        files = glob.glob(src, recursive=True)
        if files:
            logger.info(f"添加数据文件: {src} -> {dst}")
            cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
    
    # 添加入口文件
    cmd.append(entry_point)
    
    # 执行命令
    logger.info(f"执行命令: {' '.join(cmd)}")
    start_time = time.time()
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        logger.error("构建失败!")
        sys.exit(1)
    
    # 检查构建结果
    output_file = f"dist/{output_name}.exe" if sys.platform == "win32" else f"dist/{output_name}"
    if args.onedir:
        output_file = f"dist/{output_name}"
        if not os.path.exists(output_file):
            logger.error(f"未找到构建结果: {output_file}")
            sys.exit(1)
    else:
        if not os.path.exists(output_file):
            logger.error(f"未找到构建结果: {output_file}")
            sys.exit(1)
    
    # 清理版本信息文件
    if os.path.exists(version_file):
        os.remove(version_file)
    
    # 计算构建时间
    build_time = time.time() - start_time
    logger.info(f"构建完成，耗时: {build_time:.2f}秒")
    
    # 显示文件大小
    if os.path.isfile(output_file):
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        logger.info(f"生成的文件: {output_file} (大小: {size_mb:.2f} MB)")
    else:
        logger.info(f"生成的目录: {output_file}")
    
    # 创建启动批处理文件
    if args.onedir and sys.platform == "win32":
        batch_file = f"dist/{output_name}.bat"
        with open(batch_file, "w") as f:
            f.write(f"@echo off\ncd /d \"%~dp0{output_name}\"\n{output_name}.exe\n")
        logger.info(f"创建启动批处理文件: {batch_file}")
    
    return output_file

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="构建WeChat聊天记录导出工具的可执行文件")
    parser.add_argument("--clean", action="store_true", help="清理之前的构建文件")
    parser.add_argument("--onefile", action="store_true", help="构建单文件可执行文件")
    parser.add_argument("--onedir", action="store_true", help="构建目录结构可执行文件")
    parser.add_argument("--debug", action="store_true", help="构建调试版本(保留控制台)")
    parser.add_argument("--name", type=str, default="WeChatExporter", help="输出文件名")
    parser.add_argument("--icon", type=str, help="自定义图标路径")
    parser.add_argument("--upx", action="store_true", help="使用UPX压缩可执行文件")
    parser.add_argument("--version", type=str, default="1.0.0", help="应用版本号")
    parser.add_argument("--entry", type=str, default="run_wechat_export.py", help="入口文件")
    
    args = parser.parse_args()
    
    # 默认为目录结构
    if not args.onefile and not args.onedir:
        args.onedir = True
    
    logger.info(f"开始构建WeChat聊天记录导出工具...")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"平台: {platform.platform()}")
    logger.info(f"虚拟环境: {'是' if in_venv else '否'}")
    
    # 检查虚拟环境类型
    venv_type = check_venv_type()
    logger.info(f"虚拟环境类型: {venv_type}")
    
    output_file = build_executable(args)
    
    logger.info(f"构建成功! 输出文件: {output_file}")
    logger.info("感谢使用WeChat聊天记录导出工具")

if __name__ == "__main__":
    main()