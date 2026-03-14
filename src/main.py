import sys
import os
import time
import argparse
from loguru import logger as log
from utils import uac
from version import __appVer__
import installer
from config import config
from uninstaller import run_uninstallation


def parse_arguments():
    """
    解析命令行参数

    返回:
        argparse.Namespace: 解析后的参数对象
    """
    parser = argparse.ArgumentParser(description=f"{config.APP_NAME} 管理工具")

    # 版本选择参数组 (互斥)
    version_group = parser.add_mutually_exclusive_group()
    version_group.add_argument(
        "-v", "--version", help="指定要安装的版本标签, 例如 v1.0.0", type=str
    )
    version_group.add_argument(
        "-p", "--path", help="指定本地安装文件路径 (.asar 文件)", type=str
    )
    version_group.add_argument(
        "-l", "--latest", help="安装最新的稳定版本", action="store_true"
    )
    version_group.add_argument(
        "--pre", help="安装最新的预发行版本", action="store_true"
    )
    version_group.add_argument(
        "--ci", help="安装最新的 CI 版本", action="store_true"
    )

    parser.add_argument("-d", "--dir", help="指定希沃管家安装目录", type=str)
    parser.add_argument(
        "-y", "--yes", help="非交互模式, 自动确认所有操作", action="store_true"
    )
    parser.add_argument(
        "--dry-run", help="不进行实际安装操作, 仅执行下载流程", action="store_true"
    )
    parser.add_argument(
        "--list-exit-codes", help="显示所有退出代码及其释义", action="store_true"
    )
    parser.add_argument(
        "--cli", help="以 CLI 模式启动", action="store_true"
    )

    parser.add_argument(
        "--uninstall", help="卸载HugoAura", action="store_true"
    )
    parser.add_argument(
        "--keep-user-data", help="卸载保留用户数据", action="store_true"
    )

    return parser.parse_args()


def print_exit_codes():
    """
    打印所有退出代码及其释义
    """
    print("退出代码释义:")
    for code, desc in config.EXIT_CODES.items():
        print(f"  {code}: {desc}")


def main():
    """
    主函数, 处理命令行参数并执行提权安装流程
    """
    args = parse_arguments()

    if args.list_exit_codes:
        print_exit_codes()
        sys.exit(0)

    log.info(f"--- 启动 {config.APP_NAME} 管理工具 ---")
    log.info(f"管理工具版本: {__appVer__}")
    log.info(f"EXEC: {sys.executable}")
    log.info(f"Arg: {sys.argv}")

    if args.uninstall:
        run_uninstallation(
            args={
                "keep_user_data": args.keep_user_data,
                "force": False,
                "dry_run": False,
            }
        )
        sys.exit(0)

    has_version_args = args.version or args.path or args.pre or args.latest
    is_double_click = len(sys.argv) == 1

    if not has_version_args and not is_double_click and not args.dry_run:
        args.latest = True

    if not uac.is_admin():
        log.warning("管理工具需要管理员权限, 准备提权...")
        if not uac.run_as_admin():
            log.error("提权失败, 请尝试手动使用管理员权限运行")
            if not args.yes:
                log.info("按回车键退出...")
                input()
            sys.exit(2)  # 权限不足
    else:
        log.info("管理工具正以管理员权限运行, 即将启动安装流程...")
        success = False
        try:
            success = installer.run_installation(args)
        except Exception as e:
            log.exception(f"执行安装流程时发生意外错误: {e}")
            success = False
        finally:
            time.sleep(1.0)
            if not args.yes:
                print("\n按回车键退出...")
                input()

            sys.exit(0 if success else 1)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    pkg_dir = os.path.dirname(script_dir)
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)

    main()
