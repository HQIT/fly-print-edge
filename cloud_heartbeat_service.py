"""
fly-print-cloud 心跳服务
定期发送心跳到云端，报告边缘节点状态
"""

import threading
import time
import psutil
from typing import Dict, Any, Optional
from cloud_api_client import CloudAPIClient


class HeartbeatService:
    """心跳服务"""
    
    def __init__(self, api_client: CloudAPIClient, interval: int = 30):
        self.api_client = api_client
        self.interval = interval  # 心跳间隔（秒）
        self.running = False
        self.thread = None
        self.last_heartbeat_time = 0
        self.heartbeat_failures = 0
        self.max_failures = 3  # 最大连续失败次数
        
    def start(self):
        """启动心跳服务"""
        if self.running:
            print("⚠️ [DEBUG] 心跳服务已经在运行")
            return
        
        self.running = True
        self.heartbeat_failures = 0
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
        print(f"💓 [DEBUG] 心跳服务已启动，间隔: {self.interval}秒")
    
    def stop(self):
        """停止心跳服务"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("🛑 [DEBUG] 心跳服务已停止")
    
    def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                # 发送心跳
                success = self._send_heartbeat()
                
                if success:
                    self.heartbeat_failures = 0
                    self.last_heartbeat_time = time.time()
                else:
                    self.heartbeat_failures += 1
                    print(f"⚠️ [DEBUG] 心跳失败次数: {self.heartbeat_failures}/{self.max_failures}")
                
                # 如果连续失败次数过多，可以触发重连或其他恢复机制
                if self.heartbeat_failures >= self.max_failures:
                    print("❌ [DEBUG] 心跳连续失败，可能需要重新注册节点")
                    # 这里可以添加重新注册逻辑或者通知主程序
                
            except Exception as e:
                print(f"❌ [DEBUG] 心跳循环异常: {e}")
                self.heartbeat_failures += 1
            
            # 等待下次心跳
            time.sleep(self.interval)
    
    def _send_heartbeat(self) -> bool:
        """发送心跳"""
        try:
            # 收集系统状态信息
            status_info = self._collect_status_info()
            
            result = self.api_client.send_heartbeat(
                status=status_info["status"],
                connection_quality=status_info["connection_quality"],
                latency=status_info["latency"]
            )
            
            return result.get("success", False)
            
        except Exception as e:
            print(f"❌ [DEBUG] 发送心跳异常: {e}")
            return False
    
    def _collect_status_info(self) -> Dict[str, Any]:
        """收集系统状态信息"""
        try:
            # 获取CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 获取内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 获取磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # 根据系统负载确定状态
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
                status = "busy"
            elif cpu_percent > 70 or memory_percent > 70:
                status = "moderate"
            else:
                status = "online"
            
            # 简单的连接质量评估（基于最近的心跳成功率）
            if self.heartbeat_failures == 0:
                connection_quality = 100
            elif self.heartbeat_failures == 1:
                connection_quality = 80
            elif self.heartbeat_failures == 2:
                connection_quality = 60
            else:
                connection_quality = 40
            
            # 模拟延迟（实际项目中可以ping云端服务器测量）
            latency = self._measure_latency()
            
            return {
                "status": status,
                "connection_quality": connection_quality,
                "latency": latency,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent
            }
            
        except Exception as e:
            print(f"❌ [DEBUG] 收集状态信息异常: {e}")
            return {
                "status": "unknown",
                "connection_quality": 50,
                "latency": 0
            }
    
    def _measure_latency(self) -> int:
        """测量到云端的延迟（毫秒）"""
        try:
            import requests
            start_time = time.time()
            
            # 简单的HEAD请求测量延迟
            base_url = self.api_client.base_url
            response = requests.head(f"{base_url}/api/v1/health", timeout=3)
            
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            return latency_ms
            
        except Exception as e:
            print(f"⚠️ [DEBUG] 测量延迟失败: {e}")
            return 0  # 返回0表示无法测量
    
    def get_status(self) -> Dict[str, Any]:
        """获取心跳服务状态"""
        return {
            "running": self.running,
            "interval": self.interval,
            "last_heartbeat": self.last_heartbeat_time,
            "failures": self.heartbeat_failures,
            "max_failures": self.max_failures
        }
    
    def force_heartbeat(self) -> Dict[str, Any]:
        """强制发送一次心跳"""
        try:
            print("💓 [DEBUG] 强制发送心跳")
            success = self._send_heartbeat()
            
            if success:
                self.heartbeat_failures = 0
                self.last_heartbeat_time = time.time()
                return {"success": True, "message": "心跳发送成功"}
            else:
                self.heartbeat_failures += 1
                return {"success": False, "message": "心跳发送失败"}
                
        except Exception as e:
            print(f"❌ [DEBUG] 强制心跳异常: {e}")
            return {"success": False, "message": str(e)}
