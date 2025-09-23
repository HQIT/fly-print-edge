#!/bin/bash

# Fly Print Linux 安装脚本
set -e

echo "开始安装 Fly Print 服务..."

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 检查系统环境和依赖
echo "检查系统环境..."

# 检查Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，正在安装..."
    apt update && apt install -y python3 python3-venv python3-pip
    if [ $? -ne 0 ]; then
        echo "❌ Python3 安装失败"
        exit 1
    fi
else
    echo "✅ Python3 已安装: $(python3 --version)"
fi

# 检查Python3-venv
if ! python3 -c "import venv" &> /dev/null; then
    echo "❌ python3-venv 未安装，正在安装..."
    apt install -y python3-venv
    if [ $? -ne 0 ]; then
        echo "❌ python3-venv 安装失败"
        exit 1
    fi
else
    echo "✅ python3-venv 可用"
fi

# 检查pip
if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    echo "❌ pip 未安装，正在安装..."
    apt install -y python3-pip
    if [ $? -ne 0 ]; then
        echo "❌ pip 安装失败"
        exit 1
    fi
else
    echo "✅ pip 可用"
fi

# 检查CUPS (打印机支持)
if ! command -v lpstat &> /dev/null; then
    echo "⚠️ CUPS 未安装，正在安装打印机支持..."
    apt install -y cups cups-client
    systemctl enable cups
    systemctl start cups
    echo "✅ CUPS 已安装并启动"
else
    echo "✅ CUPS 已安装"
fi

# 创建安装目录
INSTALL_DIR="/opt/flyprint"
echo "创建安装目录: $INSTALL_DIR"
mkdir -p $INSTALL_DIR

# 复制文件
echo "复制应用文件..."
cp *.py $INSTALL_DIR/
cp config.json $INSTALL_DIR/
cp requirements.txt $INSTALL_DIR/

# 获取当前脚本目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 创建虚拟环境
echo "创建Python虚拟环境..."
cd $INSTALL_DIR
python3 -m venv .venv
source .venv/bin/activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 设置权限
echo "设置文件权限..."
chown -R ecnu:ecnu $INSTALL_DIR

# 安装systemd服务
echo "安装systemd服务..."
cp "$SCRIPT_DIR/flyprint.service" /etc/systemd/system/
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
