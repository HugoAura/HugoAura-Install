import os
import shutil
import subprocess
import time
from pathlib import Path
from logger.initLogger import log
from utils import dirSearch, fileDownloader, killer
from config import config


def fetch_github_releases():
    import requests
    url = config.GITHUB_API_URL
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"获取 GitHub Releases 失败: {e}")
        return None


def select_release_tag():
    releases = fetch_github_releases()
    if not releases:
        log.error("无法获取版本信息，您可以手动输入版本 Tag：")
        return input("请输入版本 Tag：")
    # 分类发行版和预发行版
    stable = [r for r in releases if not r.get("prerelease", False)]
    pre = [r for r in releases if r.get("prerelease", False)]
    options = []
    print("请选择要安装的版本：")
    if stable:
        print("--- 发行版 ---")
        for rel in stable:
            tag = rel.get("tag_name", "")
            name = rel.get("name", tag)
            print(f"[{len(options)+1}] {tag} (发行版) {name}")
            options.append(tag)
    if pre:
        print("--- 预发行版 ---")
        for rel in pre:
            tag = rel.get("tag_name", "")
            name = rel.get("name", tag)
            print(f"[{len(options)+1}] {tag} (预发行版) {name}")
            options.append(tag)
    print(f"[{len(options)+1}] 手动输入版本 Tag")
    while True:
        choice = input(f"请输入序号 [1-{len(options)+1}]：")
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx-1]
            elif idx == len(options)+1:
                return input("请输入版本 Tag：")
        print("输入无效，请重新输入。")


def run_installation():
    install_success = False
    install_dir_path = None
    downloaded_asar_path = None
    downloaded_zip_path = None
    selected_tag = None

    try:
        log.info("[0 / 9] 准备安装")
        log.info(f"即将开始运行 {config.APP_NAME} 的一键安装脚本")

        log.info("[1 / 9] 查找希沃管家安装目录")
        install_dir_path_str = dirSearch.find_seewo_resources_dir()
        if not install_dir_path_str:
            log.critical("未能找到 SeewoServiceAssistant 安装目录")
            log.info("您可以尝试手动输入安装目录:")
            install_dir_path_str = input()

        install_dir_path = Path(install_dir_path_str)

        log.info("[2 / 9] 选择 HugoAura 版本")
        selected_tag = select_release_tag()
        log.info(f"已选择版本 Tag: {selected_tag}")

        log.info("[3 / 9] 下载资源文件")
        downloaded_asar_path, downloaded_zip_path = (
            fileDownloader.download_latest_release_files()
        )
        if not downloaded_asar_path or not downloaded_zip_path:
            log.critical("资源文件下载失败, 即将结束安装")
            return False

        log.info("[4 / 9] 解压资源文件")
        temp_extract_path = Path(config.TEMP_INSTALL_DIR + "\\aura")
        if not fileDownloader.unzip_file(downloaded_zip_path, temp_extract_path):
            log.critical("资源文件解压失败, 即将结束安装")
            return False

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
                log.critical("Aura.zip 结构解析失败, 即将结束安装")
                return False

        log.info("[5 / 9] 卸载文件系统过滤驱动")
        try:
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

        log.info("[6 / 9] 移动 Aura 文件夹")
        target_aura_path = install_dir_path / config.EXTRACTED_FOLDER_NAME
        log.info(
            f"即将将 '{config.EXTRACTED_FOLDER_NAME}' 移动至 {target_aura_path}..."
        )
        try:
            if target_aura_path.exists():
                log.warning(
                    f"发现旧版本 HugoAura 目录: {target_aura_path}, 即将清理..."
                )
                shutil.rmtree(target_aura_path)
                time.sleep(0.1)
            shutil.move(str(expected_aura_source_path), str(target_aura_path))
            log.success(f"成功移动文件夹 '{config.EXTRACTED_FOLDER_NAME}'")
        except Exception as e:
            log.critical(f"移动文件夹 '{config.EXTRACTED_FOLDER_NAME}' 时发生错误: {e}")
            return False

        log.info("[7 / 9] 启动结束进程后台任务")
        killer.start_killing_process()
        time.sleep(2.0)

        log.info("[8 / 9] 替换 ASAR 包")
        original_asar_path = install_dir_path / config.TARGET_ASAR_NAME
        temp_asar_path = downloaded_asar_path

        log.info(f"正在将 {original_asar_path} 替换为新的 {temp_asar_path.name}...")

        def del_original_asar():
            if original_asar_path.exists():
                log.info(f"尝试删除旧的 {original_asar_path}...")
                try:
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
            shutil.move(str(temp_asar_path), str(original_asar_path))
            if original_asar_path.exists():
                log.success(f"替换 {config.TARGET_ASAR_NAME} 成功。")
                install_success = True
            else:
                log.critical(f"移动到 {original_asar_path} 失败, 请尝试手动操作。")
                install_success = False
        except Exception as e:
            log.critical(f"移动文件时发生未知错误: {e}")
            log.critical(
                "请再次检查文件系统过滤驱动已被 unload, 并检查对希沃管家目录的可写入性。"
            )
            install_success = False

    except Exception as e:
        log.exception(f"安装过程中发生未知错误: {e}")
        install_success = False
    finally:
        log.info("[9 / 9] 清理工作")
        killer.stop_killing_process()

        temp_dir = Path(config.TEMP_INSTALL_DIR)
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except OSError as e:
                log.warning(f"临时文件夹清理失败: {e}")
                log.warning("请尝试手动清理。")

        if install_success:
            log.success("-----------------------------------------")
            log.success(f"{config.APP_NAME} 安装完成")
            log.success("-----------------------------------------")
        else:
            log.error("---------------------------------------------")
            log.error(f"{config.APP_NAME} 安装失败")
            log.error("---------------------------------------------")

        return install_success
