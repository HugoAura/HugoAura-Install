import requests
import time
import zipfile
import shutil
import os
from pathlib import Path
from loguru import logger as log
from config.config import (
    BASE_DOWNLOAD_URLS,
    ASAR_FILENAME,
    ZIP_FILENAME,
    TEMP_INSTALL_DIR,
)
import typeDefs.lifecycle
import lifecycle as lifecycleMgr


desiredTag = None


def download_file(url: str, dest_folder: str, filename: str) -> Path | str | None:
    dest_path = Path(dest_folder) / filename
    log.info(f"正在从 {url} 下载 {filename}, 目标目录: {dest_path}")

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        downloadHeaders = {
            "Accept-Encoding": "",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        }
        with requests.get(url, stream=True, timeout=60, headers=downloadHeaders) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            log.info(
                f"文件大小: {total_size / 1024 / 1024:.2f} MB"
                if total_size
                else "文件大小: 未知"
            )

            with open(dest_path, "wb") as f:
                downloaded_size = 0
                chunk_size = 8192
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        callbackFuncName = (
                            typeDefs.lifecycle.GLOBAL_CALLBACKS.REPORT_DOWNLOAD_PROGRESS.value
                        )
                        if callbackFuncName in lifecycleMgr.callbacks.keys():
                            if lifecycleMgr.callbacks[callbackFuncName]:
                                lifecycleMgr.callbacks[callbackFuncName](
                                    downloaded_size, total_size, f.name.split("\\")[-1]
                                )  # type: ignore

        log.success(f"文件 {filename} 下载成功。")
        return dest_path
    except requests.exceptions.RequestException as e:
        log.error(f"下载文件 {filename} 时发生网络错误: {e}")
        if dest_path.exists():
            os.remove(dest_path)
        return None
    except Exception as e:
        if "INSTALLATION_CANCELLED" in str(e):
            return "DL_CANCEL"
        log.error(f"写入文件 {filename} 时发生意外错误: {e}")
        if dest_path.exists():
            os.remove(dest_path)
        return None


def download_file_multi_sources(filename: str, dest_folder: str) -> Path | None:
    """
    尝试从多个下载源下载文件, 直到成功或所有源都失败。
    """

    global desiredTag

    for base_url in BASE_DOWNLOAD_URLS:
        url = f"{base_url}/{desiredTag}/{filename}"
        result = download_file(url, dest_folder, filename)
        if result == "DL_CANCEL":
            log.warning("下载已取消")
            return None
        elif result:
            return result  # type: ignore
        else:
            log.warning(f"从 {url} 下载失败, 尝试下一个源...")
    log.critical(f"所有下载源均失败, 无法下载 {filename}")
    return None


def unzip_file(zip_path: Path, extract_to: Path) -> bool:
    log.info(f"正在解压 {zip_path.name}, 目标目录: {extract_to}")
    try:
        extract_to.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_to)
        log.success(f"解压 {zip_path.name} 成功。")
        return True
    except zipfile.BadZipFile:
        log.error(f"解压时发生错误: {zip_path.name} 不是一个有效的 ZIP 文件。")
        return False
    except Exception as e:
        log.error(f"解压时发生错误: 文件名称: {zip_path.name} | 错误: {e}")
        return False


def download_release_files(tagName) -> tuple[Path | None, Path | None]:
    log.info(f"准备下载 HugoAura 资源文件...")

    global desiredTag
    desiredTag = tagName
    temp_dir = Path(TEMP_INSTALL_DIR)
    if temp_dir.exists():
        log.info(f"正在清理旧的临时文件夹: {temp_dir}")
        try:
            shutil.rmtree(temp_dir)
        except OSError as e:
            log.error(f"清理失败 {temp_dir}, 请确保当前用户有 %TEMP% 的写入权限: {e}")
            return None, None
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"成功创建临时文件夹: {temp_dir}")
    except OSError as e:
        log.error(
            f"未能创建临时文件夹 {temp_dir}, 错误信息: {e} | 请确保当前用户有 %TEMP% 的写入权限"
        )
        return None, None

    downloaded_asar_path = download_file_multi_sources(ASAR_FILENAME, str(temp_dir))
    if not downloaded_asar_path:
        log.critical("下载 app-patched.asar 时发生错误, 安装进程终止。")
        return None, None

    downloaded_zip_path = download_file_multi_sources(ZIP_FILENAME, str(temp_dir))
    if not downloaded_zip_path:
        log.critical("下载 aura.zip 时发生错误, 安装进程终止。")
        return downloaded_asar_path, None

    return downloaded_asar_path, downloaded_zip_path
