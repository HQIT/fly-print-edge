"""
fly-print-cloud WebSocket客户端
接收云端打印任务和实时消息
"""

import asyncio
import websockets
import json
import threading
import time
from typing import Dict, Any, Callable, Optional
from cloud_auth import CloudAuthClient


class CloudWebSocketClient:
    """云端WebSocket客户端"""
    
    def __init__(self, websocket_url: str, auth_client: CloudAuthClient):
        self.websocket_url = websocket_url
        self.auth_client = auth_client
        self.websocket = None
        self.running = False
        self.thread = None
        self.message_handlers = {}
        self.reconnect_interval = 5  # 重连间隔秒数
        
    def add_message_handler(self, message_type: str, handler: Callable[[Dict[str, Any]], None]):
        """添加消息处理器"""
        self.message_handlers[message_type] = handler
        print(f"📝 [DEBUG] 添加WebSocket消息处理器: {message_type}")
    
    def start(self):
        """启动WebSocket客户端"""
        if self.running:
            print("⚠️ [DEBUG] WebSocket客户端已经在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()
        print("🚀 [DEBUG] WebSocket客户端已启动")
    
    def stop(self):
        """停止WebSocket客户端"""
        self.running = False
        # 不直接关闭WebSocket连接，让异步循环自然结束
        # WebSocket连接会在_connect_and_listen循环结束时自动关闭
        print("🛑 [DEBUG] WebSocket客户端已停止")
    
    def _run_async_loop(self):
        """在单独线程中运行异步循环"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect_and_listen())
        except Exception as e:
            print(f"❌ [DEBUG] WebSocket异步循环异常: {e}")
        finally:
            loop.close()
    
    async def _connect_and_listen(self):
        """连接WebSocket并监听消息"""
        while self.running:
            try:
                print(f"🔌 [DEBUG] 连接WebSocket: {self.websocket_url}")
                
                # 获取认证头
                token = self.auth_client.get_access_token()
                if not token:
                    print("❌ [DEBUG] 无法获取access token，等待重试")
                    await asyncio.sleep(self.reconnect_interval)
                    continue
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Connection": "Upgrade",
                    "Upgrade": "websocket"
                }
                
                async with websockets.connect(
                    self.websocket_url,
                    additional_headers=headers,
                    ping_interval=30,
                    ping_timeout=10
                ) as websocket:
                    self.websocket = websocket
                    print("✅ [DEBUG] WebSocket连接成功")
                    
                    # 监听消息
                    print("👂 [DEBUG] 开始监听WebSocket消息...")
                    async for message in websocket:
                        try:
                            print(f"📨 [DEBUG] 收到WebSocket消息: {message}")
                            await self._handle_message(message)
                        except Exception as e:
                            print(f"❌ [DEBUG] 处理WebSocket消息异常: {e}")
                            
            except websockets.exceptions.ConnectionClosed as e:
                print(f"🔌 [DEBUG] WebSocket连接关闭: {e}")
            except Exception as e:
                print(f"❌ [DEBUG] WebSocket连接异常: {e}")
            
            if self.running:
                print(f"🔄 [DEBUG] {self.reconnect_interval}秒后重连WebSocket")
                await asyncio.sleep(self.reconnect_interval)
    
    async def _handle_message(self, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            message_type = data.get("type", "unknown")
            
            print(f"📨 [DEBUG] 收到WebSocket消息: {message_type}")
            
            # 调用对应的消息处理器
            if message_type in self.message_handlers:
                handler = self.message_handlers[message_type]
                # 在线程池中执行处理器，避免阻塞WebSocket
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, data)
            else:
                print(f"⚠️ [DEBUG] 未找到消息类型处理器: {message_type}")
                
        except json.JSONDecodeError as e:
            print(f"❌ [DEBUG] WebSocket消息JSON解析失败: {e}")
        except Exception as e:
            print(f"❌ [DEBUG] 处理WebSocket消息异常: {e}")
    
    async def _send_message(self, data: Dict[str, Any]):
        """发送消息到WebSocket"""
        if self.websocket:
            try:
                message = json.dumps(data)
                await self.websocket.send(message)
                print(f"📤 [DEBUG] 发送WebSocket消息: {data.get('type', 'unknown')}")
            except Exception as e:
                print(f"❌ [DEBUG] 发送WebSocket消息失败: {e}")
    
    def send_message_sync(self, data: Dict[str, Any]):
        """同步发送消息（在其他线程中调用）"""
        if self.websocket:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._send_message(data))
                loop.close()
            except Exception as e:
                print(f"❌ [DEBUG] 同步发送WebSocket消息失败: {e}")
    
    def send_printer_status(self, node_id: str, printer_id: str, status: str, queue_length: int, error_code: Optional[str] = None):
        """发送打印机状态消息"""
        from datetime import datetime, timezone
        message = {
            "type": "printer_status",
            "node_id": node_id,
            "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "data": {
                "printer_id": printer_id,
                "status": status,
                "queue_length": queue_length,
                "error_code": error_code,
                "supplies": {}
            }
        }
        self.send_message_sync(message)


class PrintJobHandler:
    """打印任务处理器"""
    
    def __init__(self, printer_manager, api_client):
        self.printer_manager = printer_manager
        self.api_client = api_client
    
    def handle_print_job(self, data: Dict[str, Any]):
        """处理打印任务消息"""
        try:
            job_id = data.get("job_id")
            printer_name = data.get("printer_name")
            file_url = data.get("file_url")
            job_name = data.get("job_name", f"CloudJob_{job_id}")
            print_options = data.get("print_options", {})
            
            print(f"🖨️ [DEBUG] 处理云端打印任务:")
            print(f"  任务ID: {job_id}")
            print(f"  打印机: {printer_name}")
            print(f"  文件URL: {file_url}")
            
            if not all([job_id, printer_name, file_url]):
                print("❌ [DEBUG] 打印任务参数不完整")
                return
            
            # 下载文件
            file_path = self._download_print_file(file_url, job_id)
            if not file_path:
                self._report_job_failure(job_id, "文件下载失败")
                return
            
            # 提交打印任务
            result = self.printer_manager.submit_print_job(
                printer_name, file_path, job_name, print_options
            )
            
            if result.get("success"):
                print(f"✅ [DEBUG] 云端打印任务提交成功: {job_id}")
                # 可以在这里添加任务完成监控
            else:
                error_msg = result.get("message", "未知错误")
                print(f"❌ [DEBUG] 云端打印任务提交失败: {error_msg}")
                self._report_job_failure(job_id, error_msg)
                
        except Exception as e:
            print(f"❌ [DEBUG] 处理云端打印任务异常: {e}")
            self._report_job_failure(data.get("job_id"), str(e))
    
    def _download_print_file(self, file_url: str, job_id: str) -> Optional[str]:
        """下载打印文件"""
        try:
            import requests
            import tempfile
            import os
            
            print(f"📥 [DEBUG] 下载打印文件: {file_url}")
            
            # 获取认证头
            headers = self.api_client.auth_client.get_auth_headers()
            
            response = requests.get(file_url, headers=headers, timeout=30)
            if response.status_code == 200:
                # 保存到临时文件
                temp_dir = tempfile.gettempdir()
                file_extension = os.path.splitext(file_url)[1] or '.pdf'
                temp_file_path = os.path.join(temp_dir, f"cloud_job_{job_id}{file_extension}")
                
                with open(temp_file_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"✅ [DEBUG] 文件下载成功: {temp_file_path}")
                return temp_file_path
            else:
                print(f"❌ [DEBUG] 文件下载失败: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ [DEBUG] 下载打印文件异常: {e}")
            return None
    
    def _report_job_failure(self, job_id: str, error_message: str):
        """报告任务失败"""
        if job_id:
            self.api_client.report_print_job_result(job_id, False, error_message)
