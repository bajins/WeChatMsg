#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
微信聊天记录周报生成GUI组件
用于在主界面中集成周报生成功能
"""

import os
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import scrolledtext
import traceback
from PIL import Image, ImageTk
import webbrowser

# 导入API客户端
from api_client import WeeklyReportClient

class WeeklyReportFrame(ttk.Frame):
    """周报生成界面组件"""

    def __init__(self, parent, database=None, contact=None, config=None):
        """
        初始化周报生成界面

        Args:
            parent: 父级窗口
            database: 数据库连接
            contact: 当前选中的联系人
            config: 配置信息
        """
        super().__init__(parent)
        self.parent = parent
        self.database = database
        self.contact = contact
        self.config = config or {}

        # 创建API客户端
        self.api_client = WeeklyReportClient(
            base_url=self.config.get("report_api_url", "http://localhost:8000")
        )

        # 创建界面
        self.create_widgets()

        # 检查服务状态
        self.check_service_status()

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.LabelFrame(self, text="聊天记录周报生成")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 服务状态指示
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(status_frame, text="服务状态:").pack(side=tk.LEFT, padx=5)
        self.status_var = tk.StringVar(value="检查中...")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.refresh_btn = ttk.Button(status_frame, text="刷新", command=self.check_service_status)
        self.refresh_btn.pack(side=tk.RIGHT, padx=5)

        # 设置区域
        settings_frame = ttk.LabelFrame(main_frame, text="生成设置")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # 模板选择
        template_frame = ttk.Frame(settings_frame)
        template_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(template_frame, text="报告模板:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.template_var, state="readonly")
        self.template_combo.grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)

        # 数据源选择
        source_frame = ttk.Frame(settings_frame)
        source_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(source_frame, text="数据来源:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        source_options_frame = ttk.Frame(source_frame)
        source_options_frame.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        self.data_source_var = tk.StringVar(value="database")
        ttk.Radiobutton(source_options_frame, text="数据库", variable=self.data_source_var,
                        value="database", command=self._toggle_data_source).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(source_options_frame, text="聊天记录文件", variable=self.data_source_var,
                        value="file", command=self._toggle_data_source).pack(side=tk.LEFT, padx=5)

        # 文件选择框
        file_frame = ttk.Frame(settings_frame)
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        self.file_frame = file_frame  # 保存引用以便控制显示/隐藏

        ttk.Label(file_frame, text="聊天记录文件:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        file_select_frame = ttk.Frame(file_frame)
        file_select_frame.grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)

        self.chat_file_path = tk.StringVar()
        ttk.Entry(file_select_frame, textvariable=self.chat_file_path, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(file_select_frame, text="浏览...", command=self._browse_chat_file).pack(side=tk.RIGHT, padx=5)

        # 时间范围选择
        time_frame = ttk.Frame(settings_frame)
        time_frame.pack(fill=tk.X, padx=5, pady=5)
        self.time_frame = time_frame  # 保存引用以便控制显示/隐藏

        ttk.Label(time_frame, text="时间范围:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        time_options_frame = ttk.Frame(time_frame)
        time_options_frame.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        self.time_range_var = tk.StringVar(value="last_week")
        ttk.Radiobutton(time_options_frame, text="最近一周", variable=self.time_range_var, value="last_week").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(time_options_frame, text="最近一月", variable=self.time_range_var, value="last_month").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(time_options_frame, text="全部记录", variable=self.time_range_var, value="all").pack(side=tk.LEFT, padx=5)

        # 初始化界面状态
        self._toggle_data_source()

        # 输出选项
        output_frame = ttk.Frame(settings_frame)
        output_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(output_frame, text="输出选项:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        output_options_frame = ttk.Frame(output_frame)
        output_options_frame.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        self.convert_to_image_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(output_options_frame, text="生成图片", variable=self.convert_to_image_var).pack(side=tk.LEFT, padx=5)

        self.open_after_generate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(output_options_frame, text="生成后打开", variable=self.open_after_generate_var).pack(side=tk.LEFT, padx=5)

        # 生成按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=10)

        self.generate_btn = ttk.Button(btn_frame, text="生成周报", command=self.generate_report)
        self.generate_btn.pack(side=tk.RIGHT, padx=5)

        # 进度条
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 预览区域
        preview_frame = ttk.LabelFrame(main_frame, text="预览")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.preview_canvas = tk.Canvas(preview_frame, bg="white")
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_canvas.configure(yscrollcommand=scrollbar.set)

        # 设置预览画布的滚动区域
        self.preview_frame = ttk.Frame(self.preview_canvas)
        self.preview_canvas.create_window((0, 0), window=self.preview_frame, anchor=tk.NW)

        # 配置滚动区域
        def configure_scroll_region(_):
            # 使用下划线作为参数名，表示我们不使用这个参数
            self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

        self.preview_frame.bind("<Configure>", configure_scroll_region)

    def _toggle_data_source(self):
        """根据数据源选择切换界面显示"""
        data_source = self.data_source_var.get()

        if data_source == "database":
            # 使用数据库作为数据源
            self.file_frame.pack_forget()  # 隐藏文件选择框
            self.time_frame.pack(fill=tk.X, padx=5, pady=5)  # 显示时间范围选择
        else:
            # 使用文件作为数据源
            self.file_frame.pack(fill=tk.X, padx=5, pady=5, after=self.file_frame.master.winfo_children()[1])  # 显示文件选择框
            self.time_frame.pack_forget()  # 隐藏时间范围选择

    def _browse_chat_file(self):
        """浏览并选择聊天记录文件"""
        filetypes = [
            ("文本文件", "*.txt"),
            ("HTML文件", "*.html"),
            ("所有文件", "*.*")
        ]

        file_path = filedialog.askopenfilename(
            title="选择聊天记录文件",
            filetypes=filetypes,
            initialdir=self.config.get("output_dir", "./data/")
        )

        if file_path:
            self.chat_file_path.set(file_path)
            self.log(f"已选择聊天记录文件: {file_path}")

    def check_service_status(self):
        """检查服务状态"""
        self.log("正在检查周报生成服务状态...")
        self.status_var.set("检查中...")
        self.status_label.config(foreground="black")

        def check_task():
            try:
                if self.api_client.health_check():
                    self.status_var.set("在线")
                    self.status_label.config(foreground="green")
                    self.log("服务状态: 在线")

                    # 获取模板列表
                    templates = self.api_client.get_templates()
                    if templates:
                        self.template_combo['values'] = templates
                        self.template_combo.current(0)
                        self.log(f"获取到{len(templates)}个模板")
                    else:
                        self.log("未获取到模板，将使用默认模板")
                        self.template_combo['values'] = ["default.txt"]
                        self.template_combo.current(0)
                else:
                    self.status_var.set("离线")
                    self.status_label.config(foreground="red")
                    self.log("服务状态: 离线，请确保周报生成服务已启动")
            except Exception as e:
                self.status_var.set("错误")
                self.status_label.config(foreground="red")
                self.log(f"检查服务状态时出错: {str(e)}")

        threading.Thread(target=check_task).start()

    def log(self, message):
        """添加日志"""
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)

    def get_time_range(self):
        """获取时间范围"""
        time_range_value = self.time_range_var.get()
        now = time.time()

        if time_range_value == "last_week":
            # 最近一周
            start_time = now - 7 * 24 * 60 * 60
            return [time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))]
        elif time_range_value == "last_month":
            # 最近一月
            start_time = now - 30 * 24 * 60 * 60
            return [time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))]
        else:
            # 全部记录
            return None

    def generate_report(self):
        """生成周报"""
        # 检查数据源
        data_source = self.data_source_var.get()

        if data_source == "database":
            # 使用数据库作为数据源
            if not self.database:
                messagebox.showwarning("提示", "请先加载数据库")
                return

            if not self.contact:
                messagebox.showwarning("提示", "请先选择一个联系人")
                return
        else:
            # 使用文件作为数据源
            if not self.chat_file_path.get():
                messagebox.showwarning("提示", "请先选择聊天记录文件")
                return

            if not os.path.exists(self.chat_file_path.get()):
                messagebox.showwarning("提示", "所选文件不存在")
                return

        if self.status_var.get() != "在线":
            if not messagebox.askyesno("警告", "周报生成服务似乎不在线，是否继续尝试生成？"):
                return

        self.progress_var.set(0)

        # 获取数据源
        data_source = self.data_source_var.get()

        # 根据数据源设置联系人名称和日志信息
        if data_source == "database":
            contact_name = self.contact.remark if hasattr(self.contact, 'remark') else self.contact.nickname if hasattr(self.contact, 'nickname') else "未知联系人"
            self.log(f"开始为 {contact_name} 生成周报...")
        else:
            file_path = self.chat_file_path.get()
            file_name = os.path.basename(file_path)
            contact_name = os.path.splitext(file_name)[0]  # 使用文件名作为联系人名称
            self.log(f"开始从文件 {file_name} 生成周报...")

        # 禁用生成按钮
        self.generate_btn.config(state=tk.DISABLED)

        def generate_task():
            # 声明外部变量
            nonlocal data_source, contact_name

            try:
                chat_content = ""

                if data_source == "database":
                    # 从数据库获取聊天记录
                    time_range = self.get_time_range()
                    self.log(f"获取时间范围: {time_range if time_range else '全部'}")

                    self.progress_var.set(10)
                    self.log("正在从数据库获取聊天记录...")

                    messages = self.database.get_messages(self.contact.wxid, time_range=time_range)
                    if not messages:
                        self.log("未找到聊天记录")
                        messagebox.showinfo("提示", "所选时间范围内没有聊天记录")
                        self.generate_btn.config(state=tk.NORMAL)
                        return

                    self.log(f"获取到 {len(messages)} 条聊天记录")

                    # 将消息转换为文本格式
                    chat_content = self.format_messages_for_report(messages)
                else:
                    # 从文件读取聊天记录
                    self.progress_var.set(10)
                    self.log("正在从文件读取聊天记录...")

                    try:
                        with open(self.chat_file_path.get(), 'r', encoding='utf-8') as f:
                            chat_content = f.read()

                        if not chat_content.strip():
                            self.log("文件内容为空")
                            messagebox.showinfo("提示", "所选文件内容为空")
                            self.generate_btn.config(state=tk.NORMAL)
                            return

                        self.log(f"成功读取文件内容，大小: {len(chat_content)} 字节")
                    except Exception as e:
                        self.log(f"读取文件时出错: {str(e)}")
                        messagebox.showerror("错误", f"读取文件时出错: {str(e)}")
                        self.generate_btn.config(state=tk.NORMAL)
                        return

                self.progress_var.set(30)

                self.progress_var.set(50)
                self.log("正在生成周报...")

                # 获取联系人名称
                contact_name = self.contact.remark if hasattr(self.contact, 'remark') else self.contact.nickname if hasattr(self.contact, 'nickname') else "未知联系人"

                # 调用API生成周报
                result = self.api_client.generate_report(
                    chat_content=chat_content,
                    template_name=self.template_var.get(),
                    chat_file_name=contact_name,
                    convert_to_image=self.convert_to_image_var.get()
                )

                self.progress_var.set(80)

                if result.get("success"):
                    self.log("周报生成成功")

                    # 使用外部作用域的 data_source 变量，不需要重新获取

                    # 根据数据源获取联系人名称
                    if data_source == "database":
                        contact_name = self.contact.remark if hasattr(self.contact, 'remark') else self.contact.nickname if hasattr(self.contact, 'nickname') else "未知联系人"
                    else:
                        file_path = self.chat_file_path.get()
                        file_name = os.path.basename(file_path)
                        contact_name = os.path.splitext(file_name)[0]  # 使用文件名作为联系人名称

                    # 保存结果
                    output_dir = os.path.join(self.config.get("output_dir", "./data"), "reports")
                    os.makedirs(output_dir, exist_ok=True)

                    # 生成时间戳
                    timestamp = time.strftime("%Y%m%d_%H%M%S")

                    # 保存HTML
                    html_path = os.path.join(output_dir, f"{contact_name}_report_{timestamp}.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(result.get("html_content", ""))

                    self.log(f"HTML报告已保存到: {html_path}")

                    # 如果生成了图片，保存图片
                    image_path = None
                    if result.get("png_file_path") and self.convert_to_image_var.get():
                        image_filename = os.path.basename(result["png_file_path"])
                        image_path = os.path.join(output_dir, f"{contact_name}_report_{timestamp}.png")

                        if self.api_client.save_image(image_filename, image_path):
                            self.log(f"图片报告已保存到: {image_path}")

                            # 显示预览
                            self.show_preview(image_path)
                        else:
                            self.log("图片保存失败")

                    self.progress_var.set(100)

                    # 如果设置了生成后打开，则打开文件
                    if self.open_after_generate_var.get():
                        if image_path and os.path.exists(image_path):
                            webbrowser.open(f"file://{os.path.abspath(image_path)}")
                        elif html_path and os.path.exists(html_path):
                            webbrowser.open(f"file://{os.path.abspath(html_path)}")
                else:
                    self.log(f"周报生成失败: {result.get('message', '未知错误')}")
                    messagebox.showerror("错误", f"周报生成失败: {result.get('message', '未知错误')}")

            except Exception as e:
                self.log(f"生成周报时出错: {str(e)}")
                self.log(traceback.format_exc())
                messagebox.showerror("错误", f"生成周报时出错: {str(e)}")

            finally:
                # 恢复生成按钮
                self.generate_btn.config(state=tk.NORMAL)

        threading.Thread(target=generate_task).start()

    def format_messages_for_report(self, messages):
        """
        将消息格式化为周报生成服务需要的格式

        Args:
            messages: 消息列表

        Returns:
            str: 格式化后的文本
        """
        formatted_messages = []

        try:
            for message in messages:
                try:
                    # 根据消息类型进行不同处理
                    msg_type = message.type if hasattr(message, 'type') else None
                    sender_name = message.display_name if hasattr(message, 'display_name') else "未知用户"
                    content = message.content if hasattr(message, 'content') else ""

                    # 只处理文本消息
                    if msg_type == 1:  # 文本消息
                        formatted_messages.append(f"{sender_name}: {content}")
                except Exception as e:
                    self.log(f"处理消息时出错: {str(e)}")
                    continue
        except Exception as e:
            self.log(f"格式化消息时出错: {str(e)}")

        if not formatted_messages:
            self.log("警告: 没有找到可用的文本消息")
            formatted_messages.append("没有找到可用的文本消息")

        return "\n".join(formatted_messages)

    def show_preview(self, image_path):
        """
        显示预览图片

        Args:
            image_path: 图片路径
        """
        try:
            # 清除之前的预览
            for widget in self.preview_frame.winfo_children():
                widget.destroy()

            # 加载图片
            img = Image.open(image_path)

            # 调整图片大小以适应预览区域
            canvas_width = self.preview_canvas.winfo_width()
            if canvas_width < 100:  # 如果画布还没有完全初始化
                canvas_width = 600

            # 计算缩放比例
            ratio = canvas_width / img.width
            new_height = int(img.height * ratio)

            img = img.resize((canvas_width, new_height), Image.LANCZOS)

            # 转换为PhotoImage
            photo = ImageTk.PhotoImage(img)

            # 创建标签显示图片
            label = ttk.Label(self.preview_frame, image=photo)
            label.image = photo  # 保持引用
            label.pack(fill=tk.BOTH, expand=True)

            self.log("预览图片已加载")
        except Exception as e:
            self.log(f"加载预览图片时出错: {str(e)}")


# 测试代码
if __name__ == "__main__":
    root = tk.Tk()
    root.title("周报生成测试")
    root.geometry("800x600")

    frame = WeeklyReportFrame(root)
    frame.pack(fill=tk.BOTH, expand=True)

    root.mainloop()
