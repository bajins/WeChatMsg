#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
微信聊天记录周报生成API客户端
用于与微服务通信，生成聊天记录周报图片
"""

import os
import json
import requests
from typing import Dict, List, Optional, Union, Any
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WeeklyReportClient")

class WeeklyReportClient:
    """
    周报生成API客户端
    用于与微服务通信，生成聊天记录周报图片
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        初始化API客户端
        
        Args:
            base_url: API服务器基础URL，默认为http://localhost:8000
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        # 设置超时时间（连接超时5秒，读取超时30秒）
        self.timeout = (10, 180)
        
    def health_check(self) -> bool:
        """
        检查API服务是否可用
        
        Returns:
            bool: 服务是否可用
        """
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            return False
    
    def get_templates(self) -> List[str]:
        """
        获取可用的报告模板列表
        
        Returns:
            List[str]: 模板名称列表
        """
        try:
            response = self.session.get(f"{self.base_url}/api/templates", timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"获取模板列表失败: {response.status_code} {response.text}")
                return []
        except Exception as e:
            logger.error(f"获取模板列表异常: {str(e)}")
            return []
    
    def generate_report(self, 
                        chat_content: str, 
                        template_name: str = "default.txt", 
                        chat_file_name: Optional[str] = None,
                        convert_to_image: bool = True,
                        model: str = "gemini-2.5-pro-exp-03-25") -> Dict[str, Any]:
        """
        生成聊天记录周报
        
        Args:
            chat_content: 聊天记录内容
            template_name: 模板名称，默认为default.txt
            chat_file_name: 聊天文件名称，用于提取群聊名称
            convert_to_image: 是否将HTML转换为图片
            model: 使用的模型名称
            
        Returns:
            Dict: 包含生成结果的字典，包括HTML内容、HTML文件路径、图片文件路径等
        """
        try:
            payload = {
                "chat_content": chat_content,
                "template_name": template_name,
                "chat_file_name": chat_file_name,
                "convert_to_image": convert_to_image,
                "model": model
            }
            
            response = self.session.post(
                f"{self.base_url}/api/daily-report", 
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"生成报告失败: {response.status_code} {response.text}")
                return {"success": False, "message": f"API错误: {response.status_code}"}
        except Exception as e:
            logger.error(f"生成报告异常: {str(e)}")
            return {"success": False, "message": f"请求异常: {str(e)}"}
    
    def get_image(self, image_filename: str) -> Optional[bytes]:
        """
        获取生成的图片
        
        Args:
            image_filename: 图片文件名
            
        Returns:
            Optional[bytes]: 图片二进制数据，如果获取失败则返回None
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/image/{image_filename}", 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"获取图片失败: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logger.error(f"获取图片异常: {str(e)}")
            return None
    
    def save_image(self, image_filename: str, save_path: str) -> bool:
        """
        下载并保存生成的图片
        
        Args:
            image_filename: 图片文件名
            save_path: 保存路径
            
        Returns:
            bool: 是否保存成功
        """
        image_data = self.get_image(image_filename)
        if image_data:
            try:
                # 确保目录存在
                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                
                with open(save_path, 'wb') as f:
                    f.write(image_data)
                return True
            except Exception as e:
                logger.error(f"保存图片异常: {str(e)}")
                return False
        return False
    
    def html_to_image(self, html_content: str = None, html_file_path: str = None, png_file_path: str = None) -> Dict[str, Any]:
        """
        将HTML转换为图片
        
        Args:
            html_content: HTML内容
            html_file_path: HTML文件路径
            png_file_path: 输出PNG文件路径
            
        Returns:
            Dict: 包含转换结果的字典
        """
        try:
            payload = {}
            if html_content:
                payload["html_content"] = html_content
            if html_file_path:
                payload["html_file_path"] = html_file_path
            if png_file_path:
                payload["png_file_path"] = png_file_path
                
            response = self.session.post(
                f"{self.base_url}/api/html/convert", 
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"HTML转图片失败: {response.status_code} {response.text}")
                return {"success": False, "message": f"API错误: {response.status_code}"}
        except Exception as e:
            logger.error(f"HTML转图片异常: {str(e)}")
            return {"success": False, "message": f"请求异常: {str(e)}"}


# 简单的使用示例
if __name__ == "__main__":
    client = WeeklyReportClient()
    
    # 检查服务是否可用
    if client.health_check():
        print("服务正常运行")
        
        # 获取可用模板
        templates = client.get_templates()
        print(f"可用模板: {templates}")
        
        # 生成报告示例
        chat_content = """
        张三: 大家好，这周我们需要讨论一下项目进度
        李四: 好的，我这边已经完成了数据库设计
        王五: 我负责的前端页面也已经完成了70%
        张三: 太好了，看来我们进度不错
        李四: 是的，不过还有一些接口需要调整
        王五: 没问题，我们可以明天一起讨论一下
        """
        
        result = client.generate_report(
            chat_content=chat_content,
            template_name="default.txt" if "default.txt" in templates else templates[0] if templates else "default.txt",
            chat_file_name="项目讨论群",
            convert_to_image=True
        )
        
        if result.get("success"):
            print(f"报告生成成功: {result}")
            
            # 如果生成了图片，保存到本地
            if result.get("png_file_path"):
                image_filename = os.path.basename(result["png_file_path"])
                saved = client.save_image(image_filename, f"./output/{image_filename}")
                if saved:
                    print(f"图片已保存到 ./output/{image_filename}")
        else:
            print(f"报告生成失败: {result}")
    else:
        print("服务不可用，请检查API服务是否启动")
