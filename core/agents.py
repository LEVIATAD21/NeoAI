"""Sistema de 3 agentes especializados + NeoAI principal.

Fluxo de raciocínio:
1) NeoAI (agente central) recebe o pedido.
2) NeoAI "pensa" e consulta os 3 agentes (cada um com uma perspectiva):
   - Conhecimento: especialista em saber coisas (sistema, o que é X).
   - Prática: especialista em executar / caminhos práticos (comandos, ações).
   - Memória: especialista em lembrar o que já foi visto/armazenado.
3) Cada agente responde; NeoAI troca dúvidas com eles (pergunta→resposta).
4) Se alguém souber, usa; se ninguém souber, pesquisa na internet.
5) Se achar na internet, guarda na memória para a próxima.

Pesquisa web usa urllib/curl do sistema (sem dependências externas).
"""
import json
import re
import time
import urllib.parse
import urllib.request


class Agente:
    def __init__(self, nome, perfil, foco):
        self.nome = nome
        self.perfil = perfil
        self.foco = foco  # lista de palavras-chave da sua área
        self.confianca = 0.5

    def responde(self, pergunta):
        """Cada agente tenta responder com base no seu foco + regras internas.
        Retorna (resposta, confianca) ou (None, 0)."""
        return None, 0.0


class AgenteConhecimento(Agente):
    """Especialista em saber o que as coisas são, definições, fatos gerais."""

    def __init__(self):
        super().__init__("Conhecimento",
                         "Especialista em saber o que as coisas sao, definicoes e fatos.",
                         ["o que e", "oque e", "quem e", "definicao", "defina",
                          "significa", "significado", "historia", "significa",
                          "explicar", "explica", "explicacao", "o que eh"])

    def responde(self, pergunta):
        t = pergunta.lower()
        # conhecimento embutido (base própria, sem modelo de linguagem)
        conhecimento = {
            "ia": ("Inteligencia artificial: sistemas que tentam reproduzir "
                   "capacidades humanas como entender, raciocinar e aprender. "
                   "A NeoAI e feita do zero com regras proprias."),
            "linux": ("Linux e um sistema operacional de codigo aberto baseado "
                      "no nucleo Unix. Usado em servidores, Termux e desktops."),
            "python": ("Python e uma linguagem de programacao de alto nivel, "
                       "muito usada em scripts, IA e automacao."),
            "obsidian": ("Obsidian e um aplicativo de notas em Markdown que "
                         "guarda tudo em pastas locais (vault). A NeoAI guarda "
                         "memoria no seu vault quando detectado."),
            "termux": ("Termux e um emulador de terminal para Android (sem "
                       "root) que roda Linux/Unix. Permite instalar pacotes e "
                       "scripts."),
            "internet": ("Internet e uma rede mundial que conecta computadores. "
                         "Usada para buscar informacoes quando nao sabemos algo."),
        }
        for chave, txt in conhecimento.items():
            if chave in t:
                return "[{}] {}".format(self.nome, txt), 0.9
        return None, 0.0


class AgentePratica(Agente):
    """Especialista em caminhos práticos: comandos, ações, execução."""

    def __init__(self):
        super().__init__("Pratica",
                         "Especialista em caminhos praticos: comandos, acoes, execucoes.",
                         ["como", "como fazer", "passo", "passos", "comando",
                          "executar", "executa", "roda", "rodar", "caminho",
                          "instalar", "instala", "abrir", "criar", "listar",
                          "listar pastas", "cd", "touch", "mkdir"])

    def responde(self, pergunta):
        t = pergunta.lower()
        receitas = {
            "criar arquivo": ("[Pratica] Para criar um arquivo use: touch NOME "
                              "(ex: touch notas.txt) ou echo texto > arquivo."),
            "criar pasta": ("[Pratica] Para criar uma pasta use: mkdir NOME"),
            "listar": ("[Pratica] Para listar arquivos/pastas use: ls -la"),
            "o que tem aqui": ("[Pratica] Para ver o que tem aqui use: ls -la"),
            "como instalar": ("[Pratica] No Termux use: pkg install NOME. "
                              "No Linux: apt install NOME. No Windows: pip install NOME"),
            "instalar": ("[Pratica] Para instalar, use o gerenciador do SO: "
                         "pkg (Termux), apt (Linux) ou pip (Python/Windows)."),
            "abrir arquivo": ("[Pratica] Para ver um arquivo use: cat NOME file"),
            "rodar": ("[Pratica] Para rodar um script Python: python3 script.py. "
                      "Shell: bash script.sh."),
            "cd": ("[Pratica] Para mudar de pasta use: cd CAMINHO"),
        }
        for chave, txt in receitas.items():
            if chave in t:
                return txt, 0.9
        return None, 0.0


class AgenteMemoria(Agente):
    """Especialista em lembrar o que já está na memória permanente."""

    def __init__(self, memory):
        super().__init__("Memoria",
                         "Especialista em lembrar o que a NeoAI ja guardou/viveu.",
                         ["lembra", "lembre", "memoria", "memoriz", "guardou",
                          "anotou", "viveu", "aprendeu", "antes", "ja vi"])
        self.memory = memory

    def responde(self, pergunta):
        # busca fatos e memorias e planos já guardados
        if not self.memory:
            return None, 0.0
        brain = self.memory.load_brain()
        respostas = []
        pergunta_limpa = self._chaves(pergunta)
        for m in brain.get("memorias", {}).values():
            conteudo = m["conteudo"]
            if self._corresponde(pergunta_limpa, conteudo):
                respostas.append(conteudo)
        for fato in brain.get("fatos", []):
            if self._corresponde(pergunta_limpa, fato["texto"]):
                respostas.append(fato["texto"])
        if respostas:
            return "[Memoria] {} Lembro disto: {}".format(
                self.nome, "; ".join(respostas[:3])), 0.95
        return None, 0.0

    def _chaves(self, texto):
        texto = texto.lower()
        return set(re.findall(r"[a-zà-ÿ0-9]+", texto))

    def _corresponde(self, pergunta_chaves, conteudo):
        chaves_conteudo = self._chaves(conteudo)
        comuns = pergunta_chaves & chaves_conteudo
        return len(comuns) >= 2


class PesquisadorWeb:
    """Pesquisa na internet quando nenhum agente sabe."""

    def __init__(self):
        self.nome = "Web"

    def pesquisar(self, pergunta):
        """Busca conhecimento na internet. Tenta Wikipedia por primeiro (API
        confiavel), e cai para DuckDuckGo se nao achar. Retorna resumo ou None."""
        res = self._pesquisar_wikipedia(pergunta)
        if res:
            return res
        return self._pesquisar_duckduckgo(pergunta)

    def _pesquisar_wikipedia(self, pergunta):
        """Wikipedia via API publica (JSON), sem chave. Confiavel."""
        # remove palavras interrogativas/verbos iniciais para melhorar a busca
        termo = re.sub(r"^(voce |você |o que |o quê |quem |qual |quais |que |como |onde |quando |porque |me |a |o |e co |e |conhece |sabe |eh |é )+", "", pergunta.lower().strip(), flags=re.IGNORECASE)
        termo = re.sub(r'[\?\.!,;:]+$', '', termo).strip() or pergunta.strip()
        busca = urllib.parse.quote_plus(termo)
        url = ("https://pt.wikipedia.org/w/api.php?action=opensearch&search="
               + busca + "&limit=5&format=json")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "NeoAI/1.0 (research; contact: local)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
        except Exception:
            return None
        titulos = data[1]
        if not titulos:
            return None
        # testa cada artigo candidato ate achar um resumo util
        for titulo in titulos:
            try:
                surl = ("https://pt.wikipedia.org/api/rest_v1/page/summary/"
                        + urllib.parse.quote(titulo))
                req2 = urllib.request.Request(surl, headers={
                    "User-Agent": "NeoAI/1.0 (research; contact: local)"})
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    d = json.loads(r2.read().decode("utf-8", "ignore"))
                resumo = d.get("extract") or ""
                tipo = d.get("type", "")
                if resumo and resumo not in ("Rascunho de página.", "") and tipo != "disambiguation":
                    return "[Web] Sobre '{}' ({}):\n{}".format(
                        pergunta, titulo, resumo.strip()[:500])
            except Exception:
                continue
        return None

    def _pesquisar_duckduckgo(self, pergunta):
        try:
            query = urllib.parse.quote_plus(pergunta)
            url = "https://html.duckduckgo.com/html/?q=" + query
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (NeoAI; research)"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            return self._extrair(html, pergunta)
        except Exception:
            return None

    def _extrair(self, html, pergunta):
        # extrai títulos e trechos de resultados
        resultados = []
        blocos = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
        trechos = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html)
        for i, titulo in enumerate(blocos[:3]):
            titulo_limpo = re.sub(r"<[^>]+>", "", titulo).strip()
            trecho = ""
            if i < len(trechos):
                trecho = re.sub(r"<[^>]+>", "", trechos[i]).strip()
            resultados.append(titulo_limpo + (": " + trecho if trecho else ""))
        if not resultados:
            return None
        return "[Web] Encontrei isto sobre '{}':\n{}".format(
            pergunta, "\n".join("- " + r for r in resultados))


class EquipeAgentes:
    """Gerencia os 3 agentes + NeoAI central + troca de dúvidas + web."""

    def __init__(self, memory):
        self.memory = memory
        self.memoria_agente = AgenteMemoria(memory)
        self.agentes = [
            AgenteConhecimento(),
            AgentePratica(),
            self.memoria_agente,
        ]
        self.web = PesquisadorWeb()

    def pensar(self, pedido, pesquisar_web=True):
        """NeoAI pensa antes de decidir: consulta os agentes, troca dúvidas,
        e só então dá a resposta certa. Retorna um resumo do raciocínio."""
        pensamento = []
        acertos = []
        duvidas = []

        # 1) NeoAI central "pensa" e consulta cada agente
        pensamento.append("[Pensando] NeoAI recebeu: '{}'".format(pedido))

        for agente in self.agentes:
            resposta, conf = agente.responde(pedido)
            if resposta:
                acertos.append((agente.nome, resposta, conf))
                pensamento.append("  {} respondeu com confianca {:.2f}".format(
                    agente.nome, conf))
            else:
                duvidas.append(agente.nome)
                pensamento.append("  {} nao soube de primeira.".format(agente.nome))

        # 2) Troca de dúvidas: cada agente que não soube pergunta aos que sabem
        if duvidas and len(duvidas) < len(self.agentes):
            sabedo = [a for a in self.agentes if a.nome not in duvidas]
            pensamento.append("  [Troca] {} duvidam; solicito ajuda de {}.".format(
                ", ".join(duvidas), ", ".join(a.nome for a in sabedo)))
            for nome_duvida in duvidas:
                for a in sabedo:
                    r, c = a.responde(pedido)
                    if r:
                        pensamento.append("    {} ajudou {}: confianca {:.2f}".format(
                            a.nome, nome_duvida, c))
                        acertos.append((a.nome, r, c))
                        break

        # 3) Se ninguém souber -> pesquisa web (opcional)
        if not acertos and pesquisar_web:
            pensamento.append("  [Pesquisa] Nenhum agente soube. Pesquisando na internet...")
            web_res = self.web.pesquisar(pedido)
            if web_res:
                acertos.append(("Web", web_res, 0.7))
                pensamento.append("  Web retornou resultados.")
                # NAO salva automaticamente na memoria para nao poluir com
                # resumos ruins da web. O usuario pode guardar com 'lembre-se'.
            else:
                pensamento.append("  [Falha] Nem a internet respondeu (offline?).")
        elif not acertos:
            pensamento.append("  [Sem web] Nenhum agente soube (busca web desativada nesta etapa).")

        # 4) Escolhe a melhor resposta
        melhor = max(acertos, key=lambda x: x[2]) if acertos else None
        if melhor:
            pensamento.append("  [Decisao] Uso a resposta de {} (confianca {:.2f}).".format(
                melhor[0], melhor[2]))
        else:
            pensamento.append("  [Decisao] Nenhuma fonte confiavel. Resposta generica.")
            return "\n".join(pensamento), None

        return "\n".join(pensamento), melhor[1]

    def _salvar_na_memoria(self, pedido, resposta):
        """Quando acha na internet, guarda para aprender (buscar menos depois)."""
        try:
            fato = "Pesquisei '{}' e aprendi: {}".format(pedido[:60], resposta[:200])
            self.memory.add_fato(fato)
        except Exception:
            pass
