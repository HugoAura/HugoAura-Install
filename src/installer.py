from datetime import datetime
import os
import shutil
import subprocess
import time
import sys
import winreg
import requests
from pathlib import Path
from loguru import logger as log
from utils import dirSearch, fileDownloader, killer, asarPatcher
from config import config
import lifecycle as lifecycleMgr
import typeDefs.lifecycle as lifecycleTypes


def fetch_github_releases():
    url = config.GITHUB_API_URL
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"获取 GitHub Releases 失败: {e}")
        return None


def select_release_source(args=None):
    """
    选择安装版本来源

    参数:
        args: 命令行参数对象, 如果提供则尝试使用非交互式方式选择

    返回:
        str: 版本标签或本地文件路径, 如果在非交互模式下失败则返回None
    """
    # 如果指定了本地文件路径
    if args and args.path:
        if os.path.exists(args.path):
            log.info(f"使用指定的本地文件: {args.path}")
            return args.path
        else:
            log.error(f"指定的本地文件不存在: {args.path}")
            sys.exit(7)

    # 如果指定了版本标签
    if args and args.version:
        log.info(f"使用指定的版本标签: {args.version}")
        return args.version

    releases = fetch_github_releases()
    if not releases:
        log.error("无法获取版本信息")
        if args and args.yes:
            log.critical("非交互模式下无法获取版本信息, 安装终止")
            sys.exit(4)  # 资源文件下载失败
        return input("请输入版本 Tag 或本地文件路径: ")

    # 分类发行版和预发行版
    stable = [r for r in releases if not r.get("prerelease", False)]
    pre = [
        r
        for r in releases
        if r.get("prerelease", False) and not str.startswith(r["name"], "[CI")
    ]
    ci = [r for r in releases if str.startswith(r["name"], "[CI")]

    # 如果指定了使用最新稳定版
    if args and args.latest and stable:
        latest_stable = stable[0].get("tag_name", "")
        log.info(f"使用最新稳定版: {latest_stable}")
        return latest_stable

    # 如果指定了使用最新预发行版
    if args and args.pre and pre:
        latest_pre = pre[0].get("tag_name", "")
        log.info(f"使用最新预发行版: {latest_pre}")
        return latest_pre

    if args and args.ci and ci:
        latest_ci = ci[0].get("tag_name", "")
        log.info(f"使用最新 CI 构建: {latest_ci}")
        return latest_ci

    # 非交互模式下的默认行为
    if args and args.yes:
        if stable:
            latest_stable = stable[0].get("tag_name", "")
            log.info(f"默认使用最新稳定版: {latest_stable}")
            return latest_stable
        elif pre:
            latest_pre = pre[0].get("tag_name", "")
            log.info(f"未找到稳定版, 默认使用最新预发行版: {latest_pre}")
            return latest_pre
        else:
            log.critical("未找到有效版本, 安装终止")
            sys.exit(7)  # 参数错误

    # 交互式选择
    options = []
    print("请选择要安装的版本: ")
    if stable:
        print("--- 发行版 ---")
        for rel in stable:
            tag = rel.get("tag_name", "")
            name = rel.get("name", tag)
            print(f"[{len(options)+1}] {tag} {name}")
            options.append(tag)
    if pre:
        print("--- 预发行版 ---")
        for rel in pre:
            tag = rel.get("tag_name", "")
            name = rel.get("name", tag)
            print(f"[{len(options)+1}] {tag} {name}")
            options.append(tag)
    if ci:
        latest_ci = ci[0]
        print("--- 自动构建版 ---")
        print(f"[{len(options)+1}] {latest_ci["tag_name"]} {latest_ci["name"]}")
        options.append(latest_ci["tag_name"])

    print("--- 或选择手动输入 ---")
    print(f"[{len(options)+1}] 手动输入版本 Tag")

    while True:
        choice = input(f"请输入序号 [1-{len(options)+1}]: ")
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1]
            elif idx == len(options) + 1:
                return input("请输入版本 Tag: ")
        print("输入无效, 请重新输入。")


def run_installation(args=None, installerClassIns=None):
    """
    运行安装流程

    参数:
        args: 命令行参数对象, 如果提供则尝试使用非交互式方式安装
        installerClassIns: InstallerModel 实例

    返回:
        bool: 安装是否成功
    """
    install_success = False
    install_dir_path = None
    downloaded_zip_path = None
    downloaded_core_path = None
    download_source = None
    ssa_asar = config.TARGET_ASAR_NAME
    if_patch = True

    error_detail = ""

    # 获取进度回调函数
    progress_callback = getattr(args, "progress_callback", None)
    status_callback = getattr(args, "status_callback", None)

    def update_status(status):
        if status_callback:
            status_callback(status)

    def update_progress(progress, step, status=None):
        if installerClassIns:
            if not installerClassIns.is_installing:
                update_status("安装已取消")
                raise Exception("INSTALLATION_CANCELLED")
        if progress_callback:
            progress_callback(progress, step, status)
        log.info(step)

    def rep_dl_progress(curDownloadSize, fullSize, fileName):
        progress = round(curDownloadSize / fullSize * 100, 2)
        update_progress(progress, f"[3 / 10] {fileName} 文件下载中, 进度: {progress} %")

    try:
        update_progress(0, "[0 / 10] 准备")
        log.info(f"即将开始运行 {config.APP_NAME} 管理工具")

        update_progress(10, "[1 / 10] 查找希沃管家安装目录")
        # 如果指定了安装目录
        if args and args.dir:
            install_dir_path_str = args.dir
            if not os.path.isdir(install_dir_path_str):
                log.critical(f"指定的安装目录不存在: {install_dir_path_str}")
                return False
            log.info(f"使用指定的安装目录: {install_dir_path_str}")
        else:
            install_dir_path_str = dirSearch.find_seewo_resources_dir()
            if not install_dir_path_str:
                log.critical("未能找到 SeewoServiceAssistant 安装目录")
                if args and args.yes:
                    log.critical("非交互模式下无法手动输入安装目录, 安装终止")
                    sys.exit(3)  # 未找到希沃管家安装目录
                log.info("您可以尝试手动输入安装目录:")
                install_dir_path_str = input()
                if not os.path.isdir(install_dir_path_str):
                    log.critical(f"指定的目录不存在: {install_dir_path_str}")
                    return False

        install_dir_path = Path(install_dir_path_str)

        update_progress(20, "[2 / 10] 选择 HugoAura 版本")
        download_source = select_release_source(args)
        if os.path.exists(download_source):
            log.info(f"已选择本地文件: {download_source}")
        else:
            log.info(f"已选择版本 Tag: {download_source}")

        update_progress(30, "[3 / 10] 获取资源文件")
        dlCallbackFuncName = (
            lifecycleTypes.GLOBAL_CALLBACKS.REPORT_DOWNLOAD_PROGRESS.value
        )
        if not str.startswith(download_source, "v"):
            if os.path.exists(download_source):
                downloaded_zip_path = Path(str(download_source))
                downloaded_core_path = Path(
                    str(download_source).replace("aura.zip", "core.zip")
                )
            else:
                log.critical("请输入合法的路径，并确保本地路径存在 aura.zip 文件")
                return False
        else:
            lifecycleMgr.callbacks[dlCallbackFuncName] = rep_dl_progress
            downloaded_core_path, downloaded_zip_path = (
                fileDownloader.download_release_files(download_source)
            )
        if not downloaded_core_path or not downloaded_zip_path:
            log.critical("资源文件下载失败, 即将结束安装")
            return False

        lifecycleMgr.callbacks[dlCallbackFuncName] = None

        update_progress(40, "[4 / 10] 解压资源文件")
        temp_extract_path = Path(config.TEMP_INSTALL_DIR + "\\aura")
        temp_extract_path_core  = Path(config.TEMP_INSTALL_DIR + "\\core")
        if not fileDownloader.unzip_file(downloaded_zip_path, temp_extract_path) or not fileDownloader.unzip_file(downloaded_core_path, temp_extract_path_core):
            error_detail = "资源文件解压失败"
            log.critical(error_detail)
            raise Exception(error_detail)

        expected_aura_source_path = temp_extract_path
        if not expected_aura_source_path.is_dir():
            log.error(
                f"ZIP 解压后目录结构校验异常 {config.EXTRACTED_FOLDER_NAME} {temp_extract_path}, 尝试自动修复..."
            )
            potential_nested_path = (
                temp_extract_path
                / Path(downloaded_zip_path.stem)
                / config.EXTRACTED_FOLDER_NAME
            )
            if potential_nested_path.is_dir():
                log.warning(f"检测到嵌套文件夹, 自动移动中...")
                expected_aura_source_path = potential_nested_path
            else:
                error_detail = "Aura.zip 结构解析失败, 文件结构不正确"
                log.critical(error_detail)
                raise Exception(error_detail)

        update_progress(50, "[5 / 10] 卸载文件系统过滤驱动")
        try:
            if not args.dry_run:
                creationflags = subprocess.CREATE_NO_WINDOW
                command = ["fltmc", "unload", "SeewoKeLiteLady"]
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    creationflags=creationflags,
                )
                log.info(f"卸载命令执行成功, 返回值: {result.returncode}")
                if result.stdout:
                    log.debug(f"fltmc stdout: {result.stdout.strip()}")
                if result.stderr:
                    log.warning(f"fltmc stderr: {result.stderr.strip()}")
        except FileNotFoundError:
            log.error('未能找到 "fltmc" 命令, 请确保您的系统环境完整。')
        except Exception as e:
            log.error(f"调用 fltmc 时发生未知错误: {e}")

        update_progress(60, "[6 / 10] 移动 Aura 文件夹")
        target_aura_path = install_dir_path / config.EXTRACTED_FOLDER_NAME
        log.info(
            f"即将将 '{config.EXTRACTED_FOLDER_NAME}' 移动至 {target_aura_path}..."
        )
        try:
            if target_aura_path.exists():
                log.warning(
                    f"发现旧版本 HugoAura 目录: {target_aura_path}, 即将清理..."
                )
                if not args.dry_run:
                    shutil.rmtree(target_aura_path)
                    time.sleep(0.1)
                ssa_asar = "app.asar.bak"
                if os.path.exists(install_dir_path / ssa_asar):
                    log.warning(
                        "Patch ASAR 将使用备份的ASAR，请确保其完整并未更改..."
                    )
                else:
                    log.warning(
                        "app.asar.bak未找到，将不进行Patch操作..."
                    )
                    log.warning(
                        "若现有的app.asar为未patch过的，请将其复制到app.asar.bak。"
                    )
                    if_patch = False
            if not args.dry_run:
                shutil.move(str(expected_aura_source_path), str(target_aura_path))
            log.success(f"成功移动文件夹 '{config.EXTRACTED_FOLDER_NAME}'")
        except Exception as e:
            error_detail = f"移动文件夹 '{config.EXTRACTED_FOLDER_NAME}' 时发生错误: {e}"
            log.critical(error_detail)
            raise Exception(error_detail)
            
        if if_patch:
            update_progress(65, "[6.5 / 10] Patch ASAR")
            PatchResult = asarPatcher.patch_asar_file(
                input_asar_path=str(install_dir_path / ssa_asar),
                temp_extract_dir=str(Path(config.TEMP_INSTALL_DIR) / "asar_temp"),
                output_asar_path=str(Path(config.TEMP_INSTALL_DIR) / config.ASAR_FILENAME),
                core_dir=str(temp_extract_path_core)
            )
            if not PatchResult[0]:
                error_detail = f"ASAR 文件修改失败: {PatchResult[1]}"
                log.critical(error_detail)
                raise Exception(error_detail)
            log.info(f"ASAR 文件修改成功, 输出路径: {PatchResult[1]}")

        update_progress(70, "[7 / 10] 启动结束进程后台任务")
        if not args.dry_run:
            killer.start_killing_process()
            time.sleep(2.0)

        if if_patch:
            update_progress(80, "[8 / 10] 替换 ASAR 包")
            original_asar_path = install_dir_path / config.TARGET_ASAR_NAME
            temp_asar_path = PatchResult[1]

            log.info(f"正在将 {original_asar_path} 替换为新的 {temp_asar_path}...")

            # 创建原始ASAR文件的备份
            backup_asar_path = install_dir_path / "app.asar.bak"
            if original_asar_path.exists() and not backup_asar_path.exists():
                try:
                    log.info(f"创建原始ASAR备份: {backup_asar_path}")
                    if not args.dry_run:
                        shutil.copy2(str(original_asar_path), str(backup_asar_path))
                    log.success("原始ASAR备份创建成功")
                except Exception as e:
                    log.warning(f"创建ASAR备份失败: {e}")

            def del_original_asar():
                if original_asar_path.exists():
                    log.info(f"尝试删除旧的 {original_asar_path}...")
                    try:
                        if not args.dry_run:
                            os.remove(original_asar_path)
                        log.success(f"旧的 {config.TARGET_ASAR_NAME} 删除成功。")
                        time.sleep(0.2)
                    except OSError as e:
                        log.error(
                            f"未能删除 {original_asar_path}: {e} | 旧的 ASAR 可能仍被占用中..."
                        )
                        log.info("准备重试删除...")
                        time.sleep(0.5)
                        del_original_asar()
                else:
                    log.info(f"未找到旧的 {config.TARGET_ASAR_NAME}, 跳过删除...")

            del_original_asar()

            try:
                log.info(f"正在将 {temp_asar_path} 移到 {original_asar_path}...")
                if not args.dry_run:
                    shutil.move(str(temp_asar_path), str(original_asar_path))
                if original_asar_path.exists() or args.dry_run:
                    log.success(f"替换 {config.TARGET_ASAR_NAME} 成功。")
                    install_success = True
                else:
                    error_detail = f"移动到 {original_asar_path} 失败, ASAR文件替换未成功"
                    log.critical(error_detail)
                    raise Exception(error_detail)
            except Exception as e:
                error_detail = f"替换ASAR文件时发生错误: {e}。请检查文件系统过滤驱动已被卸载, 并确认对希沃管家目录有写入权限。"
                log.critical(error_detail)
                raise Exception(error_detail)
        else:
            install_success = True


        update_progress(90, "[9 / 10] 写入版本信息和安装时间到注册表")
        # 写入版本信息和安装时间到注册表
        try:
            if not args.dry_run:
                with winreg.CreateKey(
                    winreg.HKEY_CURRENT_USER, config.HUGOAURA_REGISTRY_KEY
                ) as key:
                    winreg.SetValueEx(
                        key,
                        "Version",
                        0,
                        winreg.REG_SZ,
                        (
                            download_source
                            if isinstance(download_source, str)
                            else "local"
                        ),
                    )
                    winreg.SetValueEx(
                        key, "InstallTime", 0, winreg.REG_SZ, datetime.now().isoformat()
                    )
            log.info("版本信息和安装时间已写入注册表")
        except Exception as e:
            log.warning(f"写入注册表失败: {e}")

    except Exception as e:
        error_detail = e
        if installerClassIns and not installerClassIns.is_installing:
            log.warning(f"用户取消了安装操作")
        else:
            log.exception(f"安装过程中发生未知错误: {e}")
        install_success = False
    finally:
        update_progress(
            100,
            f"[10 / 10] 安装{"完成" if install_success else f"出错: {error_detail}"}",
            "success" if install_success else "error",
        )

        if not args.dry_run:
            killer.stop_killing_process()

        temp_dir = Path(config.TEMP_INSTALL_DIR)
        if temp_dir.exists():
            try:
                if not args.dry_run:
                    shutil.rmtree(temp_dir)
                else:
                    log.info(f"临时文件夹目录: {temp_dir}")
                    log.info("可前往该目录检查 Dry Run 下载 / 解压产物")
            except OSError as e:
                log.warning(f"临时文件夹清理失败: {e}")
                log.warning("请尝试手动清理")

        if install_success:
            log.success("-----------------------------------------")
            log.success(f"{config.APP_NAME} 安装完成")
            log.success("-----------------------------------------")
        else:
            log.error("---------------------------------------------")
            log.error(f"{config.APP_NAME} 安装失败")
            log.error("---------------------------------------------")

        return {"success": install_success, "errorInfo": error_detail}
