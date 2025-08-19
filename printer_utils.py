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
                # 添加[网络]前缀以区分网络打印机
                printer['name'] = f"[网络] {printer['name']}"
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
                
                print(f"✅ [DEBUG] 网络打印机详情 - 名称: {printer_name}, 位置: {location}")
                
                self.printers.append({
                    "name": printer_name,
                    "type": "network",
                    "location": location,
                    "make_model": "网络打印机 (需要手动添加到CUPS)",
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
            df_data.append({
                "名称": p.get("name", ""),
                "类型": p.get("type", ""),
                "位置": p.get("location", ""),
                "设备型号": p.get("make_model", ""),
                "状态": actual_status
            })
        
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
