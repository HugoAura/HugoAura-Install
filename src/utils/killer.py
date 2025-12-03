import subprocess
import threading
from logger.initLogger import log
from config.config import TARGET_PROCESS_NAME, PROCESS_KILL_INTERVAL_SECONDS

_stop_event = threading.Event()
_kill_thread = None


def _kill_loop():
    log.info(
        f"启动后台任务: 每 {PROCESS_KILL_INTERVAL_SECONDS} 秒结束一次 {TARGET_PROCESS_NAME} 进程"
    )
    while not _stop_event.is_set():
        try:
            creationflags = subprocess.CREATE_NO_WINDOW
            for procName in TARGET_PROCESS_NAME:
                result = subprocess.run(
                    ["taskkill", "/f", "/im", procName],
                    capture_output=True,
                    text=True,
                    check=False,
                    creationflags=creationflags,
                )
                if result.returncode != 0 and "没有找到进程" not in result.stderr.lower():
                    log.warning(
                        f"进程结束失败: {result.stderr.strip()} (Code: {result.returncode}) 请检查管理工具的权限状态"
                    )
                else:
                    log.debug(
                        f"尝试结束进程 {TARGET_PROCESS_NAME}。操作输出: {result.stdout.strip() or result.stderr.strip()}"
                    )

        except FileNotFoundError:
            log.error('无法调用 "taskkill", 请确认系统环境是否完整。')
            _stop_event.set()
        except Exception as e:
            log.error(f"停止 taskkill 循环时发生意外错误: {e}")

        _stop_event.wait(PROCESS_KILL_INTERVAL_SECONDS)

    log.info(f"结束后台任务: 持续结束 {TARGET_PROCESS_NAME} 进程")


def start_killing_process():
    global _kill_thread, _stop_event
    if _kill_thread and _kill_thread.is_alive():
        return

    _stop_event.clear()
    _kill_thread = threading.Thread(target=_kill_loop, daemon=True)
    _kill_thread.start()


def stop_killing_process():
    global _kill_thread
    _stop_event.set()
    if _kill_thread and _kill_thread.is_alive():
        _kill_thread.join(timeout=PROCESS_KILL_INTERVAL_SECONDS * 4)
        if _kill_thread.is_alive():
            log.warning("taskkill 循环意外结束。(可忽略)")
    _kill_thread = None
