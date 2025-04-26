#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
自动收集和分析Python环境中的DLL依赖
"""

import os
import sys
import shutil
import glob
import platform
import subprocess
import site
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('collect_dlls')

def collect_dlls_from_path(search_path, dest_dir, pattern="*.dll"):
    """从指定路径收集DLL文件到目标目录"""
    count = 0
    if not os.path.exists(search_path):
        return count
    
    files = glob.glob(os.path.join(search_path, pattern))
    for file in files:
        dest = os.path.join(dest_dir, os.path.basename(file))
        try:
            if not os.path.exists(dest):
                shutil.copy2(file, dest)
                logger.info(f"复制: {file} -> {dest}")
                count += 1
        except Exception as e:
            logger.warning(f"复制文件 {file} 失败: {e}")
    
    return count

def get_package_directories():
    """获取所有可能包含DLL的包目录"""
    directories = []
    
    # 基础Python目录
    python_dir = os.path.dirname(sys.executable)
    directories.append(python_dir)
    
    # DLLs目录
    dll_dir = os.path.join(python_dir, "DLLs")
    if os.path.exists(dll_dir):
        directories.append(dll_dir)
    
    # 标准库目录
    lib_dir = os.path.join(python_dir, "Lib")
    if os.path.exists(lib_dir):
        directories.append(lib_dir)
    
    # 虚拟环境基础目录
    base_dir = sys.base_prefix
    if base_dir != python_dir:
        directories.append(base_dir)
        base_dll_dir = os.path.join(base_dir, "DLLs")
        if os.path.exists(base_dll_dir):
            directories.append(base_dll_dir)
    
    # site-packages目录
    try:
        site_packages = site.getsitepackages()
        directories.extend(site_packages)
    except Exception as e:
        logger.warning(f"获取site-packages目录失败: {e}")
    
    # 检查常见的Conda目录
    for conda_dir in [
        os.path.join(sys.base_prefix, "Library", "bin"),
        os.path.join(sys.base_prefix, "Library", "lib"),
        os.path.join(python_dir, "Library", "bin"),
        os.path.join(python_dir, "Library", "lib")
    ]:
        if os.path.exists(conda_dir):
            directories.append(conda_dir)
    
    # 用户目录
    user_site = site.getusersitepackages() if hasattr(site, 'getusersitepackages') else None
    if user_site and os.path.exists(user_site):
        directories.append(user_site)
    
    return directories

def find_package_location(package_name):
    """查找指定包的安装位置"""
    try:
        package = __import__(package_name)
        return os.path.dirname(package.__file__)
    except ImportError:
        return None
    except Exception as e:
        logger.warning(f"查找包 {package_name} 位置失败: {e}")
        return None

def main():
    """收集所有必要的DLL文件到_temp_dlls目录"""
    start_time = import_time = os.path.getmtime(__file__) if os.path.exists(__file__) else 0
    
    # 创建临时目录
    temp_dll_dir = "_temp_dlls"
    if not os.path.exists(temp_dll_dir):
        os.makedirs(temp_dll_dir)
    
    logger.info(f"Python可执行文件: {sys.executable}")
    logger.info(f"Python版本: {platform.python_version()}")
    logger.info(f"系统平台: {platform.platform()}")
    
    # 获取Python目录
    python_dir = os.path.dirname(sys.executable)
    logger.info(f"Python目录: {python_dir}")
    
    # 获取所有可能包含DLL的目录
    search_dirs = get_package_directories()
    
    logger.info("\n找到的库目录:")
    for lib_dir in search_dirs:
        logger.info(f"- {lib_dir}")
    
    # 重要的包和对应的DLL/PYD文件
    critical_packages = {
        "tkinter": ["_tkinter.pyd", "tcl*.dll", "tk*.dll"],
        "tkcalendar": ["tkcalendar"],
        "sqlite3": ["_sqlite3.pyd", "sqlite3.dll"],
        "ssl": ["_ssl.pyd", "libssl*.dll", "libcrypto*.dll"],
        "ctypes": ["_ctypes.pyd", "libffi*.dll"],
        "lzma": ["_lzma.pyd", "liblzma*.dll"],
        "bz2": ["_bz2.pyd", "libbz2*.dll"],
        "crypto": ["Crypto", "pycryptodome", "cryptography"],
        "pillow": ["PIL", "PIL._imaging"],
        "protobuf": ["google.protobuf"]
    }
    
    # 关键DLL文件列表 (正则匹配模式)
    critical_dlls = [
        "libexpat*.dll", "pyexpat*.pyd", 
        "sqlite3*.dll", "_sqlite3*.pyd",
        "libssl*.dll", "libcrypto*.dll", "_ssl*.pyd", "_hashlib*.pyd",
        "liblzma*.dll", "_lzma*.pyd",
        "libbz2*.dll", "_bz2*.pyd",
        "libffi*.dll", "_ctypes*.pyd",
        "tcl*.dll", "tk*.dll", "_tkinter*.pyd",
        "vcruntime*.dll", "msvcp*.dll", "concrt*.dll",
        "libgcc*.dll", "libstdc++*.dll", "libwinpthread*.dll",
        "python*.dll", "msvcr*.dll",
        "zlib*.dll", "_queue*.pyd", "_socket*.pyd",
        "_decimal*.pyd", "_multiprocessing*.pyd", "_overlapped*.pyd",
        "_asyncio*.pyd", "unicodedata*.pyd", "select*.pyd"
    ]
    
    # 统计
    total_copied = 0
    
    # 从Python目录复制DLL
    logger.info("\n从Python主目录复制DLL:")
    total_copied += collect_dlls_from_path(python_dir, temp_dll_dir)
    
    # 从各个可能的目录复制DLL/PYD文件
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
        
        logger.info(f"\n从 {search_dir} 复制DLL/PYD:")
        total_copied += collect_dlls_from_path(search_dir, temp_dll_dir, "*.dll")
        total_copied += collect_dlls_from_path(search_dir, temp_dll_dir, "*.pyd")
    
    # 检查关键包的位置
    logger.info("\n检查关键包位置:")
    for package_name, dlls in critical_packages.items():
        package_dir = find_package_location(package_name)
        if package_dir:
            logger.info(f"✓ 找到 {package_name} 在 {package_dir}")
            
            # 复制该包目录下的DLL和PYD文件
            for pattern in ["*.dll", "*.pyd"]:
                collected = collect_dlls_from_path(package_dir, temp_dll_dir, pattern)
                if collected > 0:
                    logger.info(f"  从 {package_name} 复制了 {collected} 个文件")
                    total_copied += collected
            
            # 遍历子目录
            for root, dirs, files in os.walk(package_dir):
                for pattern in ["*.dll", "*.pyd"]:
                    file_paths = glob.glob(os.path.join(root, pattern))
                    for file_path in file_paths:
                        dest = os.path.join(temp_dll_dir, os.path.basename(file_path))
                        if not os.path.exists(dest):
                            try:
                                shutil.copy2(file_path, dest)
                                logger.info(f"  复制: {file_path} -> {dest}")
                                total_copied += 1
                            except Exception as e:
                                logger.warning(f"  复制文件 {file_path} 失败: {e}")
        else:
            logger.warning(f"✗ 未找到 {package_name}")
    
    # 特殊处理Crypto模块
    crypto_packages = ["Crypto", "pycryptodome", "cryptography"]
    for package_name in crypto_packages:
        package_dir = find_package_location(package_name)
        if package_dir:
            logger.info(f"\n处理 {package_name} 模块目录: {package_dir}")
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    if file.endswith(".dll") or file.endswith(".pyd"):
                        source = os.path.join(root, file)
                        dest = os.path.join(temp_dll_dir, file)
                        if not os.path.exists(dest):
                            try:
                                shutil.copy2(source, dest)
                                logger.info(f"复制文件: {source} -> {dest}")
                                total_copied += 1
                            except Exception as e:
                                logger.warning(f"复制文件 {source} 失败: {e}")
    
    # 检查是否缺少关键DLL
    logger.info("\n检查关键DLL文件:")
    missing_dlls = []
    for critical in critical_dlls:
        found = False
        pattern = critical.replace("*", "")  # 简化匹配模式
        for file in os.listdir(temp_dll_dir):
            if pattern.lower() in file.lower():
                found = True
                logger.info(f"✓ 找到 {critical} ({file})")
                break
        if not found:
            missing_dlls.append(critical)
            logger.warning(f"✗ 缺少 {critical}")
    
    # 统计收集的文件
    dll_count = len(glob.glob(os.path.join(temp_dll_dir, "*.dll")))
    pyd_count = len(glob.glob(os.path.join(temp_dll_dir, "*.pyd")))
    
    logger.info(f"\n收集完成! 共复制了 {dll_count} 个DLL文件和 {pyd_count} 个PYD文件到 {temp_dll_dir} 目录")
    
    # 提供构建指导
    logger.info("\n构建指导:")
    if missing_dlls:
        logger.warning(f"存在 {len(missing_dlls)} 个缺失的关键DLL文件:")
        for dll in missing_dlls:
            logger.warning(f"  - {dll}")
        logger.info("\n尝试以下步骤:")
        logger.info("1. 确保安装了所有必要的依赖: pip install -r requirements.txt")
        logger.info("2. 考虑使用--onedir模式构建，这可能会更成功")
        logger.info("   python build_exe.py --clean --onedir")
    else:
        logger.info("✓ 所有关键DLL文件都已找到，可以尝试构建应用程序")
        logger.info("建议使用以下命令:")
        logger.info("python build_exe.py --clean --onedir")
    
    # 生成批处理文件来运行此脚本
    batch_file = "collect_dlls.bat"
    with open(batch_file, "w") as f:
        f.write(f"""@echo off
echo 正在收集DLL文件...
"{sys.executable}" "{os.path.abspath(__file__)}"
echo 完成!
pause
""")
    
    logger.info(f"\n生成批处理文件: {batch_file}")
    
    # 将_temp_dlls目录添加到环境变量PATH
    logger.info("\n将_temp_dlls目录添加到PATH环境变量")
    path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.path.abspath(temp_dll_dir) + os.pathsep + path
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 