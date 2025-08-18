"""
打印机核心管理功能
包含打印机发现、状态查询、队列管理和打印任务提交
"""

import platform
import time
import threading
from typing import List, Dict, Any
import pandas as pd
import subprocess

# 导入拆分的模块
from printer_config import PrinterConfig
from printer_parsers import PrinterParameterParserManager

try:
    from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
except ImportError:
    pass


def run_command_with_debug(cmd, timeout=10):
    """运行命令并打印调试信息"""
    print(f"🔧 [DEBUG] 执行命令: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        print(f"📤 [DEBUG] 返回码: {result.returncode}")
        if result.stdout:
            stdout_preview = result.stdout.strip()
            # 如果输出太长，只显示前200字符
            if len(stdout_preview) > 200:
                print(f"📝 [DEBUG] 标准输出(前200字符): {stdout_preview[:200]}...")
            else:
                print(f"📝 [DEBUG] 标准输出: {stdout_preview}")
        if result.stderr:
            print(f"❌ [DEBUG] 错误输出: {result.stderr.strip()}")
        return result
    except subprocess.TimeoutExpired:
        print(f"⏰ [DEBUG] 命令超时: {timeout}秒")
        return None
    except Exception as e:
        print(f"💥 [DEBUG] 命令执行异常: {str(e)}")
        return None


class PrinterDiscovery:
    """打印机发现服务"""
    
    def __init__(self):
        self.discovered_printers = []
    
    def discover_local_printers(self) -> List[Dict]:
        """发现本地已安装的打印机"""
        printers = []
        
        try:
            if platform.system() == "Linux":
                # 使用lpstat -a 获取可用的打印机队列（真正的打印机名）
                result_a = run_command_with_debug(['lpstat', '-a'])
                if result_a and result_a.returncode == 0:
                    print("📋 [DEBUG] 解析 lpstat -a 输出获取打印机名称...")
                    lines = result_a.stdout.strip().split('\n')
                    for line in lines:
                        if line and not line.startswith(' '):
                            # 格式通常是: "打印机名 accepting requests since ..."
                            parts = line.split(' ')
                            if len(parts) >= 1:
                                printer_name = parts[0]
                                print(f"🔍 [DEBUG] 发现打印机名称: {printer_name}")
                                
                                # 获取该打印机的详细信息
                                status_result = run_command_with_debug(['lpstat', '-p', printer_name])
                                status = "离线"
                                description = "CUPS打印机"
                                
                                if status_result and status_result.returncode == 0:
                                    status_output = status_result.stdout
                                    # 支持中英文状态判断
                                    if "空闲" in status_output or "idle" in status_output.lower():
                                        status = "空闲"
                                    elif "打印中" in status_output or "printing" in status_output.lower():
                                        status = "打印中"
                                    elif "已禁用" in status_output or "disabled" in status_output.lower():
                                        status = "已禁用"
                                    elif "启用" in status_output or "enabled" in status_output.lower():
                                        status = "在线"
                                    else:
                                        status = "在线"
                                    
                                    # 使用打印机名称作为描述，因为CUPS的描述信息不够友好
                                    # 将内部名称转换为更友好的显示名称
                                    display_name = printer_name.replace('_', ' ')
                                    description = f"CUPS打印机 ({display_name})"
                                
                                printers.append({
                                    "name": printer_name,  # 使用实际的CUPS打印机名
                                    "type": "local",
                                    "location": "本地",
                                    "make_model": description,
                                    "enabled": status in ["空闲", "在线", "打印中"]
                                })
                                
            elif platform.system() == "Windows":
                result = run_command_with_debug(['wmic', 'printer', 'get', 'name,status,location'])
                if result and result.returncode == 0:
                    lines = result.stdout.split('\n')[1:]  # 跳过标题行
                    for line in lines:
                        if line.strip():
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                printers.append({
                                    "name": parts[1],
                                    "type": "local",
                                    "location": parts[0] if len(parts) > 2 else "本地",
                                    "make_model": "Windows打印机",
                                    "enabled": True
                                })
                                
        except Exception as e:
            print(f"发现本地打印机时出错: {e}")
        
        print(f"📊 [DEBUG] 发现本地打印机数量: {len(printers)}")
        return printers
    
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
            df_data.append({
                "名称": p.get("name", ""),
                "类型": p.get("type", ""),
                "位置": p.get("location", ""),
                "设备型号": p.get("make_model", ""),
                "状态": "在线" if p.get("enabled", False) else "离线"
            })
        
        return pd.DataFrame(df_data)
    
    def get_printer_status(self, printer_name: str) -> str:
        """获取打印机状态"""
        try:
            if platform.system() == "Linux":
                result = run_command_with_debug(['lpstat', '-p', printer_name])
                if result and result.returncode == 0:
                    status_output = result.stdout
                    # 支持中英文状态判断
                    if "空闲" in status_output or "idle" in status_output.lower():
                        return "空闲"
                    elif "打印中" in status_output or "printing" in status_output.lower():
                        return "打印中"
                    elif "已禁用" in status_output or "disabled" in status_output.lower():
                        return "已禁用"
                    elif "启用" in status_output or "enabled" in status_output.lower():
                        return "在线"
                    else:
                        return "在线"
                else:
                    return "离线"
                    
            elif platform.system() == "Windows":
                result = run_command_with_debug(['wmic', 'printer', 'where', f'name="{printer_name}"', 'get', 'status'])
                if result and result.returncode == 0:
                    return "在线" if "OK" in result.stdout else "离线"
                    
        except Exception as e:
            print(f"获取打印机状态时出错: {e}")
        
        return "未知"
    
    def get_print_queue(self, printer_name: str) -> List[Dict]:
        """获取打印队列"""
        jobs = []
        
        try:
            if platform.system() == "Linux":
                result = run_command_with_debug(['lpq', '-P', printer_name])
                if result and result.returncode == 0:
                    lines = result.stdout.split('\n')[1:]  # 跳过标题行
                    for line in lines:
                        if line.strip():
                            parts = line.strip().split()
                            if len(parts) >= 4:
                                jobs.append({
                                    "job_id": parts[0],
                                    "user": parts[1],
                                    "title": parts[2],
                                    "size": parts[3],
                                    "status": "等待中"
                                })
                                
            elif platform.system() == "Windows":
                result = run_command_with_debug(['wmic', 'printjob', 'where', f'name like "%{printer_name}%"', 'get', 'jobid,owner,name,status'])
                if result and result.returncode == 0:
                    lines = result.stdout.split('\n')[1:]  # 跳过标题行
                    for line in lines:
                        if line.strip():
                            parts = line.strip().split()
                            if len(parts) >= 3:
                                jobs.append({
                                    "job_id": parts[0],
                                    "user": parts[1],
                                    "title": parts[2],
                                    "size": "未知",
                                    "status": "等待中"
                                })
                                
        except Exception as e:
            print(f"获取打印队列时出错: {e}")
        
        return jobs
    
    def submit_print_job(self, printer_name: str, file_path: str, job_name: str = "", print_options: Dict[str, str] = None) -> bool:
        """提交打印任务"""
        try:
            if not print_options:
                print_options = {}
            
            if platform.system() == "Linux":
                # 构建lpr命令
                cmd = ['lpr', '-P', printer_name]
                
                # 添加打印选项
                for key, value in print_options.items():
                    if value and value != "None" and value.strip():
                        option_str = f"{key}={value}"
                        cmd.extend(['-o', option_str])
                        print(f"🔧 [DEBUG] 添加打印选项: {option_str}")
                
                # 添加文件路径
                cmd.append(file_path)
                
                # 执行打印命令
                result = run_command_with_debug(cmd)
                if result and result.returncode == 0:
                    print(f"✅ [DEBUG] 打印任务提交成功")
                    return True
                else:
                    print(f"❌ [DEBUG] 打印任务提交失败")
                    return False
                    
            elif platform.system() == "Windows":
                # Windows使用notepad /p（简单实现，不支持参数）
                result = run_command_with_debug(['notepad', '/p', file_path])
                print(f"⚠️ [DEBUG] Windows平台打印暂不支持参数，使用notepad /p")
                return True
                
        except Exception as e:
            print(f"❌ [DEBUG] 提交打印任务时出错: {e}")
            return False
        
        return False
    
    def get_printer_capabilities(self, printer_name: str) -> Dict[str, Any]:
        """获取打印机支持的参数选项（使用解析器管理器）"""
        print(f"🔍 [DEBUG] 获取打印机 '{printer_name}' 的参数选项")
        
        try:
            if platform.system() == "Linux":
                # 执行lpoptions命令
                result = run_command_with_debug(['lpoptions', '-p', printer_name, '-l'])
                
                if result and result.returncode == 0:
                    print(f"✅ [DEBUG] lpoptions命令执行成功")
                    # 使用解析器管理器解析输出
                    return self.parser_manager.get_capabilities(printer_name, result.stdout)
                else:
                    print(f"❌ [DEBUG] lpoptions命令执行失败")
            else:
                print(f"⚠️ [DEBUG] 非Linux系统，使用默认参数")
                
        except Exception as e:
            print(f"❌ [DEBUG] 获取打印机参数时出错: {e}")
        
        # 返回默认参数
        print(f"📋 [DEBUG] 使用默认参数选项")
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
        try:
            print(f"🔄 [DEBUG] 启用打印机: {printer_name}")
            if platform.system() == "Linux":
                result = run_command_with_debug(['cupsenable', printer_name])
                if result and result.returncode == 0:
                    print(f"✅ [DEBUG] 打印机启用成功")
                    return True, f"打印机 {printer_name} 已启用"
                else:
                    print(f"❌ [DEBUG] 打印机启用失败")
                    return False, f"启用失败: {result.stderr if result else '命令执行失败'}"
            else:
                return False, "Windows系统暂不支持此功能"
        except Exception as e:
            print(f"❌ [DEBUG] 启用打印机时出错: {e}")
            return False, f"启用出错: {str(e)}"
    
    def disable_printer(self, printer_name: str, reason: str = "") -> tuple[bool, str]:
        """禁用打印机"""
        try:
            print(f"🚫 [DEBUG] 禁用打印机: {printer_name}")
            if platform.system() == "Linux":
                cmd = ['cupsdisable']
                if reason:
                    cmd.extend(['-r', reason])
                cmd.append(printer_name)
                
                result = run_command_with_debug(cmd)
                if result and result.returncode == 0:
                    print(f"✅ [DEBUG] 打印机禁用成功")
                    return True, f"打印机 {printer_name} 已禁用"
                else:
                    print(f"❌ [DEBUG] 打印机禁用失败")
                    return False, f"禁用失败: {result.stderr if result else '命令执行失败'}"
            else:
                return False, "Windows系统暂不支持此功能"
        except Exception as e:
            print(f"❌ [DEBUG] 禁用打印机时出错: {e}")
            return False, f"禁用出错: {str(e)}"
    
    def clear_print_queue(self, printer_name: str) -> tuple[bool, str]:
        """清空打印队列"""
        try:
            print(f"🧹 [DEBUG] 清空打印队列: {printer_name}")
            if platform.system() == "Linux":
                result = run_command_with_debug(['lprm', '-P', printer_name, '-'])
                if result and result.returncode == 0:
                    print(f"✅ [DEBUG] 打印队列清空成功")
                    return True, f"打印机 {printer_name} 队列已清空"
                else:
                    print(f"❌ [DEBUG] 打印队列清空失败")
                    return False, f"清空失败: {result.stderr if result else '命令执行失败'}"
            else:
                return False, "Windows系统暂不支持此功能"
        except Exception as e:
            print(f"❌ [DEBUG] 清空打印队列时出错: {e}")
            return False, f"清空出错: {str(e)}"
    
    def remove_print_job(self, printer_name: str, job_id: str) -> tuple[bool, str]:
        """删除特定打印任务"""
        try:
            print(f"🗑️ [DEBUG] 删除打印任务: {printer_name} - {job_id}")
            if platform.system() == "Linux":
                result = run_command_with_debug(['lprm', '-P', printer_name, job_id])
                if result and result.returncode == 0:
                    print(f"✅ [DEBUG] 打印任务删除成功")
                    return True, f"任务 {job_id} 已删除"
                else:
                    print(f"❌ [DEBUG] 打印任务删除失败")
                    return False, f"删除失败: {result.stderr if result else '命令执行失败'}"
            else:
                return False, "Windows系统暂不支持此功能"
        except Exception as e:
            print(f"❌ [DEBUG] 删除打印任务时出错: {e}")
            return False, f"删除出错: {str(e)}"
    
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
