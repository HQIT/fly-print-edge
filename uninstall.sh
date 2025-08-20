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
    rm -rf $INSTALL_DIR
fi

echo "卸载完成！"
