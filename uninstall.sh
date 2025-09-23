#!/bin/bash

# Fly Print Linux 卸载脚本
set -e

echo "开始卸载 Fly Print 服务..."

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 停止并禁用服务
echo "停止并禁用服务..."
systemctl stop flyprint.service 2>/dev/null || true
systemctl disable flyprint.service 2>/dev/null || true

# 删除服务文件
echo "删除服务文件..."
rm -f /etc/systemd/system/flyprint.service
systemctl daemon-reload

# 删除安装目录
INSTALL_DIR="/opt/flyprint"
if [ -d "$INSTALL_DIR" ]; then
    echo "删除安装目录: $INSTALL_DIR"
    echo "  - 删除 Python 虚拟环境..."
    rm -rf $INSTALL_DIR/.venv
    echo "  - 删除应用文件..."
    rm -rf $INSTALL_DIR
fi

# 清理日志文件（可选）
LOG_DIR="/var/log/flyprint"
if [ -d "$LOG_DIR" ]; then
    echo "删除日志目录: $LOG_DIR"
    rm -rf $LOG_DIR
fi

echo "✅ 卸载完成！"
echo ""
echo "已清理的内容："
echo "  - systemd 服务 (flyprint.service)"
echo "  - 应用目录 (/opt/flyprint)"
echo "  - Python 虚拟环境"
echo "  - 日志文件 (/var/log/flyprint)"
