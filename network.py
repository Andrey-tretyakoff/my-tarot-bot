import os
import sys


def get_proxy_url() -> str | None:
    proxy = (os.getenv("TELEGRAM_PROXY") or "").strip()
    if proxy:
        return proxy
    return _windows_system_proxy()


def ssl_verify_enabled() -> bool:
    return os.getenv("TELEGRAM_SSL_VERIFY", "true").lower() not in ("0", "false", "no")


def _windows_system_proxy() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not enabled:
                return None
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            if not server:
                return None
            if ";" in server:
                server = server.split(";")[0]
            if "=" in server:
                server = server.split("=")[-1]
            if not server.startswith("http"):
                server = f"http://{server}"
            return server
    except Exception:
        return None
