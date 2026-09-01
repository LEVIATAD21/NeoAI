"""Sistema de armazenamento de memoria com grafo de conhecimento.

Regra de prioridade:
1) Se o Obsidian (vault) estiver instalado/disponivel no dispositivo, usa SOMENTE ele.
2) Se o Obsidian nao for encontrado, usa a pasta Downloads.
3) Nos dois casos, tudo fica conectado: quando Obsidian estiver presente, os dados
   do Download sao migrados para dentro do vault; e o vault funciona como fonte
   unica conectada.

Memoria conectada (grafo):
- notas .md com frontmatter YAML (titulo, tags, criado/atualizado, links [[...]])
- indice de grafo/backlinks atualizado a cada salvamento (vira o Grafo do Obsidian)
- busca local por TF-IDF sobre as notas (sem libs externas)

Obsidian nao e um app de linha de comando, mas usamos seus dados locais via
arquivos Markdown dentro do vault (que o usuario escolhe).
"""
import json
import os
import re
import shutil
import time


OBSIDIAN_CONFIG_NAME = ".obsidian"
BRAIN_FILE = "neobrain.json"
VAULT_SUBDIR = "NeoAI"
MEMORY_EXPORT_DIR = "memoria"
NOTES_DIR = "notas"
GRAFO_NOTA = "NeoAI - Grafo de Conhecimento.md"
INDICE_NOTA = "NeoAI - Indice.md"
GRAFO_JSON = "grafo.json"

_STOPWORDS = set(
    "a o e de do da em para por com que no na os as um uma uns umas se mas "
    "ou nao sim ser estar tem ter foi mas mais menos ja jao eu voce vc tu ela "
    "ele eles elas nos meu minha seu sua isso isso aquilo este esta esse essa "
    "sobre como quando onde qual quem quanto porque assim tambem muito pouco "
    "agora depois antes sempre nunca hoje ontem amanha dia noite manha vez "
    "coisa coisas essa esse dele dela deles delas nosso nossa".split())


def _tokenizar(texto):
    palavras = re.findall(r"[a-zA-Z\u00C0-\u017F]+", (texto or "").lower())
    return [p for p in palavras if len(p) > 2 and p not in _STOPWORDS]


def _stem(p):
    for suf in ("izacao", "acoes", "acao", "oes", "coes", "mente", "idade",
                "idades", "ando", "endo", "indo", "ados", "ados", "ada",
                "ido", "ida"):
        if p.endswith(suf) and len(p) - len(suf) >= 3:
            return p[: -len(suf)]
    return p[:-1] if p.endswith("s") and len(p) > 4 else p


class MemoryStore:
    def __init__(self, platform_info):
        self.platform = platform_info
        self.vault_dir = None
        self.using_obsidian = False
        self.using_downloads = False
        self._locate_memory_root()

    # ---------------------- localização ----------------------

    def _search_obsidian_vault(self):
        """Tenta localizar um vault do Obsidian buscando por pastas .obsidian."""
        home = self.platform.home
        candidates = [home]
        # Termux: procurar no storage compartilhado
        if self.platform.is_termux:
            shared = os.path.join(home, "storage", "shared")
            if os.path.isdir(shared):
                candidates.append(shared)
        # procura superficial (máx. profundidade 3, não varre tudo)
        found = self._scan_for_obsidian(candidates)
        return found

    def _scan_for_obsidian(self, roots, max_depth=3):
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                depth = dirpath[len(root):].count(os.sep)
                if depth > max_depth:
                    dirnames[:] = []
                    continue
                if OBSIDIAN_CONFIG_NAME in dirnames:
                    return dirpath
                # não descer em pastas enormes/ocultas desnecessárias
                dirnames[:] = [d for d in dirnames
                               if not d.startswith(".")
                               and d not in ("node_modules", ".git", "Android",
                                             ".cache")]
        return None

    def _locate_memory_root(self):
        vault = self._search_obsidian_vault()
        if vault:
            self.using_obsidian = True
            self.vault_dir = os.path.join(vault, VAULT_SUBDIR)
            # Migra dados do Download para o Obsidian (conectar tudo)
            self._migrate_from_downloads()
            self._ensure_dirs()
            return
        # Sem Obsidian -> usa Downloads
        self.using_downloads = True
        base = self.platform.download_dir
        self.vault_dir = os.path.join(base, VAULT_SUBDIR)
        self._ensure_dirs()

    def _ensure_dirs(self):
        for sub in (NOTES_DIR, MEMORY_EXPORT_DIR):
            p = os.path.join(self.vault_dir, sub)
            os.makedirs(p, exist_ok=True)

    def _migrate_from_downloads(self):
        dl_root = os.path.join(self.platform.download_dir, VAULT_SUBDIR)
        if not os.path.isdir(dl_root):
            return
        # copia tudo que estiver no download para o vault
        try:
            for item in os.listdir(dl_root):
                src = os.path.join(dl_root, item)
                dst = os.path.join(self.vault_dir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
        except Exception:
            pass

    # ---------------------- paths ----------------------

    def brain_path(self):
        return os.path.join(self.vault_dir, BRAIN_FILE)

    def notes_dir(self):
        return os.path.join(self.vault_dir, NOTES_DIR)

    def export_dir(self):
        return os.path.join(self.vault_dir, MEMORY_EXPORT_DIR)

    # ---------------------- carregamento / salvamento ----------------------

    def load_brain(self):
        path = self.brain_path()
        default = {
            "versao": 1,
            "criado_em": time.time(),
            "ultima_atualizacao": time.time(),
            "memorias": {},
            "fatos": [],
            "conversas": [],
            "conhecimento": {},
        }
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in default.items():
                    data.setdefault(k, v)
                return data
            except Exception:
                pass
        return default

    def save_brain(self, brain):
        brain["ultima_atualizacao"] = time.time()
        path = self.brain_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(brain, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        self._write_obsidian_index()
        return path

    def _write_obsidian_index(self):
        """Gera um índice .md e o grafo no vault para o usuário ver no Obsidian."""
        brain = self.load_brain()
        n_mem = len(brain.get("memorias", {}))
        n_fatos = len(brain.get("fatos", []))
        n_convs = len(brain.get("conversas", []))
        rotas = brain.get("dados", {}).get("rotas", {})
        n_apps = len(rotas.get("apps", {}))
        n_sites = len(rotas.get("sites", {}))
        conteudo = (
            "# NeoAI - Indice de Memoria\n\n"
            "- Memorias salvas: {}\n"
            "- Fatos conhecidos: {}\n"
            "- Rotas de apps: {}\n"
            "- Rotas de sites: {}\n"
            "- Conversas: {}\n"
            "- Local: {}\n\n"
            "- Grafos: veja o grafo de conhecimento (aba Grafos do Obsidian)\n\n"
            "*Este arquivo e atualizado automaticamente.*\n"
        ).format(n_mem, n_fatos, n_apps, n_sites, n_convs, self.vault_dir)
        try:
            with open(os.path.join(self.vault_dir, INDICE_NOTA), "w",
                      encoding="utf-8") as f:
                f.write(conteudo)
        except Exception:
            pass

    # ---------------------- operações de memória ----------------------

    def get(self, chave):
        """Le um bloco de dados estruturado do cerebro (ex: rotas)."""
        brain = self.load_brain()
        return brain.get("dados", {}).get(chave)

    def set(self, chave, valor):
        """Grava um bloco de dados estruturado no cerebro e persiste."""
        brain = self.load_brain()
        brain.setdefault("dados", {})[chave] = valor
        self.save_brain(brain)
        return True

    def add_memoria(self, chave, conteudo, tags=None, links=None):
        brain = self.load_brain()
        brain["memorias"][chave] = {
            "conteudo": conteudo,
            "criado_em": time.time(),
            "atualizado_em": time.time(),
            "tags": tags or [],
            "links": links or [],
        }
        self.save_brain(brain)
        self._write_note(chave, conteudo, tags=tags)
        return True

    def get_memoria(self, chave):
        brain = self.load_brain()
        m = brain["memorias"].get(chave)
        if m:
            return m["conteudo"]
        return None

    def add_fato(self, frase):
        brain = self.load_brain()
        if not any(f.get("texto") == frase for f in brain["fatos"]):
            brain["fatos"].append({"texto": frase, "tempo": time.time()})
            self.save_brain(brain)
            return True
        return False

    def get_fatos(self):
        brain = self.load_brain()
        return brain["fatos"]

    def add_conversa(self, entrada, saida):
        brain = self.load_brain()
        brain["conversas"].append({
            "entrada": entrada,
            "saida": saida,
            "tempo": time.time(),
        })
        # limita histórico para não crescer infinito
        if len(brain["conversas"]) > 500:
            brain["conversas"] = brain["conversas"][-500:]
        self.save_brain(brain)
        return True

    # ---------------------- notas conectadas (grafo) ----------------------

    def _nome_nota(self, chave):
        safe = "".join(c for c in chave if c.isalnum() or c in " _-").strip()
        return safe or str(int(time.time()))

    def _chave_from_file(self, nome_arquivo, corpo):
        base = os.path.splitext(nome_arquivo)[0]
        m = re.search(r"^#\s+(.+)$", corpo, re.MULTILINE)
        return (m.group(1).strip() if m else base)

    def _listar_notas(self):
        """Lista notas .md do vault com titulo, conteudo e links existentes."""
        notas = []
        d = self.notes_dir()
        if not os.path.isdir(d):
            return notas
        try:
            for nome in sorted(os.listdir(d)):
                if not nome.endswith(".md"):
                    continue
                path = os.path.join(d, nome)
                with open(path, "r", encoding="utf-8") as f:
                    corpo = f.read()
                # extrai frontmatter
                bruto = corpo
                fm = {}
                m = re.match(r"^---\n(.*?)\n---\n", corpo, re.S)
                if m:
                    for linha in m.group(1).splitlines():
                        if ":" in linha and not linha.lstrip().startswith("-"):
                            k, v = linha.split(":", 1)
                            fm[k.strip()] = v.strip().strip('"{}[]').strip()
                    corpo = corpo[m.end():]
                titulo = fm.get("titulo") or self._chave_from_file(nome, corpo)
                m_tags = re.search(r"tags:\s*\[(.*?)\]", bruto, re.S)
                tags = [t.strip() for t in m_tags.group(1).split(",")
                        if t.strip()] if m_tags else []
                links = [l.strip() for l in
                         re.findall(r"\[\[([^\]]+)\]\]", bruto)]
                conteudo_txt = re.sub(r"^#\s+.+", "", corpo, flags=re.M)
                notas.append({
                    "titulo": titulo,
                    "arquivo": nome,
                    "conteudo": conteudo_txt,
                    "tags": tags,
                    "links": links,
                })
        except Exception:
            pass
        return notas

    def _write_note(self, chave, conteudo, tags=None):
        nome = self._nome_nota(chave)
        path = os.path.join(self.notes_dir(), nome + ".md")
        corpus = _tokenizar(str(conteudo))
        if not tags:
            # tags automaticas: termos mais frequentes do conteudo
            from collections import Counter
            conta = Counter(_stem(p) for p in corpus)
            tags = [t for t, _ in conta.most_common(4)
                    if len(t) >= 3 and not t.isdigit()][:3]
        tags = list(tags)

        # links: notas relacionadas (compartilham termos/tags)
        relacionadas = self._relacionadas(corpus, tags, ignore=nome)
        links = ["[[" + r["titulo"] + "]]" for r in relacionadas]

        agora = time.strftime("%Y-%m-%d %H:%M:%S")
        front = ("---\n"
                 "titulo: {}\n"
                 "tags: [{}]\n"
                 "criado_em: {}\n"
                 "atualizado_em: {}\n"
                 "links:\n{}\n"
                 "---\n").format(
            nome,
            ", ".join(tags) if tags else "neoai",
            agora, agora,
            "\n".join("  - " + l for l in links))
        with open(path, "w", encoding="utf-8") as f:
            f.write(front + "\n# " + nome + "\n\n" + str(conteudo) + "\n")
        self._atualizar_grafo()
        return path

    def _relacionadas(self, corpus_derivado, tags, ignore=None, limite=5):
        """Notas ja existentes relacionadas por termos/tags compartilhados."""
        tokens = set(_stem(p) for p in corpus_derivado) | set(tags)
        notas = self._listar_notas()
        relacionadas = []
        for n in notas:
            if ignore and n["titulo"] == ignore:
                continue
            n_tokens = set(_stem(t) for t in
                           n["conteudo"].split() + n["tags"])
            inter = tokens & n_tokens
            if len(inter) >= 1:
                relacionadas.append({"titulo": n["titulo"],
                                     "pontos": len(inter)})
        relacionadas.sort(key=lambda x: x["pontos"], reverse=True)
        return relacionadas[:limite]

    def _atualizar_grafo(self):
        """Regera o grafo de conhecimento (nota de Indice) + grafo.json."""
        notas = self._listar_notas()
        por_titulo = {n["titulo"]: n for n in notas}
        arestas = set()
        linhas = ["# NeoAI - Grafo de Conhecimento\n",
                  "Notas: {} | Os links [[...]] alimentam o Grafo do Obsidian.\n".format(
                      len(notas))]
        for n in notas:
            saida = [l.strip("[]") for l in n["links"] if l]
            arestas.update((n["titulo"], x) for x in saida)
        for n in notas:
            meus = [l.strip("[]") for l in n["links"] if l]
            recebe = [t for t in por_titulo
                      if n["titulo"] in por_titulo[t]["links"]]
            # backlinks: tambem busca mencoes no conteudo
            for t in por_titulo:
                if t != n["titulo"] and n["titulo"] in por_titulo[t]["conteudo"]:
                    recebe.append(t)
            recebe = sorted(set(recebe))
            linhas.append("- **{}**{}  ".format(
                n["titulo"],
                ("\n  - sai para: " + ", ".join("[[{}]]".format(x) for x in meus)
                 if meus else "")))
            if recebe:
                linhas.append("  - recebe de: " +
                              ", ".join("[[{}]]".format(t) for t in recebe))
        try:
            with open(os.path.join(self.vault_dir, GRAFO_NOTA), "w",
                      encoding="utf-8") as f:
                f.write("\n".join(linhas))
            lista = [{"titulo": t, "tags": n["tags"]} for t, n in
                     sorted(por_titulo.items())]
            with open(os.path.join(self.vault_dir, GRAFO_JSON), "w",
                      encoding="utf-8") as f:
                json.dump({"nos": lista,
                           "arestas": sorted(list(arestas))},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def info_grafo(self):
        try:
            with open(os.path.join(self.vault_dir, GRAFO_JSON), "r",
                      encoding="utf-8") as f:
                g = json.load(f)
            return len(g.get("nos", [])), len(g.get("arestas", []))
        except Exception:
            return 0, 0

    def backlinks(self, nome):
        """Nomes das notas que referenciam 'nome'."""
        notas = self._listar_notas()
        refs = []
        for n in notas:
            if n["titulo"] == nome:
                continue
            if nome in n["links"] or nome in n["conteudo"]:
                refs.append(n["titulo"])
        return refs

    # ---------------------- busca local (TF-IDF) ----------------------

    def buscar(self, consulta, limite=5):
        """Busca semantica simples por TF-IDF nas notas do vault."""
        consulta_tokens = _tokenizar(consulta)
        if not consulta_tokens:
            return []
        notas = self._listar_notas()
        # corpus: notas + memorias do cerebro
        brain = self.load_brain()
        for chave, m in brain.get("memorias", {}).items():
            if any(n["titulo"] == chave for n in notas):
                continue
            notas.append({"titulo": chave,
                          "conteudo": m.get("conteudo", ""),
                          "tags": m.get("tags", []), "links": [],
                          "arquivo": chave + ".md"})
        if not notas:
            return []

        import math
        doc_toks = []
        for n in notas:
            toks = [_stem(t) for t in _tokenizar(str(n["conteudo"]))]
            toks += [str(t) for t in n.get("tags", [])]
            doc_toks.append(toks)
        # frequencia dos termos
        from collections import Counter
        counts = [Counter(d) for d in doc_toks]
        N = len(notas)
        df = Counter()
        for c in counts:
            for t in set(c):
                df[t] += 1
        idf = {t: math.log((1 + N) / (1 + df[t])) + 1 for t in df}

        cons = Counter(_stem(t) for t in consulta_tokens)
        resultados = []
        for idx, n in enumerate(notas):
            total = sum(counts[idx].values()) or 1
            score = 0.0
            for t, qf in cons.items():
                tfidf = (counts[idx].get(t, 0) / total) * idf.get(t, 0.0)
                score += qf * tfidf
            if score > 0:
                trecho = self._trecho(n["conteudo"], consulta)
                resultados.append({"titulo": n["titulo"],
                                   "score": round(score, 4),
                                   "trecho": trecho,
                                   "arquivo": n.get("arquivo", "")})
        resultados.sort(key=lambda x: x["score"], reverse=True)
        return resultados[:limite]

    def _trecho(self, texto, consulta, tamanho=120):
        texto = " ".join(str(texto).split())
        for termo in _tokenizar(consulta):
            i = texto.lower().find(termo)
            if i >= 0:
                ini = max(0, i - tamanho // 2)
                fim = min(len(texto), i + tamanho // 2)
                return ("..." + texto[ini:fim] + "...") if ini else \
                    texto[:fim] + "..."
        return texto[:tamanho] + ("..." if len(texto) > tamanho else "")

    def export_tudo(self):
        """Exporta a memória para o diretório de exportação (no vault)."""
        brain = self.load_brain()
        path = os.path.join(self.export_dir(),
                            "memoria_export_{}.json".format(int(time.time())))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(brain, f, ensure_ascii=False, indent=2)
        return path