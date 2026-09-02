"""Navegador da NeoAI: "ver" paginas da web (com Playwright OU modo leitura).

Como funciona o "ver":
- PLAYWRIGHT disponivel: abre navegador real, le a pagina renderizada (titulo,
  titulos, links, botoes, campos, texto), rola a pagina e tira prints.
- SEM Playwright (fallback): le a pagina via HTTP puro (stdlib) e extrai texto,
  links e titulos. Nao renderiza JS nem tira print.

Honesto: "ver" aqui significa LER a estrutura/conteudo da pagina. Nao e visao
por modelo de IA. Prints servem para VOCE ver com seus proprios olhos.
"""
import re
import os
import time
import urllib.parse

# PACOTE_DE_BAIXO_NIVEL_DEIXA: TENTAR_PLAYWRIGHT removido (detecta sozinho)


class Navegador:
    def __init__(self):
        self.playwright = None
        self.navegador = None
        self.pagina = None
        self.modo = self._detectar_modo()
        self.ultima_url = None
        self.ultima_leitura = None

    def _detectar_modo(self):
        try:
            import playwright  # noqa: F401
            return "playwright"
        except Exception:
            return "http"

    def _iniciar_playwright(self):
        try:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.navegador = self.playwright.chromium.launch(headless=True)
            self.pagina = self.navegador.new_page()
            return True
        except Exception as ex:
            self.modo = "http"
            return ("Nao consegui iniciar o Chromium do Playwright ({}). "
                    "Tente: pip install playwright && python3 -m playwright "
                    "install chromium".format(ex))

    # ---------------------- leitura ----------------------

    def ler(self, url, rolar=False):
        """'Ve' a pagina: retorna dict com o conteudo estruturado."""
        url = url if "://" in url else "https://" + url
        self.ultima_url = url
        if self.modo == "playwright":
            return self._ler_playwright(url, rolar)
        return self._ler_http(url)

    def _ler_playwright(self, url, rolar=False):
        iniciou = self._iniciar_playwright() if self.pagina is None else True
        if isinstance(iniciou, str):
            return {"erro": iniciou}
        try:
            self.pagina.goto(url, timeout=30000, wait_until="domcontentloaded")
            if rolar:
                self._rolar(constante=True)
            leitura = self.pagina.accessibility.snapshot() if hasattr(
                self.pagina.accessibility, "snapshot") else None
            texto = self.pagina.inner_text("body") if self._existe("body") else ""
            dados = {
                "titulo": self.pagina.title() or "",
                "url": self.pagina.url,
                "texto": texto[:4000],
                "links": self.pagina.eval_on_selector_all(
                    "a", "els => els.map(e => (e.innerText||'').trim())"
                    ).filter(None)[:25],
                "botoes": self.pagina.eval_on_selector_all(
                    "button", "els => els.map(e => (e.innerText||'').trim())"
                    ).filter(None)[:25],
                "campos": self.pagina.eval_on_selector_all(
                    "input", "els => els.map(e => e.placeholder || e.name || "
                    "e.type).filter(Boolean)")[:25],
                "acessibilidade": leitura,
            }
            self.ultima_leitura = dados
            return dados
        except Exception as ex:
            return {"erro": "Erro ao abrir {} (Playwright): {}".format(url, ex)}

    def _ler_http(self, url):
        import urllib.request
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Linux; Android 12) "
                                        "NeoAI/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                texto = r.read()
                encoding = r.headers.get_content_charset() or "utf-8"
                corpo = texto.decode(encoding, errors="replace")
        except Exception as ex:
            return {"erro": "Erro ao abrir {}: {}".format(url, ex)}
        return self._extrair_html(url, corpo)

    def _extrair_html(self, url, corpo):
        from html.parser import HTMLParser

        class V(HTMLParser):
            def __init__(self):
                super().__init__()
                self.titulo = ""
                self.titulos = []
                self.links = []
                self.texto = []
                self._em_titulo = False
                self._em_h = None
                self._pular = 0

            def handle_starttag(self, tag, attrs):
                d = dict(attrs)
                if tag in ("script", "style", "noscript"):
                    self._pular += 1
                    return
                if tag == "title":
                    self._em_titulo = True
                if tag in ("h1", "h2", "h3", "h4"):
                    self._em_h = tag
                    self.texto.append("\n[{}] ".format(tag.upper()))
                if tag == "a" and d.get("href"):
                    self.links.append((d["href"], ""))

            def handle_endtag(self, tag):
                if tag in ("script", "style", "noscript"):
                    self._pular = max(0, self._pular - 1)
                    return
                if tag == "title":
                    self._em_titulo = False
                if tag in ("h1", "h2", "h3", "h4"):
                    self._em_h = None

            def handle_data(self, data):
                if self._pular:
                    return
                d = data.strip()
                if not d:
                    return
                if self._em_titulo:
                    self.titulo += d
                if self._em_h:
                    self.titulos.append(d)
                    self.texto.append(d)
                elif len(d) > 2:
                    self.texto.append(d)

        v = V()
        try:
            v.feed(corpo)
        except Exception:
            pass
        texto = " ".join(t for t in v.texto if t and t != "[H1]")
        texto = re.sub(r"\s+", " ", texto)
        links = [l[0] for l in v.links if l[0].startswith(("http", "/"))][:25]
        return {
            "titulo": v.titulo.strip() or url,
            "url": url,
            "texto": texto[:4000],
            "links": links,
            "botoes": [],
            "campos": [],
            "modo": "http",
        }

    def _existe(self, sel):
        try:
            return self.pagina.query_selector(sel) is not None
        except Exception:
            return False

    # ---------------------- acoes ----------------------

    def rolar(self):
        if self.modo != "playwright" or self.pagina is None:
            return "Rolar so e possivel com Playwright (Chromium)."
        self._rolar()
        return "Rolei a pagina."

    def _rolar(self, constante=False):
        try:
            self.pagina.mouse.wheel(0, 1600)
            time.sleep(0.8)
        except Exception:
            pass

    def procurar(self, url, termo):
        dados = self.ler(url)
        if dados.get("erro"):
            return dados["erro"]
        termo_l = termo.lower()
        ocorrencias = []
        texto = dados.get("texto", "")
        for m in re.finditer(re.escape(termo_l), texto.lower()):
            ini = max(0, m.start() - 40)
            fim = m.end() + 40
            ocorrencias.append("..." + texto[ini:fim] + "...")
        links = [l for l in dados.get("links", [])
                 if termo_l in str(l).lower()]
        saida = "Nao encontrei '{}' na pagina.".format(termo)
        if ocorrencias:
            saida = "Encontrei {} vez(es) '{}' em {}:\n{}".format(
                len(ocorrencias), termo, dados.get("titulo"),
                "\n".join("- " + o for o in ocorrencias[:5]))
        elif links:
            saida = "Nao no texto, mas achei links: " + ", ".join(links[:5])
        return saida

    def screenshot(self, url, destino):
        iniciou = self._iniciar_playwright() if self.pagina is None else True
        if isinstance(iniciou, str):
            return None, iniciou
        try:
            self.pagina.goto(url if "://" in url else "https://" + url,
                             timeout=30000, wait_until="domcontentloaded")
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            self.pagina.screenshot(path=destino)
            return destino, None
        except Exception as ex:
            return None, "Erro no print (Playwright): {}".format(ex)

    def fechar(self):
        try:
            if self.navegador:
                self.navegador.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self.navegador = self.pagina = None
        self.playwright = None


def resumo_para_texto(dados):
    """Transforma a leitura da pagina em texto que a NeoAI usa pra responder."""
    if not dados:
        return "Nao tenho leitura dessa pagina ainda."
    if dados.get("erro"):
        return dados["erro"]
    linhas = []
    linhas.append("PAGINA: {} ({})".format(
        dados.get("titulo", "sem titulo"), dados.get("url", "")))
    if dados.get("modo") == "http":
        linhas.append("[modo leitura HTTP: conteudo estatico, sem JS/print]")
    texto = dados.get("texto", "").strip()
    if texto:
        linhas.append("TEXTO: " + texto[:1200])
    ts = dados.get("titulos")
    if ts:
        linhas.append("TITULOS: " + "; ".join(ts[:8]))
    links = dados.get("links") or []
    botoes = dados.get("botoes") or []
    if links:
        linhas.append("LINKs ({}): {}".format(len(links),
                                              "; ".join(str(x) for x in links[:8])))
    if botoes:
        linhas.append("BOTOES: " + "; ".join(str(x) for x in botoes[:8]))
    campos = dados.get("campos")
    if campos:
        linhas.append("CAMPOS: " + "; ".join(str(x) for x in campos[:8]))
    if dados.get("acessibilidade"):
        linhas.append("(snapshot de acessibilidade disponivel)")
    return "\n".join(linhas)