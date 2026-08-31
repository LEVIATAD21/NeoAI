"""Detecção de plataforma multiplataforma (Linux, Windows, Termux)
e detecção/recusa de dispositivos iPhone (iOS / Apple).

Tem como objetivo rodar em qualquer lugar, mas evitar deliberadamente
dispositivos iPhone (iOS). Se detectado, o sistema recusa-se a operar.
"""
import os
import sys
import platform


class PlatformInfo:
    def __init__(self):
        self.os_name = self._detect_os()
        self.is_termux = self._detect_termux()
        self.is_android = self._detect_android()
        self.is_linux = (self.os_name == "linux")
        self.is_windows = (self.os_name == "windows")
        self.is_iphone = self._detect_iphone()
        self.is_macos = (self.os_name == "darwin")
        self.is_root = self._detect_root()
        self.home = self._resolve_home()
        self.download_dir = self._resolve_download_dir()

    def _detect_os(self):
        p = sys.platform.lower()
        if p.startswith("win"):
            return "windows"
        if p == "darwin":
            return "darwin"
        if "linux" in p:
            return "linux"
        if p.startswith("freebsd") or p.startswith("openbsd"):
            return "bsd"
        return p

    def _detect_termux(self):
        # Caminho clássico do Termux no Android
        return "/data/data/com.termux" in os.getcwd() or \
            os.environ.get("TERMUX_VERSION") is not None or \
            "com.termux" in (os.environ.get("PREFIX") or "")

    def _detect_android(self):
        # getprop está disponível no Android via Termux
        try:
            import subprocess
            r = subprocess.run(["getprop", "ro.build.version.release"],
                               capture_output=True, text=True, timeout=3)
            if r.stdout.strip():
                return True
        except Exception:
            pass
        if platform.system() == "Linux" and self._termux_binary_present():
            return True
        return False

    def _termux_binary_present(self):
        return os.path.exists("/data/data/com.termux/files/usr/bin/termux-info") or \
            os.path.exists("/system/bin/getprop")

    def _detect_iphone(self):
        # iOS / iPhone: não há /proc, mas há sinais específicos.
        iphone_signals = [
            os.path.exists("/usr/lib/libMobileGestalt.dylib"),
            os.path.exists("/System/Library/CoreServices/SystemVersion.plist"),
        ]
        if self.os_name == "darwin":
            # Um Mac é darwin mas não é iPhone. Distinguir por sinais iOS.
            if any(iphone_signals):
                return True
            try:
                import subprocess
                r = subprocess.run(["uname", "-m"], capture_output=True,
                                   text=True, timeout=3)
                if "arm64" in r.stdout and "mac" not in platform.platform().lower():
                    # iOS usa arm64 também, mas esta heurística é conservadora
                    pass
            except Exception:
                pass
        return any(iphone_signals)

    def _detect_root(self):
        try:
            import subprocess
            r = subprocess.run(["id", "-u"], capture_output=True, text=True,
                               timeout=3)
            return r.stdout.strip() == "0"
        except Exception:
            return False

    def _resolve_home(self):
        if self.is_termux:
            return "/data/data/com.termux/files/home"
        return os.path.expanduser("~")

    def _resolve_download_dir(self):
        # Termux: ~/storage/shared/Download (acesso via storage, sem root)
        if self.is_termux:
            candidates = [
                os.path.join(self.home, "storage", "shared", "Download"),
                os.path.join(self.home, "storage", "downloads"),
            ]
            for c in candidates:
                if os.path.isdir(c):
                    return c
            # fallback: cria a pasta storage/downloads local
            local = os.path.join(self.home, "storage", "downloads")
            try:
                os.makedirs(local, exist_ok=True)
                return local
            except Exception:
                pass
        # Linux / Windows
        home = self.home
        if self.is_windows:
            downloads = os.path.join(home, "Downloads")
            if os.path.isdir(downloads):
                return downloads
            os.makedirs(downloads, exist_ok=True)
            return downloads
        downloads = os.path.join(home, "Downloads")
        if os.path.isdir(downloads):
            return downloads
        os.makedirs(downloads, exist_ok=True)
        return downloads

    def describe(self):
        lines = [
            "Sistema Operacional: {}".format(self.os_name),
            "Termux: {}".format("sim" if self.is_termux else "nao"),
            "Android: {}".format("sim" if self.is_android else "nao"),
            "Linux: {}".format("sim" if self.is_linux else "nao"),
            "Windows: {}".format("sim" if self.is_windows else "nao"),
            "iPhone/iOS: {}".format("sim" if self.is_iphone else "nao"),
            "Root: {}".format("sim" if self.is_root else "nao"),
            "Home: {}".format(self.home),
            "Download: {}".format(self.download_dir),
        ]
        return "\n".join(lines)
