# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# 获取项目根目录
project_root = Path.cwd()
src_dir = project_root / 'src'

block_cipher = None

# 定义数据文件
datas = [
    # 包含图标文件
    (str(src_dir / 'app' / 'pubilc' / 'aura.ico'), '.'),
    # 包含配置文件
    (str(src_dir / 'config'), 'config'),
]

# 定义隐藏导入的模块
hiddenimports = [
    # tkinter 相关
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.font',
    
    # ttkbootstrap 相关
    'ttkbootstrap',
    'ttkbootstrap.constants',
    'ttkbootstrap.themes',
    'ttkbootstrap.style',
    'ttkbootstrap.widgets',
    'ttkbootstrap.icons',
    
    # PIL/Pillow 相关 (ttkbootstrap依赖)
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageFilter',
    'PIL.ImageEnhance',
    'PIL.ImageOps',
    'PIL._tkinter_finder',
    'PIL._imaging',
    
    # 日志系统
    'loguru',
    
    # 网络请求
    'requests',
    'urllib3',
    
    # 系统相关
    'ctypes',
    'winreg',
    'subprocess',
    'threading',
    'pathlib',
    
    # 项目模块
    'app.tk.controller.main_controller',
    'app.tk.ui.main_window',
    'app.tk.models.installer_model',
    'logger.initLogger',
    'utils.uac',
    'utils.dirSearch',
    'utils.fileDownloader',
    'utils.killer',
    'config.config',
    'installer',
    'uninstaller',
]

# 分析阶段
a = Analysis(
    [str(src_dir / 'app.py')],  # 主程序入口
    pathex=[str(src_dir)],      # Python路径
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(project_root / 'hooks')],  # 添加自定义钩子路径
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减小文件大小
        'matplotlib',
        'numpy',
        'pandas',
        # 注意：已移除PIL从排除列表，因为ttkbootstrap需要它
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ阶段
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE阶段 - 生成可执行文件
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AuraInstaller',           # 可执行文件名
    debug=False,                    # 不包含调试信息
    bootloader_ignore_signals=False,
    strip=False,                    # 不删除符号表
    upx=True,                      # 使用UPX压缩（如果可用）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(src_dir / 'app' / 'pubilc' / 'aura.ico'),  # 设置图标
    version_file=str(project_root / 'version_info.py'),  # 版本信息文件
    uac_admin=True,                # 请求管理员权限
    uac_uiaccess=False,
)

# 如果需要生成目录分发版本，取消注释以下代码
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='AuraInstaller'
# ) 