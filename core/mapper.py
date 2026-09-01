"""Aprendizado de rotas do dispositivo (mapeamento de ponta a ponta).

NeoAI conhece o aparelho onde roda: instala apps Android, informacoes do
sistema, pastas do usuario, e guarda cada rota descoberta na memoria
(Obsidian/Downloads) com data. Tudo que executa no dia a dia vira rota
aprendida e reutilizavel.
"""
import os
import time
import json
import subprocess

ROTA_APPS = "apps"      # chave-> nome amigavel (Android: pacote conhecido)
ROTA_DISPOSITIVO = "dispositivo"


def mapear(platform, memory, executor):
    """Varre o aparelho e guarda as rotas na memoria. Retorna relatorio."""
    rotas = memory.get("rotas") or {}
    rotas.setdefault(ROTA_DISPOSITIVO, {})
    achados = []
    agora = time.strftime("%Y-%m-%d %H:%M:%S")
    info = rotas[ROTA_DISPOSITIVO].setdefault("informacoes", {})
    info["plataforma"] = platform.os_name
    info["termux"] = platform.is_termux
    info["android"] = platform.is_android
    info["root"] = platform.is_root
    info["home"] = platform.home
    info["ultimo_mapeamento"] = agora

    # --- apps Android (Termux sem root) ---
    apps = rotas.setdefault(ROTA_APPS, {})
    if platform.is_termux:
        try:
            r = subprocess.run(["pm", "list", "packages"], capture_output=True,
                               text=True, timeout=30)
            pacotes = [ln.replace("package:", "").strip()
                       for ln in r.stdout.splitlines() if ln]
            nomes = {v: k for k, v in executor.APPS_ANDROID.items()}
            for pkg in pacotes:
                nome = nomes.get(pkg)
                if nome:
                    apps.setdefault(nome, {"pacote": pkg,
                                           "descoberto": agora})
            achados.append("{} apps mapeados ({} conhecidos pelo nome)."
                           .format(len(pacotes), len(apps)))
        except Exception as ex:
            achados.append("apps: nao foi possivel listar ({})".format(ex))

    # --- pastas principais do usuario (sem entrar em tudo) ---
    rotas_pastas = rotas.setdefault("pastas", {})
    try:
        for item in sorted(os.listdir(platform.home)):
            caminho = os.path.join(platform.home, item)
            if not os.path.isdir(caminho):
                continue
            if item in (".", "node_modules", ".git") or item.startswith("."):
                continue
            tipo = []
            try:
                for sub in os.listdir(caminho)[:400]:
                    tipo.append(sub)
            except Exception:
                pass
            if not rotas_pastas.get(item):
                rotas_pastas[item] = {"caminho": caminho, "descoberto": agora}
            achados.append("rota de pasta: ~/{} ({} itens)".format(item, len(tipo)))
    except Exception as ex:
        achados.append("pastas: erro ({})".format(ex))

    memory.set("rotas", rotas)
    memory.add_memoria(
        "rota_dispositivo",
        "Mapeamento do dispositivo em {} (plataforma {}, termux {}).\n"
        "Apps: {}.\n{}\n"
        "Nao falta nada: novas rotas sao gravadas quando descobertas."
        .format(agora, platform.os_name, platform.is_termux,
                json.dumps(rotas.get(ROTA_APPS, {}), ensure_ascii=False,
                           indent=1),
                "\n".join(achados)))
    return achados


def registrar_rota_app(memory, nome, pacote):
    """Guarda no repositorio uma rota descoberta ao abrir um app."""
    rotas = memory.get("rotas") or {}
    rotas.setdefault(ROTA_APPS, {})
    rotas[ROTA_APPS].setdefault(nome, {"pacote": pacote,
                                       "descoberto": time.strftime(
                                           "%Y-%m-%d %H:%M:%S"),
                                       "usado": True})
    rotas[ROTA_APPS][nome]["usado"] = True
    rotas[ROTA_APPS][nome]["ultimo_uso"] = time.strftime("%Y-%m-%d %H:%M:%S")
    memory.set("rotas", rotas)


def registrar_rota_site(memory, url):
    """Guarda sites que o mestre ja mandou abrir (aprende a rotina)."""
    rotas = memory.get("rotas") or {}
    sites = rotas.setdefault("sites", {})
    sites.setdefault(url, {"visitas": 0,
                           "descoberto": time.strftime("%Y-%m-%d %H:%M:%S")})
    sites[url]["visitas"] += 1
    sites[url]["ultimo_acesso"] = time.strftime("%Y-%m-%d %H:%M:%S")
    memory.set("rotas", rotas)
    memory.add_memoria("site_" + url.replace("/", "_"),
                       "Rota de site: abrir https://{} ({} visitas)."
                       .format(url, sites[url]["visitas"]))


def relatorio_rotas(memory):
    """Resumo do que NeoAI ja aprendeu sobre o aparelho."""
    rotas = memory.get("rotas") or {}
    linhas = []
    for grupo in ("apps", "sites", "pastas"):
        v = rotas.get(grupo, {})
        linhas.append("{}: {}".format(grupo, ", ".join(list(v)[:25])
                                       or "nada ainda"))
    dev = rotas.get("dispositivo", {}).get("informacoes", {})
    linhas.append("plataforma: {} | termux: {} | root: {}".format(
        dev.get("plataforma"), dev.get("termux"), dev.get("root")))
    return "\n".join(linhas)