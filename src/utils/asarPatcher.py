import os
import shutil
from asar import extract_archive, create_archive, AsarArchive
from pathlib import Path
from loguru import logger as log

"""
这些全是笨蛋希沃和笨蛋asar库的造的孽
也不知道这段代码咋样反正它就是跑起来了就这样吧
"""
def _new_parse_metadata(self, info, path_in):
    for name, child in info["files"].items():
        cur_path = path_in / name
        node = self._search_node_from_path(cur_path, create=True)

        if "files" in child:
            node.unpacked = child.get("unpacked", False)
            setattr(node, 'type', 'DIRECTORY')
            node.files = {}
            _new_parse_metadata(self, child, cur_path)
        elif "link" in child:
            setattr(node, 'type', 'LINK')
            node.link = Path(child["link"])
        else:
            node.unpacked = child.get("unpacked", False)
            setattr(node, 'type', 'FILE')
            node.size = child["size"]
            node.integrity = child.get("integrity", {})

            if node.unpacked:
                node.file_path = self.asar_unpacked / node.path
            else:
                node.offset = int(child["offset"])
                if hasattr(self, '_asar_io') and self._asar_io is not None:
                    from asar.limited_reader import LimitedReader
                    node.file_reader = LimitedReader(self._asar_io, self._offset + node.offset, node.size)
                else:
                    node.file_reader = None
                    log.debug(f"文件 {cur_path} 的 _asar_io 无效，跳过 LimitedReader 创建")

def _new_extract(self, dst: Path = None):
    dst = dst if dst else Path.cwd()
    dst.mkdir(parents=True, exist_ok=True)

    for meta in self.metas:
        cur_dst = dst / meta.path

        try:
            if getattr(meta, 'type', None) == 'DIRECTORY' or (hasattr(meta, 'files') and meta.files):
                cur_dst.mkdir(parents=True, exist_ok=True)
            elif getattr(meta, 'type', None) == 'LINK':
                src_link = dst / meta.link
                try:
                    cur_dst.symlink_to(src_link)
                except (FileExistsError, OSError):
                    if cur_dst.exists():
                        cur_dst.unlink()
                    cur_dst.symlink_to(src_link)
            elif getattr(meta, 'unpacked', False):
                if hasattr(meta, 'file_path') and meta.file_path and meta.file_path.exists():
                    shutil.copy2(meta.file_path, cur_dst)
            else:
                if hasattr(meta, 'file_reader') and meta.file_reader is not None:
                    try:
                        with cur_dst.open("wb") as writer:
                            meta.file_reader.seek(0)
                            shutil.copyfileobj(meta.file_reader, writer)
                    except AttributeError as e:
                        if "'NoneType' object has no attribute 'seek'" in str(e):
                            log.warning(f"文件 {meta.path} 的 file_reader 无效，跳过")
                        else:
                            raise
                else:
                    log.warning(f"文件 {meta.path} 没有有效的 file_reader，无法提取")

        except Exception as e:
            log.error(f"提取文件 {meta.path} 时出错: {e}")

_original_parse_metadata = AsarArchive._parse_metadata
_original_extract = AsarArchive.extract
AsarArchive._parse_metadata = _new_parse_metadata
AsarArchive.extract = _new_extract

"""
下面才是真正的修改ASAR文件的代码
上面的啥也不是（雾
"""
def patch_asar_file(input_asar_path, temp_extract_dir, output_asar_path, core_dir):
    """
    解包、修改并重新打包 ASAR 文件

    Args:
        input_asar_path (str): 输入的 ASAR 文件完整路径
        temp_extract_dir (str): 解包临时目录位置
        output_asar_path (str): 修改后打包的 ASAR 文件完整路径
        core_dir (str): HugoAura 本体的 core 目录位置

    Returns:
        str: 修改后的 ASAR 文件输出路径
    """
    try:
        # 目录检查准备
        if not os.path.exists(core_dir):
            raise FileNotFoundError(f"Core 未找到: {core_dir}")
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)
        os.makedirs(temp_extract_dir)
        os.makedirs(os.path.dirname(output_asar_path), exist_ok=True)

        # 解包 ASAR 文件
        extract_archive(Path(input_asar_path), Path(temp_extract_dir))

        # 修改 ASRR 文件
        mainjs_patch(temp_extract_dir)
        for item in os.listdir(core_dir):
            src = os.path.join(core_dir, item)
            dst = os.path.join(temp_extract_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

        # 打包 ASAR 文件
        create_archive(Path(temp_extract_dir), Path(output_asar_path))
        return (True, output_asar_path)

    except Exception as e:
        return (False, e)

def mainjs_patch(extracted_dir):
    main_js_path = os.path.join(extracted_dir, "main.js")

    if not os.path.exists(main_js_path):
        raise FileNotFoundError(f"{main_js_path} not found.")

    with open(main_js_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = 'const hook = require("./hook.js");\n' + content
    content = content.replace('n.m=e', ';const zeron = require("./zeron.js");n = zeron(n);n.m=e')
    content = content.replace('let f=new s(Object.assign({},{transparent:!0,',
                             ';hook({ central: n, windowName: this.wname, config: c });let f=new s(Object.assign({},{transparent:!0,')
    content = content.replace('c.canOpenDevTool',
                             'c.canOpenDevTool,preload: __dirname + "\\\\preload.js"')

    with open(main_js_path, 'w', encoding='utf-8') as f:
        f.write(content)