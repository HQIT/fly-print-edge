#!/bin/bash

# Linux 安装包打包脚本
set -e

echo "开始打包 Linux 安装包..."

# 检查必要文件
if [ ! -f "dist/FlyPrint" ]; then
    echo "错误: 找不到 dist/FlyPrint，请先运行 PyInstaller 构建"
    exit 1
fi

# 创建临时打包目录
PACKAGE_DIR="flyprint-linux-$(date +%Y%m%d)"
echo "创建打包目录: $PACKAGE_DIR"
mkdir -p $PACKAGE_DIR

# 复制文件
echo "复制安装文件..."
cp install.sh $PACKAGE_DIR/
cp uninstall.sh $PACKAGE_DIR/
cp flyprint.service $PACKAGE_DIR/
cp dist/FlyPrint $PACKAGE_DIR/
cp config.json $PACKAGE_DIR/
cp -r printer_*.py $PACKAGE_DIR/

# 设置执行权限
chmod +x $PACKAGE_DIR/*.sh

# 创建README
cat > $PACKAGE_DIR/README.md << EOF
# Fly Print Linux 安装包

## 安装步骤

1. 解压安装包
2. 运行安装脚本: \`sudo ./install.sh\`
3. 检查服务状态: \`sudo systemctl status flyprint\`

## 卸载步骤

运行卸载脚本: \`sudo ./uninstall.sh\`

## 服务管理

- 启动: \`sudo systemctl start flyprint\`
- 停止: \`sudo systemctl stop flyprint\`
- 重启: \`sudo systemctl restart flyprint\`
- 状态: \`sudo systemctl status flyprint\`
- 日志: \`sudo journalctl -u flyprint -f\`

## 注意事项

- 需要 root 权限安装
- 服务将自动开机启动
- 默认安装到 /opt/flyprint 目录
EOF

# 创建压缩包
echo "创建压缩包..."
tar -czf "${PACKAGE_DIR}.tar.gz" $PACKAGE_DIR

# 清理临时目录
rm -rf $PACKAGE_DIR

echo "打包完成！"
echo "安装包: ${PACKAGE_DIR}.tar.gz"
echo "文件大小: $(du -h "${PACKAGE_DIR}.tar.gz" | cut -f1)"
