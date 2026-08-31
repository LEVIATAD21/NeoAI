"""Executor de funções cross-platform (Linux, Windows, Termux).

Usa apenas subprocess e ferramentas do sistema, sem dependências externas.
Classifica cada comando como 'seguro' (leitura) ou 'perigoso' (escrita/efeito)
para que o fluxo de confirmação decida.
"""
import os
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
