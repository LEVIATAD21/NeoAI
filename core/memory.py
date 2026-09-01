"""Sistema de armazenamento de memória.

Regra de prioridade:
1) Se o Obsidian (vault) estiver instalado/disponível no dispositivo, usa SOMENTE ele.
2) Se o Obsidian não for encontrado, usa a pasta Downloads.
3) Nos dois casos, tudo fica conectado: quando Obsidian estiver presente, os dados
   do Download são migrados para dentro do vault; e o vault funciona como fonte
   única conectada.

Obsidian não é um app de linha de comando, mas usamos seus dados locais via
arquivos Markdown dentro do vault (que o usuário escolhe). Também procuramos por
",Sync" /.obsidian para detectar a presença do app.
"""
import json
import os
import shutil
import time


OBSIDIAN_CONFIG_NAME = ".obsidian"
BRAIN_FILE = "neobrain.json"
VAULT_SUBDIR = "NeoAI"
MEMORY_EXPORT_DIR = "memoria"
NOTES_DIR = "notas"


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
        """Gera um índice .md legível no vault para o usuário ver no Obsidian."""
        path = os.path.join(self.vault_dir, "NeoAI - Indice.md")
        brain = self.load_brain()
        n_mem = len(brain.get("memorias", {}))
        n_fatos = len(brain.get("fatos", []))
        n_convs = len(brain.get("conversas", []))
        conteudo = (
            "# NeoAI - Indice de Memoria\n\n"
            "- Memorias salvas: {}\n"
            "- Fatos conhecidos: {}\n"
            "- Conversas: {}\n"
            "- Local: {}\n\n"
            "*Este arquivo e atualizado automaticamente.*\n"
        ).format(n_mem, n_fatos, n_convs, self.vault_dir)
        try:
            with open(path, "w", encoding="utf-8") as f:
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

    def add_memoria(self, chave, conteudo):
        brain = self.load_brain()
        brain["memorias"][chave] = {
            "conteudo": conteudo,
            "criado_em": time.time(),
            "atualizado_em": time.time(),
        }
        self.save_brain(brain)
        self._write_note(chave, conteudo)
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

    def _write_note(self, chave, conteudo):
        safe = "".join(c for c in chave if c.isalnum() or c in " _-").strip()
        if not safe:
            safe = str(int(time.time()))
        path = os.path.join(self.notes_dir(), safe + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# " + safe + "\n\n" + str(conteudo) + "\n")

    def export_tudo(self):
        """Exporta a memória para o diretório de exportação (no vault)."""
        brain = self.load_brain()
        path = os.path.join(self.export_dir(),
                            "memoria_export_{}.json".format(int(time.time())))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(brain, f, ensure_ascii=False, indent=2)
        return path
