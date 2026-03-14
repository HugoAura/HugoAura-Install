"""
HugoAura 卸载器
"""

import os
import shutil
import subprocess
import time
import winreg
from pathlib import Path
from loguru import logger as log
from utils import dirSearch, killer
from config import config


def check_hugoaura_installation():
    """
    检查HugoAura是否已安装

    返回:
        tuple: (是否已安装, 安装信息字典)
    """
    install_info = {
        "installed": False,
        "version": None,
        "install_time": None,
        "install_path": None,
        "asar_path": None,
        "aura_folder_path": None,
    }

    try:
        # 检查注册表信息
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, config.HUGOAURA_REGISTRY_KEY
        ) as key:
            try:
                version, _ = winreg.QueryValueEx(key, "Version")
                install_info["version"] = version
            except FileNotFoundError:
                pass

            try:
                install_time, _ = winreg.QueryValueEx(key, "InstallTime")
                install_info["install_time"] = install_time
            except FileNotFoundError:
                pass

        # 查找安装目录
        seewo_dir = dirSearch.find_seewo_resources_dir()
        if seewo_dir:
            install_path = Path(seewo_dir)
            asar_path = install_path / config.TARGET_ASAR_NAME
            aura_folder_path = install_path / config.EXTRACTED_FOLDER_NAME

            install_info["install_path"] = str(install_path)

            # 检查关键文件是否存在
            if asar_path.exists():
                install_info["asar_path"] = str(asar_path)

            if aura_folder_path.exists():
                install_info["aura_folder_path"] = str(aura_folder_path)

            # 必须同时满足以下条件才认为已安装：
            # 1. 注册表中有版本信息
            # 2. 存在 app.asar 文件 (被替换的希沃管家主程序)
            # 3. 存在 aura 文件夹 (HugoAura的资源文件)
            if (
                install_info["version"]
                and install_info["asar_path"]
                and install_info["aura_folder_path"]
            ):
                install_info["installed"] = True

    except FileNotFoundError:
        # 注册表项不存在
        pass
    except Exception as e:
        log.error(f"检查安装状态时发生错误: {e}")

    return install_info["installed"], install_info


def backup_original_asar(install_path):
    """
    检查是否存在原始app.asar的备份

    参数:
        install_path: 安装路径

    返回:
        str: 备份文件路径, 如果不存在则返回None
    """
    backup_patterns = [
        "app.asar.bak",
        "app.asar.backup",
        "app.asar.original",
        "app_original.asar",
    ]

    install_dir = Path(install_path)
    for pattern in backup_patterns:
        backup_path = install_dir / pattern
        if backup_path.exists():
            log.info(f"找到备份文件: {backup_path}")
            return str(backup_path)

    return None


def run_uninstallation(args=None, installerClassIns=None):
    uninstall_success = False
    error_detail = ""

    # 获取进度回调函数
    progress_callback = getattr(args, "progress_callback", None)
    status_callback = getattr(args, "status_callback", None)

    def update_progress(progress, step, status=None):
        if installerClassIns:
            if not installerClassIns.is_uninstalling:
                update_status("卸载已取消")
                raise Exception("UNINSTALLATION_CANCELLED")
        if progress_callback:
            progress_callback(progress, step, status)
        log.info(step)

    def update_status(status):
        if status_callback:
            status_callback(status)

    try:
        update_progress(0, "[0 / 8] 准备卸载")
        log.info(f"开始卸载 {config.APP_NAME}")

        update_progress(10, "[1 / 8] 检查安装状态")
        is_installed, install_info = check_hugoaura_installation()

        if not is_installed:
            log.warning("未检测到 HugoAura 安装, 可能已经卸载或未安装")
            if not (args and args.force): # not provide --force because it may cause UndefinedBehavior
                update_status("未检测到安装")
                return {"success": False, "errorInfo": "HugoAura 未安装"}

        log.info(f"检测到HugoAura安装:")
        if install_info["version"]:
            log.info(f"  版本: {install_info['version']}")
        if install_info["install_time"]:
            log.info(f"  安装时间: {install_info['install_time']}")
        if install_info["install_path"]:
            log.info(f"  安装路径: {install_info['install_path']}")

        update_progress(20, "[2 / 8] 停止相关进程")
        # 启动进程终止任务
        if not (args and args.dry_run):
            killer.start_killing_process()
            time.sleep(2.0)

        update_progress(30, "[3 / 8] 卸载文件系统过滤驱动")
        try:
            if not (args and args.dry_run):
                creationflags = subprocess.CREATE_NO_WINDOW
                command = ["fltmc", "unload", "SeewoKeLiteLady"]
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    creationflags=creationflags,
                )
                log.info(f"卸载驱动命令执行, 返回值: {result.returncode}")
        except Exception as e:
            log.warning(f"卸载文件系统过滤驱动时发生错误: {e}")

        update_progress(40, "[4 / 8] 恢复原始ASAR文件")
        if install_info["install_path"]:
            # 尝试恢复原始app.asar
            backup_path = backup_original_asar(install_info["install_path"])
            if backup_path:
                try:
                    current_asar = (
                        Path(install_info["install_path"]) / config.TARGET_ASAR_NAME
                    )
                    backup_file = Path(backup_path)

                    log.info(f"恢复原始ASAR文件: {backup_path} -> {current_asar}")
                    if not (args and args.dry_run):
                        if current_asar.exists():
                            os.remove(current_asar)
                        shutil.copy2(backup_file, current_asar)
                        # 删除备份文件
                        os.remove(backup_file)
                    log.success("原始ASAR文件恢复成功")
                except Exception as e:
                    error_detail = f"恢复原始ASAR文件失败: {e}"
                    log.error(error_detail)
                    raise Exception(error_detail)
            else:
                error_detail = "未找到原始ASAR备份文件, 无法恢复希沃管家到原始状态"
                log.error(error_detail)
                log.warning("建议从官网重新下载希沃管家完整安装包")
                raise Exception("OLD_ASAR_ENOENT")

        update_progress(50, "[5 / 8] 移除Aura文件夹")
        if install_info["aura_folder_path"]:
            aura_folder = Path(install_info["aura_folder_path"])
            try:
                if aura_folder.exists():
                    log.info(f"删除Aura文件夹: {aura_folder}")
                    if not (args and args.dry_run):
                        shutil.rmtree(aura_folder)
                    log.success("Aura文件夹删除成功")
                else:
                    log.info("Aura文件夹不存在, 跳过")
            except Exception as e:
                error_detail = f"删除Aura文件夹失败: {e}, 可能文件被占用"
                log.error(error_detail)
                # Aura文件夹删除失败不是致命错误, 记录警告但继续执行
                log.warning("Aura文件夹删除失败, 但不影响主要卸载流程")

        update_progress(60, "[6 / 8] 清理注册表")
        try:
            if not (args and args.dry_run):
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, config.HUGOAURA_REGISTRY_KEY)
            log.success("注册表清理完成")
        except FileNotFoundError:
            log.info("注册表项不存在, 跳过")
        except Exception as e:
            log.warning(f"清理注册表失败: {e}")

        update_progress(70, "[7 / 8] 清理用户数据")
        user_data_dir = Path(config.HUGOAURA_USER_DATA_DIR)
        try:
            if user_data_dir.exists():
                if args and hasattr(args, "keep_user_data") and args.keep_user_data:
                    log.info("保留用户数据目录")
                else:
                    log.info(f"删除用户数据目录: {user_data_dir}")
                    if not (args and args.dry_run):
                        shutil.rmtree(user_data_dir)
                    log.success("用户数据清理完成")
            else:
                log.info("用户数据目录不存在, 跳过")
        except Exception as e:
            log.warning(f"清理用户数据失败: {e}")

        uninstall_success = True
    except Exception as e:
        error_detail = e
        log.error(f"卸载过程中发生错误: {e}")
        uninstall_success = False
    finally:
        update_progress(90, "[8 / 8] 清理工作")
        if not (args and args.dry_run):
            killer.stop_killing_process()

        update_progress(100, "卸载完成" if uninstall_success else f"出现错误: {error_detail}", "success" if uninstall_success else "error")

        if uninstall_success:
            log.success("=========================================")
            log.success(f"{config.APP_NAME} 卸载完成")
            log.success("=========================================")
            log.info("希沃管家已恢复到原始状态")
        else:
            log.error("=========================================")
            log.error(f"{config.APP_NAME} 卸载失败")
            log.error("=========================================")
        return {"success": uninstall_success, "errorInfo": error_detail}


def get_uninstall_info():
    """
    获取卸载相关信息, 供 GUI 显示

    返回:
        dict: 卸载信息
    """
    is_installed, install_info = check_hugoaura_installation()

    uninstall_info = {
        "can_uninstall": is_installed,
        "version": install_info.get("version", "未知"),
        "install_time": install_info.get("install_time", "未知"),
        "install_path": install_info.get("install_path", "未知"),
        "has_backup": False,
        "estimated_time": "约 30 秒",
    }

    # 检查是否有备份文件
    if install_info.get("install_path"):
        backup_path = backup_original_asar(install_info["install_path"])
        uninstall_info["has_backup"] = backup_path is not None

    return uninstall_info
