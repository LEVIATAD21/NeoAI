"""Instalador unico da NeoAI: baixa TUDO de que ela precisa, de uma vez so.

Uso:
  python3 instala.py            (Linux, Termux, macOS)
  py -3 instala.py              (Windows)

O que faz:
  1. Verifica Python/git e produz mensagem clara se faltar.
  2. Instala o pacote Playwright (a unica dependencia externa; o resto e stdlib).
  3. Baixa o Chromium do Playwright (com dependencias do sistema quando root/Linux).
  4. Confere se instala a NeoAI e da o resumo final.

A NeoAI roda mesmo sem Playwright (modo leitura HTTP de paginas). O Playwright
so adiciona: leitura de paginas com JS, rolagem e captura de tela.
"""
import os
import shutil
import subprocess
import sys

VERDE = "\033[92m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
FIM = "\033[0m"


def info(msg):
    print(AMARELO + "[i] " + msg + FIM)


def ok(msg):
    print(VERDE + "[ok] " + msg + FIM)


def erro(msg):
    print(VERMELHO + "[!] " + msg + FIM)


def tem(programa):
    return shutil.which(programa) is not None


def rodar(cmd, fatal=False, timeout=1800):
    print("\n$ " + " ".join(str(c) for c in cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        saida = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0:
            return True, saida[-800:]
        msg = saida[-600:]
        if fatal:
            erro("Comando falhou: " + msg)
        return False, msg
    except subprocess.TimeoutExpired:
        erro("Comando estourou o tempo (timeout).")
        return False, "timeout"
    except Exception as ex:
        erro("Nao consegui executar: {}".format(ex))
        return False, str(ex)


def plataforma():
    if os.environ.get("PREFIX") and os.path.exists("/data/data/com.termux"):
        return "termux"
    if os.name == "nt":
        return "windows"
    return "linux"


def verificar_base():
    faltas = []
    if not tem("python3") and not tem("python"):
        faltas.append("Python 3")
    pip = tem("pip3") or tem("pip")
    if not pip:
        faltas.append("pip (instale com: python -m ensurepip ou pkg install python-pip)")
    if os.name != "nt" and not tem("git"):
        info("git nao achado, mas o repo ja foi clonado.")
    if faltas:
        erro("Faltam itens essenciais: " + ", ".join(faltas))
        erro("Instale-os e rode este script de novo.")
        return False
    return True


def instalar_playwright():
    info("Instalando o Playwright (dependencia externa) via pip...")
    if tem("pip3"):
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "playwright"]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "playwright"]
    certo, saida = rodar(cmd)
    if not certo:
        erro("Nao consegui instalar o pacote playwright por pip.")
        erro("Possiveis causas: Python 3.14 sem wheel para esta plataforma, "
             "ou rede/proxy.")
        erro("A NeoAI continua funcionando em modo leitura HTTP. Para tentar "
             "de novo depois, rode: python3 instala.py")
        return False
    ok("Playwright instalado.")
    return True


def instalar_chromium(local):
    info("Baixando o Chromium do Playwright (uma vez so; pode demorar)...")
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    certo, saida = rodar(cmd)
    if not certo and os.name != "nt" and os.geteuid() == 0:
        info("Chromium falhou sem as libs do sistema. Tentando --with-deps...")
        cmd = [sys.executable, "-m", "playwright", "install", "--with-deps",
               "chromium"]
        certo, saida = rodar(cmd, timeout=3600)
    if not certo:
        erro("Nao consegui baixar o Chromium do Playwright.")
        erro("Leitura de paginas via HTTP continua funcionando.")
        return False
    ok("Chromium pronto.")
    return True


def configurar_termux():
    if not tem("pkg"):
        return
    info("Termux detectado: garantindo pacotes base (python, etc).")
    r = subprocess.run(["pkg", "update", "-y"], capture_output=True, text=True,
                       timeout=600)
    rodar(["pkg", "install", "-y", "python"], timeout=900)


def testar_neoi():
    info("Testando se a NeoAI sobe...")
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        r = subprocess.run([sys.executable, "-c",
                            "import sys; sys.path.insert(0,%r); "
                            "from core.platform import PlatformInfo; "
                            "from core.memory import MemoryStore; "
                            "from core.engine import NeoEngine; "
                            "p=PlatformInfo(); m=MemoryStore(p); "
                            "e=NeoEngine(m,p); "
                            "print('NEOAI_CARREGADA')" % base],
                           capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and "NEOAI_CARREGADA" in r.stdout:
            ok("NeoAI carrega e responde.")
            return True
        erro("Falha ao carregar: " + r.stderr[-300:])
        return False
    except Exception as ex:
        erro("Falha no teste: {}".format(ex))
        return False


def main():
    print()
    print(VERDE + "=" * 58)
    print("  NeoAI - instalador unico (baixa tudo de uma vez)")
    print("=" * 58 + FIM)
    local = plataforma()
    info("Plataforma: {}".format(local))

    if not verificar_base():
        return 1

    if local == "termux":
        configurar_termux()

    instalar_playwright()
    instalar_chromium(local)

    testar_neoi()

    print()
    print(VERDE + "=" * 58)
    print("  TUDO PRONTO!")
    print("=" * 58 + FIM)
    print("Rode com:  python3 neoai.py")
    print("Se algo deu aviso: a NeoAI ja funciona mesmo sem Playwright")
    print("(modo leitura HTTP de paginas).")
    return 0


if __name__ == "__main__":
    sys.exit(main())