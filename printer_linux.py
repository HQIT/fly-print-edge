"""Linux/CUPS打印机实现
包含所有Linux平台的打印机操作
"""

import subprocess
from typing import List, Dict, Any


def run_command_with_debug(cmd, timeout=10):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8'
        )
        return result
    except subprocess.TimeoutExpired:
        print(f"⏰ [DEBUG] 命令超时: {' '.join(cmd)}")
        return None
    except Exception as e:
        print(f"❌ [DEBUG] 命令执行出错: {e}")
        return None


class LinuxPrinter:
    """Linux/CUPS打印机操作类"""
    
    def __init__(self):
        pass
    
    def discover_local_printers(self) -> List[Dict]:
        """发现本地已安装的打印机"""
        # 直接调用discover_printers方法，避免重复代码
        return self.discover_printers()
    
    def discover_printers(self) -> List[Dict]:
        """发现本地打印机"""
        printers = []
        
        try:
            # 使用lpstat -a 获取可用的打印机队列
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
                                
                                # 使用打印机名称作为描述
                                display_name = printer_name.replace('_', ' ')
                                description = f"CUPS打印机 ({display_name})"
                            
                            printers.append({
                                "name": printer_name,
                                "type": "local",
                                "location": "本地",
                                "make_model": description,
                                "enabled": status in ["空闲", "在线", "打印中"]
                            })
                            
        except Exception as e:
            print(f"发现本地打印机时出错: {e}")
        
        print(f"📊 [DEBUG] 发现本地打印机数量: {len(printers)}")
        return printers
    
    def get_printer_status(self, printer_name: str) -> str:
        """获取打印机状态"""
        try:
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
        except Exception as e:
            print(f"获取打印机状态时出错: {e}")
            return "未知"
    
    def get_print_queue(self, printer_name: str) -> List[Dict]:
        """获取打印队列"""
        jobs = []
        
        try:
            result = run_command_with_debug(['lpq', '-P', printer_name])
            if result and result.returncode == 0:
                lines = result.stdout.split('\n')[1:]  # 跳过标题行
                for line in lines:
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            # 统一字段格式，与Windows平台保持一致
                            jobs.append({
                                "job_id": parts[0],
                                "document": parts[2],  # 使用document而不是title
                                "user": parts[1],
                                "status": "等待中",
                                "pages": 0,  # Linux lpq通常不显示页数
                                "size": parts[3] if len(parts) > 3 else "0"
                            })
        except Exception as e:
            print(f"获取打印队列时出错: {e}")
        
        return jobs
    
    def _get_latest_job_id(self, printer_name: str) -> int:
        """获取最新的打印任务ID"""
        try:
            result = run_command_with_debug(['lpq', '-P', printer_name])
            if result and result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # 跳过标题行，查找最新的任务
                for line in lines[1:]:
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 1:
                            try:
                                return int(parts[0])
                            except ValueError:
                                continue
        except Exception as e:
            print(f"获取最新任务ID失败: {e}")
        return None
    
    def submit_print_job(self, printer_name: str, file_path: str, job_name: str = "", print_options: Dict[str, str] = None) -> Dict[str, Any]:
        """提交打印任务"""
        try:
            if not print_options:
                print_options = {}
            
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
                
                # 尝试获取job_id
                job_id = self._get_latest_job_id(printer_name)
                
                return {
                    "success": True,
                    "job_id": job_id,
                    "printer_name": printer_name,
                    "file_path": file_path,
                    "message": "打印任务已提交"
                }
            else:
                print(f"❌ [DEBUG] 打印任务提交失败")
                error_msg = result.stderr if result and result.stderr else "未知错误"
                return {
                    "success": False,
                    "message": f"打印任务提交失败: {error_msg}"
                }
                
        except Exception as e:
            print(f"提交打印任务时出错: {e}")
            return {
                 "success": False,
                 "message": f"提交打印任务时出错: {e}"
             }
    
    def get_job_status(self, printer_name: str, job_id: int) -> Dict[str, Any]:
        """获取特定打印任务的状态"""
        try:
            result = run_command_with_debug(['lpq', '-P', printer_name])
            if result and result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # 跳过标题行，查找指定的任务
                for line in lines[1:]:
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 1:
                            try:
                                current_job_id = int(parts[0])
                                if current_job_id == job_id:
                                    # 任务仍在队列中
                                    status = "waiting" if len(parts) >= 5 else "printing"
                                    return {
                                        "exists": True,
                                        "status": status,
                                        "user": parts[1] if len(parts) > 1 else "unknown",
                                        "title": parts[2] if len(parts) > 2 else "unknown"
                                    }
                            except ValueError:
                                continue
                
                # 如果在队列中找不到任务，说明任务已完成或失败
                return {"exists": False, "status": "completed_or_failed"}
            else:
                return {"exists": False, "status": "error"}
        except Exception as e:
            print(f"获取任务状态失败: {e}")
            return {"exists": False, "status": "error"}
    
    def get_printer_capabilities(self, printer_name: str, parser_manager=None) -> Dict[str, Any]:
        """获取打印机能力"""
        try:
            # 执行lpoptions命令
            result = run_command_with_debug(['lpoptions', '-p', printer_name, '-l'])
            
            if result and result.returncode == 0:
                print(f"✅ [DEBUG] lpoptions命令执行成功")
                # 使用解析器管理器解析输出
                return parser_manager.get_capabilities(printer_name, result.stdout)
            else:
                print(f"❌ [DEBUG] lpoptions命令执行失败")
        except Exception as e:
            print(f"获取打印机能力时出错: {e}")
        
        # 返回默认参数
        return {
            "resolution": ["300dpi", "600dpi", "1200dpi"],
            "page_size": ["A4", "Letter", "Legal"],
            "duplex": ["None"],
            "color_model": ["Gray", "RGB"],
            "media_type": ["Plain"]
        }
    
    def enable_printer(self, printer_name: str) -> tuple[bool, str]:
        """启用打印机"""
        try:
            print(f"🔄 [DEBUG] 启用打印机: {printer_name}")
            result = run_command_with_debug(['cupsenable', printer_name])
            if result and result.returncode == 0:
                print(f"✅ [DEBUG] 打印机启用成功")
                return True, f"打印机 {printer_name} 已启用"
            else:
                print(f"❌ [DEBUG] 打印机启用失败")
                return False, f"启用失败: {result.stderr if result else '命令执行失败'}"
        except Exception as e:
            print(f"❌ [DEBUG] 启用打印机时出错: {e}")
            return False, f"启用出错: {str(e)}"
    
    def disable_printer(self, printer_name: str, reason: str = "") -> tuple[bool, str]:
        """禁用打印机"""
        try:
            print(f"🚫 [DEBUG] 禁用打印机: {printer_name}")
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
        except Exception as e:
            print(f"❌ [DEBUG] 禁用打印机时出错: {e}")
            return False, f"禁用出错: {str(e)}"
    
    def clear_print_queue(self, printer_name: str) -> tuple[bool, str]:
        """清空打印队列"""
        try:
            print(f"🗑️ [DEBUG] 清空打印队列: {printer_name}")
            result = run_command_with_debug(['lprm', '-P', printer_name, '-'])
            if result and result.returncode == 0:
                print(f"✅ [DEBUG] 打印队列清空成功")
                return True, f"打印机 {printer_name} 的队列已清空"
            else:
                print(f"❌ [DEBUG] 打印队列清空失败")
                return False, f"清空失败: {result.stderr if result else '命令执行失败'}"
        except Exception as e:
            print(f"❌ [DEBUG] 清空打印队列时出错: {e}")
            return False, f"清空出错: {str(e)}"
    
    def remove_print_job(self, printer_name: str, job_id: str) -> tuple[bool, str]:
        """删除特定打印任务"""
        try:
            print(f"🗑️ [DEBUG] 删除打印任务: {printer_name} - {job_id}")
            result = run_command_with_debug(['lprm', '-P', printer_name, job_id])
            if result and result.returncode == 0:
                print(f"✅ [DEBUG] 打印任务删除成功")
                return True, f"任务 {job_id} 已删除"
            else:
                print(f"❌ [DEBUG] 打印任务删除失败")
                return False, f"删除失败: {result.stderr if result else '命令执行失败'}"
        except Exception as e:
            print(f"❌ [DEBUG] 删除打印任务时出错: {e}")
            return False, f"删除出错: {str(e)}"