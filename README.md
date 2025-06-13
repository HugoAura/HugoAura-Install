# HugoAura-Install

HugoAura 的生命周期管理工具

## 简介

这是一个用于 [HugoAura](https://github.com/HugoAura/Seewo-HugoAura) 的管理工具, 支持安装以及备份管理等功能。

## 使用方法

### 基本用法

1. 下载最新的 [Release](https://github.com/HugoAura/HugoAura-Install/releases) EXE 包
2. 以管理员身份运行 `AuraInstaller.exe`
3. 按照提示选择版本并完成安装

### 命令行参数

```
usage: AuraInstaller.exe [-h] [-v VERSION | -p PATH | -l | --pre] [-d DIR] [-y] [--list-exit-codes]

options:
  -h, --help            显示帮助信息并退出
  -v VERSION, --version VERSION
                        指定要安装的版本 Tag, 例如 v1.0.0
  -p PATH, --path PATH  指定本地安装文件路径（app-patched.asar 文件路径）
  -l, --latest          安装最新的稳定版本（默认）
  --pre                 安装最新的预发行版本
  -d DIR, --dir DIR     指定希沃管家安装目录
  -y, --yes             非交互模式, 自动确认所有操作
  --list-exit-codes     显示所有退出代码及其释义
```

### 非交互式安装示例

```bash
# 安装最新稳定版
HugoAura-Install.exe -l -y

# 安装最新预发行版
HugoAura-Install.exe --pre -y

# 安装指定版本
HugoAura-Install.exe -v v1.0.0 -y

# 从本地文件安装
HugoAura-Install.exe -p "C:\path\to\app-patched.asar" -y

# 指定安装目录
HugoAura-Install.exe -l -d "C:\Program Files (x86)\Seewo\SeewoService\SeewoService_1.0.0\SeewoServiceAssistant\resources" -y
```

### 退出代码释义

安装程序会根据不同的情况返回以下退出代码：

```
0: 安装成功
1: 安装失败 (一般错误)
2: 权限不足, 需要管理员权限
3: 未找到希沃管家安装目录
4: 资源文件下载失败
5: 资源文件解压失败
6: 文件系统操作失败
7: 参数错误
```

您可以通过检查退出代码来判断安装是否成功以及失败的原因。

## 注意事项

1. 安装前, HugoAura-Install 会自动尝试卸载希沃的文件系统过滤驱动 (`SeewoKeLiteLady`)
2. 如果您使用本地文件安装, 请确保提供目录同时存在 app-patched.asar 和 aura.zip 文件。

## 面向开发者

### 预先准备

- [Poetry](https://python-poetry.org/)
- Python 3.13.X

### 构建方法

1. 创建 venv & 安装依赖：`poetry install`
2. 进入 venv: `poetry shell` (可能需要手动安装 Shell Plugin)
3. 运行构建脚本：`scripts\build.bat`

### 贡献代码

欢迎提交 Issues 和 Pull Request!

如有关于 HugoAura 的使用问题 / 建议, 请勿提交至本 Repo。请前往 [HugoAura 主项目](https://github.com/HugoAura/Seewo-HugoAura) 提交 Issues。
