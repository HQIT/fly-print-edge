import gradio as gr
import pandas as pd
import os
import tempfile
import threading
import time
import platform
from printer_utils import PrinterManager
from cloud_service import CloudService


class PrintApp:
    """打印机管理应用"""
    
    def __init__(self):
        self.printer_manager = PrinterManager()
        self.selected_discovered_row = None
        self.selected_managed_row = None
        
        # 初始化云端服务
        cloud_config = self.printer_manager.config.config.get("cloud", {})
        self.cloud_service = CloudService(cloud_config, self.printer_manager)
        
        # 如果启用云端服务，自动启动
        if cloud_config.get("enabled", False):
            self._start_cloud_service()
    
    def refresh_discovered_printers(self):
        """刷新发现的打印机列表"""
        try:
            df = self.printer_manager.get_discovered_printers_df()
            return df, "打印机列表已刷新"
        except Exception as e:
            return pd.DataFrame(), f"刷新失败: {str(e)}"
    
    def refresh_managed_printers(self):
        """刷新管理的打印机列表"""
        try:
            df = self.printer_manager.get_managed_printers_df()
            return df, "管理列表已刷新"
        except Exception as e:
            return pd.DataFrame(), f"刷新失败: {str(e)}"
    
    def add_selected_printer_by_name(self, discovered_df, selected_printer):
        """根据下拉菜单选择添加打印机"""
        if len(discovered_df) == 0:
            return self.refresh_managed_printers()[0], "❌ 没有发现可添加的打印机"
            
        if not selected_printer:
            return self.refresh_managed_printers()[0], "❌ 请先从下拉菜单选择一台打印机"
        
        try:
            # 从选择文本中提取打印机名称 (格式: "名称 (类型)")
            printer_name = selected_printer.split(" (")[0]
            
            # 检查是否是网络打印机
            if printer_name.startswith("[网络]"):
                return self.refresh_managed_printers()[0], "⚠️ 网络打印机需要先手动添加到CUPS系统中才能使用。请参考CUPS管理文档。"
            
            # 查找对应的行
            found_row = None
            for _, row in discovered_df.iterrows():
                if row["名称"] == printer_name:
                    found_row = row
                    break
            
            if found_row is None:
                return self.refresh_managed_printers()[0], f"❌ 找不到打印机: {printer_name}"
            
            # 在Linux系统中只允许添加本地CUPS打印机
            if platform.system() == "Linux" and found_row["类型"] != "local":
                return self.refresh_managed_printers()[0], f"⚠️ 只能添加本地CUPS打印机，网络打印机请先添加到CUPS系统"
            
            # 检查是否已存在
            existing_names = [p.get("name", "") for p in self.printer_manager.config.get_managed_printers()]
            if printer_name in existing_names:
                return self.refresh_managed_printers()[0], f"⚠️ 打印机 {printer_name} 已经在管理列表中"
                
            printer_info = {
                "name": found_row["名称"],
                "type": found_row["类型"], 
                "location": found_row["位置"],
                "make_model": found_row["设备型号"],
                "enabled": True
            }
            self.printer_manager.config.add_printer(printer_info)
            
            managed_df, _ = self.refresh_managed_printers()
            return managed_df, f"✅ 已添加打印机: {printer_name}"
        except Exception as e:
            return self.refresh_managed_printers()[0], f"❌ 添加失败: {str(e)}"
    
    def delete_selected_printer_by_name(self, managed_df, selected_printer):
        """根据下拉菜单选择删除打印机"""
        if len(managed_df) == 0:
            return self.refresh_managed_printers()[0], "❌ 没有管理的打印机"
            
        if not selected_printer:
            return self.refresh_managed_printers()[0], "❌ 请先从下拉菜单选择要删除的打印机"
        
        try:
            # 从选择文本中提取打印机名称 (格式: "名称 (类型)")
            printer_name = selected_printer.split(" (")[0]
            
            # 查找对应的打印机ID
            found_id = None
            for _, row in managed_df.iterrows():
                if row["名称"] == printer_name:
                    found_id = row["ID"]
                    break
            
            if found_id is None:
                return self.refresh_managed_printers()[0], f"❌ 找不到要删除的打印机: {printer_name}"
            
            # 删除打印机
            current_printers = self.printer_manager.config.get_managed_printers()
            remaining_printers = [p for p in current_printers if p.get("id") != found_id]
            
            self.printer_manager.config.config["managed_printers"] = remaining_printers
            self.printer_manager.config.save_config()
            
            managed_df, _ = self.refresh_managed_printers()
            return managed_df, f"✅ 已删除打印机: {printer_name}"
        except Exception as e:
            return self.refresh_managed_printers()[0], f"❌ 删除失败: {str(e)}"
    
    def clear_all_printers(self):
        """清空所有打印机"""
        try:
            current_printers = self.printer_manager.config.get_managed_printers()
            if len(current_printers) == 0:
                return self.refresh_managed_printers()[0], "❌ 没有管理的打印机"
            
            total_count = len(current_printers)
            self.printer_manager.config.config["managed_printers"] = []
            self.printer_manager.config.save_config()
            
            managed_df, _ = self.refresh_managed_printers()
            return managed_df, f"✅ 已清空所有打印机 (共 {total_count} 台)"
        except Exception as e:
            return self.refresh_managed_printers()[0], f"❌ 清空失败: {str(e)}"
    
    def get_selected_printer_queue_by_name(self, managed_df, selected_printer):
        """根据下拉菜单选择获取打印机队列"""
        if len(managed_df) == 0:
            return pd.DataFrame(), "❌ 没有管理的打印机"
            
        if not selected_printer:
            return pd.DataFrame(), "❌ 请先从下拉菜单选择一台打印机"
        
        try:
            # 从选择文本中提取打印机名称 (格式: "名称 (类型)")
            printer_name = selected_printer.split(" (")[0]
            
            # 验证打印机是否存在
            found = False
            for _, row in managed_df.iterrows():
                if row["名称"] == printer_name:
                    found = True
                    break
            
            if not found:
                return pd.DataFrame(), f"❌ 找不到打印机: {printer_name}"
            
            queue = self.printer_manager.get_print_queue(printer_name)
            if queue:
                return pd.DataFrame(queue), f"✅ 打印机 {printer_name} 的队列信息"
            else:
                return pd.DataFrame(), f"📝 打印机 {printer_name} 队列为空"
        except Exception as e:
            return pd.DataFrame(), f"❌ 获取队列失败: {str(e)}"
    
    def submit_print_job(self, printer_name, uploaded_file, job_name, resolution, page_size, duplex, color, media, manual_options):
        """提交打印任务"""
        if not printer_name:
            return "❌ 请先选择一台打印机"
        
        if not uploaded_file:
            return "❌ 请先上传要打印的文件"
        
        try:
            print(f"📄 [DEBUG] 上传文件类型: {type(uploaded_file)}")
            
            # 处理不同类型的文件对象
            if hasattr(uploaded_file, 'name') and hasattr(uploaded_file, 'read'):
                # 标准文件对象
                file_name = uploaded_file.name
                file_content = uploaded_file.read()
                print(f"📄 [DEBUG] 标准文件对象: {file_name}")
            elif isinstance(uploaded_file, str):
                # 文件路径字符串
                file_name = os.path.basename(uploaded_file)
                with open(uploaded_file, 'rb') as f:
                    file_content = f.read()
                print(f"📄 [DEBUG] 文件路径: {uploaded_file}")
            elif hasattr(uploaded_file, 'path'):
                # Gradio文件对象（新版本）
                file_name = os.path.basename(uploaded_file.path) if hasattr(uploaded_file, 'path') else "uploaded_file"
                with open(uploaded_file.path, 'rb') as f:
                    file_content = f.read()
                print(f"📄 [DEBUG] Gradio文件对象: {uploaded_file.path}")
            else:
                # 其他情况，尝试转换为字符串作为路径
                file_path = str(uploaded_file)
                if os.path.exists(file_path):
                    file_name = os.path.basename(file_path)
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    print(f"📄 [DEBUG] 字符串路径: {file_path}")
                else:
                    return f"❌ 无法处理的文件对象类型: {type(uploaded_file)}"
            
            # 保存到临时文件
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, file_name)
            
            print(f"💾 [DEBUG] 保存文件到: {temp_file_path}")
            with open(temp_file_path, 'wb') as f:
                f.write(file_content)
            
            # 构建打印选项
            print_options = {}
            
            # 处理手动输入的选项（优先级最高）
            if manual_options and manual_options.strip():
                try:
                    for option in manual_options.split(','):
                        if '=' in option:
                            key, value = option.strip().split('=', 1)
                            print_options[key.strip()] = value.strip()
                    print(f"🔧 [DEBUG] 使用手动输入的选项: {print_options}")
                except Exception as e:
                    print(f"⚠️ [DEBUG] 解析手动选项失败: {e}")
            
            # 如果没有手动选项，使用下拉菜单的选择
            if not print_options:
                if resolution and resolution != "默认":
                    # 自动判断是分辨率还是打印质量
                    if "dpi" in resolution.lower():
                        print_options["Resolution"] = resolution
                    else:
                        print_options["cupsPrintQuality"] = resolution
                if page_size and page_size != "默认":
                    print_options["PageSize"] = page_size
                if duplex and duplex != "默认":
                    print_options["Duplex"] = duplex
                if color and color != "默认":
                    print_options["ColorModel"] = color
                if media and media != "默认":
                    print_options["MediaType"] = media
            
            # 提交打印任务
            result = self.printer_manager.submit_print_job(
                printer_name, 
                temp_file_path, 
                job_name or f"Print_{file_name}",
                print_options
            )
            
            # 智能清理临时文件，基于打印任务状态
            def smart_cleanup():
                try:
                    # 如果提交失败，立即清理
                    if not result.get("success", False):
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                            print(f"🗑️ [DEBUG] 打印失败，立即清理临时文件: {temp_file_path}")
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
                            job_status = self.printer_manager.get_job_status(printer_name, job_id)
                            
                            # 如果任务不存在（完成或失败）或状态为完成，清理文件
                            if not job_status.get("exists", True) or job_status.get("status") in ["completed", "completed_or_failed"]:
                                if os.path.exists(temp_file_path):
                                    os.remove(temp_file_path)
                                    print(f"🗑️ [DEBUG] 打印任务完成，清理临时文件: {temp_file_path}")
                                return
                        
                        # 超时后强制清理
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                            print(f"🗑️ [DEBUG] 等待超时，强制清理临时文件: {temp_file_path}")
                    else:
                        # 没有job_id，使用短延迟后清理
                        time.sleep(30)
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                            print(f"🗑️ [DEBUG] 无job_id，延迟清理临时文件: {temp_file_path}")
                        
                except Exception as cleanup_error:
                    print(f"⚠️ [DEBUG] 清理临时文件失败: {cleanup_error}")
            
            # 在后台线程中执行智能清理
            cleanup_thread = threading.Thread(target=smart_cleanup, daemon=True)
            cleanup_thread.start()
            
            return result
            
        except Exception as e:
            print(f"💥 [DEBUG] 打印任务提交异常: {str(e)}")
            return f"❌ 打印失败: {str(e)}"
    
    def get_printer_names(self):
        """获取管理的打印机名称列表"""
        try:
            printers = self.printer_manager.config.get_managed_printers()
            return [p.get("name", "") for p in printers]
        except Exception as e:
            return []
    
    def get_discovered_printer_choices(self, discovered_df):
        """获取发现的打印机选择列表"""
        if len(discovered_df) == 0:
            return []
        try:
            return [f"{row['名称']} ({row['类型']})" for _, row in discovered_df.iterrows()]
        except Exception as e:
            return []
    
    def get_managed_printer_choices(self, managed_df):
        """获取管理的打印机选择列表"""
        if len(managed_df) == 0:
            return []
        try:
            return [f"{row['名称']} ({row['类型']})" for _, row in managed_df.iterrows()]
        except Exception as e:
            return []
    
    def update_printer_parameters(self, selected_printer):
        """根据选中的打印机更新参数选项"""
        if not selected_printer:
            return (
                gr.update(choices=["默认", "300dpi", "600dpi", "1200dpi"], value="默认"),
                gr.update(choices=["默认", "A4", "Letter", "Legal", "A3"], value="默认"),
                gr.update(choices=["默认", "None", "DuplexNoTumble", "DuplexTumble"], value="默认"),
                gr.update(choices=["默认", "RGB", "Gray"], value="默认"),
                gr.update(choices=["默认", "Plain", "Photo", "Transparency"], value="默认"),
                "请先选择打印机"
            )
        
        try:
            # 从选择文本中提取打印机名称
            printer_name = selected_printer.split(" (")[0]
            print(f"🔍 [DEBUG] 获取打印机 {printer_name} 的参数...")
            
            # 获取打印机能力
            capabilities = self.printer_manager.get_printer_capabilities(printer_name)
            
            # 更新各个参数的选择项
            resolution_choices = ["默认"] + capabilities.get("resolution", ["300dpi", "600dpi", "1200dpi"])
            page_size_choices = ["默认"] + capabilities.get("page_size", ["A4", "Letter", "Legal", "A3"])
            duplex_choices = ["默认"] + capabilities.get("duplex", ["None", "DuplexNoTumble", "DuplexTumble"])
            color_choices = ["默认"] + capabilities.get("color_model", ["RGB", "Gray"])
            media_choices = ["默认"] + capabilities.get("media_type", ["Plain", "Photo", "Transparency"])
            
            status_msg = f"✅ 已获取打印机 {printer_name} 的参数配置"
            
            return (
                gr.update(choices=resolution_choices, value="默认"),
                gr.update(choices=page_size_choices, value="默认"),
                gr.update(choices=duplex_choices, value="默认"),
                gr.update(choices=color_choices, value="默认"),
                gr.update(choices=media_choices, value="默认"),
                status_msg
            )
            
        except Exception as e:
            print(f"❌ [DEBUG] 获取打印机参数失败: {str(e)}")
            return (
                gr.update(choices=["默认", "300dpi", "600dpi", "1200dpi"], value="默认"),
                gr.update(choices=["默认", "A4", "Letter", "Legal", "A3"], value="默认"),
                gr.update(choices=["默认", "None", "DuplexNoTumble", "DuplexTumble"], value="默认"),
                gr.update(choices=["默认", "RGB", "Gray"], value="默认"),
                gr.update(choices=["默认", "Plain", "Photo", "Transparency"], value="默认"),
                f"⚠️ 获取打印机参数失败: {str(e)}，使用默认选项"
            )
    
    # ==================== 打印机管理功能 ====================
    
    def enable_printer_by_name(self, managed_df, selected_printer):
        """启用选中的打印机"""
        if not selected_printer:
            return managed_df, "⚠️ 请先选择要启用的打印机"
        
        try:
            printer_name = selected_printer.split(" (")[0]
            success, message = self.printer_manager.enable_printer(printer_name)
            
            if success:
                # 刷新管理列表
                updated_df = self.printer_manager.get_managed_printers_df()
                return updated_df, f"✅ {message}"
            else:
                return managed_df, f"❌ {message}"
                
        except Exception as e:
            return managed_df, f"❌ 启用打印机时出错: {str(e)}"
    
    def disable_printer_by_name(self, managed_df, selected_printer, reason=""):
        """禁用选中的打印机"""
        if not selected_printer:
            return managed_df, "⚠️ 请先选择要禁用的打印机"
        
        try:
            printer_name = selected_printer.split(" (")[0]
            success, message = self.printer_manager.disable_printer(printer_name, reason)
            
            if success:
                # 刷新管理列表
                updated_df = self.printer_manager.get_managed_printers_df()
                return updated_df, f"✅ {message}"
            else:
                return managed_df, f"❌ {message}"
                
        except Exception as e:
            return managed_df, f"❌ 禁用打印机时出错: {str(e)}"
    
    def get_queue_by_printer_name(self, selected_printer):
        """获取选中打印机的队列"""
        if not selected_printer:
            return pd.DataFrame(columns=["任务ID", "用户", "文件名", "大小", "状态"]), "⚠️ 请先选择打印机"
        
        try:
            printer_name = selected_printer.split(" (")[0]
            queue_df = self.printer_manager.get_print_queue_df(printer_name)
            
            if queue_df.empty:
                return queue_df, f"📭 打印机 {printer_name} 队列为空"
            else:
                return queue_df, f"📋 打印机 {printer_name} 队列（共{len(queue_df)}个任务）"
                
        except Exception as e:
            return pd.DataFrame(columns=["任务ID", "用户", "文件名", "大小", "状态"]), f"❌ 获取队列失败: {str(e)}"
    
    def clear_queue_by_printer_name(self, selected_printer):
        """清空选中打印机的队列"""
        if not selected_printer:
            return pd.DataFrame(columns=["任务ID", "用户", "文件名", "大小", "状态"]), "⚠️ 请先选择打印机"
        
        try:
            printer_name = selected_printer.split(" (")[0]
            success, message = self.printer_manager.clear_print_queue(printer_name)
            
            if success:
                # 刷新队列显示
                queue_df = self.printer_manager.get_print_queue_df(printer_name)
                return queue_df, f"✅ {message}"
            else:
                # 如果清空失败，仍然获取当前队列
                queue_df = self.printer_manager.get_print_queue_df(printer_name)
                return queue_df, f"❌ {message}"
                
        except Exception as e:
            return pd.DataFrame(columns=["任务ID", "用户", "文件名", "大小", "状态"]), f"❌ 清空队列失败: {str(e)}"
    
    def remove_job_by_id(self, selected_printer, job_id):
        """删除指定任务ID的打印任务"""
        if not selected_printer:
            return pd.DataFrame(columns=["任务ID", "用户", "文件名", "大小", "状态"]), "⚠️ 请先选择打印机"
        
        if not job_id or not job_id.strip():
            return self.get_queue_by_printer_name(selected_printer)[0], "⚠️ 请输入要删除的任务ID"
        
        try:
            printer_name = selected_printer.split(" (")[0]
            success, message = self.printer_manager.remove_print_job(printer_name, job_id.strip())
            
            # 刷新队列显示
            queue_df = self.printer_manager.get_print_queue_df(printer_name)
            
            if success:
                return queue_df, f"✅ {message}"
            else:
                return queue_df, f"❌ {message}"
                
        except Exception as e:
            return pd.DataFrame(columns=["任务ID", "用户", "文件名", "大小", "状态"]), f"❌ 删除任务失败: {str(e)}"
    
    # ==================== 云端服务功能 ====================
    
    def _start_cloud_service(self):
        """启动云端服务"""
        def start_async():
            try:
                result = self.cloud_service.start()
                if result["success"]:
                    print(f"✅ [DEBUG] 云端服务启动成功: {result.get('node_id', '')}")
                else:
                    print(f"❌ [DEBUG] 云端服务启动失败: {result.get('message', '')}")
            except Exception as e:
                print(f"❌ [DEBUG] 云端服务启动异常: {e}")
        
        # 在后台线程中启动云端服务
        threading.Thread(target=start_async, daemon=True).start()
    
    def get_cloud_status(self):
        """获取云端服务状态"""
        try:
            status = self.cloud_service.get_status()
            status_text = f"云端服务状态:\n"
            status_text += f"  启用: {'是' if status['enabled'] else '否'}\n"
            status_text += f"  已注册: {'是' if status['registered'] else '否'}\n"
            status_text += f"  节点ID: {status.get('node_id', '未分配')}\n"
            
            if status.get('heartbeat'):
                hb = status['heartbeat']
                status_text += f"  心跳服务: {'运行中' if hb['running'] else '已停止'}\n"
                status_text += f"  心跳间隔: {hb['interval']}秒\n"
                status_text += f"  失败次数: {hb['failures']}/{hb['max_failures']}\n"
            
            if status.get('websocket'):
                ws = status['websocket']
                status_text += f"  WebSocket: {'已连接' if ws['running'] else '未连接'}\n"
            
            return status_text
        except Exception as e:
            return f"❌ 获取云端状态失败: {str(e)}"
    
    def toggle_cloud_service(self):
        """切换云端服务状态"""
        try:
            cloud_config = self.printer_manager.config.config.get("cloud", {})
            current_enabled = cloud_config.get("enabled", False)
            
            if current_enabled:
                # 停止云端服务
                self.cloud_service.stop()
                cloud_config["enabled"] = False
                message = "✅ 云端服务已停用"
            else:
                # 启动云端服务
                cloud_config["enabled"] = True
                self.cloud_service.enabled = True
                self.cloud_service._initialize_components()
                self._start_cloud_service()
                message = "✅ 云端服务已启用"
            
            # 保存配置
            self.printer_manager.config.config["cloud"] = cloud_config
            self.printer_manager.config.save_config()
            
            return message
        except Exception as e:
            return f"❌ 切换云端服务失败: {str(e)}"
    
    def force_cloud_heartbeat(self):
        """强制发送云端心跳"""
        try:
            result = self.cloud_service.force_heartbeat()
            if result["success"]:
                return "✅ 心跳发送成功"
            else:
                return f"❌ 心跳发送失败: {result['message']}"
        except Exception as e:
            return f"❌ 心跳发送异常: {str(e)}"


def create_app():
    """创建Gradio应用"""
    app = PrintApp()
    
    with gr.Blocks(title="飞印 - 打印机管理", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🖨️ 飞印 - 边缘打印机管理软件")
        
        with gr.Tab("📡 发现打印机"):
            gr.Markdown("### 扫描并发现网络中的打印机")
            
            refresh_discovered_btn = gr.Button("🔄 刷新打印机列表", variant="primary")
            
            discovered_table = gr.Dataframe(
                headers=["名称", "类型", "位置", "设备型号", "状态"],
                interactive=False,
                label="发现的打印机"
            )
            
            with gr.Row():
                discovered_dropdown = gr.Dropdown(
                    label="选择要添加的打印机",
                    choices=[],
                    interactive=True
                )
                add_to_managed_btn = gr.Button("➕ 添加到管理列表")
            
            discovered_status = gr.Textbox(label="状态", interactive=False)
        
        with gr.Tab("🖨️ 管理打印机"):
            gr.Markdown("### 管理已添加的打印机")
            
            refresh_managed_btn = gr.Button("🔄 刷新管理列表", variant="primary")
            
            managed_table = gr.Dataframe(
                headers=["ID", "名称", "类型", "状态", "添加时间"],
                interactive=False,
                label="管理的打印机"
            )
            
            with gr.Row():
                managed_dropdown = gr.Dropdown(
                    label="选择打印机进行操作",
                    choices=[],
                    interactive=True
                )
                with gr.Column():
                    delete_selected_btn = gr.Button("🗑️ 删除选中的打印机", variant="secondary")
                    get_queue_btn = gr.Button("📋 查看选中的队列")
            
            # 打印机控制按钮
            gr.Markdown("### 🎛️ 打印机控制")
            with gr.Row():
                enable_printer_btn = gr.Button("✅ 启用打印机", variant="primary")
                disable_printer_btn = gr.Button("🚫 禁用打印机", variant="secondary")
                disable_reason_input = gr.Textbox(
                    label="禁用原因（可选）",
                    placeholder="例如：设备维护中...",
                    interactive=True
                )
            
            clear_all_btn = gr.Button("💥 清空所有打印机", variant="stop")
            
            managed_status = gr.Textbox(label="状态", interactive=False)
            
            # 队列管理区域
            gr.Markdown("### 📋 打印队列管理")
            queue_table = gr.Dataframe(
                headers=["任务ID", "用户", "文件名", "大小", "状态"],
                interactive=False,
                label="打印队列"
            )
            
            # 队列操作按钮
            with gr.Row():
                clear_queue_btn = gr.Button("🧹 清空选中打印机队列", variant="secondary")
                remove_job_input = gr.Textbox(
                    label="任务ID",
                    placeholder="输入要删除的任务ID",
                    interactive=True
                )
                remove_job_btn = gr.Button("🗑️ 删除指定任务", variant="secondary")
        
        with gr.Tab("📄 打印文件"):
            gr.Markdown("### 选择打印机并上传文件进行打印")
            
            printer_dropdown = gr.Dropdown(
                label="选择打印机",
                choices=[],
                interactive=True
            )
            
            # 打印参数设置区域
            with gr.Accordion("🔧 打印参数设置", open=False):
                gr.Markdown("_选择打印机后会自动获取支持的参数，如果获取失败可手动输入_")
                
                with gr.Row():
                    resolution_dropdown = gr.Dropdown(
                        label="分辨率",
                        choices=["默认", "300dpi", "600dpi", "1200dpi"],
                        value="默认",
                        interactive=True
                    )
                    page_size_dropdown = gr.Dropdown(
                        label="纸张大小",
                        choices=["默认", "A4", "Letter", "Legal", "A3"],
                        value="默认",
                        interactive=True
                    )
                
                with gr.Row():
                    duplex_dropdown = gr.Dropdown(
                        label="双面打印",
                        choices=["默认", "None", "DuplexNoTumble", "DuplexTumble"],
                        value="默认",
                        interactive=True
                    )
                    color_dropdown = gr.Dropdown(
                        label="颜色模式",
                        choices=["默认", "RGB", "Gray"],
                        value="默认",
                        interactive=True
                    )
                
                media_dropdown = gr.Dropdown(
                    label="介质类型",
                    choices=["默认", "Plain", "Photo", "Transparency"],
                    value="默认",
                    interactive=True
                )
                
                # 手动输入选项
                with gr.Accordion("🔧 手动输入参数 (高级)", open=False):
                    manual_options = gr.Textbox(
                        label="自定义打印选项",
                        placeholder="例如: Resolution=600dpi,PageSize=A4,Duplex=None",
                        info="格式: 选项名=值,选项名=值 (会覆盖上面的下拉选择)"
                    )
            
            with gr.Row():
                uploaded_file = gr.File(
                    label="上传要打印的文件", 
                    file_types=[".pdf", ".txt", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"]
                )
                job_name_input = gr.Textbox(label="任务名称(可选)", placeholder="留空将自动生成")
            
            print_btn = gr.Button("🖨️ 开始打印", variant="primary")
            print_result = gr.Textbox(label="打印结果", interactive=False)
        
        with gr.Tab("☁️ 云端服务"):
            gr.Markdown("### fly-print-cloud 云端服务管理")
            
            with gr.Row():
                cloud_status_btn = gr.Button("📊 查看状态", variant="secondary")
                toggle_cloud_btn = gr.Button("🔄 启用/停用", variant="primary")
                heartbeat_btn = gr.Button("💓 发送心跳", variant="secondary")
            
            cloud_status_display = gr.Textbox(
                label="云端服务状态",
                lines=10,
                interactive=False,
                value="点击'查看状态'获取云端服务信息"
            )
            
            cloud_operation_result = gr.Textbox(label="操作结果", interactive=False)
        
        # 事件绑定
        def refresh_discovered():
            df, status = app.refresh_discovered_printers()
            choices = app.get_discovered_printer_choices(df)
            return df, status, gr.update(choices=choices, value=None)
        
        refresh_discovered_btn.click(
            refresh_discovered,
            outputs=[discovered_table, discovered_status, discovered_dropdown]
        )
        
        def add_and_update(discovered_df, selected_printer):
            managed_df, status = app.add_selected_printer_by_name(discovered_df, selected_printer)
            printer_names = app.get_printer_names()
            managed_choices = app.get_managed_printer_choices(managed_df)
            return managed_df, status, gr.update(choices=printer_names), gr.update(choices=managed_choices, value=None)
        
        add_to_managed_btn.click(
            add_and_update,
            inputs=[discovered_table, discovered_dropdown],
            outputs=[managed_table, discovered_status, printer_dropdown, managed_dropdown]
        )
        
        def refresh_managed():
            df, status = app.refresh_managed_printers()
            choices = app.get_managed_printer_choices(df)
            printer_names = app.get_printer_names()
            return df, status, gr.update(choices=choices, value=None), gr.update(choices=printer_names)
        
        refresh_managed_btn.click(
            refresh_managed,
            outputs=[managed_table, managed_status, managed_dropdown, printer_dropdown]
        )
        
        def delete_and_update(managed_df, selected_printer):
            managed_df, status = app.delete_selected_printer_by_name(managed_df, selected_printer)
            printer_names = app.get_printer_names()
            managed_choices = app.get_managed_printer_choices(managed_df)
            return managed_df, status, gr.update(choices=printer_names), gr.update(choices=managed_choices, value=None)
        
        delete_selected_btn.click(
            delete_and_update,
            inputs=[managed_table, managed_dropdown],
            outputs=[managed_table, managed_status, printer_dropdown, managed_dropdown]
        )
        
        def clear_and_update():
            managed_df, status = app.clear_all_printers()
            printer_names = app.get_printer_names()
            managed_choices = app.get_managed_printer_choices(managed_df)
            return managed_df, status, gr.update(choices=printer_names), gr.update(choices=managed_choices, value=None)
        
        clear_all_btn.click(
            clear_and_update,
            outputs=[managed_table, managed_status, printer_dropdown, managed_dropdown]
        )
        
        def get_queue(managed_df, selected_printer):
            queue_df, queue_status = app.get_selected_printer_queue_by_name(managed_df, selected_printer)
            return queue_df, queue_status
        
        get_queue_btn.click(
            get_queue,
            inputs=[managed_table, managed_dropdown],
            outputs=[queue_table, managed_status]
        )
        
        # 打印机选择时更新参数
        printer_dropdown.change(
            app.update_printer_parameters,
            inputs=[printer_dropdown],
            outputs=[
                resolution_dropdown, page_size_dropdown, duplex_dropdown, 
                color_dropdown, media_dropdown, print_result
            ]
        )
        
        # 打印功能
        print_btn.click(
            app.submit_print_job,
            inputs=[
                printer_dropdown, uploaded_file, job_name_input,
                resolution_dropdown, page_size_dropdown, duplex_dropdown,
                color_dropdown, media_dropdown, manual_options
            ],
            outputs=[print_result]
        )
        
        # ==================== 新增打印机管理事件绑定 ====================
        
        # 启用打印机
        def enable_and_update(managed_df, selected_printer):
            managed_df, status = app.enable_printer_by_name(managed_df, selected_printer)
            managed_choices = app.get_managed_printer_choices(managed_df)
            return managed_df, status, gr.update(choices=managed_choices)
        
        enable_printer_btn.click(
            enable_and_update,
            inputs=[managed_table, managed_dropdown],
            outputs=[managed_table, managed_status, managed_dropdown]
        )
        
        # 禁用打印机
        def disable_and_update(managed_df, selected_printer, reason):
            managed_df, status = app.disable_printer_by_name(managed_df, selected_printer, reason)
            managed_choices = app.get_managed_printer_choices(managed_df)
            return managed_df, status, gr.update(choices=managed_choices), ""
        
        disable_printer_btn.click(
            disable_and_update,
            inputs=[managed_table, managed_dropdown, disable_reason_input],
            outputs=[managed_table, managed_status, managed_dropdown, disable_reason_input]
        )
        
        # 清空打印队列
        def clear_queue_and_refresh(selected_printer):
            queue_df, status = app.clear_queue_by_printer_name(selected_printer)
            return queue_df, status
        
        clear_queue_btn.click(
            clear_queue_and_refresh,
            inputs=[managed_dropdown],
            outputs=[queue_table, managed_status]
        )
        
        # 删除指定打印任务
        def remove_job_and_refresh(selected_printer, job_id):
            queue_df, status = app.remove_job_by_id(selected_printer, job_id)
            return queue_df, status, ""
        
        remove_job_btn.click(
            remove_job_and_refresh,
            inputs=[managed_dropdown, remove_job_input],
            outputs=[queue_table, managed_status, remove_job_input]
        )
        
        # ==================== 云端服务事件绑定 ====================
        
        # 查看云端状态
        cloud_status_btn.click(
            app.get_cloud_status,
            outputs=[cloud_status_display]
        )
        
        # 启用/停用云端服务
        def toggle_and_refresh():
            result = app.toggle_cloud_service()
            status = app.get_cloud_status()
            return result, status
        
        toggle_cloud_btn.click(
            toggle_and_refresh,
            outputs=[cloud_operation_result, cloud_status_display]
        )
        
        # 发送心跳
        def heartbeat_and_refresh():
            result = app.force_cloud_heartbeat()
            status = app.get_cloud_status()
            return result, status
        
        heartbeat_btn.click(
            heartbeat_and_refresh,
            outputs=[cloud_operation_result, cloud_status_display]
        )
        
        # 页面加载时刷新数据
        def on_load():
            # 刷新发现的打印机
            discovered_df, discovered_status = app.refresh_discovered_printers()
            discovered_choices = app.get_discovered_printer_choices(discovered_df)
            
            # 刷新管理的打印机
            managed_df, managed_status = app.refresh_managed_printers()
            managed_choices = app.get_managed_printer_choices(managed_df)
            printer_names = app.get_printer_names()
            
            return (
                discovered_df, discovered_status, gr.update(choices=discovered_choices),
                managed_df, managed_status, gr.update(choices=managed_choices),
                gr.update(choices=printer_names)
            )
        
        demo.load(
            on_load,
            outputs=[
                discovered_table, discovered_status, discovered_dropdown,
                managed_table, managed_status, managed_dropdown,
                printer_dropdown
            ]
        )
    
    return demo


if __name__ == "__main__":
    print("🚀 启动飞印打印机管理软件...")
    print("📝 访问地址: http://0.0.0.0:7860")
    print("💡 使用说明:")
    print("   1. 在'发现打印机'标签页扫描并添加打印机")
    print("   2. 在'管理打印机'标签页查看和管理打印机")
    print("   3. 在'打印文件'标签页上传文件并打印")
    print("🔧 [DEBUG] 调试模式已开启，所有命令调用都会显示")
    print("=" * 50)
    
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
