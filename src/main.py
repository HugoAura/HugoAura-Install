import sys
import os
import time
import argparse
from logger.initLogger import log
from utils import dirSearch, uac
import installer
from config import config
import shutil
from pathlib import Path
from utils.backup import BackupManager


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

    parser.add_argument("-d", "--dir", help="指定希沃管家安装目录", type=str)
    parser.add_argument(
        "-y", "--yes", help="非交互模式, 自动确认所有操作", action="store_true"
    )
    parser.add_argument(
        "--list-exit-codes", help="显示所有退出代码及其释义", action="store_true"
    )
    parser.add_argument(
        "-u", "--update", help="更新已安装的 HugoAura", action="store_true"
    )
    parser.add_argument(
        "-f", "--fresh", help="全新安装 HugoAura", action="store_true"
    )
    parser.add_argument(
        "-b", "--backup", help="创建备份", action="store_true"
    )
    parser.add_argument(
        "-r", "--restore", help="从备份恢复", action="store_true"
    )

    return parser.parse_args()


def print_exit_codes():
    """
    打印所有退出代码及其释义
    """
    log.info("退出代码释义:")
    for code, desc in config.EXIT_CODES.items():
        log.info(f"  {code}: {desc}")


def check_installed():
    """
    检查是否已安装HugoAura
    
    返回:
        bool: 是否已安装
    """
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, config.HUGOAURA_REGISTRY_KEY) as key:
            winreg.QueryValueEx(key, "Version")
            return True
    except WindowsError:
        return False

def show_menu():
    """
    显示操作菜单
    
    返回:
        int: 用户选择的操作编号
    """
    log.info("HugoAura 已安装, 请选择操作:")
    log.info("1. 更新 (删除旧资源并下载新的)")
    log.info("2. 全新安装 (同时删除旧资源和 HugoAura 的所有配置后重新安装)")
    log.info("3. 备份 (立即创建新的备份, 不进行其他操作)")
    log.info("4. 恢复 (选择一个备份进行恢复)")
    
    while True:
        log.info("请输入选项 [1-4]: ")
        choice = input()
        if choice in ["1", "2", "3", "4"]:
            return int(choice)
        log.info("输入无效, 请重新输入。")

def main():
    """
    主函数, 处理命令行参数并执行提权安装流程
    """
    while True: # 添加循环以实现不退出
        args = parse_arguments()

        if args.list_exit_codes:
            print_exit_codes()
            log.info("按回车键退出...")
            input()
            sys.exit(0)

        log.info(f"--- 启动 {config.APP_NAME} 管理工具 ---")
        log.info(f"管理工具版本: 0.0.2-early-alpha")
        log.info(f"EXEC: {sys.executable}")
        log.info(f"Arg: {sys.argv}")

        has_version_args = args.version or args.path or args.pre or args.latest
        is_double_click = len(sys.argv) == 1
        
        if not has_version_args and not is_double_click:
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
            log.info("🎉 管理工具正以管理员权限运行")
            success = False
            isInstalled = check_installed()
            isInteractive = False
            try:
                if isInstalled:
                    if args.update or args.fresh or args.backup or args.restore:
                        # 命令行参数
                        if args.update:
                            choice = 1
                        elif args.fresh:
                            choice = 2
                        elif args.backup:
                            choice = 3
                        elif args.restore:
                            choice = 4
                    else:
                        # 交互式菜单
                        isInteractive = True
                        choice = show_menu()
                    
                    if choice == 1:
                        # 更新操作
                        success = installer.run_installation(args)
                    elif choice == 2:
                        # 全新安装操作
                        log.info("开始全新安装, 将删除旧配置和资源...")
                        
                        # 删除旧ASAR文件
                        resources_dir = dirSearch.find_seewo_resources_dir()
                        if resources_dir:
                            asar_path = Path(resources_dir) / config.TARGET_ASAR_NAME
                            aura_dir = Path(resources_dir) / config.EXTRACTED_FOLDER_NAME
                            
                            try:
                                if asar_path.exists():
                                    os.remove(asar_path)
                                    log.info(f"已删除旧 ASAR 文件: {asar_path}")
                                
                                if aura_dir.exists():
                                    shutil.rmtree(aura_dir)
                                    log.info(f"已删除旧 Aura 目录: {aura_dir}")
                            except Exception as e:
                                log.error(f"删除旧资源失败: {e}")
                        
                        # 删除注册表信息
                        try:
                            import winreg
                            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, config.HUGOAURA_REGISTRY_KEY)
                            log.info("已删除注册表信息")
                        except WindowsError as e:
                            log.warning(f"删除注册表信息失败: {e}")
                        
                        success = installer.run_installation(args)
                    elif choice == 3:
                        # 备份操作
                        backup_manager = BackupManager()
                        success, backup_name = backup_manager.create_backup()
                        if success:
                            log.info(f"✅ 备份创建成功: {backup_name}")
                        else:
                            log.error("❌ 备份创建失败")
                    elif choice == 4:
                        # 恢复操作
                        backup_manager = BackupManager()
                        backups = backup_manager.list_backups()
                        if not backups:
                            log.error("没有可用的备份")
                            success = False
                        else:
                            log.info("\n可用备份列表:")
                            for i, backup in enumerate(backups, 1):
                                log.info(f"[{i}] {backup['backup_name']} ({backup['timestamp']})")
                            
                            while True:
                                log.info(f"请选择要恢复的备份 [1 - {len(backups)}]: ")
                                choice = input()
                                if choice.isdigit() and 1 <= int(choice) <= len(backups):
                                    backup_name = backups[int(choice)-1]['backup_name']
                                    backup_info = backup_manager.get_backup_info(backup_name) ### To Be Done
                                    
                                    log.info("\n备份详细信息:")
                                    log.info(f"名称: {backup_info['backup_name']}")
                                    log.info(f"时间: {backup_info['timestamp']}")
                                    log.info(f"希沃版本: {backup_info.get('seewo_version', '未知')}")
                                    log.info(f"HugoAura版本: {backup_info.get('aura_version', '未知')}")
                                    log.info(f"跳过项目: {len(backup_info.get('skipped_items', []))}")
                                    log.info(f"MD5校验值: {backup_info.get('archive_md5', '无')}")
                                    log.info(f"验证状态: {'已验证' if backup_info.get('verified') else '未验证'}")
                                    
                                    log.info("确认恢复此备份吗？(Y/n): ") # APT-style 选项 (确信
                                    confirm = input()
                                    if confirm.lower() == 'y':
                                        success = backup_manager.restore_backup(backup_name)
                                        if success:
                                            log.info(f"✅ 备份恢复成功: {backup_name}")
                                        else:
                                            log.error(f"❌ 备份恢复失败: {backup_name}")
                                        break
                                    else:
                                        log.info("已取消恢复操作")
                                        success = False
                                        break
                                log.info("输入无效, 请重新输入。")
                else:
                    # 未安装, 直接进入安装流程
                    success = installer.run_installation(args)
            except Exception as e:
                log.exception(f"执行管理流程时发生意外错误: {e}")
                success = False
            finally:
                time.sleep(1.0)
                if not args.yes:
                    log.info("\n按回车键继续...")
                    input()
                if isInteractive: # 仅在交互式菜单下要求继续操作, 否则退出循环
                    os.system('cls') # 清屏
                else:
                    sys.exit(0) # 跑路


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    pkg_dir = os.path.dirname(script_dir)
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)

    main()
