import os
import shutil
import json
import winreg
import zipfile
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from logger.initLogger import log
from config.config import (
    BACKUP_BASE_DIR,
    HUGOAURA_USER_DATA_DIR,
    HUGOAURA_REGISTRY_KEY,
    TARGET_ASAR_NAME,
    EXTRACTED_FOLDER_NAME,
    SWASS_PATH_PATTERN,
    MAX_BACKUPS,
    BACKUP_ARCHIVE_NAME
)
from utils.dirSearch import find_seewo_resources_dir

class BackupManager:
    """HugoAura 备份管理器"""
    
    def __init__(self):
        """初始化备份管理器"""
        self.backup_base_dir = Path(BACKUP_BASE_DIR)
        self.user_data_dir = Path(HUGOAURA_USER_DATA_DIR)
        self.registry_key = HUGOAURA_REGISTRY_KEY
        
        self.backup_base_dir.mkdir(parents=True, exist_ok=True)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化时检查并清理过期备份
        self._cleanup_old_backups()
    
    def _get_seewo_version(self) -> Optional[str]:
        """获取希沃管家版本号"""
        try:
            resources_dir = find_seewo_resources_dir()
            if not resources_dir:
                return None
            
            # 从路径中提取版本号
            path_parts = Path(resources_dir).parts
            for part in path_parts:
                if part.startswith('SeewoService_'):
                    return part.replace('SeewoService_', '')
            return None
        except Exception as e:
            log.error(f"获取希沃管家版本失败: {e}")
            return None
    
    def _get_aura_version(self) -> Optional[str]:
        """从注册表获取 HugoAura 版本号"""
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, self.registry_key) as key:
                version, _ = winreg.QueryValueEx(key, "Version")
                return version
        except (FileNotFoundError, OSError):
            log.warning("注册表中未找到 HugoAura 版本信息")
            return None
        except Exception as e:
            log.error(f"读取注册表版本信息失败: {e}")
            return None
    
    def _set_aura_version(self, version: str) -> bool:
        """设置 HugoAura 版本号到注册表"""
        try:
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, self.registry_key) as key:
                winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, version)
            return True
        except Exception as e:
            log.error(f"写入注册表版本信息失败: {e}")
            return False
    
    def _generate_backup_name(self) -> str:
        """生成备份目录名称（基于时间戳）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"backup_{timestamp}"
        
    def _calculate_md5(self, file_path: Path) -> Optional[str]:
        """计算文件的MD5哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: MD5哈希值, 如果计算失败则返回None
        """
        try:
            if not file_path.exists() or not file_path.is_file():
                log.error(f"无法计算MD5: 文件不存在或不是文件: {file_path}")
                return None
                
            md5_hash = hashlib.md5()
            with open(file_path, "rb") as f:
                # 分块读取大文件
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            log.error(f"计算 MD5 哈希值失败: {e}")
            return None
            
    def _compress_backup(self, backup_dir: Path, files_to_compress: List[Path]) -> Optional[Path]:
        """将备份文件压缩到 ZIP 文件
        
        Args:
            backup_dir: 备份目录
            files_to_compress: 要压缩的文件列表
            
        Returns:
            Optional[Path]: 压缩文件路径, 如果压缩失败则返回 None
        """
        try:
            if not files_to_compress:
                log.warning("没有文件需要压缩")
                return None
                
            archive_path = backup_dir / BACKUP_ARCHIVE_NAME
            file_hashes = {}
            
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in files_to_compress:
                    if not file_path.exists():
                        log.warning(f"跳过不存在的文件: {file_path}")
                        continue
                        
                    # 计算文件的MD5哈希值
                    file_hash = self._calculate_md5(file_path)
                    if file_hash:
                        file_hashes[file_path.name] = file_hash
                    
                    # 添加到压缩文件
                    if file_path.is_file():
                        zipf.write(file_path, arcname=file_path.name)
                        log.debug(f"已添加文件到压缩包: {file_path.name}")
                    elif file_path.is_dir():
                        # 递归添加目录中的所有文件
                        for root, _, files in os.walk(file_path):
                            for file in files:
                                file_full_path = Path(root) / file
                                relative_path = file_full_path.relative_to(backup_dir)
                                zipf.write(file_full_path, arcname=str(relative_path))
                                log.debug(f"已添加文件到压缩包: {relative_path}")
            
            # 将哈希值写入压缩包
            if file_hashes:
                hash_file = backup_dir / "file_hashes.json"
                with open(hash_file, 'w', encoding='utf-8') as f:
                    json.dump(file_hashes, f, ensure_ascii=False, indent=2)
                    
                # 将哈希文件也添加到压缩包
                with zipfile.ZipFile(archive_path, 'a', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(hash_file, arcname=hash_file.name)
                    
                # 删除临时哈希文件
                hash_file.unlink()
                
            log.info(f"备份文件已压缩: {archive_path}")
            return archive_path
        except Exception as e:
            log.error(f"压缩备份文件失败: {e}")
            return None
            
    def _cleanup_old_backups(self) -> None:
        """清理旧备份"""
        try:
            if not self.backup_base_dir.exists():
                return
                
            backups = self.list_backups()
            if len(backups) <= MAX_BACKUPS:
                return
                
            # 按时间戳排序, 删除最旧的备份
            backups_to_delete = backups[MAX_BACKUPS:]
            for backup in backups_to_delete:
                backup_name = backup.get('backup_name')
                if backup_name:
                    log.info(f"清理旧备份: {backup_name}")
                    self.delete_backup(backup_name)
                    
            log.info(f"备份清理完成, 当前备份数量: {min(len(backups), MAX_BACKUPS)}")
        except Exception as e:
            log.error(f"清理旧备份失败: {e}")
            
    def _verify_backup_integrity(self, backup_dir: Path) -> bool:
        """验证备份文件的完整性
        
        Args:
            backup_dir: 备份目录
            
        Returns:
            bool: 验证是否成功
        """
        try:
            archive_path = backup_dir / BACKUP_ARCHIVE_NAME
            if not archive_path.exists():
                log.error(f"备份压缩包不存在: {archive_path}")
                return False
                
            # 验证压缩包是否可以正常打开
            try:
                with zipfile.ZipFile(archive_path, 'r') as zipf:
                    # 检查文件列表
                    file_list = zipf.namelist()
                    if not file_list:
                        log.error("备份压缩包为空")
                        return False
                        
                    # 检查文件完整性
                    bad_files = zipf.testzip()
                    if bad_files:
                        log.error(f"备份压缩包中存在损坏的文件: {bad_files}")
                        return False
                        
                    # 检查哈希值文件是否存在
                    if "file_hashes.json" not in file_list:
                        log.warning("备份中没有找到哈希值文件, 跳过哈希验证")
                    else:
                        # 提取哈希值文件
                        with zipf.open("file_hashes.json") as f:
                            file_hashes = json.load(f)
                            
                        # 验证文件哈希值
                        for filename, expected_hash in file_hashes.items():
                            if filename not in file_list:
                                log.error(f"备份中缺少文件: {filename}")
                                return False
            except zipfile.BadZipFile:
                log.error(f"备份压缩包已损坏: {archive_path}")
                return False
                
            log.info(f"备份完整性验证成功: {backup_dir.name}")
            return True
        except Exception as e:
            log.error(f"验证备份完整性失败: {e}")
            return False
    
    def _save_backup_info(self, backup_dir: Path, seewo_version: Optional[str], aura_version: Optional[str], skipped_items: List[Dict] = None, archive_path: Optional[Path] = None) -> bool:
        """保存备份信息到 JSON 文件
        
        Args:
            backup_dir: 备份目录路径
            seewo_version: 希沃管家版本号
            aura_version: HugoAura 版本号
            skipped_items: 备份过程中跳过的项目列表
            archive_path: 备份压缩包路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            archive_md5 = None
            if archive_path and archive_path.exists():
                archive_md5 = self._calculate_md5(archive_path)
                
            backup_info = {
                "timestamp": datetime.now().isoformat(),
                "seewo_version": seewo_version,
                "aura_version": aura_version,
                "backup_name": backup_dir.name,
                "skipped_items": skipped_items or [],
                "archive_file": str(archive_path.name) if archive_path else None,
                "archive_md5": archive_md5,
                "verified": bool(archive_md5),
                "created_at": time.time()
            }
            
            info_file = backup_dir / "backup_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)
            
            log.info(f"备份信息已保存: {info_file}")
            return True
        except Exception as e:
            log.error(f"保存备份信息失败: {e}")
            return False
    
    def _load_backup_info(self, backup_dir: Path) -> Optional[Dict]:
        """加载备份信息"""
        try:
            info_file = backup_dir / "backup_info.json"
            if not info_file.exists():
                return None
            
            with open(info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"加载备份信息失败: {e}")
            return None
    
    def create_backup(self, aura_version: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """创建备份
        
        Args:
            aura_version: HugoAura 版本号（从注册表读取）
            
        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 备份目录名称)
        """
        try:
            # 初始化跳过项目列表
            skipped_items = []
            files_to_compress = []
            
            # 获取希沃管家资源目录
            resources_dir = find_seewo_resources_dir()
            if not resources_dir:
                log.error("未找到希沃管家安装目录, 无法创建备份")
                return False, None
            
            resources_path = Path(resources_dir)
            asar_file = resources_path / TARGET_ASAR_NAME
            aura_folder = resources_path / EXTRACTED_FOLDER_NAME
            
            # 创建备份目录
            backup_name = self._generate_backup_name()
            backup_dir = self.backup_base_dir / backup_name
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            log.info(f"开始创建备份到: {backup_dir}")
            
            # 备份 ASAR 文件
            backup_asar = backup_dir / TARGET_ASAR_NAME
            try:
                if not asar_file.exists():
                    log.warning(f"ASAR 文件不存在, 跳过备份: {asar_file}")
                    skipped_items.append({
                        "type": "file",
                        "path": str(asar_file),
                        "reason": "文件不存在"
                    })
                else:
                    shutil.copy2(asar_file, backup_asar)
                    log.info(f"已备份 ASAR 文件: {backup_asar}")
                    files_to_compress.append(backup_asar)
                    
                    # 计算并记录MD5哈希值
                    asar_md5 = self._calculate_md5(backup_asar)
                    if asar_md5:
                        log.debug(f"ASAR 文件 MD5: {asar_md5}")
            except Exception as e:
                log.warning(f"备份 ASAR 文件失败, 跳过: {e}")
                skipped_items.append({
                    "type": "file",
                    "path": str(asar_file),
                    "reason": f"备份失败: {str(e)}"
                })
            
            # 备份 aura 文件夹（如果存在）
            backup_aura_folder = backup_dir / EXTRACTED_FOLDER_NAME
            try:
                if not aura_folder.exists():
                    log.warning(f"aura 文件夹不存在, 跳过备份: {aura_folder}")
                    skipped_items.append({
                        "type": "folder",
                        "path": str(aura_folder),
                        "reason": "文件夹不存在"
                    })
                else:
                    shutil.copytree(aura_folder, backup_aura_folder)
                    log.info(f"已备份 aura 文件夹: {backup_aura_folder}")
                    files_to_compress.append(backup_aura_folder)
            except Exception as e:
                log.warning(f"备份 aura 文件夹失败, 跳过: {e}")
                skipped_items.append({
                    "type": "folder",
                    "path": str(aura_folder),
                    "reason": f"备份失败: {str(e)}"
                })
            
            # 获取版本信息
            seewo_version = self._get_seewo_version()
            if aura_version is None:
                aura_version = self._get_aura_version()
            
            # 检查是否有任何文件被成功备份
            if len(skipped_items) > 0 and not backup_asar.exists() and not backup_aura_folder.exists():
                log.error("所有备份项目都失败, 无法创建有效备份")
                # 清理空备份目录
                shutil.rmtree(backup_dir)
                return False, None
                
            # 压缩备份文件
            archive_path = None
            if files_to_compress:
                log.info("开始压缩备份文件...")
                archive_path = self._compress_backup(backup_dir, files_to_compress)
                if not archive_path:
                    log.warning("备份文件压缩失败, 将保留未压缩的文件")
                else:
                    # 验证备份完整性
                    if not self._verify_backup_integrity(backup_dir):
                        log.warning("备份完整性验证失败, 但备份文件已创建")
                    
                    # 压缩成功后删除原始文件
                    for file_path in files_to_compress:
                        if file_path.is_file() and file_path.exists():
                            file_path.unlink()
                        elif file_path.is_dir() and file_path.exists():
                            shutil.rmtree(file_path)
            
            # 保存备份信息
            if not self._save_backup_info(backup_dir, seewo_version, aura_version, skipped_items, archive_path):
                log.warning("备份信息保存失败, 但备份文件已创建")
            
            # 清理旧备份
            self._cleanup_old_backups()
            
            log.info(f"✅ 备份创建成功: {backup_name}")
            if skipped_items:
                log.warning(f"备份过程中有 {len(skipped_items)} 个项目被跳过, 详情请查看备份信息文件")
                
            return True, backup_name
            
        except Exception as e:
            log.error(f"创建备份失败: {e}")
            # 记录详细的异常信息
            import traceback
            log.debug(f"备份异常详情: {traceback.format_exc()}")
            return False, None
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份
        
        Returns:
            List[Dict[str, Any]]: 备份信息列表, 包含以下字段：
                - name: 备份名称
                - path: 备份路径
                - time: 备份时间（格式化字符串）
                - timestamp: 备份时间戳
                - seewo_version: 希沃管家版本
                - aura_version: HugoAura 版本
                - compressed: 是否已压缩
                - archive_name: 压缩包名称（如果已压缩）
                - verified: 备份完整性验证状态
                - md5_hash: 备份文件的MD5哈希值（如果有）
                - skipped_items: 备份过程中跳过的项目列表（如果有）
        """
        try:
            if not self.backup_base_dir.exists():
                log.warning(f"备份目录不存在: {self.backup_base_dir}")
                return []
            
            backups = []
            for backup_dir in self.backup_base_dir.iterdir():
                if not backup_dir.is_dir() or not backup_dir.name.startswith('backup_'):
                    continue
                    
                backup_info = self._load_backup_info(backup_dir)
                if not backup_info:
                    # 没有备份信息文件, 尝试从目录名称中提取信息
                    backup_name = backup_dir.name
                    timestamp_str = backup_name.split("_")[1] if "_" in backup_name else ""
                    
                    try:
                        backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        backup_time = "未知"
                        
                    backup_info = {
                        "name": backup_name,
                        "path": str(backup_dir),
                        "time": backup_time,
                        "timestamp": timestamp_str,
                        "seewo_version": "未知",
                        "aura_version": "未知",
                        "compressed": False,
                        "verified": False
                    }
                else:
                    # 添加备份路径
                    backup_info["path"] = str(backup_dir)
                    backup_info["name"] = backup_dir.name
                    
                    # 添加压缩状态
                    backup_info["compressed"] = "archive_file" in backup_info and backup_info["archive_file"] is not None
                    
                    # 检查备份完整性
                    if backup_info.get("compressed", False) and not backup_info.get("verified", False):
                        # 如果备份已压缩但未验证, 尝试验证
                        backup_info["verified"] = self._verify_backup_integrity(backup_dir)
                        # 更新备份信息文件
                        self._save_backup_info(
                            backup_dir,
                            backup_info.get("seewo_version"),
                            backup_info.get("aura_version"),
                            backup_info.get("skipped_items", []),
                            backup_dir / backup_info.get("archive_file", "")
                        )
                    
                backups.append(backup_info)
            
            # 按时间戳排序（最新的在前面）
            backups.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return backups
            
        except Exception as e:
            log.error(f"列出备份失败: {e}")
            # 记录详细的异常信息
            import traceback
            log.debug(f"列出备份异常详情: {traceback.format_exc()}")
            return []
    
    def delete_backup(self, backup_name: str) -> bool:
        """删除指定备份
        
        Args:
            backup_name: 备份名称
            
        Returns:
            bool: 是否删除成功
        """
        try:
            backup_dir = self.backup_base_dir / backup_name
            
            if not backup_dir.exists():
                log.error(f"备份不存在: {backup_name}")
                return False
            
            if not backup_dir.is_dir():
                log.error(f"备份路径不是目录: {backup_dir}")
                return False
            
            # 检查备份目录是否可访问
            try:
                # 尝试列出目录内容, 确保有访问权限
                list(backup_dir.iterdir())
            except PermissionError:
                log.error(f"无权限访问备份目录: {backup_dir}")
                return False
            except Exception as e:
                log.warning(f"检查备份目录访问权限时出错: {e}")
            
            # 删除备份目录
            try:
                shutil.rmtree(backup_dir)
                log.info(f"✅ 备份已删除: {backup_name}")
                return True
            except PermissionError:
                log.error(f"无权限删除备份目录: {backup_dir}")
                return False
            except FileNotFoundError:
                log.warning(f"备份目录已不存在: {backup_dir}")
                return True  # 目录已不存在, 视为删除成功
            except Exception as e:
                log.error(f"删除备份目录时出错: {e}")
                return False
            
        except Exception as e:
            log.error(f"删除备份失败: {e}")
            # 记录详细的异常信息
            import traceback
            log.debug(f"删除备份异常详情: {traceback.format_exc()}")
            return False
    
    def restore_backup(self, backup_name: str) -> bool:
        """还原备份
        
        Args:
            backup_name: 备份目录名称
            
        Returns:
            bool: 是否成功
        """
        try:
            backup_dir = self.backup_base_dir / backup_name
            if not backup_dir.exists() or not backup_dir.is_dir():
                log.error(f"备份目录不存在: {backup_dir}")
                return False
                
            log.info(f"开始还原备份: {backup_name}")
            
            # 获取希沃管家资源目录
            resources_dir = find_seewo_resources_dir()
            if not resources_dir:
                log.error("未找到希沃管家安装目录, 无法还原备份")
                return False
                
            resources_path = Path(resources_dir)
            asar_file = resources_path / TARGET_ASAR_NAME
            aura_folder = resources_path / EXTRACTED_FOLDER_NAME
            
            # 加载备份信息
            backup_info = self._load_backup_info(backup_dir)
            if not backup_info:
                log.error(f"无法加载备份信息, 还原失败")
                return False
                
            # 检查是否是压缩备份
            archive_path = None
            if "archive_name" in backup_info and backup_info["archive_name"]:
                archive_path = backup_dir / backup_info["archive_name"]
                if not archive_path.exists():
                    log.error(f"备份压缩包不存在: {archive_path}")
                    return False
                    
                # 验证备份完整性
                if not self._verify_backup_integrity(backup_dir):
                    log.error("备份完整性验证失败, 无法还原")
                    return False
                    
                # 解压备份文件
                log.info(f"开始解压备份文件: {archive_path}")
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        zip_ref.extractall(backup_dir)
                    log.info("备份文件解压成功")
                except Exception as e:
                    log.error(f"解压备份文件失败: {e}")
                    return False
            
            backup_asar = backup_dir / TARGET_ASAR_NAME
            backup_aura_folder = backup_dir / EXTRACTED_FOLDER_NAME
            
            # 还原 ASAR 文件
            if backup_asar.exists():
                # 备份当前文件
                if asar_file.exists():
                    current_backup = asar_file.with_suffix(".bak")
                    shutil.copy2(asar_file, current_backup)
                    log.info(f"已备份当前 ASAR 文件: {current_backup}")
                
                # 复制备份文件
                shutil.copy2(backup_asar, asar_file)
                log.info(f"已还原 ASAR 文件: {asar_file}")
            else:
                log.warning(f"备份中不存在 ASAR 文件, 跳过还原")
            
            # 还原 aura 文件夹
            if backup_aura_folder.exists():
                # 备份当前文件夹
                if aura_folder.exists():
                    current_backup = aura_folder.with_suffix(".bak")
                    if current_backup.exists():
                        shutil.rmtree(current_backup)
                    shutil.copytree(aura_folder, current_backup)
                    log.info(f"已备份当前 aura 文件夹: {current_backup}")
                    # 删除当前文件夹
                    shutil.rmtree(aura_folder)
                
                # 复制备份文件夹
                shutil.copytree(backup_aura_folder, aura_folder)
                log.info(f"已还原 aura 文件夹: {aura_folder}")
            else:
                log.warning(f"备份中不存在 aura 文件夹, 跳过还原")
            
            # 清理解压的临时文件
            if archive_path and archive_path.exists():
                if backup_asar.exists() and backup_asar != archive_path:
                    backup_asar.unlink()
                if backup_aura_folder.exists() and backup_aura_folder != archive_path:
                    shutil.rmtree(backup_aura_folder)
            
            if backup_info and "aura_version" in backup_info:
                # 更新注册表版本信息
                self._set_aura_version(backup_info["aura_version"])
                log.info(f"已更新 HugoAura 版本信息: {backup_info['aura_version']}")
            
            log.info(f"✅ 备份还原成功: {backup_name}")
            return True
            
        except Exception as e:
            log.error(f"还原备份失败: {e}")
            # 记录详细的异常信息
            import traceback
            log.debug(f"还原异常详情: {traceback.format_exc()}")
            return False


# 便捷函数
def create_backup(aura_version: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """创建备份的便捷函数"""
    manager = BackupManager()
    return manager.create_backup(aura_version)


def list_backups() -> List[Dict]:
    """列出备份的便捷函数"""
    manager = BackupManager()
    return manager.list_backups()


def delete_backup(backup_name: str) -> bool:
    """删除备份的便捷函数"""
    manager = BackupManager()
    return manager.delete_backup(backup_name)


def restore_backup(backup_name: str) -> bool:
    """还原备份的便捷函数"""
    manager = BackupManager()
    return manager.restore_backup(backup_name)