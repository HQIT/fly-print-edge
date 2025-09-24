"""
打印机核心管理功能
包含打印机发现、状态查询、队列管理和打印任务提交
"""

import platform
import time
import threading
from typing import List, Dict, Any
import pandas as pd

# 导入拆分的模块
from printer_config import PrinterConfig
from printer_parsers import PrinterParameterParserManager

# 导入平台特定的打印机实现
if platform.system() == "Windows":
    from printer_windows import WindowsEnterprisePrinter
else:
    from printer_linux import LinuxPrinter

try:
    from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
except ImportError:
    pass








class PrinterDiscovery:
    """打印机发现服务"""
    
    def __init__(self):
        self.discovered_printers = []
        # 初始化平台特定的打印机实现
        if platform.system() == "Windows":
            self.platform_printer = WindowsEnterprisePrinter()
        else:
            self.platform_printer = LinuxPrinter()
    
    def discover_local_printers(self) -> List[Dict]:
        """发现本地已安装的打印机"""
        try:
            return self.platform_printer.discover_local_printers()
        except Exception as e:
            print(f"发现本地打印机时出错: {e}")
            return []
    
    def discover_network_printers(self) -> List[Dict]:
        """发现网络打印机"""
        printers = []
        
        try:
            print("🔍 [DEBUG] 开始网络打印机发现...")
            zeroconf = Zeroconf()
            listener = NetworkPrinterListener()
            
            # 发现IPP打印机
            browser = ServiceBrowser(zeroconf, "_ipp._tcp.local.", listener)
            time.sleep(3)  # 等待发现
            
            # 从监听器获取发现的打印机
            discovered = listener.get_printers()
            print(f"📊 [DEBUG] 发现网络打印机数量: {len(discovered)}")
            
            for printer in discovered:
                printers.append(printer)
            
            zeroconf.close()
            
        except Exception as e:
            print(f"❌ [DEBUG] 网络打印机发现出错: {e}")
        
        return printers


class NetworkPrinterListener(ServiceListener):
    """网络打印机监听器"""
    
    def __init__(self):
        self.printers = []
    
    def add_service(self, zeroconf, type, name):
        """发现新的网络服务"""
        try:
            print(f"🔍 [DEBUG] 发现网络服务: {name}")
            info = zeroconf.get_service_info(type, name)
            if info:
                # 提取IP地址
                ip_address = None
                if info.addresses:
                    # addresses 是字节数组，需要转换为字符串
                    address_bytes = info.addresses[0]
                    if len(address_bytes) == 4:  # IPv4
                        ip_address = ".".join(str(b) for b in address_bytes)
                    elif len(address_bytes) == 16:  # IPv6
                        ip_address = ":".join(f"{address_bytes[i]:02x}{address_bytes[i+1]:02x}" 
                                            for i in range(0, 16, 2))
                
                printer_name = name.replace('._ipp._tcp.local.', '')
                location = f"{ip_address}:{info.port}" if ip_address and info.port else "网络"
                
                # 构建IPP URI
                uri = ""
                if ip_address and info.port:
                    # 尝试不同的IPP路径
                    uri = f"ipp://{ip_address}:{info.port}/ipp/print"
                    # 也可以尝试其他常见路径如: /printers/{printer_name}
                
                print(f"✅ [DEBUG] 网络打印机详情 - 名称: {printer_name}, 位置: {location}, URI: {uri}")
                
                self.printers.append({
                    "name": printer_name,
                    "type": "network",
                    "location": location,
                    "make_model": "IPP网络打印机",
                    "uri": uri,  # 添加URI字段
                    "enabled": False  # 网络打印机需要手动配置
                })
        except Exception as e:
            print(f"❌ [DEBUG] 处理网络服务时出错: {e}")
    
    def remove_service(self, zeroconf, type, name):
        pass
    
    def update_service(self, zeroconf, type, name):
        pass
    
    def get_printers(self):
        return self.printers


class PrinterManager:
    """打印机管理器"""
    
    def __init__(self):
        self.config = PrinterConfig()
        self.discovery = PrinterDiscovery()
        self.parser_manager = PrinterParameterParserManager()  # 解析器管理器
        # 初始化平台特定的打印机实现
        if platform.system() == "Windows":
            self.platform_printer = WindowsEnterprisePrinter()
        else:
            self.platform_printer = LinuxPrinter()
        print("🎯 [DEBUG] PrinterManager初始化完成")
    
    def get_discovered_printers_df(self) -> pd.DataFrame:
        """获取发现的打印机DataFrame"""
        local_printers = self.discovery.discover_local_printers()
        network_printers = self.discovery.discover_network_printers()
        all_printers = local_printers + network_printers
        
        if not all_printers:
            return pd.DataFrame(columns=["名称", "类型", "位置", "设备型号", "状态"])
        
        df_data = []
        for p in all_printers:
            # 使用实际的打印机状态而不是enabled字段
            actual_status = p.get("status", "未知")
            row_data = {
                "名称": p.get("name", ""),
                "类型": p.get("type", ""),
                "位置": p.get("location", ""),
                "设备型号": p.get("make_model", ""),
                "状态": actual_status
            }
            # 为网络打印机添加URI信息（不显示在表格中）
            if p.get("uri"):
                row_data["URI"] = p.get("uri")
            
            df_data.append(row_data)
        
        return pd.DataFrame(df_data)
    
    def get_printer_status(self, printer_name: str) -> str:
        """获取打印机状态"""
        try:
            return self.platform_printer.get_printer_status(printer_name)
        except Exception as e:
            print(f"获取打印机状态时出错: {e}")
            return "未知"
    
    def get_print_queue(self, printer_name: str) -> List[Dict]:
        """获取打印队列"""
        try:
            return self.platform_printer.get_print_queue(printer_name)
        except Exception as e:
            print(f"获取打印队列时出错: {e}")
            return []
    
    def submit_print_job(self, printer_name: str, file_path: str, job_name: str = "", print_options: Dict[str, str] = None) -> Dict[str, Any]:
        """提交打印任务"""
        try:
            if not print_options:
                print_options = {}
            result = self.platform_printer.submit_print_job(printer_name, file_path, job_name, print_options)
            
            # 处理不同平台的返回格式
            if isinstance(result, bool):
                # Linux平台返回bool
                return {"success": result, "message": "打印任务已提交" if result else "打印任务提交失败"}
            elif isinstance(result, dict):
                # Windows平台返回dict
                return result
            else:
                return {"success": False, "message": "未知的返回格式"}
        except Exception as e:
            print(f"❌ [DEBUG] 提交打印任务时出错: {e}")
            return {"success": False, "message": f"提交打印任务时出错: {e}"}
    
    def get_job_status(self, printer_name: str, job_id: int) -> Dict[str, Any]:
        """获取打印任务状态"""
        try:
            if hasattr(self.platform_printer, 'get_job_status'):
                return self.platform_printer.get_job_status(printer_name, job_id)
            else:
                # 对于不支持任务状态查询的平台，返回默认状态
                return {"exists": False, "status": "not_supported"}
        except Exception as e:
            print(f"❌ [DEBUG] 获取任务状态时出错: {e}")
            return {"exists": False, "status": "error"}
    
    def get_printer_capabilities(self, printer_name: str) -> Dict[str, Any]:
        """获取打印机支持的参数选项"""
        try:
            return self.platform_printer.get_printer_capabilities(printer_name, self.parser_manager)
        except Exception as e:
            print(f"❌ [DEBUG] 获取打印机参数时出错: {e}")
            # 返回默认参数
            return {
                "resolution": ["300dpi", "600dpi", "1200dpi"],
                "page_size": ["A4", "Letter", "Legal"],
                "duplex": ["None", "DuplexNoTumble", "DuplexTumble"],
                "color_model": ["Gray", "RGB"],
                "media_type": ["Plain", "Cardstock", "Transparency"]
            }
    
    def get_managed_printers_df(self) -> pd.DataFrame:
        """获取管理的打印机DataFrame"""
        printers = self.config.get_managed_printers()
        
        if not printers:
            return pd.DataFrame(columns=["ID", "名称", "类型", "状态", "添加时间"])
        
        df_data = []
        for p in printers:
            status = self.get_printer_status(p.get("name", ""))
            df_data.append({
                "ID": p.get("id", ""),
                "名称": p.get("name", ""),
                "类型": p.get("type", ""),
                "状态": status,
                "添加时间": p.get("added_time", "")
            })
        
        return pd.DataFrame(df_data)
    
    def enable_printer(self, printer_name: str) -> tuple[bool, str]:
        """启用打印机"""
        return self.platform_printer.enable_printer(printer_name)
    
    def disable_printer(self, printer_name: str, reason: str = "") -> tuple[bool, str]:
        """禁用打印机"""
        return self.platform_printer.disable_printer(printer_name, reason)
    
    def clear_print_queue(self, printer_name: str) -> tuple[bool, str]:
        """清空打印队列"""
        return self.platform_printer.clear_print_queue(printer_name)
    
    def remove_print_job(self, printer_name: str, job_id: str) -> tuple[bool, str]:
        """删除特定打印任务"""
        return self.platform_printer.remove_print_job(printer_name, job_id)
    
    def add_network_printer_to_cups(self, printer_info: Dict[str, Any]) -> tuple[bool, str]:
        """自动将网络打印机添加到CUPS系统"""
        try:
            if hasattr(self.platform_printer, 'add_network_printer_to_cups'):
                return self.platform_printer.add_network_printer_to_cups(printer_info)
            else:
                return False, "当前平台不支持自动添加网络打印机"
        except Exception as e:
            print(f"❌ [DEBUG] 添加网络打印机时出错: {e}")
            return False, f"添加出错: {str(e)}"
    
    def get_printer_port_info(self, printer_name: str) -> str:
        """获取打印机端口信息"""
        try:
            if hasattr(self.platform_printer, 'get_printer_port_info'):
                return self.platform_printer.get_printer_port_info(printer_name)
            else:
                return ""
        except Exception as e:
            print(f"❌ [DEBUG] 获取端口信息时出错: {e}")
            return ""
    
    def add_printer_intelligently(self, printer_info: Dict[str, Any]) -> tuple[bool, str]:
        """智能添加打印机（自动处理网络打印机）"""
        try:
            printer_type = printer_info.get("type", "")
            printer_name = printer_info.get("name", "")
            
            # 如果是网络打印机，先添加到CUPS
            if printer_type == "network":
                print(f"🌐 [DEBUG] 检测到网络打印机，自动添加到CUPS: {printer_name}")
                success, message = self.add_network_printer_to_cups(printer_info)
                if not success:
                    return False, f"网络打印机添加到CUPS失败: {message}"
                
                # 等待CUPS更新
                import time
                time.sleep(2)
                
                # 重新发现打印机，获取CUPS中的版本
                local_printers = self.discovery.discover_local_printers()
                cups_printer = None
                for printer in local_printers:
                    if printer_name in printer.get("name", "") or printer.get("name", "") in printer_name:
                        cups_printer = printer
                        break
                
                if cups_printer:
                    # 使用CUPS中的打印机信息
                    printer_info = cups_printer
                    print(f"✅ [DEBUG] 找到CUPS中的打印机: {printer_info.get('name')}")
                else:
                    return False, "网络打印机添加到CUPS成功，但无法在CUPS中找到对应的打印机"
            
            # 检查是否已存在
            existing_names = [p.get("name", "") for p in self.config.get_managed_printers()]
            if printer_info.get("name") in existing_names:
                return False, f"打印机 {printer_info.get('name')} 已经在管理列表中"
            
            # 添加到管理列表
            printer_id = f"printer_{len(self.config.get_managed_printers())}"
            managed_printer = {
                "name": printer_info.get("name"),
                "type": printer_info.get("type", "local"),  # 网络打印机在CUPS中会变成local
                "location": printer_info.get("location", ""),
                "make_model": printer_info.get("make_model", ""),
                "enabled": True,
                "added_time": self._get_current_time(),
                "id": printer_id
            }
            
            # 保存配置
            current_printers = self.config.get_managed_printers()
            current_printers.append(managed_printer)
            self.config.config["managed_printers"] = current_printers
            self.config.save_config()
            
            return True, f"打印机 {printer_info.get('name')} 添加成功"
            
        except Exception as e:
            print(f"❌ [DEBUG] 智能添加打印机失败: {e}")
            return False, f"添加失败: {str(e)}"
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def submit_print_job_with_cleanup(self, printer_name: str, file_path: str, job_name: str, print_options: Dict[str, str] = None, cleanup_source: str = "unknown") -> Dict[str, Any]:
        """提交打印任务并智能清理临时文件（统一入口）"""
        import threading
        import time
        import os
        
        try:
            print(f"🖨️ [DEBUG] [{cleanup_source}] 提交打印任务: {job_name}")
            print(f"  打印机: {printer_name}")
            print(f"  文件: {file_path}")
            
            # 提交打印任务
            result = self.submit_print_job(printer_name, file_path, job_name, print_options or {})
            
            # 智能清理临时文件
            def smart_cleanup():
                try:
                    # 如果提交失败，立即清理
                    if not result.get("success", False):
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"🗑️ [DEBUG] [{cleanup_source}] 打印失败，立即清理临时文件: {file_path}")
                        return
                    
                    # 如果有job_id，监控任务状态
                    job_id = result.get("job_id")
                    if job_id:
                        max_wait_time = 300  # 最大等待5分钟
                        check_interval = 5   # 每5秒检查一次
                        waited_time = 0
                        
                        while waited_time < max_wait_time:
                            time.sleep(check_interval)
                            waited_time += check_interval
                            
                            # 检查任务状态
                            job_status = self.get_job_status(printer_name, job_id)
                            
                            # 如果任务不存在（完成或失败）或状态为完成，清理文件
                            if not job_status.get("exists", True) or job_status.get("status") in ["completed", "completed_or_failed"]:
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                    print(f"🗑️ [DEBUG] [{cleanup_source}] 打印任务完成，清理临时文件: {file_path}")
                                return
                        
                        # 超时后强制清理
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"🗑️ [DEBUG] [{cleanup_source}] 等待超时，强制清理临时文件: {file_path}")
                    else:
                        # 没有job_id，使用短延迟后清理
                        time.sleep(30)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"🗑️ [DEBUG] [{cleanup_source}] 无job_id，延迟清理临时文件: {file_path}")
                        
                except Exception as cleanup_error:
                    print(f"⚠️ [DEBUG] [{cleanup_source}] 智能清理临时文件失败: {cleanup_error}")
            
            # 在后台线程中执行智能清理
            cleanup_thread = threading.Thread(target=smart_cleanup, daemon=True)
            cleanup_thread.start()
            
            return result
            
        except Exception as e:
            print(f"❌ [DEBUG] [{cleanup_source}] 打印任务提交异常: {e}")
            # 异常时也尝试清理文件
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"🗑️ [DEBUG] [{cleanup_source}] 异常清理临时文件: {file_path}")
            except:
                pass
            return {"success": False, "message": str(e)}
    
    def get_print_queue_df(self, printer_name: str) -> pd.DataFrame:
        """获取打印队列DataFrame"""
        jobs = self.get_print_queue(printer_name)
        
        if not jobs:
            return pd.DataFrame(columns=["任务ID", "用户", "文件名", "大小", "状态"])
        
        df_data = []
        for job in jobs:
            df_data.append({
                "任务ID": job.get("job_id", ""),
                "用户": job.get("user", ""),
                "文件名": job.get("title", ""),
                "大小": job.get("size", ""),
                "状态": job.get("status", "")
            })
        
        return pd.DataFrame(df_data)
