"""Planejador passo-a-passo com aprendizado de caminhos.

Quebra uma tarefa ("abra o arquivo X", "liste as pastas", "instale Y") em
etapas executáveis. Cada vez que executa com sucesso, guarda o "caminho"
(plano passo-a-passo) na memória permanente, e em chamadas futuras reusa o
caminho já conhecido para a mesma tarefa — aprendendo e otimizando.

O plano é guardado de forma conectada à memória existente (Obsidian ou
Downloads), pois usa a mesma MemoryStore.
"""
import os
import re
import hashlib
import time


class Plano:
    def __init__(self, passos, descricao, chave=None):
        self.passos = passos  # lista de dicts: {comando, explicacao, seguro}
        self.descricao = descricao
        self.chave = chave


class Planejador:
    def __init__(self, memory, executor, platform):
        self.memory = memory
        self.executor = executor
        self.platform = platform

    @staticmethod
    def _tag(texto):
        return re.sub(r"[^\w]", "", texto.lower())

    # ---------------------- construção de passos ----------------------

    def _extrair_alvo(self, texto, palavras_chave):
        tl = texto.lower()
        for kw in palavras_chave:
            idx = tl.find(kw)
            if idx >= 0:
                resto = texto[idx + len(kw):].strip(" ,;:.!?\"'")
                if resto:
                    return resto
        return None

    def _plano_abrir_programa(self, alvo):
        return [{"comando": alvo + " &",
                 "explicacao": "Abrir o programa " + alvo,
                 "seguro": False}], None

    def _plano_abrir_arquivo(self, alvo):
        eh_script = alvo.endswith((".py", ".sh"))
        return [
            {"comando": "ls -la " + alvo,
             "explicacao": "Verificar se o arquivo existe: " + alvo,
             "seguro": True},
            {"comando": ("python3 " + alvo if alvo.endswith(".py")
                         else ("bash " + alvo if alvo.endswith(".sh")
                               else "cat " + alvo)),
             "explicacao": ("Executar o script" if eh_script
                            else "Mostrar o conteudo do arquivo") + ": " + alvo,
             "seguro": not eh_script},
        ], alvo

    def _plano_info_sistema(self):
        if self.platform.is_windows:
            return [{"comando": "ver & echo --- & echo %PROCESSOR_ARCHITECTURE%",
                     "explicacao": "Mostrar versao do sistema operacional",
                     "seguro": True}], None
        return [
            {"comando": "uname -a", "explicacao": "Mostrar o kernel do sistema",
             "seguro": True},
            {"comando": "grep MemTotal /proc/meminfo",
             "explicacao": "Mostrar memoria total", "seguro": True},
            {"comando": "grep -m1 'model name' /proc/cpuinfo",
             "explicacao": "Mostrar o modelo do processador", "seguro": True},
        ], None

    def _quebrar_pedido(self, texto):
        """Devolve (passos, chave) ou (None, None) se nao entender."""
        original = texto
        texto = texto.lower().strip()
        limpo = re.sub(r"^(neoa|e ai|oia|hey|por favor|pfv|vai|pode|pode me|me)\s+",
                       "", texto)

        # --- abrir site (aprende a rota) - ANTES de app para nao confundir ---
        m = re.search(r"(abr[a-z]+|acess[a-z]+|visita?|entra no|entrar no)\s+(?:o |a )?(?:site |url |pagina |link )?([a-zA-Z0-9][a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?:/[^\s,;]*)?)",
                      limpo)
        if m:
            url = m.group(2).strip().strip(" ,;:.!?")
            if url.lower().endswith((".py", ".sh", ".txt", ".md")):
                pass
            else:
                return [{"comando": "SITE::" + url,
                         "explicacao": "Abrir o site " + url,
                         "seguro": False}], url

        # --- abrir app do Android / programa ---
        m = re.search(r"(abr[a-z]+|execut[a-z]+|roda?|inicia?|open)\s+(?:meu |me |o |a )?(.+)",
                      limpo)
        if m:
            alvo = m.group(2).strip().strip(" ,;:.!?")
            nome_app = re.sub(r"^(meu|me)\s+", "", alvo.lower())
            app = self.executor.encontrar_app(nome_app)
            if app:
                return [{"comando": "APP::" + nome_app,
                         "explicacao": "Abrir o aplicativo " + app["nome"],
                         "seguro": False}], app["pkg"]

        # --- abrir arquivo / programa / rodar script ---
        m = re.search(r"(abr[a-z]+|open|execut[a-z]+|roda?|run)\s+(?:o |a |arquivo |programa )?(?:script\s+)?([\w.\-/ ]+)",
                      limpo)
        if m and not any(x in limpo for x in ("pasta", "diretorio", "cd ", "list",
                                               "as pastas", "o que tem")):
            alvo = m.group(2).strip()
            if alvo.endswith(".py"):
                return [{"comando": "python3 " + alvo,
                         "explicacao": "Executar o script Python " + alvo,
                         "seguro": False}], alvo
            if alvo.endswith(".sh"):
                return [{"comando": "bash " + alvo,
                         "explicacao": "Executar o script Shell " + alvo,
                         "seguro": False}], alvo
            if self.executor.disponivel(alvo):
                return self._plano_abrir_programa(alvo)
            if os.path.exists(alvo) or alvo.endswith((".txt", ".json", ".md")):
                return self._plano_abrir_arquivo(alvo)
            return (None, None)

        # --- alterar diretório ---
        m = re.search(r"(cd|entr[a-z]+)\s+(?:na |no |em |para a |para )?([^,\n]+)",
                      limpo)
        if m:
            alvo = m.group(2).strip()
            return [{"comando": "cd " + alvo,
                     "explicacao": "Alterar diretorio para " + alvo,
                     "seguro": True}], None

        # --- listar conteúdo de pasta ---
        if any(x in limpo for x in ("list", "mostra", "exib", "o que tem",
                                    "conteudo da pasta", "arquivos da pasta")):
            pasta = self._extrair_alvo(original, ["pasta ", "diretorio ", "em ",
                                                  "de "])
            if not pasta or pasta.lower() in ("aqui", "atual", ""):
                pasta = "."
            return [{"comando": "ls -la " + pasta,
                     "explicacao": "Listar arquivos e pastas em " + pasta,
                     "seguro": True}], None

        # --- instalar pacote ---
        m = re.search(r"instal[a-z]+\s+(?:o |a |o pacote |de |do |a biblioteca )?([\w.+@/-]+)",
                      limpo)
        if m:
            pkg = m.group(1).strip()
            if self.platform.is_termux:
                cmd = "pkg install -y " + pkg
                desc = "Instalar pacote " + pkg + " via pkg (Termux)"
            elif self.platform.is_windows:
                cmd = "pip install " + pkg
                desc = "Instalar pacote " + pkg + " via pip"
            else:
                cmd = "sudo apt-get install -y " + pkg
                desc = "Instalar pacote " + pkg + " via apt"
            return [{"comando": cmd, "explicacao": desc, "seguro": False}], None

        # --- criar arquivo ---
        m = re.search(r"cri[a-z]+\s+(?:um |um gerenciador |o )?arquivo\s+([\w.\-/]+)",
                      limpo)
        if m:
            nome = m.group(1).strip()
            return [{"comando": "touch " + nome,
                     "explicacao": "Criar arquivo vazio " + nome,
                     "seguro": False}], None

        # --- informações do sistema ---
        if any(x in limpo for x in ("informacoes do sistema", "info do sistema",
                                    "detalhes do sistema", "hardware")):
            return self._plano_info_sistema()

        return (None, None)

    # ---------------------- API pública ----------------------

    def planejar(self, texto):
        # 1) caminho já aprendido
        conhecido = self._plano_aprendido(texto)
        if conhecido:
            return conhecido
        # 2) novo plano
        passos, chave = self._quebrar_pedido(texto)
        if passos is None:
            return None
        return Plano(passos, texto, chave)

    def _plano_aprendido(self, texto):
        brain = self.memory.load_brain()
        planos = brain.get("planos", {})
        tag = self._tag(texto)
        for chave, dados in planos.items():
            if dados.get("tag") == tag:
                return Plano(dados["passos"], dados.get("descricao", chave),
                             chave=chave)
        return None

    def registrar_sucesso(self, texto, passos):
        brain = self.memory.load_brain()
        planos = brain.setdefault("planos", {})
        chave = "plano_" + str(int(time.time()))
        planos[chave] = {
            "tag": self._tag(texto),
            "descricao": texto,
            "passos": passos,
            "criado_em": time.time(),
            "sucessos": 1,
        }
        brain["planos"] = planos
        self.memory.save_brain(brain)
        self._write_plano_nota(texto, passos)
        return chave

    def _write_plano_nota(self, texto, passos):
        nome = "plano_" + hashlib.md5(texto.encode()).hexdigest()[:8] + ".md"
        path = os.path.join(self.memory.notes_dir(), nome)
        linhas = ["# Plano de execucao: " + texto, ""]
        for i, p in enumerate(passos, 1):
            linhas.append("{}. {}  `{}`".format(i, p["explicacao"], p["comando"]))
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(linhas))
        except Exception:
            pass
