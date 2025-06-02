import os
import tempfile

APP_NAME = "HugoAura"
TARGET_PROCESS_NAME = "SeewoServiceAssistant.exe"
GITHUB_OWNER = "HugoAura"
GITHUB_REPO = "Seewo-HugoAura"
GITHUB_DL_REPO = "HugoAura-Resources"
ASAR_FILENAME = "app-patched.asar"
ZIP_FILENAME = "aura.zip"
TARGET_ASAR_NAME = "app.asar"
EXTRACTED_FOLDER_NAME = "aura"

BASE_DOWNLOAD_URLS = [
    f"https://bgithub.xyz/{GITHUB_OWNER}/{GITHUB_DL_REPO}/raw/main",  # bgithub 镜像
    f"https://ghfast.top/github.com/{GITHUB_OWNER}/{GITHUB_DL_REPO}/raw/main",  # GHFast 镜像
    f"https://gcore.jsdelivr.net/gh/{GITHUB_OWNER}/{GITHUB_DL_REPO}",  # GCore JSDelivr
    f"https://testingcf.jsdelivr.net/gh/{GITHUB_OWNER}/{GITHUB_DL_REPO}",  # Testing Cloudflare JSDelivr
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_DL_REPO}/raw/main",  # GitHub 源
]

GITHUB_API_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
)

SWASS_PATH_PATTERN = r"C:\Program Files (x86)\Seewo\SeewoService\SeewoService_*\SeewoServiceAssistant\resources"
TEMP_DIR_NAME = "Aura-Install-Temp"
TEMP_INSTALL_DIR = os.path.join(tempfile.gettempdir(), TEMP_DIR_NAME)

PROCESS_KILL_INTERVAL_SECONDS = 0.5
