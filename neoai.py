#!/usr/bin/env python3
"""NeoAI - Inteligencia criada do zero (NLP puro, sem modelos de linguagem).

Roda em Linux, Windows e Termux (sem root). Recusa-se a rodar em iPhone/iOS.

Memoria: no Obsidian (vault) se presente, senao na pasta Downloads.
Tudo conectado nos dois casos.
"""
import os
import re
import sys

# garante importação dos módulos core
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _modo_servir(engine, porta, host="0.0.0.0"):
    """Sobe o servidor de controle remoto e informa IPs (modo headless)."""
    from core import netctrl
    token = getattr(engine.cofre, "senha_mestra", None) or "neoai-mudar"
    servidor = netctrl.ServidorControle(engine, porta=porta, host=host,
                                        token=token)
    msg = servidor.iniciar()
    print(msg)
    print("")
    print("Painel web (apenas na sua rede, com token):")
    print("  http://{}:{}  (token: {})".format(host, porta, token))
    print("")
    print("Aperte Ctrl+C para encerrar o servidor.")
    import threading
    import time
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        print("\nServidor encerrado.")


def _modo_enviar(alvo, token, texto):
    """Envia um comando para outro aparelho NeoAI e printa a resposta."""
    from core import netctrl
    if ":" in alvo:
        ip, porta = alvo.rsplit(":", 1)
        porta = int(porta)
    else:
        ip, porta = alvo, 8890
    try:
        resp = netctrl.enviar_comando(ip.replace("http://", "").replace(
            "https://", ""), porta, token, texto)
        print(resp)
    except Exception as ex:
        print("Falha: {}".format(ex))
        sys.exit(1)


def main():
    from core.platform import PlatformInfo
    from core.memory import MemoryStore
    from core.engine import NeoEngine
    from core.iphone_guard import verificar_iphone

    args = [a for a in sys.argv[1:]]
    morfar_servir = any(a in args for a in ("--servir", "-s"))
    porta_arg = None
    for i, a in enumerate(args):
        if a in ("--porta", "-p") and i + 1 < len(args):
            try:
                porta_arg = int(args[i + 1])
            except ValueError:
                porta_arg = None
    morfar_enviar = "--enviar" in args
    alvo = None
    token = None
    texto = None
    if morfar_enviar:
        for i, a in enumerate(args):
            if a == "--enviar" and i + 1 < len(args):
                alvo = args[i + 1]
            if a == "--token" and i + 1 < len(args):
                token = args[i + 1]
        resto = [a for i, a in enumerate(args)
                 if i > 0 and args[i - 1] not in ("--enviar", "--token", "--porta", "-p")
                 and a not in ("--enviar", "--servir", "-s") and not a.startswith("-")]
        texto = " ".join(resto)
        if not alvo or not token or not texto:
            print("Uso: python3 neoai.py --enviar IP:PORTA --token TOKEN <comando>")
            sys.exit(2)

    print("==========================================================")
    print("  NeoAI - Inteligencia criada do ZERO (NLP puro)")
    print("  Sem modelos de linguagem: nada de Ollama/OpenCode/Kimi/QWEN")
    print("==========================================================")

    platform = PlatformInfo()

    # RECUSA em iPhone/iOS
    if verificar_iphone(platform):
        print("")
        print("[!] DISPOSITIVO NAO SUPORTADO")
        print("    A NeoAI recusa-se a rodar em iPhone/iOS (Apple).")
        print("    Motivo: dispositivos Apple nao sao suportados por escolha do")
        print("    usuario. Execute em Linux, Windows ou Termux (Android).")
        print("    Encerrando.")
        sys.exit(1)

    print("Plataforma: {} {} (Termux: {}, Android: {}, Root: {})".format(
        platform.os_name,
        "Sim" if platform.is_linux else
        "Sim" if platform.is_windows else platform.os_name,
        "sim" if platform.is_termux else "nao",
        "sim" if platform.is_android else "nao",
        "sim" if platform.is_root else "nao"))
    print("")

    # Memória: Obsidian preferencial; fallback Downloads
    memory = MemoryStore(platform)
    origem = "Obsidian (vault)" if memory.using_obsidian else "Downloads"
    print("Modo de memoria ativo: {}".format(origem))
    print("Local da memoria:      {}".format(memory.vault_dir))
    print("")

    engine = NeoEngine(memory, platform)

    if morfar_enviar:
        _modo_enviar(alvo, token, texto)
        return

    if morfar_servir:
        _modo_servir(engine, porta_arg or 8890)
        return

    print("NeoAI pronta. Digite 'ajuda' para ver os comandos, 'sair' para encerrar.")
    print("-" * 58)
    while True:
        try:
            entrada = input("voce> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAte mais!")
            break
        if not entrada:
            continue
        if entrada.lower() in ("sair", "exit", "quit", "sairdo"):
            print("NeoAI: Ate a proxima!")
            break
        resposta = engine.responder(entrada)
        print("NeoAI: " + resposta)
        print("")


if __name__ == "__main__":
    main()
