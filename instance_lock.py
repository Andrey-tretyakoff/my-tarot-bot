import os
import sys
from paths import TEMP_DIR, ensure_runtime_dirs

LOCK_FILE = TEMP_DIR / "bot.pid"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        synchronize = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_single_instance() -> None:
    ensure_runtime_dirs()
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            if old_pid != os.getpid() and _pid_alive(old_pid):
                raise SystemExit(
                    f"❌ Уже запущен другой экземпляр бота (PID {old_pid}).\n"
                    "Остановите его, иначе будут ошибки Conflict в терминале."
                )
        except ValueError:
            pass
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def release_single_instance() -> None:
    if not LOCK_FILE.exists():
        return
    try:
        if int(LOCK_FILE.read_text(encoding="utf-8").strip()) == os.getpid():
            LOCK_FILE.unlink(missing_ok=True)
    except (ValueError, OSError):
        pass
