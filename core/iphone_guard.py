"""Bloco de recusa para iPhone/iOS. A IA se recusa a rodar em dispositivos Apple
(iPhone), conforme requisito. Inclui uma segunda verificação por sinais do SO."""
from core.platform import PlatformInfo


IPHONE_HINTS = [
    "/usr/lib/libMobileGestalt.dylib",
    "/System/Library/CoreServices/SystemVersion.plist",
]


def verificar_iphone(platform=None):
    if platform is None:
        platform = PlatformInfo()
    if platform.is_iphone:
        return True
    # verificação dupla
    import os
    for h in IPHONE_HINTS:
        if os.path.exists(h):
            return True
    # iOS não tem /proc e tem uname Darwin + arm64 normalmente iOS
    if platform.os_name == "darwin":
        try:
            import subprocess
            r = subprocess.run(["uname", "-a"], capture_output=True,
                               text=True, timeout=3)
            lower = r.stdout.lower()
            if "iphone" in lower or "ipad" in lower or "ios" in lower:
                return True
        except Exception:
            pass
    return False
