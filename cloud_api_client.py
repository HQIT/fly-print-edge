"""
fly-print-cloud API客户端
实现边缘节点注册、心跳、打印机注册等API调用
"""

import requests
import time
from typing import Dict, Any, List, Optional
from cloud_auth import CloudAuthClient
from edge_node_info import EdgeNodeInfo


class CloudAPIClient:
    """云端API客户端"""
    
    def __init__(self, base_url: str, auth_client: CloudAuthClient):
        self.base_url = base_url.rstrip('/')
        self.auth_client = auth_client
        self.node_id = None  # 注册后获得
        self.edge_info = EdgeNodeInfo()
    
    def register_edge_node(self, node_name: str = None, location: str = None) -> Dict[str, Any]:
        """注册边缘节点"""
        try:
            if node_name:
                self.edge_info.node_name = node_name
            if location:
                self.edge_info.location = location
            
            url = f"{self.base_url}/api/v1/edge/register"
            headers = self.auth_client.get_auth_headers()
            data = self.edge_info.get_edge_node_data()
            
            print(f"📡 [DEBUG] 注册边缘节点: {url}")
            print(f"📊 [DEBUG] 注册数据: {data}")
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                # 按照后端接口定义，node_id在data.id字段中
                self.node_id = result['data']['id']
                print(f"✅ [DEBUG] 边缘节点注册成功, node_id: {self.node_id}")
                return {"success": True, "node_id": self.node_id, "data": result}
            else:
                print(f"❌ [DEBUG] 边缘节点注册失败: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ [DEBUG] 边缘节点注册异常: {e}")
            return {"success": False, "error": str(e)}
    
    def send_heartbeat(self, status: str = "online", connection_quality: int = 100, latency: int = 0) -> Dict[str, Any]:
        """发送心跳"""
        if not self.node_id:
            return {"success": False, "error": "节点未注册"}
        
        try:
            url = f"{self.base_url}/api/v1/edge/heartbeat"
            headers = self.auth_client.get_auth_headers()
            
            data = {
                "node_id": self.node_id,
                "status": status,
                "connection_quality": connection_quality,
                "latency": latency,
                "timestamp": int(time.time())
            }
            
            print(f"💓 [DEBUG] 发送心跳: {url}")
            
            response = requests.post(url, json=data, headers=headers, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ [DEBUG] 心跳发送成功")
                return {"success": True, "data": response.json()}
            else:
                print(f"❌ [DEBUG] 心跳发送失败: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ [DEBUG] 心跳发送异常: {e}")
            return {"success": False, "error": str(e)}
    
    def register_printers(self, printers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """注册打印机到云端"""
        if not self.node_id:
            return {"success": False, "error": "节点未注册"}
        
        try:
            url = f"{self.base_url}/api/v1/edge/{self.node_id}/printers"
            headers = self.auth_client.get_auth_headers()
            
            # 转换打印机数据格式
            printer_data = []
            for printer in printers:
                printer_info = {
                    "name": printer.get("name", ""),
                    "type": printer.get("type", "local"),
                    "location": printer.get("location", ""),
                    "make_model": printer.get("make_model", ""),
                    "status": printer.get("status", "unknown"),
                    "capabilities": printer.get("capabilities", {}),
                    "enabled": printer.get("enabled", True)
                }
                printer_data.append(printer_info)
            
            data = {"printers": printer_data}
            
            print(f"🖨️ [DEBUG] 注册打印机: {url}")
            print(f"📊 [DEBUG] 打印机数量: {len(printer_data)}")
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                print(f"✅ [DEBUG] 打印机注册成功")
                return {"success": True, "data": result}
            else:
                print(f"❌ [DEBUG] 打印机注册失败: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ [DEBUG] 打印机注册异常: {e}")
            return {"success": False, "error": str(e)}
    
    def get_websocket_url(self) -> str:
        """获取WebSocket连接URL"""
        if not self.node_id:
            return None
        
        # 将HTTP(S)协议转换为WS(S)协议
        ws_base = self.base_url.replace('http://', 'ws://').replace('https://', 'wss://')
        return f"{ws_base}/api/v1/edge/ws?node_id={self.node_id}"
    
    def update_printer_status(self, printer_name: str, status: str, job_count: int = 0) -> Dict[str, Any]:
        """更新打印机状态"""
        if not self.node_id:
            return {"success": False, "error": "节点未注册"}
        
        try:
            url = f"{self.base_url}/api/v1/edge/{self.node_id}/printers/{printer_name}/status"
            headers = self.auth_client.get_auth_headers()
            
            data = {
                "status": status,
                "job_count": job_count,
                "timestamp": int(time.time())
            }
            
            response = requests.put(url, json=data, headers=headers, timeout=5)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                print(f"❌ [DEBUG] 更新打印机状态失败: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ [DEBUG] 更新打印机状态异常: {e}")
            return {"success": False, "error": str(e)}
    
    def report_print_job_result(self, job_id: str, success: bool, error_message: str = None) -> Dict[str, Any]:
        """报告打印任务结果"""
        if not self.node_id:
            return {"success": False, "error": "节点未注册"}
        
        try:
            url = f"{self.base_url}/api/v1/edge/{self.node_id}/jobs/{job_id}/result"
            headers = self.auth_client.get_auth_headers()
            
            data = {
                "success": success,
                "timestamp": int(time.time())
            }
            
            if error_message:
                data["error_message"] = error_message
            
            response = requests.post(url, json=data, headers=headers, timeout=5)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                print(f"❌ [DEBUG] 报告打印任务结果失败: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ [DEBUG] 报告打印任务结果异常: {e}")
            return {"success": False, "error": str(e)}
