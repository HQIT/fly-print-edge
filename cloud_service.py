"""
fly-print-cloud 云端服务集成模块
整合所有云端功能：认证、注册、心跳、WebSocket等
"""

import time
from typing import Dict, Any, Optional
from cloud_auth import CloudAuthClient
from cloud_api_client import CloudAPIClient
from cloud_websocket_client import CloudWebSocketClient, PrintJobHandler
from cloud_heartbeat_service import HeartbeatService
from edge_node_info import EdgeNodeInfo


class CloudService:
    """云端服务管理器"""
    
    def __init__(self, config: Dict[str, Any], printer_manager=None):
        self.config = config
        self.printer_manager = printer_manager
        self.enabled = config.get("enabled", False)
        
        # 初始化各个组件
        self.auth_client = None
        self.api_client = None
        self.websocket_client = None
        self.heartbeat_service = None
        self.print_job_handler = None
        
        # 状态跟踪
        self.registered = False
        self.node_id = None
        
        if self.enabled:
            self._initialize_components()
    
    def _initialize_components(self):
        """初始化云端服务组件"""
        try:
            print("🌐 [DEBUG] 初始化云端服务组件...")
            
            # 初始化认证客户端
            self.auth_client = CloudAuthClient(
                auth_url=self.config["auth_url"],
                client_id=self.config["client_id"],
                client_secret=self.config["client_secret"]
            )
            
            # 初始化API客户端
            self.api_client = CloudAPIClient(
                base_url=self.config["base_url"],
                auth_client=self.auth_client
            )
            
            # 初始化心跳服务
            heartbeat_interval = self.config.get("heartbeat_interval", 30)
            self.heartbeat_service = HeartbeatService(
                api_client=self.api_client,
                interval=heartbeat_interval
            )
            
            # 初始化打印任务处理器
            if self.printer_manager:
                self.print_job_handler = PrintJobHandler(
                    printer_manager=self.printer_manager,
                    api_client=self.api_client
                )
            
            print("✅ [DEBUG] 云端服务组件初始化完成")
            
        except Exception as e:
            print(f"❌ [DEBUG] 云端服务组件初始化失败: {e}")
            self.enabled = False
    
    def start(self) -> Dict[str, Any]:
        """启动云端服务"""
        if not self.enabled:
            return {"success": False, "message": "云端服务未启用"}
        
        try:
            print("🚀 [DEBUG] 启动云端服务...")
            
            # 1. 如果启用自动注册，先注册边缘节点
            if self.config.get("auto_register", True):
                register_result = self._register_node()
                if not register_result["success"]:
                    return register_result
            
            # 2. 启动心跳服务
            self.heartbeat_service.start()
            
            # 3. 如果启用自动注册打印机，注册当前管理的打印机
            if self.config.get("auto_register_printers", True) and self.printer_manager:
                self._register_current_printers()
            
            # 4. 启动WebSocket客户端
            self._start_websocket()
            
            print("✅ [DEBUG] 云端服务启动成功")
            return {"success": True, "message": "云端服务启动成功", "node_id": self.node_id}
            
        except Exception as e:
            print(f"❌ [DEBUG] 云端服务启动失败: {e}")
            return {"success": False, "message": str(e)}
    
    def stop(self):
        """停止云端服务"""
        print("🛑 [DEBUG] 停止云端服务...")
        
        if self.websocket_client:
            self.websocket_client.stop()
        
        if self.heartbeat_service:
            self.heartbeat_service.stop()
        
        self.registered = False
        print("✅ [DEBUG] 云端服务已停止")
    
    def _register_node(self) -> Dict[str, Any]:
        """注册边缘节点"""
        try:
            print("📝 [DEBUG] 注册边缘节点...")
            
            node_name = self.config.get("node_name") or None
            location = self.config.get("location") or None
            
            result = self.api_client.register_edge_node(node_name, location)
            
            if result["success"]:
                self.registered = True
                self.node_id = result["node_id"]
                print(f"✅ [DEBUG] 边缘节点注册成功: {self.node_id}")
                return {"success": True, "node_id": self.node_id}
            else:
                print(f"❌ [DEBUG] 边缘节点注册失败: {result.get('error')}")
                return {"success": False, "message": result.get("error")}
                
        except Exception as e:
            print(f"❌ [DEBUG] 边缘节点注册异常: {e}")
            return {"success": False, "message": str(e)}
    
    def _register_current_printers(self):
        """注册当前管理的打印机"""
        try:
            if not self.printer_manager:
                return
            
            print("🖨️ [DEBUG] 注册当前管理的打印机...")
            
            # 获取当前管理的打印机
            managed_printers = self.printer_manager.config.get_managed_printers()
            
            if not managed_printers:
                print("📝 [DEBUG] 没有管理的打印机需要注册")
                return
            
            # 获取打印机详细信息
            printer_data = []
            for printer in managed_printers:
                printer_name = printer.get("name")
                if printer_name:
                    # 获取打印机状态和能力
                    status = self.printer_manager.get_printer_status(printer_name)
                    capabilities = self.printer_manager.get_printer_capabilities(printer_name)
                    
                    printer_info = {
                        "name": printer_name,
                        "type": printer.get("type", "local"),
                        "location": printer.get("location", "本地"),
                        "make_model": printer.get("make_model", ""),
                        "status": status,
                        "capabilities": capabilities,
                        "enabled": printer.get("enabled", True)
                    }
                    printer_data.append(printer_info)
            
            # 注册到云端
            result = self.api_client.register_printers(printer_data)
            
            if result["success"]:
                print(f"✅ [DEBUG] 打印机注册成功，数量: {len(printer_data)}")
            else:
                print(f"❌ [DEBUG] 打印机注册失败: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ [DEBUG] 注册打印机异常: {e}")
    
    def _start_websocket(self):
        """启动WebSocket客户端"""
        try:
            if not self.registered:
                print("⚠️ [DEBUG] 节点未注册，跳过WebSocket连接")
                return
            
            print("🔌 [DEBUG] 启动WebSocket客户端...")
            
            # 获取WebSocket URL
            ws_url = self.api_client.get_websocket_url()
            if not ws_url:
                print("❌ [DEBUG] 无法获取WebSocket URL")
                return
            
            # 初始化WebSocket客户端
            self.websocket_client = CloudWebSocketClient(ws_url, self.auth_client)
            
            # 添加消息处理器
            if self.print_job_handler:
                self.websocket_client.add_message_handler("print_job", self.print_job_handler.handle_print_job)
            
            # 启动WebSocket客户端
            self.websocket_client.start()
            
            print("✅ [DEBUG] WebSocket客户端启动成功")
            
        except Exception as e:
            print(f"❌ [DEBUG] WebSocket客户端启动失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取云端服务状态"""
        status = {
            "enabled": self.enabled,
            "registered": self.registered,
            "node_id": self.node_id,
            "heartbeat": None,
            "websocket": None
        }
        
        if self.heartbeat_service:
            status["heartbeat"] = self.heartbeat_service.get_status()
        
        if self.websocket_client:
            status["websocket"] = {
                "running": self.websocket_client.running,
                "url": self.websocket_client.websocket_url
            }
        
        return status
    
    def force_heartbeat(self) -> Dict[str, Any]:
        """强制发送心跳"""
        if not self.heartbeat_service:
            return {"success": False, "message": "心跳服务未启动"}
        
        return self.heartbeat_service.force_heartbeat()
    
    def register_printer(self, printer_info: Dict[str, Any]) -> Dict[str, Any]:
        """注册单个打印机到云端"""
        if not self.registered:
            return {"success": False, "message": "节点未注册"}
        
        try:
            # 获取打印机详细信息
            printer_name = printer_info.get("name")
            if not printer_name:
                return {"success": False, "message": "打印机名称不能为空"}
            
            # 获取打印机状态和能力
            status = self.printer_manager.get_printer_status(printer_name)
            capabilities = self.printer_manager.get_printer_capabilities(printer_name)
            
            enhanced_info = {
                **printer_info,
                "status": status,
                "capabilities": capabilities
            }
            
            result = self.api_client.register_printers([enhanced_info])
            return result
            
        except Exception as e:
            print(f"❌ [DEBUG] 注册打印机异常: {e}")
            return {"success": False, "message": str(e)}
    
    def update_printer_status(self, printer_name: str) -> Dict[str, Any]:
        """更新打印机状态到云端"""
        if not self.registered or not self.printer_manager:
            return {"success": False, "message": "服务未就绪"}
        
        try:
            # 获取打印机状态和队列信息
            status = self.printer_manager.get_printer_status(printer_name)
            queue = self.printer_manager.get_print_queue(printer_name)
            job_count = len(queue) if queue else 0
            
            return self.api_client.update_printer_status(printer_name, status, job_count)
            
        except Exception as e:
            print(f"❌ [DEBUG] 更新打印机状态异常: {e}")
            return {"success": False, "message": str(e)}
