#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WeChat导出工具启动程序
"""

import os
import sys
import tkinter as tk
from multiprocessing import freeze_support

def setup_environment():
    """设置运行环境"""
    # 获取程序所在目录
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件
        application_path = os.path.dirname(sys.executable)
    else:
        # 如果是源代码运行
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    # 设置工作目录
    os.chdir(application_path)
    
    # 确保配置目录存在
    config_dir = os.path.join(os.path.expanduser('~'), '.wechat_exporter')
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    # 添加当前目录到路径，确保能找到模块
    if application_path not in sys.path:
        sys.path.insert(0, application_path)
    
    # 检查并处理虚拟环境
    try:
        # 忽略pyvenv.cfg检查错误
        import venv
        original_cfg_fn = getattr(venv, '_detect_venv_by_cfg_file', None)
        if original_cfg_fn:
            def patched_cfg_fn(*args, **kwargs):
                try:
                    return original_cfg_fn(*args, **kwargs)
                except Exception:
                    return None
            venv._detect_venv_by_cfg_file = patched_cfg_fn
    except ImportError:
        pass

def main():
    """主函数"""
    # 处理多进程问题（Windows平台需要）
    freeze_support()
    
    # 设置环境
    setup_environment()
    
    try:
        # 导入界面主类
        from wechat_export_gui import WeChatExportGUI
        
        # 创建主窗口
        root = tk.Tk()
        root.title("微信记录导出工具")
        
        # 应用图标
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception:
            pass  # 忽略图标加载错误
        
        # 创建应用
        app = WeChatExportGUI(root)
        
        # 运行主循环
        root.mainloop()
        
    except Exception as e:
        import traceback
        error_msg = f"程序启动时出错:\n{str(e)}\n\n{traceback.format_exc()}"
        
        # 显示错误对话框
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            import tkinter.messagebox as messagebox
            messagebox.showerror("启动错误", error_msg)
        except Exception:
            # 如果连错误对话框都无法显示，打印到控制台
            logger.info(error_msg)
        
        # 返回错误代码
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
