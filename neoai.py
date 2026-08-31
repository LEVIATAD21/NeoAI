#!/usr/bin/env python3
"""NeoAI - Inteligencia criada do zero (NLP puro, sem modelos de linguagem).

Roda em Linux, Windows e Termux (sem root). Recusa-se a rodar em iPhone/iOS.

Memoria: no Obsidian (vault) se presente, senao na pasta Downloads.
Tudo conectado nos dois casos.
"""
import os
import sys

# garante importação dos módulos core
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def main():
    from core.platform import PlatformInfo
    from core.memory import MemoryStore
    from core.engine import NeoEngine
    from core.iphone_guard import verificar_iphone

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
