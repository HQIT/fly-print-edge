#!/bin/bash

# Fly Print Linux 安装脚本
set -e

echo "开始安装 Fly Print 服务..."

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 创建安装目录
INSTALL_DIR="/opt/flyprint"
echo "创建安装目录: $INSTALL_DIR"
mkdir -p $INSTALL_DIR

# 复制文件
echo "复制应用文件..."
cp dist/FlyPrint $INSTALL_DIR/
cp config.json $INSTALL_DIR/
cp -r printer_*.py $INSTALL_DIR/

# 设置权限
echo "设置文件权限..."
chmod +x $INSTALL_DIR/FlyPrint
chown -R ecnu:ecnu $INSTALL_DIR

# 安装systemd服务
echo "安装systemd服务..."
cp flyprint.service /etc/systemd/system/
systemctl daemon-reload

# 启用并启动服务
echo "启用并启动服务..."
systemctl enable flyprint.service
systemctl start flyprint.service

# 检查服务状态
echo "检查服务状态..."
systemctl status flyprint.service --no-pager

echo "安装完成！"
echo "服务管理命令："
echo "  启动: sudo systemctl start flyprint"
echo "  停止: sudo systemctl stop flyprint"
echo "  重启: sudo systemctl restart flyprint"
echo "  状态: sudo systemctl status flyprint"
echo "  日志: sudo journalctl -u flyprint -f"
