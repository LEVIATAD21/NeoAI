"""Executor de funções cross-platform (Linux, Windows, Termux).

Usa apenas subprocess e ferramentas do sistema, sem dependências externas.
Classifica cada comando como 'seguro' (leitura) ou 'perigoso' (escrita/efeito)
para que o fluxo de confirmação decida.
"""
import os
import re
import shutil
import subprocess
import sys


# padrões que indicam ação de escrita / efeito colateral
PERIGOSO_SUBSTRINGS = [
    "rm ", "rm -rf", "del ", "format ", "mkfs", "dd ", "shutdown", ":(){",
    "> ", ">> ", "mv ", "chmod ", "chown ", "curl", "wget", "pip install",
    "npm install", "apt install", "pkg install", "apt-get", "git push",
    "git commit", "python", "sudo", "make ", "install ", "kill ", "reboot",
    "mklink", "runas", "taskkill ",
]

COMANDOS_SEGUROS_EXPLICITOS = [
    "ls", "dir", "cat", "type", "echo", "pwd", "cd", "whoami", "id", "uname",
    "date", "time", "which", "where", "find", "ls", "head", "tail", "grep",
    "history", "free", "df", "ps", "top", "getprop",
]


class Executor:
    def __init__(self, platform):
        self.platform = platform
        self.pwd = self._pwd_inicial()

    def _pwd_inicial(self):
        if self.platform.is_termux:
            return "/data/data/com.termux/files/home"
        return os.path.expanduser("~")

    @property
    def shell(self):
        if self.platform.is_windows:
            return ["cmd", "/c"]
        return ["/bin/sh", "-c"]

    def is_perigoso(self, comando):
        cl = comando.lower().strip()
        for p in PERIGOSO_SUBSTRINGS:
            if p in cl:
                return True
        base = cl.split()[0].lower() if cl.split() else ""
        return base not in COMANDOS_SEGUROS_EXPLICITOS

    def executar(self, comando, cwd=None):
        """Executa um comando e retorna (codigo_saida, stdout, stderr)."""
        if self.platform.is_windows:
            proc = subprocess.run(comando, shell=True, capture_output=True,
                                  text=True, cwd=cwd or self.pwd, timeout=120)
        else:
            proc = subprocess.run(comando, shell=True, capture_output=True,
                                  text=True, cwd=cwd or self.pwd, timeout=120)
        if proc.returncode == 0 and cwd:
            # atualiza o diretório de trabalho se o comando foi um cd válido
            pass
        self.pwd = cwd or self.pwd
        return proc.returncode, proc.stdout, proc.stderr

    def mudar_dir(self, caminho):
        if os.path.isdir(caminho):
            self.pwd = os.path.abspath(caminho)
            return "Diretorio alterado para: " + self.pwd
        return "Erro: diretorio nao encontrado: " + caminho

    def disponivel(self, programa):
        """Verifica se um programa/binário existe no sistema."""
        if self.platform.is_windows:
            r = subprocess.run(["where", programa], capture_output=True,
                               text=True)
            return r.returncode == 0
        return shutil.which(programa) is not None

    def detectar_shell(self):
        return ("cmd" if self.platform.is_windows
                else "Termux/bash (Android)" if self.platform.is_termux
                else "bash")

    def info_comandos(self):
        """Retorna comandos comuns disponíveis no SO atual."""
        lista = ['ls', 'cat', 'echo', 'pwd', 'date', 'whoami', 'id',
                 'uname', 'which', 'find', 'grep', 'head', 'tail', 'cd']
        if self.platform.is_windows:
            lista_w = ['dir', 'type', 'cd', 'echo', 'where', 'ver', 'date',
                       'time', 'mkdir', 'copy', 'del', 'move']
            return {"sistema": "Windows (cmd)", "comandos": lista_w}
        if self.platform.is_termux:
            lista_t = ['pkg', 'termux-*', 'getprop', 'echo', 'ls', 'cat',
                       'cd', 'pwd', 'whoami', 'id', 'uname', 'date']
            return {"sistema": "Termux (Android)", "comandos": lista_t}
        return {"sistema": "Linux", "comandos": lista}

    # ---------------------- apps Android (via Termux, sem root) ----------------------

    APPS_ANDROID = {
        "whatsapp": {"nome": "WhatsApp", "pkg": "com.whatsapp",
                     "activity": "com.whatsapp.Main"},
        "zap": {"nome": "WhatsApp", "pkg": "com.whatsapp",
                "activity": "com.whatsapp.Main"},
        "zapzap": {"nome": "WhatsApp", "pkg": "com.whatsapp",
                   "activity": "com.whatsapp.Main"},
        "instagram": {"nome": "Instagram", "pkg": "com.instagram.android",
                      "activity": "com.instagram.mainactivity.MainActivity"},
        "insta": {"nome": "Instagram", "pkg": "com.instagram.android",
                  "activity": "com.instagram.mainactivity.MainActivity"},
        "telegram": {"nome": "Telegram", "pkg": "org.telegram.messenger",
                     "activity": "org.telegram.ui.LaunchActivity"},
        "youtube": {"nome": "YouTube", "pkg": "com.google.android.youtube",
                    "activity": "com.google.android.apps.youtube.app.WatchWhileActivity"},
        "yt": {"nome": "YouTube", "pkg": "com.google.android.youtube",
               "activity": "com.google.android.apps.youtube.app.WatchWhileActivity"},
        "chrome": {"nome": "Chrome", "pkg": "com.android.chrome",
                   "activity": "com.google.android.apps.chrome.Main"},
        "galeria": {"nome": "Galeria", "pkg": "com.google.android.apps.photos",
                    "activity": "com.google.android.apps.photos.home.HomeActivity"},
        "fotos": {"nome": "Galeria", "pkg": "com.google.android.apps.photos",
                  "activity": "com.google.android.apps.photos.home.HomeActivity"},
        "spotify": {"nome": "Spotify", "pkg": "com.spotify.music",
                    "activity": "com.spotify.music.MainActivity"},
        "maps": {"nome": "Google Maps", "pkg": "com.google.android.apps.maps",
                 "activity": "com.google.android.maps.MapsActivity"},
        "maps": {"nome": "Google Maps", "pkg": "com.google.android.apps.maps",
                 "activity": "com.google.android.maps.MapsActivity"},
        "calculadora": {"nome": "Calculadora", "pkg": "com.google.android.calculator",
                        "activity": "com.google.android.calculator.Calculator"},
        "relogio": {"nome": "Relogio", "pkg": "com.google.android.deskclock",
                    "activity": "com.android.deskclock.DeskClock"},
        "camera": {"nome": "Camera", "pkg": "com.android.camera2",
                   "activity": "com.android.camera.CameraActivity"},
        "jogos": {"nome": "Play Store", "pkg": "com.android.vending",
                  "activity": "com.android.vending.AssetBrowserActivity"},
        "playstore": {"nome": "Play Store", "pkg": "com.android.vending",
                      "activity": "com.android.vending.AssetBrowserActivity"},
        "configuracoes": {"nome": "Configuracoes", "pkg": "com.android.settings",
                          "activity": "com.android.settings.Settings"},
        "ajustes": {"nome": "Configuracoes", "pkg": "com.android.settings",
                    "activity": "com.android.settings.Settings"},
        "file": {"nome": "Gerenciador de Arquivos",
                 "pkg": "com.android.documentsui",
                 "activity": "com.android.documentsui.files.FilesActivity"},
        "arquivos": {"nome": "Gerenciador de Arquivos",
                     "pkg": "com.android.documentsui",
                     "activity": "com.android.documentsui.files.FilesActivity"},
        "x": {"nome": "X (Twitter)", "pkg": "com.twitter.android",
              "activity": "com.twitter.android.StartActivity"},
        "discord": {"nome": "Discord", "pkg": "com.discord",
                    "activity": "com.discord.app.main.MainActivity"},
        "email": {"nome": "Gmail", "pkg": "com.google.android.gm",
                  "activity": "com.google.android.gm.ConversationListActivityGmail"},
        "gmail": {"nome": "Gmail", "pkg": "com.google.android.gm",
                  "activity": "com.google.android.gm.ConversationListActivityGmail"},
    }

    def encontrar_app(self, nome):
        """Localiza o app pelo nome digitado (sinônimos/abreviações)."""
        nome = nome.lower().strip()
        # nome exato (chave ou nome bonito)
        for chave, info in self.APPS_ANDROID.items():
            if chave == nome or info["nome"].lower() == nome:
                return info
        # busca parcial segura (nome com pelo menos 3 letras para evitar falso
        # positivo tipo 'x' batendo em 'lixo')
        nome_base = re.sub(r"[^a-z]+", "", nome)
        if len(nome_base) >= 3:
            for chave, info in self.APPS_ANDROID.items():
                chave_base = re.sub(r"[^a-z]+", "", chave)
                if len(chave_base) >= 3:
                    if nome_base in chave_base or chave_base in nome_base:
                        return info
        return None

    def abrir_app(self, nome):
        """Abre um app Android via Termux (am start). Requer Termux e sem root."""
        if not self.platform.is_termux:
            return "Abrir apps do celular so funciona no Termux (Android)."
        info = self.encontrar_app(nome)
        if not info:
            return None
        comando = "am start -n {}/{}".format(info["pkg"], info["activity"])
        codigo, stdout, stderr = self.executar(comando)
        if codigo == 0:
            return "Abrindo {}...".format(info["nome"])
        return "App {} nao encontrado/nao instalado. ({}: {})".format(
            info["nome"], stderr.strip(), stdout.strip())

    def abrir_site(self, url):
        """Abre um site no navegador padrao (Termux: termux-open-url; Linux: xdg-open)."""
        url = url if "://" in url else "https://" + url
        if self.platform.is_termux and shutil.which("termux-open-url"):
            comando = "termux-open-url '{}'".format(url.replace("'", "''"))
        elif not self.platform.is_windows and shutil.which("xdg-open"):
            comando = "xdg-open '{}'".format(url.replace("'", "''"))
        elif self.platform.is_windows:
            comando = "start {}".format(url)
        else:
            return None
        codigo, stdout, stderr = self.executar(comando)
        if codigo == 0:
            return "Abrindo o site: " + url
        return "Nao consegui abrir o site ({})".format(stderr.strip() or stdout.strip())
