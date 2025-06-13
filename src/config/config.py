import os
import tempfile

# 应用信息
APP_NAME = "HugoAura"
TARGET_PROCESS_NAME = "SeewoServiceAssistant.exe"

# GitHub 仓库信息
GITHUB_OWNER = "HugoAura"
GITHUB_REPO = "Seewo-HugoAura"
GITHUB_DL_REPO = "Seewo-HugoAura"

# 文件名
ASAR_FILENAME = "app-patched.asar"
ZIP_FILENAME = "aura.zip"
TARGET_ASAR_NAME = "app.asar"
EXTRACTED_FOLDER_NAME = "aura"

# 下载 URL 列表
BASE_DOWNLOAD_URLS = [
    f"https://bgithub.xyz/{GITHUB_OWNER}/{GITHUB_DL_REPO}/releases/download",  # bgithub 镜像
    f"https://ghproxy.net/github.com/{GITHUB_OWNER}/{GITHUB_DL_REPO}/releases/download", # GHProxy 镜像
    f"https://github.tbedu.top/github.com/{GITHUB_OWNER}/{GITHUB_DL_REPO}/releases/download", # TBEdu 镜像
    f"https://ghfast.top/github.com/{GITHUB_OWNER}/{GITHUB_DL_REPO}/releases/download",  # GHFast 镜像
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_DL_REPO}/releases/download",  # GitHub 源
]

# GitHub API URL
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# 目标路径模式
SWASS_PATH_PATTERN = r"C:\\Program Files (x86)\\Seewo\\SeewoService\\SeewoService_*\\SeewoServiceAssistant\\resources"

# 临时目录信息
TEMP_DIR_NAME = "Aura-Install-Temp"
TEMP_INSTALL_DIR = os.path.join(tempfile.gettempdir(), TEMP_DIR_NAME)

# HugoAura 数据路径
HUGOAURA_USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "Documents", "HugoAura")
HUGOAURA_REGISTRY_KEY = r"SOFTWARE\\HugoAura"

# 备份目录信息
BACKUP_DIR_NAME = "HugoAura-Backup"
BACKUP_BASE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "HugoAura-Install-Backup")

# 备份配置
MAX_BACKUPS = 10  # 最大备份数量
BACKUP_ARCHIVE_NAME = "backup.zip"  # 备份压缩包名称

# 进程杀死间隔
PROCESS_KILL_INTERVAL_SECONDS = 0.5

# 退出代码释义
EXIT_CODES = {
    0: "安装成功",
    1: "安装失败（一般错误）",
    2: "权限不足, 需要管理员权限",
    3: "未找到希沃管家安装目录",
    4: "资源文件下载失败",
    5: "资源文件解压失败",
    6: "文件系统操作失败",
    7: "参数错误"
}
