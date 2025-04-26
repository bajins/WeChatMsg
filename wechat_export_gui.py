#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WeChat Export GUI Application
This application provides a graphical user interface for exporting WeChat records.
It integrates the three main steps from the examples folder:
1. Decrypt database
2. Connect to database and get contact information
3. Export records based on contacts
"""

import os
import sys
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import scrolledtext
import traceback
import importlib.util
import subprocess
from PIL import Image, ImageTk
import io

# Add the parent directory to the path to import the required modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Check for required packages
required_packages = [
    ('Crypto', 'pycryptodome', 'Crypto.Protocol.KDF'),
    ('google', 'google', 'google'),
    ('protobuf', 'protobuf', 'google.protobuf'),
    ('PIL', 'pillow', 'PIL'),
    ('tkcalendar', 'tkcalendar', 'tkcalendar'),
]

missing_packages = []
for package_name, pip_name, import_path in required_packages:
    try:
        # Try to import the module
        module_name = import_path.split('.')[0]
        if importlib.util.find_spec(module_name) is None:
            missing_packages.append((package_name, pip_name))
    except ImportError:
        missing_packages.append((package_name, pip_name))

# If there are missing packages, show a message and exit
if missing_packages:
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    message = "缺少以下必要的依赖包:\n\n"
    for package_name, pip_name in missing_packages:
        message += f"- {package_name} (安装命令: pip install {pip_name})\n"
    message += "\n请安装这些包后再运行程序。"

    messagebox.showerror("缺少依赖", message)

    # Ask if the user wants to install the packages automatically
    if messagebox.askyesno("自动安装", "是否要自动安装这些依赖包?"):
        try:
            for _, pip_name in missing_packages:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            messagebox.showinfo("安装完成", "依赖包已安装完成，请重新启动程序。")
        except Exception as e:
            messagebox.showerror("安装失败", f"安装依赖包时出错: {str(e)}")

    sys.exit(1)

# Import required modules
from multiprocessing import freeze_support
from wxManager import Me, DatabaseConnection, MessageType
from wxManager.decrypt import get_info_v4, get_info_v3
from wxManager.decrypt.decrypt_dat import get_decode_code_v4
from wxManager.decrypt import decrypt_v4, decrypt_v3
from exporter.config import FileType
from exporter import (
    HtmlExporter, TxtExporter, AiTxtExporter,
    DocxExporter, MarkdownExporter, ExcelExporter
)


class WeChatExportGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("微信记录导出工具")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)

        # 导入配置模块
        try:
            import config
            self.config = config.load_config()
        except ImportError:
            # 如果配置模块不存在，使用默认值
            self.config = {
                "db_dir": "",
                "db_version": 3,
                "output_dir": "./data/",
                "last_export_format": "HTML",
                "recent_contacts": [],
                "recent_databases": []
            }
            self.log_message_console("未找到配置模块，使用默认配置")

        # Create custom styles
        self.create_custom_styles()

        # Create variables
        self.db_dir = tk.StringVar()
        self.db_version = tk.IntVar(value=self.config.get("db_version", 3))
        self.output_dir = tk.StringVar(value=self.config.get("output_dir", "./data/"))
        self.selected_wxid = tk.StringVar()
        self.search_text = tk.StringVar()
        self.search_text.trace("w", self.filter_contacts)

        # 如果配置中有数据库目录，设置它
        if self.config.get("db_dir"):
            self.db_dir.set(self.config.get("db_dir"))

        # Create main notebook (tabbed interface)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建只有两个主要标签页的新界面
        self.create_contacts_tab()  # 联系人管理 (主界面)
        self.create_settings_tab()  # 设置

        # Initialize database connection and other variables
        self.database = None
        self.contacts = []
        self.filtered_contacts = []
        self.load_button = None

        # Status bar
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 如果配置中有数据库目录，自动尝试连接
        if self.config.get("db_dir") and os.path.exists(self.config.get("db_dir")):
            self.root.after(1000, lambda: self.auto_connect_database())

        # 初始化联系人头像缓存
        self.contact_avatar_cache = {}

    def create_custom_styles(self):
        """Create custom styles for widgets"""
        style = ttk.Style()

        # Create a custom style for accent buttons
        style.configure(
            "Accent.TButton",
            font=("Helvetica", 10, "bold"),
            background="#4CAF50",
            foreground="#ffffff"
        )

        # Create a custom style for disabled buttons
        style.configure(
            "Disabled.TButton",
            font=("Helvetica", 10),
            background="#cccccc",
            foreground="#888888"
        )
        
        # 创建微信风格的样式
        style.configure(
            "WeChat.TLabelframe",
            background="#f5f5f5",
            borderwidth=0
        )
        
        style.configure(
            "WeChat.TFrame",
            background="#f5f5f5"
        )
        
        style.configure(
            "WeChat.TLabel",
            background="#f5f5f5",
            font=("微软雅黑", 9)
        )
        
        style.configure(
            "WeChat.Search.TEntry",
            fieldbackground="#e6e6e6",
            bordercolor="#e6e6e6",
            lightcolor="#e6e6e6",
            darkcolor="#e6e6e6",
            borderwidth=1
        )
        
        style.configure(
            "WeChat.Contacts.TFrame",
            background="#ffffff"
        )
        
        # 自定义联系人项目样式
        style.configure(
            "Contact.TFrame",
            background="#ffffff"
        )
        
        style.configure(
            "Contact.TLabel",
            background="#ffffff",
            font=("微软雅黑", 9)
        )
        
        # 联系人悬停效果样式
        style.configure(
            "ContactHover.TFrame",
            background="#f0f0f0"
        )
        
        style.configure(
            "ContactHover.TLabel",
            background="#f0f0f0",
            font=("微软雅黑", 9)
        )

        # 微信绿色按钮样式，确保文字颜色能清晰显示
        style.configure(
            "WeChat.TButton",
            background="#07c160",
            foreground="#000000",  # 白色文字
            font=("微软雅黑", 9, "bold"),  # 加粗字体增加可读性
            padding=(10, 5)  # 增加内边距
        )

        # 映射按钮的不同状态效果
        style.map(
            "WeChat.TButton",
            background=[("active", "#06ae56"), ("!active", "#07c160")],  # 活动状态稍暗
            foreground=[("active", "#000000"), ("!active", "#000000")],
            relief=[("pressed", "sunken"), ("!pressed", "raised")]  # 按下时凹陷效果
        )

    def create_decrypt_tab(self):
        """Create the database decryption tab"""
        decrypt_tab = ttk.Frame(self.notebook)
        self.notebook.add(decrypt_tab, text="1. 解密数据库")

        # WeChat version selection
        version_frame = ttk.LabelFrame(decrypt_tab, text="微信版本")
        version_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Radiobutton(version_frame, text="微信 3.x", variable=self.db_version, value=3).pack(side=tk.LEFT, padx=20, pady=10)
        ttk.Radiobutton(version_frame, text="微信 4.0", variable=self.db_version, value=4).pack(side=tk.LEFT, padx=20, pady=10)

        # Decrypt button
        decrypt_button = ttk.Button(decrypt_tab, text="开始解密", command=self.start_decrypt)
        decrypt_button.pack(pady=20)

        # Log area
        log_frame = ttk.LabelFrame(decrypt_tab, text="日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.decrypt_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.decrypt_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.decrypt_log.config(state=tk.DISABLED)

    def create_contacts_tab(self):
        """Create the contacts management tab"""
        contacts_tab = ttk.Frame(self.notebook, style="WeChat.TFrame")
        self.notebook.add(contacts_tab, text="联系人管理")

        # 创建左右分栏的布局
        paned_window = ttk.PanedWindow(contacts_tab, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # 左侧面板 - 数据库设置和联系人列表
        left_panel = ttk.Frame(paned_window, style="WeChat.TFrame")
        paned_window.add(left_panel, weight=2)
        
        # 右侧面板 - 联系人详情和导出功能
        right_panel = ttk.Frame(paned_window, style="WeChat.TFrame")
        paned_window.add(right_panel, weight=3)

        # 数据库设置区域
        db_frame = ttk.LabelFrame(left_panel, text="数据库设置", style="WeChat.TLabelframe")
        db_frame.pack(fill=tk.X, padx=10, pady=10)

        # 数据库目录选择
        ttk.Label(db_frame, text="数据库目录:", style="WeChat.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(db_frame, textvariable=self.db_dir, width=30).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        ttk.Button(db_frame, text="浏览...", command=self.browse_db_dir).grid(row=0, column=2, padx=5, pady=5)

        # 数据库版本选择
        version_frame = ttk.Frame(db_frame, style="WeChat.TFrame")
        version_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W+tk.E)
        
        ttk.Label(version_frame, text="数据库版本:", style="WeChat.TLabel").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(version_frame, text="微信 3.x", variable=self.db_version, value=3).pack(side=tk.LEFT, padx=15)
        ttk.Radiobutton(version_frame, text="微信 4.0", variable=self.db_version, value=4).pack(side=tk.LEFT, padx=15)

        # 按钮区域
        button_frame = ttk.Frame(db_frame, style="WeChat.TFrame")
        button_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=10)
        
        self.load_status_var = tk.StringVar(value="")
        load_status_label = ttk.Label(button_frame, textvariable=self.load_status_var, foreground="blue", style="WeChat.TLabel")
        load_status_label.pack(pady=2)
        
        button_container = ttk.Frame(button_frame, style="WeChat.TFrame")
        button_container.pack(fill=tk.X, pady=5)
        
        self.load_button = ttk.Button(
            button_container,
            text="加载联系人",
            command=self.load_contacts,
            style="WeChat.TButton"
        )
        self.load_button.pack(side=tk.LEFT, padx=5, ipadx=10, ipady=5, expand=True, fill=tk.X)
        
        self.test_button = ttk.Button(
            button_container,
            text="测试连接",
            command=self.test_database_connection
        )
        self.test_button.pack(side=tk.LEFT, padx=5, ipadx=10, ipady=5, expand=True, fill=tk.X)

        # 联系人列表区域
        contacts_container = ttk.Frame(left_panel, style="WeChat.TFrame")
        contacts_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 搜索框 - 微信风格
        search_frame = ttk.Frame(contacts_container, style="WeChat.TFrame")
        search_frame.pack(fill=tk.X, padx=0, pady=5)
        
        search_container = ttk.Frame(search_frame, style="WeChat.TFrame")
        search_container.pack(fill=tk.X, pady=5, padx=5)
        search_container.configure(borderwidth=1, relief="solid")
        
        search_icon = ttk.Label(search_container, text="🔍", style="WeChat.TLabel")
        search_icon.pack(side=tk.LEFT, padx=5)
        
        search_entry = ttk.Entry(
            search_container, 
            textvariable=self.search_text,
            font=("微软雅黑", 9),
            style="WeChat.Search.TEntry",
            width=25
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=5)
        
        # 联系人列表容器（使用Canvas和Scrollbar创建可滚动区域）
        contacts_list_frame = ttk.Frame(contacts_container, style="WeChat.TFrame")
        contacts_list_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)
        
        # 创建滚动条
        scrollbar = ttk.Scrollbar(contacts_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建Canvas用于滚动
        contacts_canvas = tk.Canvas(contacts_list_frame, 
                                   bg="#ffffff", 
                                   highlightthickness=0,
                                   yscrollcommand=scrollbar.set)
        contacts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 绑定滚动条与Canvas
        scrollbar.config(command=contacts_canvas.yview)
        
        # 创建一个框架放在Canvas中，用于存放所有联系人项目
        self.contacts_frame = ttk.Frame(contacts_canvas, style="WeChat.Contacts.TFrame")
        contacts_canvas.create_window((0, 0), window=self.contacts_frame, anchor=tk.NW, tags="self.contacts_frame")
        
        # 设置Canvas滚动区域
        def _configure_canvas(event):
            contacts_canvas.configure(scrollregion=contacts_canvas.bbox("all"), width=event.width)
        
        self.contacts_frame.bind("<Configure>", _configure_canvas)
        
        # 鼠标滚轮绑定
        def _on_mousewheel(event):
            contacts_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        contacts_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # ========== 右侧面板 - 联系人详情和导出功能 ==========
        
        # 联系人详情
        details_frame = ttk.LabelFrame(right_panel, text="联系人详情", style="WeChat.TLabelframe")
        details_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 联系人信息头部
        contact_header = ttk.Frame(details_frame, style="WeChat.TFrame")
        contact_header.pack(fill=tk.X, padx=10, pady=10)
        
        # 头像占位符 - 修改为可存储图像的标签
        self.avatar_label = ttk.Label(contact_header, text="👤", font=("Arial", 36), style="WeChat.TLabel")
        self.avatar_label.pack(side=tk.LEFT, padx=10)
        
        # 联系人基本信息
        contact_info = ttk.Frame(contact_header, style="WeChat.TFrame")
        contact_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        ttk.Label(contact_info, text="选中的联系人:", style="WeChat.TLabel").pack(anchor=tk.W, pady=2)
        ttk.Entry(contact_info, textvariable=self.selected_wxid, state="readonly", width=30).pack(anchor=tk.W, pady=2, fill=tk.X)
        
        # 详细信息
        self.contact_details = scrolledtext.ScrolledText(
            details_frame, 
            wrap=tk.WORD, 
            height=10,
            font=("微软雅黑", 9),
            background="#ffffff",
            borderwidth=0
        )
        self.contact_details.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.contact_details.config(state=tk.DISABLED)

        # 添加导出功能区
        export_frame = ttk.LabelFrame(right_panel, text="导出设置", style="WeChat.TLabelframe")
        export_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 输出目录
        ttk.Label(export_frame, text="输出目录:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(export_frame, textvariable=self.output_dir, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(export_frame, text="浏览...", command=self.browse_output_dir).grid(row=0, column=2, padx=5, pady=5)

        # 导出格式
        ttk.Label(export_frame, text="导出格式:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.format_combobox = ttk.Combobox(export_frame, values=["HTML", "TXT", "AI_TXT", "DOCX", "MARKDOWN", "XLSX"])
        self.format_combobox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        self.format_combobox.current(0)  # Default to HTML

        # 时间范围
        time_frame = ttk.LabelFrame(export_frame, text="时间范围")
        time_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W+tk.E)

        # 替换原始的输入框为日历选择器
        try:
            from tkcalendar import DateEntry
            
            ttk.Label(time_frame, text="开始时间:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
            
            # 使用DateEntry替代普通Entry
            self.start_date_entry = DateEntry(time_frame, width=18, 
                                    background='darkblue', foreground='white', 
                                    borderwidth=2, 
                                    date_pattern='yyyy-mm-dd',
                                    year=2020, month=1, day=1)
            self.start_date_entry.grid(row=0, column=1, padx=5, pady=5)
            
            # 添加时间选择
            time_frame1 = ttk.Frame(time_frame)
            time_frame1.grid(row=0, column=2, padx=(0, 5), pady=5)
            self.start_hour = ttk.Spinbox(time_frame1, from_=0, to=23, width=3, format="%02.0f")
            self.start_hour.set("00")
            self.start_hour.pack(side=tk.LEFT)
            ttk.Label(time_frame1, text=":").pack(side=tk.LEFT)
            self.start_minute = ttk.Spinbox(time_frame1, from_=0, to=59, width=3, format="%02.0f")
            self.start_minute.set("00")
            self.start_minute.pack(side=tk.LEFT)
            ttk.Label(time_frame1, text=":").pack(side=tk.LEFT)
            self.start_second = ttk.Spinbox(time_frame1, from_=0, to=59, width=3, format="%02.0f")
            self.start_second.set("00")
            self.start_second.pack(side=tk.LEFT)
            
            ttk.Label(time_frame, text="结束时间:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
            
            # 使用DateEntry替代普通Entry
            self.end_date_entry = DateEntry(time_frame, width=18, 
                                    background='darkblue', foreground='white', 
                                    borderwidth=2,
                                    date_pattern='yyyy-mm-dd',
                                    year=2035, month=12, day=31)
            self.end_date_entry.grid(row=1, column=1, padx=5, pady=5)
            
            # 添加时间选择
            time_frame2 = ttk.Frame(time_frame)
            time_frame2.grid(row=1, column=2, padx=(0, 5), pady=5)
            self.end_hour = ttk.Spinbox(time_frame2, from_=0, to=23, width=3, format="%02.0f")
            self.end_hour.set("23")
            self.end_hour.pack(side=tk.LEFT)
            ttk.Label(time_frame2, text=":").pack(side=tk.LEFT)
            self.end_minute = ttk.Spinbox(time_frame2, from_=0, to=59, width=3, format="%02.0f")
            self.end_minute.set("59")
            self.end_minute.pack(side=tk.LEFT)
            ttk.Label(time_frame2, text=":").pack(side=tk.LEFT)
            self.end_second = ttk.Spinbox(time_frame2, from_=0, to=59, width=3, format="%02.0f")
            self.end_second.set("59")
            self.end_second.pack(side=tk.LEFT)
            
        except ImportError:
            # 如果tkcalendar不可用，回退到普通的输入框
            ttk.Label(time_frame, text="开始时间:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
            self.start_time_entry = ttk.Entry(time_frame, width=20)
            self.start_time_entry.grid(row=0, column=1, padx=5, pady=5)
            self.start_time_entry.insert(0, "2020-01-01 00:00:00")

            ttk.Label(time_frame, text="结束时间:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
            self.end_time_entry = ttk.Entry(time_frame, width=20)
            self.end_time_entry.grid(row=0, column=3, padx=5, pady=5)
            self.end_time_entry.insert(0, "2035-12-31 23:59:59")

        # 消息类型选择
        types_frame = ttk.LabelFrame(export_frame, text="消息类型")
        types_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W+tk.E)

        self.msg_types = {}
        msg_type_values = [
            ("文本消息", MessageType.Text),
            ("图片消息", MessageType.Image),
            ("语音消息", MessageType.Audio),
            ("视频消息", MessageType.Video),
            ("链接消息", MessageType.LinkMessage),
            ("表情消息", MessageType.Emoji),
            ("文件消息", MessageType.File),
            ("系统消息", MessageType.System),
            ("引用消息", MessageType.Quote),
            ("合并转发消息", MessageType.MergedMessages),
            ("全部消息", None)
        ]

        row, col = 0, 0
        for text, value in msg_type_values:
            var = tk.BooleanVar(value=True if value is None else False)
            self.msg_types[value] = var
            cb = ttk.Checkbutton(types_frame, text=text, variable=var)
            cb.grid(row=row, column=col, padx=5, pady=2, sticky=tk.W)
            col += 1
            if col > 2:
                col = 0
                row += 1

        # 导出按钮
        ttk.Button(export_frame, text="开始导出", command=self.start_export, style="WeChat.TButton").grid(row=4, column=0, columnspan=3, padx=5, pady=10, sticky=tk.W+tk.E)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(export_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W+tk.E)

        # 导出日志
        log_frame = ttk.LabelFrame(right_panel, text="操作日志", style="WeChat.TLabelframe")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.contacts_log = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD,
            height=8,
            font=("微软雅黑", 9),
            background="#ffffff",
            borderwidth=0
        )
        self.contacts_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.contacts_log.config(state=tk.DISABLED)

    def create_export_tab(self):
        """Create the export records tab"""
        export_tab = ttk.Frame(self.notebook)
        self.notebook.add(export_tab, text="3. 导出记录")

        # Export settings
        settings_frame = ttk.LabelFrame(export_tab, text="导出设置")
        settings_frame.pack(fill=tk.X, padx=10, pady=10)

        # Output directory
        ttk.Label(settings_frame, text="输出目录:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(settings_frame, textvariable=self.output_dir, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="浏览...", command=self.browse_output_dir).grid(row=0, column=2, padx=5, pady=5)

        # Selected contact
        ttk.Label(settings_frame, text="选中的联系人:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(settings_frame, textvariable=self.selected_wxid, width=50, state="readonly").grid(row=1, column=1, padx=5, pady=5)

        # Export format
        ttk.Label(settings_frame, text="导出格式:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.format_combobox = ttk.Combobox(settings_frame, values=["HTML", "TXT", "AI_TXT", "DOCX", "MARKDOWN", "XLSX"])
        self.format_combobox.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        self.format_combobox.current(0)  # Default to HTML

        # Time range
        time_frame = ttk.LabelFrame(settings_frame, text="时间范围")
        time_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W+tk.E)

        # 替换原始的输入框为日历选择器
        try:
            from tkcalendar import DateEntry
            
            ttk.Label(time_frame, text="开始时间:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
            
            # 使用DateEntry替代普通Entry
            self.start_date_entry = DateEntry(time_frame, width=18, 
                                      background='darkblue', foreground='white', 
                                      borderwidth=2, 
                                      date_pattern='yyyy-mm-dd',
                                      year=2020, month=1, day=1)
            self.start_date_entry.grid(row=0, column=1, padx=5, pady=5)
            
            # 添加时间选择
            time_frame1 = ttk.Frame(time_frame)
            time_frame1.grid(row=0, column=2, padx=(0, 5), pady=5)
            self.start_hour = ttk.Spinbox(time_frame1, from_=0, to=23, width=3, format="%02.0f")
            self.start_hour.set("00")
            self.start_hour.pack(side=tk.LEFT)
            ttk.Label(time_frame1, text=":").pack(side=tk.LEFT)
            self.start_minute = ttk.Spinbox(time_frame1, from_=0, to=59, width=3, format="%02.0f")
            self.start_minute.set("00")
            self.start_minute.pack(side=tk.LEFT)
            ttk.Label(time_frame1, text=":").pack(side=tk.LEFT)
            self.start_second = ttk.Spinbox(time_frame1, from_=0, to=59, width=3, format="%02.0f")
            self.start_second.set("00")
            self.start_second.pack(side=tk.LEFT)
            
            ttk.Label(time_frame, text="结束时间:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
            
            # 使用DateEntry替代普通Entry
            self.end_date_entry = DateEntry(time_frame, width=18, 
                                    background='darkblue', foreground='white', 
                                    borderwidth=2,
                                    date_pattern='yyyy-mm-dd',
                                    year=2035, month=12, day=31)
            self.end_date_entry.grid(row=1, column=1, padx=5, pady=5)
            
            # 添加时间选择
            time_frame2 = ttk.Frame(time_frame)
            time_frame2.grid(row=1, column=2, padx=(0, 5), pady=5)
            self.end_hour = ttk.Spinbox(time_frame2, from_=0, to=23, width=3, format="%02.0f")
            self.end_hour.set("23")
            self.end_hour.pack(side=tk.LEFT)
            ttk.Label(time_frame2, text=":").pack(side=tk.LEFT)
            self.end_minute = ttk.Spinbox(time_frame2, from_=0, to=59, width=3, format="%02.0f")
            self.end_minute.set("59")
            self.end_minute.pack(side=tk.LEFT)
            ttk.Label(time_frame2, text=":").pack(side=tk.LEFT)
            self.end_second = ttk.Spinbox(time_frame2, from_=0, to=59, width=3, format="%02.0f")
            self.end_second.set("59")
            self.end_second.pack(side=tk.LEFT)
            
        except ImportError:
            # 如果tkcalendar不可用，回退到普通的输入框
            ttk.Label(time_frame, text="开始时间:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
            self.start_time_entry = ttk.Entry(time_frame, width=20)
            self.start_time_entry.grid(row=0, column=1, padx=5, pady=5)
            self.start_time_entry.insert(0, "2020-01-01 00:00:00")

            ttk.Label(time_frame, text="结束时间:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
            self.end_time_entry = ttk.Entry(time_frame, width=20)
            self.end_time_entry.grid(row=0, column=3, padx=5, pady=5)
            self.end_time_entry.insert(0, "2035-12-31 23:59:59")

        # Message types
        types_frame = ttk.LabelFrame(settings_frame, text="消息类型")
        types_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W+tk.E)

        self.msg_types = {}
        msg_type_values = [
            ("文本消息", MessageType.Text),
            ("图片消息", MessageType.Image),
            ("语音消息", MessageType.Audio),
            ("视频消息", MessageType.Video),
            ("链接消息", MessageType.LinkMessage),
            ("表情消息", MessageType.Emoji),
            ("文件消息", MessageType.File),
            ("系统消息", MessageType.System),
            ("引用消息", MessageType.Quote),
            ("合并转发消息", MessageType.MergedMessages),
            ("全部消息", None)
        ]

        row, col = 0, 0
        for text, value in msg_type_values:
            var = tk.BooleanVar(value=True if value is None else False)
            self.msg_types[value] = var
            cb = ttk.Checkbutton(types_frame, text=text, variable=var)
            cb.grid(row=row, column=col, padx=5, pady=2, sticky=tk.W)
            col += 1
            if col > 2:
                col = 0
                row += 1

        # Export button
        export_button = ttk.Button(export_tab, text="开始导出", command=self.start_export)
        export_button.pack(pady=10)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(export_tab, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)

        # Export log
        log_frame = ttk.LabelFrame(export_tab, text="导出日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.export_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.export_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.export_log.config(state=tk.DISABLED)

    def create_settings_tab(self):
        """创建设置标签页，整合解密和导出功能"""
        settings_tab = ttk.Frame(self.notebook, style="WeChat.TFrame")
        self.notebook.add(settings_tab, text="设置")
        
        # 创建左右分栏布局
        paned_window = ttk.PanedWindow(settings_tab, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧面板 - 基本设置
        left_panel = ttk.Frame(paned_window, style="WeChat.TFrame")
        paned_window.add(left_panel, weight=1)
        
        # 右侧面板 - 数据库解密
        right_panel = ttk.Frame(paned_window, style="WeChat.TFrame")
        paned_window.add(right_panel, weight=1)
        
        # ========== 左侧面板 - 基本设置 ==========
        base_settings_frame = ttk.LabelFrame(left_panel, text="基本设置", style="WeChat.TLabelframe")
        base_settings_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 数据库目录设置
        db_frame = ttk.Frame(base_settings_frame, style="WeChat.TFrame")
        db_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(db_frame, text="数据库目录:", style="WeChat.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(db_frame, textvariable=self.db_dir, width=30).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        ttk.Button(db_frame, text="浏览...", command=self.browse_db_dir).grid(row=0, column=2, padx=5, pady=5)
        
        # 数据库版本设置
        version_frame = ttk.Frame(base_settings_frame, style="WeChat.TFrame")
        version_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(version_frame, text="数据库版本:", style="WeChat.TLabel").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(version_frame, text="微信 3.x", variable=self.db_version, value=3).pack(side=tk.LEFT, padx=15)
        ttk.Radiobutton(version_frame, text="微信 4.0", variable=self.db_version, value=4).pack(side=tk.LEFT, padx=15)
        
        # 输出目录设置
        output_frame = ttk.Frame(base_settings_frame, style="WeChat.TFrame")
        output_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(output_frame, text="输出目录:", style="WeChat.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(output_frame, textvariable=self.output_dir, width=30).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        ttk.Button(output_frame, text="浏览...", command=self.browse_output_dir).grid(row=0, column=2, padx=5, pady=5)
        
        # 测试和保存按钮
        btn_frame = ttk.Frame(base_settings_frame, style="WeChat.TFrame")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(
            btn_frame, 
            text="测试数据库连接", 
            command=self.test_database_connection
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        ttk.Button(
            btn_frame, 
            text="保存设置", 
            command=self.save_current_config,
            style="WeChat.TButton"
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        # 最近使用的数据库
        recent_db_frame = ttk.LabelFrame(base_settings_frame, text="最近使用的数据库", style="WeChat.TLabelframe")
        recent_db_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建最近数据库列表
        self.recent_db_listbox = tk.Listbox(
            recent_db_frame,
            height=5,
            font=("微软雅黑", 9),
            selectbackground="#d4eef9",
            selectforeground="#000000"
        )
        self.recent_db_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.recent_db_listbox.bind('<<ListboxSelect>>', self.on_recent_db_select)
        
        # 填充最近数据库列表
        for db_item in self.config.get("recent_databases", []):
            if isinstance(db_item, dict) and "path" in db_item:
                display_text = f"{db_item['path']} (微信 {db_item['version']})"
                self.recent_db_listbox.insert(tk.END, display_text)
        
        # ========== 右侧面板 - 数据库解密 ==========
        decrypt_frame = ttk.LabelFrame(right_panel, text="数据库解密", style="WeChat.TLabelframe")
        decrypt_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # WeChat版本选择
        version_frame = ttk.Frame(decrypt_frame, style="WeChat.TFrame")
        version_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(version_frame, text="微信版本:", style="WeChat.TLabel").pack(side=tk.LEFT, padx=5)
        self.decrypt_version = tk.IntVar(value=3)
        ttk.Radiobutton(version_frame, text="微信 3.x", variable=self.decrypt_version, value=3).pack(side=tk.LEFT, padx=15)
        ttk.Radiobutton(version_frame, text="微信 4.0", variable=self.decrypt_version, value=4).pack(side=tk.LEFT, padx=15)
        
        # 解密按钮
        decrypt_button = ttk.Button(decrypt_frame, text="开始解密", command=self.start_decrypt, style="WeChat.TButton")
        decrypt_button.pack(pady=10)
        
        # 日志区域
        log_frame = ttk.LabelFrame(decrypt_frame, text="解密日志", style="WeChat.TLabelframe")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.decrypt_log = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD,
            height=8,
            font=("微软雅黑", 9),
            background="#ffffff",
            borderwidth=0
        )
        self.decrypt_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.decrypt_log.config(state=tk.DISABLED)
        
        # 历史解密记录区域
        history_frame = ttk.LabelFrame(decrypt_frame, text="历史解密记录", style="WeChat.TLabelframe")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建历史解密记录列表
        self.decrypt_history_listbox = tk.Listbox(
            history_frame,
            height=5,
            font=("微软雅黑", 9),
            selectbackground="#d4eef9",
            selectforeground="#000000"
        )
        self.decrypt_history_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.decrypt_history_listbox.bind('<<ListboxSelect>>', self.on_decrypt_history_select)
        
        # 填充历史解密记录列表
        for history_item in self.config.get("decrypt_history", []):
            if isinstance(history_item, dict) and "wxid" in history_item:
                display_text = f"{history_item['name']} ({history_item['wxid']}) - 微信{history_item['version']}"
                self.decrypt_history_listbox.insert(tk.END, display_text)

    def on_recent_db_select(self, event):
        """处理选择最近使用的数据库"""
        selection = self.recent_db_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        if index >= len(self.config.get("recent_databases", [])):
            return
            
        # 获取选定的数据库
        db_item = self.config["recent_databases"][index]
        if isinstance(db_item, dict) and "path" in db_item:
            # 设置数据库路径和版本
            self.db_dir.set(db_item["path"])
            self.db_version.set(db_item["version"])
            
            # 尝试连接数据库
            self.root.after(100, self.test_database_connection)

    def on_decrypt_history_select(self, event):
        """处理选择历史解密记录"""
        selection = self.decrypt_history_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        if index >= len(self.config.get("decrypt_history", [])):
            return
            
        # 获取选定的历史记录
        history_item = self.config["decrypt_history"][index]
        if isinstance(history_item, dict) and "db_path" in history_item:
            # 设置数据库路径和版本
            self.db_dir.set(history_item["db_path"])
            self.db_version.set(history_item["version"])
            
            # 尝试连接数据库
            self.root.after(100, self.test_database_connection)

    def load_contacts(self, auto=False):
        """Load contacts from the database"""
        # Disable the button to prevent multiple clicks
        if self.load_button:
            self.load_button.config(state=tk.DISABLED, text="正在加载...")

        # 更新状态
        self.load_status_var.set("正在加载联系人...")

        db_dir = self.db_dir.get()
        db_version = self.db_version.get()

        self.log_message(self.contacts_log, f"尝试加载联系人，数据库目录: {db_dir}, 版本: {db_version}")

        if not db_dir:
            messagebox.showerror("错误", "请先选择数据库目录")
            self.log_message(self.contacts_log, "错误: 未选择数据库目录")
            self.load_status_var.set("未选择数据库目录")
            if self.load_button:
                self.load_button.config(state=tk.NORMAL, text="加载联系人")
            return

        if not os.path.exists(db_dir):
            messagebox.showerror("错误", f"数据库目录不存在: {db_dir}")
            self.log_message(self.contacts_log, f"错误: 数据库目录不存在: {db_dir}")
            self.load_status_var.set("数据库目录不存在")
            if self.load_button:
                self.load_button.config(state=tk.NORMAL, text="加载联系人")
            return

        # 检查目录中是否有数据库文件
        db_files = [f for f in os.listdir(db_dir) if f.endswith('.db')]
        if not db_files:
            error_msg = "目录中没有找到数据库文件"
            messagebox.showerror("错误", error_msg)
            self.log_message(self.contacts_log, f"错误: {error_msg}")
            self.load_status_var.set("未找到数据库文件")
            if self.load_button:
                self.load_button.config(state=tk.NORMAL, text="加载联系人")
            return

        # 列出找到的数据库文件
        self.log_message(self.contacts_log, f"找到的数据库文件: {db_files}")

        # 如果不是自动加载，确认用户是否要继续
        if not auto and not messagebox.askyesno("确认", f"确定要从目录 {db_dir} 加载联系人吗？"):
            self.log_message(self.contacts_log, "用户取消了加载联系人")
            self.load_status_var.set("已取消")
            if self.load_button:
                self.load_button.config(state=tk.NORMAL, text="加载联系人")
            return

        self.status_var.set("正在加载联系人...")
        self.log_message(self.contacts_log, "开始加载联系人...")

        # 保存当前数据库设置到配置
        try:
            import config
            self.config = config.add_recent_database(self.config, db_dir, db_version)
            config.save_config(self.config)
        except ImportError:
            pass

        # Run in a separate thread to avoid freezing the UI
        threading.Thread(target=self._load_contacts_thread, args=(db_dir, db_version), daemon=True).start()

    def _load_contacts_thread(self, db_dir, db_version):
        """Thread function for loading contacts"""
        try:
            # 记录更详细的调试信息
            self.log_message(self.contacts_log, f"创建数据库连接: {db_dir}, 版本: {db_version}")
            self.log_message(self.contacts_log, f"当前工作目录: {os.getcwd()}")
            self.log_message(self.contacts_log, f"数据库目录是否存在: {os.path.exists(db_dir)}")
            self.log_message(self.contacts_log, f"数据库目录是否是目录: {os.path.isdir(db_dir)}")

            # 更新状态
            self.root.after(0, lambda: self.load_status_var.set("正在检查数据库文件..."))

            # 尝试列出数据库目录中的文件
            try:
                files = os.listdir(db_dir)
                self.log_message(self.contacts_log, f"数据库目录中的文件: {files}")

                # 检查数据库文件是否可读
                for file in files:
                    if file.endswith('.db'):
                        file_path = os.path.join(db_dir, file)
                        self.log_message(self.contacts_log, f"检查文件 {file_path}")
                        self.log_message(self.contacts_log, f"  - 文件存在: {os.path.exists(file_path)}")
                        self.log_message(self.contacts_log, f"  - 文件大小: {os.path.getsize(file_path)} 字节")
                        self.log_message(self.contacts_log, f"  - 文件可读: {os.access(file_path, os.R_OK)}")
            except Exception as e:
                self.log_message(self.contacts_log, f"列出数据库目录中的文件时出错: {str(e)}")

            # 更新状态
            self.root.after(0, lambda: self.load_status_var.set("正在创建数据库连接..."))

            # 创建数据库连接
            self.log_message(self.contacts_log, "正在创建 DatabaseConnection 对象...")
            conn = DatabaseConnection(db_dir, db_version)
            self.log_message(self.contacts_log, "DatabaseConnection 对象创建成功，正在获取接口...")
            self.database = conn.get_interface()
            self.log_message(self.contacts_log, f"接口获取结果: {self.database is not None}")

            if not self.database:
                error_msg = "数据库连接失败，请检查数据库路径和版本是否正确"
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
                self.log_message(self.contacts_log, f"错误: {error_msg}")
                self.status_var.set("联系人加载失败")
                self.root.after(0, lambda: self.load_status_var.set("数据库连接失败"))
                # Re-enable the button
                if self.load_button:
                    self.root.after(0, lambda: self.load_button.config(state=tk.NORMAL, text="加载联系人"))
                return

            # 更新状态
            self.root.after(0, lambda: self.load_status_var.set("正在获取联系人列表..."))

            self.log_message(self.contacts_log, "数据库连接成功，开始获取联系人列表...")
            try:
                self.contacts = self.database.get_contacts()
                self.log_message(self.contacts_log, f"get_contacts() 返回结果类型: {type(self.contacts)}")
                self.log_message(self.contacts_log, f"联系人列表长度: {len(self.contacts) if self.contacts else 0}")
            except Exception as e:
                self.log_message(self.contacts_log, f"获取联系人列表时出错: {str(e)}")
                self.log_message(self.contacts_log, traceback.format_exc())
                self.root.after(0, lambda: self.load_status_var.set("获取联系人列表失败"))
                raise  # 重新抛出异常，让外层的 try-except 捕获

            if not self.contacts:
                self.log_message(self.contacts_log, "警告: 未找到任何联系人，请检查数据库是否正确")
                self.root.after(0, lambda: messagebox.showwarning("警告", "未找到任何联系人，请检查数据库是否正确"))
                self.status_var.set("未找到联系人")
                self.root.after(0, lambda: self.load_status_var.set("未找到联系人"))
                # Re-enable the button
                if self.load_button:
                    self.root.after(0, lambda: self.load_button.config(state=tk.NORMAL, text="加载联系人"))
                return

            # 更新状态
            self.root.after(0, lambda: self.load_status_var.set("正在处理联系人数据..."))

            self.log_message(self.contacts_log, "复制联系人列表...")
            self.filtered_contacts = self.contacts.copy()
            self.log_message(self.contacts_log, f"成功获取 {len(self.contacts)} 个联系人")

            # 记录一些联系人信息用于调试
            if self.contacts:
                self.log_message(self.contacts_log, "联系人示例:")
                for i, contact in enumerate(self.contacts[:3]):  # 只显示前3个联系人
                    self.log_message(self.contacts_log, f"联系人 {i+1}: wxid={contact.wxid}, nickname={contact.nickname}")
                    if hasattr(contact, 'remark'):
                        self.log_message(self.contacts_log, f"  备注: {contact.remark}")

            # 更新状态
            self.root.after(0, lambda: self.load_status_var.set("正在更新界面..."))

            # Update the UI in the main thread
            self.log_message(self.contacts_log, "更新UI...")
            self.root.after(0, self._update_contacts_list)
            self.status_var.set(f"已加载 {len(self.contacts)} 个联系人")

            # 更新最终状态
            success_msg = f"已成功加载 {len(self.contacts)} 个联系人"
            self.root.after(0, lambda: self.load_status_var.set(success_msg))
            self.root.after(0, lambda: messagebox.showinfo("成功", success_msg))

            # Re-enable the button
            if self.load_button:
                self.root.after(0, lambda: self.load_button.config(state=tk.NORMAL, text="重新加载联系人"))

        except Exception as e:
            error_msg = f"加载联系人时出错: {str(e)}"
            self.log_message(self.contacts_log, f"错误: {error_msg}")
            self.log_message(self.contacts_log, traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
            self.status_var.set("联系人加载失败")
            self.root.after(0, lambda: self.load_status_var.set("加载失败"))

            # Re-enable the button
            if self.load_button:
                self.root.after(0, lambda: self.load_button.config(state=tk.NORMAL, text="加载联系人"))

    def _update_contacts_list(self):
        """Update the contacts listbox with performance optimizations"""
        self.log_message(self.contacts_log, "开始更新联系人列表UI...")

        # 检查 contacts_frame 是否存在
        if not hasattr(self, 'contacts_frame') or self.contacts_frame is None:
            self.log_message(self.contacts_log, "错误: contacts_frame 不存在或为 None")
            return
        
        # 清除现有的联系人列表
        try:
            # 删除所有现有的联系人项目
            for widget in self.contacts_frame.winfo_children():
                widget.destroy()
        except Exception as e:
            self.log_message(self.contacts_log, f"清除联系人列表出错: {str(e)}")
        
        if not self.filtered_contacts:
            self.log_message(self.contacts_log, "警告: filtered_contacts 为空")
            return

        try:
            self.log_message(self.contacts_log, f"开始添加 {len(self.filtered_contacts)} 个联系人到列表")
            
            # 按类型对联系人分组
            groups = {
                "星标联系人": [],
                "公众号": [],
                "群聊": [],
                "好友": []
            }
            
            for contact in self.filtered_contacts:
                if hasattr(contact, 'type') and contact.type == 'star':
                    groups["星标联系人"].append(contact)
                elif hasattr(contact, 'wxid') and contact.wxid.startswith('gh_'):
                    groups["公众号"].append(contact)
                elif hasattr(contact, 'is_chatroom') and contact.is_chatroom:
                    groups["群聊"].append(contact)
                else:
                    groups["好友"].append(contact)
            
            # 创建一个装载所有要创建的联系人项目信息的列表
            # 延迟创建实际的UI组件，以减少UI事件循环的压力
            items_to_create = []
            for group_name, contacts in groups.items():
                if contacts:
                    # 添加分组标题
                    items_to_create.append({
                        'type': 'group',
                        'text': f"--- {group_name} ({len(contacts)}) ---",
                    })
                    
                    # 只添加前100个联系人，超过后添加"加载更多"按钮
                    MAX_INITIAL_CONTACTS = 100
                    
                    # 添加该分组的联系人
                    for i, contact in enumerate(contacts[:MAX_INITIAL_CONTACTS]):
                        items_to_create.append({
                            'type': 'contact',
                            'contact': contact,
                            'position': i
                        })
                    
                    # 如果超过限制，添加"加载更多"按钮
                    if len(contacts) > MAX_INITIAL_CONTACTS:
                        items_to_create.append({
                            'type': 'load_more',
                            'group': group_name,
                            'contacts': contacts[MAX_INITIAL_CONTACTS:],
                            'start_index': MAX_INITIAL_CONTACTS
                        })
            
            # 一次性创建所有UI组件，减少重绘次数
            self.root.update_idletasks()  # 刷新界面，避免卡顿感
            
            total_added = 0
            for item in items_to_create:
                if item['type'] == 'group':
                    # 创建分组标题
                    group_label = ttk.Label(
                        self.contacts_frame, 
                        text=item['text'],
                        style="WeChat.TLabel",
                        background="#f0f0f0",
                        foreground="#888888"
                    )
                    group_label.pack(fill=tk.X, pady=(10, 5), padx=5)
                    
                elif item['type'] == 'contact':
                    # 创建联系人项目
                    self._create_contact_item(item['contact'])
                    total_added += 1
                    
                elif item['type'] == 'load_more':
                    # 创建"加载更多"按钮
                    load_more_frame = ttk.Frame(self.contacts_frame, style="Contact.TFrame")
                    load_more_frame.pack(fill=tk.X, pady=2, padx=5)
                    
                    load_more_btn = ttk.Button(
                        load_more_frame, 
                        text=f"加载更多 {item['group']} ({len(item['contacts'])}个)",
                        command=lambda g=item['group'], c=item['contacts']: self._load_more_contacts(g, c)
                    )
                    load_more_btn.pack(fill=tk.X, pady=2)
                
                # 每创建10个项目就更新一次界面，平衡性能和响应性
                if total_added % 10 == 0:
                    self.root.update_idletasks()
            
            self.log_message(self.contacts_log, f"联系人列表更新完成，添加了 {total_added} 个联系人")
        except Exception as e:
            self.log_message(self.contacts_log, f"更新联系人列表时出错: {str(e)}")
            self.log_message(self.contacts_log, traceback.format_exc())

    def _create_contact_item(self, contact):
        """创建单个联系人项目，单独提取为方法以便重用"""
        try:
            # 使用缓存检查是否已经加载过此联系人的头像
            avatar_key = f"avatar_{contact.wxid}"
            
            # 创建联系人项目框架
            contact_frame = ttk.Frame(self.contacts_frame, style="Contact.TFrame")
            contact_frame.pack(fill=tk.X, pady=2, padx=5)
            
            # 创建头像容器（固定大小）
            avatar_container = ttk.Frame(contact_frame, style="Contact.TFrame", width=32, height=32)
            avatar_container.pack(side=tk.LEFT, padx=(5, 10))
            avatar_container.pack_propagate(False)  # 保持固定大小
            
            # 确定默认头像类型
            if hasattr(contact, 'is_chatroom') and contact.is_chatroom:
                avatar_text = "👥"  # 群聊图标
            elif hasattr(contact, 'wxid') and contact.wxid.startswith('gh_'):
                avatar_text = "📢"  # 公众号图标
            else:
                avatar_text = "👤"  # 普通联系人图标
            
            # 创建头像标签
            avatar_label = ttk.Label(
                avatar_container, 
                text=avatar_text, 
                font=("Arial", 16),
                style="Contact.TLabel",
                anchor=tk.CENTER
            )
            avatar_label.pack(fill=tk.BOTH, expand=True)
            
            # 获取显示名称
            display_name = contact.nickname if hasattr(contact, 'nickname') and contact.nickname else "未知"
            if hasattr(contact, 'remark') and contact.remark:
                display_name = f"{contact.remark} ({contact.nickname})"
            
            # 创建联系人名称标签
            name_label = ttk.Label(
                contact_frame, 
                text=display_name,
                style="Contact.TLabel"
            )
            name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.W)
            
            # 异步加载头像（不阻塞UI线程）
            if hasattr(self, 'contact_avatar_cache') and avatar_key in self.contact_avatar_cache:
                # 从缓存中使用头像
                photo = self.contact_avatar_cache[avatar_key]
                if photo:
                    avatar_label.config(image=photo, text='')
                    avatar_label.image = photo
            elif self.database:
                # 在新线程中加载头像
                threading.Thread(
                    target=self._load_contact_avatar_thread,
                    args=(contact, avatar_label),
                    daemon=True
                ).start()
            
            # 绑定点击事件
            contact_frame.bind("<Button-1>", lambda e, c=contact: self._on_contact_item_select(c))
            avatar_label.bind("<Button-1>", lambda e, c=contact: self._on_contact_item_select(c))
            name_label.bind("<Button-1>", lambda e, c=contact: self._on_contact_item_select(c))
            
            # 添加悬停效果
            contact_frame.bind("<Enter>", lambda e, frame=contact_frame: self._on_contact_hover_enter(frame))
            contact_frame.bind("<Leave>", lambda e, frame=contact_frame: self._on_contact_hover_leave(frame))
            
        except Exception as e:
            self.log_message(self.contacts_log, f"创建联系人项目时出错: {str(e)}")

    def _load_more_contacts(self, group_name, remaining_contacts):
        """加载更多联系人"""
        # 每次加载的联系人数量
        BATCH_SIZE = 50
        
        contacts_to_load = remaining_contacts[:BATCH_SIZE]
        for contact in contacts_to_load:
            self._create_contact_item(contact)
        
        # 更新界面
        self.root.update_idletasks()
        
        # 若还有剩余，添加新的"加载更多"按钮
        if len(remaining_contacts) > BATCH_SIZE:
            load_more_frame = ttk.Frame(self.contacts_frame, style="Contact.TFrame")
            load_more_frame.pack(fill=tk.X, pady=2, padx=5)
            
            load_more_btn = ttk.Button(
                load_more_frame, 
                text=f"加载更多 {group_name} ({len(remaining_contacts) - BATCH_SIZE}个)",
                command=lambda g=group_name, c=remaining_contacts[BATCH_SIZE:]: self._load_more_contacts(g, c)
            )
            load_more_btn.pack(fill=tk.X, pady=2)

    def _load_contact_avatar_thread(self, contact, avatar_label):
        """在后台线程中加载联系人头像"""
        try:
            # 初始化头像缓存字典（如果尚未初始化）
            if not hasattr(self, 'contact_avatar_cache'):
                self.contact_avatar_cache = {}
                
            avatar_key = f"avatar_{contact.wxid}"
            
            # 获取头像数据
            avatar_buffer = None
            try:
                # 尝试从数据库获取头像
                if hasattr(self.database, 'get_avatar_buffer'):
                    avatar_buffer = self.database.get_avatar_buffer(contact.wxid)
                elif hasattr(self.database, 'get_avatar_urls'):
                    # 如果头像已经被保存到文件系统
                    avatar_urls = self.database.get_avatar_urls(contact.wxid)
                    if avatar_urls and len(avatar_urls) > 0:
                        # 使用第一个URL
                        avatar_path = avatar_urls[0]
                        # 检查文件是否存在
                        if os.path.exists(avatar_path):
                            with open(avatar_path, 'rb') as f:
                                avatar_buffer = f.read()
            except Exception:
                # 忽略错误，使用默认头像
                pass
                
            # 如果获取到头像数据
            if avatar_buffer:
                # 使用PIL处理图像
                img = Image.open(io.BytesIO(avatar_buffer))
                # 调整大小为小头像
                img = img.resize((32, 32), Image.LANCZOS)
                # 创建Tkinter兼容的图像
                photo = ImageTk.PhotoImage(img)
                
                # 保存到缓存中
                self.contact_avatar_cache[avatar_key] = photo
                
                # 在主线程更新UI
                self.root.after(0, lambda: self._update_avatar_label(avatar_label, photo))
        except Exception as e:
            # 忽略错误，保持默认头像
            pass

    def _update_avatar_label(self, label, photo):
        """在主线程中更新头像标签"""
        try:
            if label.winfo_exists():  # 检查标签是否仍然存在
                label.config(image=photo, text='')
                # 保存引用以防止垃圾回收
                label.image = photo
        except Exception:
            pass

    def _on_contact_item_select(self, contact):
        """处理联系人项目被选中的事件"""
        self.selected_wxid.set(contact.wxid)
        self._update_contact_details(contact)
        # 尝试加载并显示联系人头像
        self._load_avatar(contact)
    
    def _update_contact_details(self, contact):
        """更新联系人详情显示"""
        # 更新联系人详情
        self.contact_details.config(state=tk.NORMAL)
        self.contact_details.delete(1.0, tk.END)

        # 使用更美观的格式显示联系人信息
        self.contact_details.tag_configure("title", font=("微软雅黑", 10, "bold"))
        self.contact_details.tag_configure("content", font=("微软雅黑", 9))
        self.contact_details.tag_configure("section", font=("微软雅黑", 10, "bold"), foreground="#07c160")
        
        # 基本信息部分
        self.contact_details.insert(tk.END, "基本信息\n", "section")
        
        self.contact_details.insert(tk.END, "微信ID: ", "title")
        self.contact_details.insert(tk.END, f"{contact.wxid}\n", "content")
        
        self.contact_details.insert(tk.END, "昵称: ", "title")
        self.contact_details.insert(tk.END, f"{contact.nickname}\n", "content")
        
        if hasattr(contact, 'remark') and contact.remark:
            self.contact_details.insert(tk.END, "备注: ", "title")
            self.contact_details.insert(tk.END, f"{contact.remark}\n", "content")
        
        if hasattr(contact, 'alias') and contact.alias:
            self.contact_details.insert(tk.END, "别名: ", "title")
            self.contact_details.insert(tk.END, f"{contact.alias}\n", "content")
        
        # 添加类型信息
        self.contact_details.insert(tk.END, "\n类型信息\n", "section")
        
        if hasattr(contact, 'is_chatroom') and contact.is_chatroom:
            self.contact_details.insert(tk.END, "类型: ", "title")
            self.contact_details.insert(tk.END, "群聊\n", "content")
            
            # 获取群成员信息
            if self.database:
                try:
                    chatroom_members = self.database.get_chatroom_members(contact.wxid)
                    member_count = len(chatroom_members) if chatroom_members else 0
                    
                    self.contact_details.insert(tk.END, "成员数: ", "title")
                    self.contact_details.insert(tk.END, f"{member_count}\n", "content")
                    
                    if member_count > 0 and member_count <= 20:  # 限制显示的成员数量
                        self.contact_details.insert(tk.END, "\n群成员列表: \n", "title")
                        for i, member in enumerate(chatroom_members[:20]):
                            member_name = member.nickname
                            if hasattr(member, 'display_name') and member.display_name:
                                member_name = member.display_name
                            self.contact_details.insert(tk.END, f"{i+1}. {member_name}\n", "content")
                        
                        if member_count > 20:
                            self.contact_details.insert(tk.END, "...(更多)\n", "content")
                except Exception as e:
                    self.log_message(self.contacts_log, f"获取群成员信息时出错: {str(e)}")
                    self.contact_details.insert(tk.END, "无法获取群成员信息\n", "content")
        elif hasattr(contact, 'wxid') and contact.wxid.startswith('gh_'):
            self.contact_details.insert(tk.END, "类型: ", "title")
            self.contact_details.insert(tk.END, "公众号\n", "content")
        else:
            self.contact_details.insert(tk.END, "类型: ", "title")
            self.contact_details.insert(tk.END, "个人\n", "content")
        
        # 添加操作提示
        self.contact_details.insert(tk.END, "\n操作提示\n", "section")
        self.contact_details.insert(tk.END, "选择此联系人后，可以切换到\"导出记录\"标签页导出聊天记录。\n", "content")

        self.contact_details.config(state=tk.DISABLED)

    def _on_contact_hover_enter(self, frame):
        """鼠标悬停在联系人项目上的效果"""
        try:
            # 对于ttk组件，不能直接设置background，需要使用style
            frame.configure(style="ContactHover.TFrame")
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(style="ContactHover.TLabel")
        except Exception as e:
            # 忽略样式设置错误，不影响功能
            self.log_message_console(f"设置悬停样式出错: {str(e)}")

    def _on_contact_hover_leave(self, frame):
        """鼠标离开联系人项目的效果"""
        try:
            # 恢复原始样式
            frame.configure(style="Contact.TFrame")
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(style="Contact.TLabel")
        except Exception as e:
            # 忽略样式设置错误，不影响功能
            self.log_message_console(f"恢复样式出错: {str(e)}")

    def filter_contacts(self, *args):
        """Filter contacts based on search text"""
        search_text = self.search_text.get().lower()

        if not search_text:
            self.filtered_contacts = self.contacts.copy()
        else:
            self.filtered_contacts = [
                contact for contact in self.contacts
                if (search_text in contact.nickname.lower() or
                    (contact.remark and search_text in contact.remark.lower()) or
                    search_text in contact.wxid.lower())
            ]

        self._update_contacts_list()

    def start_export(self):
        """Start the export process"""
        wxid = self.selected_wxid.get()
        if not wxid:
            messagebox.showerror("错误", "请先选择一个联系人")
            return

        if not self.database:
            messagebox.showerror("错误", "请先加载联系人")
            return

        output_dir = self.output_dir.get()
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Get export format
        format_str = self.format_combobox.get()
        format_map = {
            "HTML": FileType.HTML,
            "TXT": FileType.TXT,
            "AI_TXT": FileType.AI_TXT,
            "DOCX": FileType.DOCX,
            "MARKDOWN": FileType.MARKDOWN,
            "XLSX": FileType.XLSX
        }
        file_type = format_map.get(format_str, FileType.HTML)

        # Get time range
        try:
            # 检查是否使用日历选择器
            if hasattr(self, 'start_date_entry'):
                # 使用日历选择器和时间选择器获取完整的日期时间字符串
                start_date = self.start_date_entry.get_date()
                start_time = f"{self.start_hour.get()}:{self.start_minute.get()}:{self.start_second.get()}"
                start_time = f"{start_date.strftime('%Y-%m-%d')} {start_time}"
                
                end_date = self.end_date_entry.get_date()
                end_time = f"{self.end_hour.get()}:{self.end_minute.get()}:{self.end_second.get()}"
                end_time = f"{end_date.strftime('%Y-%m-%d')} {end_time}"
            else:
                # 使用常规输入框
                start_time = self.start_time_entry.get()
                end_time = self.end_time_entry.get()
        except Exception as e:
            self.log_message(self.export_log, f"获取时间范围时出错: {str(e)}")
            self.log_message(self.export_log, traceback.format_exc())
            messagebox.showerror("错误", f"时间格式错误: {str(e)}")
            return

        # Get message types
        selected_types = set()
        for msg_type, var in self.msg_types.items():
            if var.get() and msg_type is not None:
                selected_types.add(msg_type)

        # If "All messages" is selected, set message_types to None
        message_types = None if self.msg_types[None].get() else selected_types

        self.status_var.set("正在导出记录...")
        self.progress_var.set(0)
        self.log_message(self.export_log, f"开始导出 {wxid} 的聊天记录...")
        self.log_message(self.export_log, f"时间范围: {start_time} 到 {end_time}")

        # Run export in a separate thread
        threading.Thread(
            target=self._export_thread,
            args=(wxid, output_dir, file_type, message_types, [start_time, end_time]),
            daemon=True
        ).start()

    def _export_thread(self, wxid, output_dir, file_type, message_types, time_range):
        """Thread function for exporting records"""
        try:
            contact = self.database.get_contact_by_username(wxid)
            if not contact:
                self.root.after(0, lambda: messagebox.showerror("错误", f"找不到联系人: {wxid}"))
                self.status_var.set("导出失败")
                return

            exporter_map = {
                FileType.HTML: HtmlExporter,
                FileType.TXT: TxtExporter,
                FileType.AI_TXT: AiTxtExporter,
                FileType.DOCX: DocxExporter,
                FileType.MARKDOWN: MarkdownExporter,
                FileType.XLSX: ExcelExporter
            }

            exporter_class = exporter_map.get(file_type)
            if not exporter_class:
                self.root.after(0, lambda: messagebox.showerror("错误", f"不支持的导出格式: {file_type}"))
                self.status_var.set("导出失败")
                return

            self.log_message(self.export_log, f"使用 {exporter_class.__name__} 导出到 {output_dir}")

            exporter = exporter_class(
                self.database,
                contact,
                output_dir=output_dir,
                type_=file_type,
                message_types=message_types,
                time_range=time_range,
                group_members=None
            )

            # Start export
            self.log_message(self.export_log, "导出中，请稍候...")
            start_time = time.time()
            exporter.start()
            end_time = time.time()

            self.log_message(self.export_log, f"导出完成，耗时: {end_time - start_time:.2f}秒")
            self.progress_var.set(100)
            self.status_var.set("导出完成")

            # Show success message
            self.root.after(0, lambda: messagebox.showinfo("成功", f"导出完成，文件保存在 {output_dir}"))
        except Exception as e:
            self.log_message(self.export_log, f"导出过程中出错: {str(e)}")
            self.log_message(self.export_log, traceback.format_exc())
            self.status_var.set("导出失败")
            self.root.after(0, lambda: messagebox.showerror("错误", f"导出过程中出错: {str(e)}"))

    def _load_avatar(self, contact):
        """加载并显示联系人头像"""
        try:
            avatar_image = None
            # 检查数据库是否已经加载
            if not self.database:
                return
            
            # 获取头像数据
            avatar_buffer = None
            try:
                # 尝试从数据库获取头像
                if hasattr(self.database, 'get_avatar_buffer'):
                    avatar_buffer = self.database.get_avatar_buffer(contact.wxid)
                elif hasattr(self.database, 'get_avatar_urls'):
                    # 如果头像已经被保存到文件系统
                    avatar_urls = self.database.get_avatar_urls(contact.wxid)
                    if avatar_urls and len(avatar_urls) > 0:
                        # 使用第一个URL
                        avatar_path = avatar_urls[0]
                        # 检查文件是否存在
                        if os.path.exists(avatar_path):
                            with open(avatar_path, 'rb') as f:
                                avatar_buffer = f.read()
            except Exception as e:
                self.log_message(self.contacts_log, f"获取联系人头像时出错: {str(e)}")
            
            # 如果获取到头像数据
            if avatar_buffer:
                try:
                    # 使用PIL处理图像
                    img = Image.open(io.BytesIO(avatar_buffer))
                    # 调整大小为圆形头像
                    img = img.resize((64, 64), Image.LANCZOS)
                    # 创建Tkinter兼容的图像
                    photo = ImageTk.PhotoImage(img)
                    
                    # 更新头像显示
                    if hasattr(self, 'avatar_label') and self.avatar_label:
                        self.avatar_label.config(image=photo, text='')
                        # 保存引用以防止垃圾回收
                        self.avatar_label.image = photo
                    self.log_message(self.contacts_log, f"加载联系人 {contact.wxid} 的头像成功")
                except Exception as e:
                    self.log_message(self.contacts_log, f"处理联系人头像图像时出错: {str(e)}")
        except Exception as e:
            self.log_message(self.contacts_log, f"加载联系人头像时出错: {str(e)}")

    def browse_db_dir(self):
        """Browse for database directory"""
        directory = filedialog.askdirectory(title="选择数据库目录")
        if directory:
            self.db_dir.set(directory)

    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir.set(directory)

    def log_message(self, log_widget, message):
        """Add a message to the log widget"""
        log_widget.config(state=tk.NORMAL)
        log_widget.insert(tk.END, f"{message}\n")
        log_widget.see(tk.END)
        log_widget.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def test_database_connection(self):
        """测试数据库连接"""
        # 更新状态
        self.load_status_var.set("正在测试数据库连接...")
        if hasattr(self, 'test_button'):
            self.test_button.config(state=tk.DISABLED, text="测试中...")

        db_dir = self.db_dir.get()
        db_version = self.db_version.get()

        self.log_message(self.contacts_log, f"测试数据库连接: {db_dir}, 版本: {db_version}")

        if not db_dir:
            messagebox.showerror("错误", "请先选择数据库目录")
            self.log_message(self.contacts_log, "错误: 未选择数据库目录")
            self.load_status_var.set("未选择数据库目录")
            if hasattr(self, 'test_button'):
                self.test_button.config(state=tk.NORMAL, text="测试连接")
            return

        if not os.path.exists(db_dir):
            messagebox.showerror("错误", f"数据库目录不存在: {db_dir}")
            self.log_message(self.contacts_log, f"错误: 数据库目录不存在: {db_dir}")
            self.load_status_var.set("数据库目录不存在")
            if hasattr(self, 'test_button'):
                self.test_button.config(state=tk.NORMAL, text="测试连接")
            return

        # 在单独的线程中运行测试
        threading.Thread(target=self._test_connection_thread, args=(db_dir, db_version), daemon=True).start()

    def _test_connection_thread(self, db_dir, db_version):
        """测试数据库连接的线程函数"""
        try:
            # 列出目录内容
            self.log_message(self.contacts_log, f"目录内容: {os.listdir(db_dir)}")

            # 检查数据库文件
            db_files = [f for f in os.listdir(db_dir) if f.endswith('.db')]
            self.log_message(self.contacts_log, f"找到的数据库文件: {db_files}")

            if not db_files:
                self.root.after(0, lambda: messagebox.showerror("错误", "目录中没有找到数据库文件"))
                self.log_message(self.contacts_log, "错误: 目录中没有找到数据库文件")
                self.root.after(0, lambda: self.load_status_var.set("未找到数据库文件"))
                if hasattr(self, 'test_button'):
                    self.root.after(0, lambda: self.test_button.config(state=tk.NORMAL, text="测试连接"))
                return

            # 尝试创建数据库连接
            self.log_message(self.contacts_log, "尝试创建数据库连接...")
            conn = DatabaseConnection(db_dir, db_version)
            db_interface = conn.get_interface()

            if not db_interface:
                self.root.after(0, lambda: messagebox.showerror("错误", "数据库连接失败"))
                self.log_message(self.contacts_log, "错误: 数据库连接失败")
                self.root.after(0, lambda: self.load_status_var.set("数据库连接失败"))
                if hasattr(self, 'test_button'):
                    self.root.after(0, lambda: self.test_button.config(state=tk.NORMAL, text="测试连接"))
                return

            # 尝试获取联系人数量
            self.log_message(self.contacts_log, "尝试获取联系人数量...")
            try:
                contacts = db_interface.get_contacts()
                contact_count = len(contacts) if contacts else 0
                self.log_message(self.contacts_log, f"找到 {contact_count} 个联系人")

                # 保存数据库信息到配置
                try:
                    import config
                    self.config = config.add_recent_database(self.config, db_dir, db_version)
                    config.save_config(self.config)
                except ImportError:
                    pass

                # 显示成功消息
                success_msg = f"连接成功! 找到 {contact_count} 个联系人"
                self.root.after(0, lambda: messagebox.showinfo("测试成功", success_msg))
                self.root.after(0, lambda: self.load_status_var.set(success_msg))
            except Exception as e:
                self.log_message(self.contacts_log, f"获取联系人时出错: {str(e)}")
                self.log_message(self.contacts_log, traceback.format_exc())
                self.root.after(0, lambda: messagebox.showwarning("警告", f"数据库连接成功，但获取联系人时出错: {str(e)}"))
                self.root.after(0, lambda: self.load_status_var.set("连接成功，但获取联系人失败"))

            if hasattr(self, 'test_button'):
                self.root.after(0, lambda: self.test_button.config(state=tk.NORMAL, text="测试连接"))
        except Exception as e:
            self.log_message(self.contacts_log, f"测试连接时出错: {str(e)}")
            self.log_message(self.contacts_log, traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("错误", f"测试连接时出错: {str(e)}"))
            self.root.after(0, lambda: self.load_status_var.set("测试连接失败"))
            if hasattr(self, 'test_button'):
                self.root.after(0, lambda: self.test_button.config(state=tk.NORMAL, text="测试连接"))

    def start_decrypt(self):
        """开始数据库解密过程"""
        self.log_message(self.decrypt_log, "开始解密数据库...")
        self.status_var.set("正在解密数据库...")

        # 在单独的线程中运行解密以避免UI卡顿
        threading.Thread(target=self._decrypt_thread, daemon=True).start()

    def _decrypt_thread(self):
        """数据库解密的线程函数"""
        try:
            # 使用设置页面的解密版本值
            decrypt_version = getattr(self, 'decrypt_version', self.db_version).get()
            
            if decrypt_version == 3:
                self.log_message(self.decrypt_log, "解析微信3.x版本的数据库...")
                version_list_path = './wxManager/decrypt/version_list.json'
                try:
                    with open(version_list_path, "r", encoding="utf-8") as f:
                        version_list = json.loads(f.read())
                except Exception as e:
                    self.log_message(self.decrypt_log, f"读取版本列表失败: {str(e)}")
                    self.status_var.set("解密失败")
                    return

                r_3 = get_info_v3(version_list)
                if not r_3:
                    self.log_message(self.decrypt_log, "未找到微信3.x版本信息，请确保微信已启动")
                    self.status_var.set("解密失败")
                    return

                for wx_info in r_3:
                    self.log_message(self.decrypt_log, f"找到微信账号: {wx_info.wxid} ({wx_info.nick_name})")
                    me = Me()
                    me.wx_dir = wx_info.wx_dir
                    me.wxid = wx_info.wxid
                    me.name = wx_info.nick_name
                    info_data = me.to_json()
                    output_dir = wx_info.wxid
                    key = wx_info.key
                    if not key:
                        self.log_message(self.decrypt_log, "错误! 未找到key，请重启微信后再试")
                        continue

                    wx_dir = wx_info.wx_dir
                    self.log_message(self.decrypt_log, f"开始解密数据库文件，源目录: {wx_dir}")
                    decrypt_v3.decrypt_db_files(key, src_dir=wx_dir, dest_dir=output_dir)

                    # 导出的数据库在 output_dir/Msg 文件夹下，后面会用到
                    db_path = os.path.join(output_dir, "Msg")
                    with open(os.path.join(db_path, 'info.json'), 'w', encoding='utf-8') as f:
                        json.dump(info_data, f, ensure_ascii=False, indent=4)

                    self.log_message(self.decrypt_log, f"数据库解析成功，在{db_path}路径下")
                    self.db_dir.set(db_path)
                    
                    # 保存解密历史记录
                    try:
                        import config
                        self.config = config.add_decrypt_history(
                            self.config, wx_info.wxid, wx_info.nick_name, db_path, 3
                        )
                        # 更新最近数据库列表
                        self.config = config.add_recent_database(self.config, db_path, 3)
                        config.save_config(self.config)
                        
                        # 刷新历史记录列表
                        if hasattr(self, 'decrypt_history_listbox'):
                            self.decrypt_history_listbox.delete(0, tk.END)
                            for history_item in self.config.get("decrypt_history", []):
                                if isinstance(history_item, dict) and "wxid" in history_item:
                                    display_text = f"{history_item['name']} ({history_item['wxid']}) - 微信{history_item['version']}"
                                    self.decrypt_history_listbox.insert(tk.END, display_text)
                    except ImportError:
                        pass
            else:
                self.log_message(self.decrypt_log, "解析微信4.0版本的数据库...")
                r_4 = get_info_v4()
                if not r_4:
                    self.log_message(self.decrypt_log, "未找到微信4.0版本信息，请确保微信已启动")
                    self.status_var.set("解密失败")
                    return

                for wx_info in r_4:
                    self.log_message(self.decrypt_log, f"找到微信账号: {wx_info.wxid} ({wx_info.nick_name})")
                    me = Me()
                    me.wx_dir = wx_info.wx_dir
                    me.wxid = wx_info.wxid
                    me.name = wx_info.nick_name
                    me.xor_key = get_decode_code_v4(wx_info.wx_dir)
                    info_data = me.to_json()
                    output_dir = wx_info.wxid  # 数据库输出文件夹
                    key = wx_info.key
                    if not key:
                        self.log_message(self.decrypt_log, "错误! 未找到key，请重启微信后再试")
                        continue

                    wx_dir = wx_info.wx_dir
                    self.log_message(self.decrypt_log, f"开始解密数据库文件，源目录: {wx_dir}")
                    decrypt_v4.decrypt_db_files(key, src_dir=wx_dir, dest_dir=output_dir)

                    # 导出的数据库在 output_dir/db_storage 文件夹下，后面会用到
                    db_path = os.path.join(output_dir, "db_storage")
                    with open(os.path.join(db_path, 'info.json'), 'w', encoding='utf-8') as f:
                        json.dump(info_data, f, ensure_ascii=False, indent=4)

                    self.log_message(self.decrypt_log, f"数据库解析成功，在{db_path}路径下")
                    self.db_dir.set(db_path)
                    
                    # 保存解密历史记录
                    try:
                        import config
                        self.config = config.add_decrypt_history(
                            self.config, wx_info.wxid, wx_info.nick_name, db_path, 4
                        )
                        # 更新最近数据库列表
                        self.config = config.add_recent_database(self.config, db_path, 4)
                        config.save_config(self.config)
                        
                        # 刷新历史记录列表
                        if hasattr(self, 'decrypt_history_listbox'):
                            self.decrypt_history_listbox.delete(0, tk.END)
                            for history_item in self.config.get("decrypt_history", []):
                                if isinstance(history_item, dict) and "wxid" in history_item:
                                    display_text = f"{history_item['name']} ({history_item['wxid']}) - 微信{history_item['version']}"
                                    self.decrypt_history_listbox.insert(tk.END, display_text)
                    except ImportError:
                        pass

            self.status_var.set("数据库解密完成")
            # 自动切换到联系人管理标签页
            self.notebook.select(0)
            # 自动尝试连接数据库
            self.root.after(1000, self.test_database_connection)
        except Exception as e:
            self.log_message(self.decrypt_log, f"解密过程中出错: {str(e)}")
            self.log_message(self.decrypt_log, traceback.format_exc())
            self.status_var.set("解密失败")

    def save_current_config(self):
        """保存当前配置"""
        try:
            import config
            
            # 更新配置
            self.config["db_dir"] = self.db_dir.get()
            self.config["db_version"] = self.db_version.get()
            self.config["output_dir"] = self.output_dir.get()
            if hasattr(self, 'format_combobox') and self.format_combobox.get():
                self.config["last_export_format"] = self.format_combobox.get()
            
            # 保存配置
            config.save_config(self.config)
            self.log_message_console("配置已保存")
            messagebox.showinfo("提示", "设置已保存")
        except ImportError:
            self.log_message_console("未找到配置模块，无法保存配置")
            messagebox.showerror("错误", "无法保存配置：未找到配置模块")
        except Exception as e:
            self.log_message_console(f"保存配置出错: {str(e)}")
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")
            traceback.print_exc()

    def log_message_console(self, message):
        """直接在控制台输出日志，不使用GUI组件"""
        print(f"[WeChat Export] {message}")


if __name__ == "__main__":
    freeze_support()  # Required for multiprocessing
    root = tk.Tk()
    app = WeChatExportGUI(root)
    root.mainloop()
