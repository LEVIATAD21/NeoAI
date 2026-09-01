"""Controle remoto NeoAI: servidor HTTP proprio (stdlib) + cliente + painel.

Permite controlar o dispositivo onde NeoAI roda a partir de outro aparelho
(notebook -> celular, celular -> notebook), sempre autenticado por TOKEN.
Inclui "assumir controle" para o usuario (mestre) intervir manualmente.

Honesto: e HTTP puro (nao HTTPS/TLS). Use apenas na sua rede local e
defina um token forte.
"""
import json
import threading
import time
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

METADADOS = {"status": "parado", "porta": None, "iniciado_em": None,
             "ultimo_comando": None}

_ATIVIDADE = []
_ATIVIDADE_MAX = 50
_FECHADURA = threading.Lock()


def registrar_atividade(texto):
    """Guarda a ultima linha de atividade para o painel."""
    entrada = {"t": time.strftime("%H:%M:%S"), "msg": texto[:300]}
    with _FECHADURA:
        _ATIVIDADE.append(entrada)
        if len(_ATIVIDADE) > _ATIVIDADE_MAX:
            del _ATIVIDADE[: len(_ATIVIDADE) - _ATIVIDADE_MAX]


def atividade():
    with _FECHADURA:
        return list(_ATIVIDADE)


class NeoHubHandler(BaseHTTPRequestHandler):
    server_version = "NeoAI/1.0"

    def _token_ok(self):
        qs = parse_qs(urlparse(self.path).query)
        tok = self.headers.get("X-NeoAI-Token") or (qs.get("token") or [None])[0]
        return bool(tok and tok == self.server.neoai_token)

    def _responde_json(self, obj, code=200):
        corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _responde_html(self, texto, code=200):
        corpo = texto.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _le_json(self):
        tam = int(self.headers.get("Content-Length") or 0)
        if tam <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(tam).decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, fmt, *args):
        return

    # ---- rotas ----

    def do_GET(self):
        caminho = urlparse(self.path).path
        if not self._token_ok():
            return self._responde_json({"ok": False, "erro": "token invalido"}, 401)
        if caminho == "/status":
            return self._responde_json({
                "ok": True,
                "status": METADADOS,
                "takeover": self.server.engine.takeover,
                "atividade": atividade(),
            })
        if caminho == "/painel":
            return self._responde_html(self._painel())
        return self._responde_json({"ok": False, "erro": "rota desconhecida"}, 404)

    def do_POST(self):
        caminho = urlparse(self.path).path
        dados = self._le_json()
        tok = dados.get("token") or self.headers.get("X-NeoAI-Token")
        en = self.server.neoai_token
        if not tok or tok != en:
            return self._responde_json({"ok": False, "erro": "token invalido"}, 401)

        if caminho == "/cmd":
            texto = (dados.get("texto") or "").strip()
            if not texto:
                return self._responde_json({"ok": False, "erro": "sem comando"})
            registrar_atividade("Comando recebido de " +
                                self.client_address[0] + ": " + texto)
            resp = self.server.executor.executar(texto)
            registrar_atividade("Resposta: " + resp.splitlines()[0][:100])
            return self._responde_json({"ok": True, "resposta": resp})

        if caminho == "/takeover":
            self.server.engine.takeover = True
            registrar_atividade("USUARIO/MESTRE assumiu o controle manual.")
            return self._responde_json({"ok": True, "takeover": True,
                                        "resposta": "Voce assumiu o controle. "
                                                    "Acoes automaticas pausadas."})
        if caminho == "/release":
            self.server.engine.takeover = False
            registrar_atividade("MESTRE liberou o controle automatico de novo.")
            return self._responde_json({"ok": True, "takeover": False,
                                        "resposta": "Controle automatico liberado."})
        return self._responde_json({"ok": False, "erro": "rota desconhecida"}, 404)

    def _painel(self):
        st = "DISPONÍVEL" if not self.server.engine.takeover else \
             "CONTROLE DO MESTRE"
        ativ = "".join(
            "<li><b>{t}</b> {m}</li>".format(t=html.escape(a["t"]),
                                             m=html.escape(a["msg"]))
            for a in atividade())
        return """<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8">
<title>NeoAI - Painel de Controle</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:system-ui,sans-serif;background:#0e1217;color:#e6edf3;max-width:760px;margin:0 auto;padding:16px}
h1{font-size:20px} .badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px}
.auto{background:#1f6f43}.master{background:#b62324}.disp{background:#1f6f43}
input[type=text]{width:100%;padding:10px;border:1px solid #3a4552;border-radius:8px;background:#161b22;color:#e6edf3}
button{padding:10px 16px;border:0;border-radius:8px;background:#2f81f7;color:#fff;cursor:pointer;margin:4px 4px 4px 0}
button.red{background:#b62324} button.green{background:#1f6f43}
#res{background:#161b22;border:1px solid #3a4552;border-radius:8px;padding:12px;margin-top:12px;white-space:pre-wrap}
#ativ{background:#161b22;border:1px solid #3a4552;border-radius:8px;padding:8px 16px;margin-top:12px}
</style></head><body>
<h1>&#x1F9E0; NeoAI &mdash; Painel de controle</h1>
<p>Estado: <span class="badge auto">ao vivo</span>
Conectado a: <span id="st"></span></p>
<input type="password" id="tok" placeholder="token de acesso (so voce sabe)">
<div><button onclick="cmd()">Enviar comando</button>
<button class="red" onclick="gotake()">&#x270B; Assumir controle</button>
<button class="green" onclick="gorelease()">Liberar automatico</button></div>
<input type="text" id="q" placeholder="ex: abra o whatsapp, liste as pastas, o que voce sabe sobre X"
 onkeydown="if(event.key==='Enter')cmd()">
<div id="res"></div><div id="ativ"><b>Atividade recente:</b><ul id="ul"></ul></div>
<script>
function tok(){return document.getElementById('tok').value}
async function j(u,o){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});return r.json()}
async function cmd(){const texto=document.getElementById('q').value;if(!texto)return;
 document.getElementById('res').textContent='pensando...';
 const o={token:tok(),texto:texto};
 if(window.__exec){try{const x=await window.__exec(texto);document.getElementById('res').textContent=x;return}catch(e){}}
 const r=await fetch('/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});
 const d=await r.json();document.getElementById('res').textContent=d.resposta||d.erro}
async function gotake(){const o={token:tok()};await fetch('/takeover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)})}
async function gorelease(){const o={token:tok()};await fetch('/release',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)})}
async function refresh(){const r=await fetch('/status?token='+encodeURIComponent(tok()));const d=await r.json();
 document.getElementById('st').textContent=d.status.porta?('porta '+d.status.porta):'offline';
 document.getElementById('ul').innerHTML=(d.atividade||[]).map(a=>'<li><b>'+a.t+'</b> '+a.msg+'</li>').join('')}
setInterval(refresh,3000);refresh();
</script></body></html>"""


class HubExecutor:
    """Adaptador: roda comandos dentro do motor remoto com aprovacao
    automatica apenas de comandos seguros (modo_remoto do motor)."""

    def __init__(self, engine):
        self.engine = engine

    def executar(self, texto):
        eng = self.engine
        if getattr(eng, "takeover", False):
            registrar_atividade("Comando bloqueado: MESTRE esta no controle manual.")
            return ("O MESTRE esta com o controle manual agora "
                    "(tomou a maozinha). Ele libera quando terminar. "
                    "Nenhuma acao automatica executada.")
        antigo = eng.modo_remoto
        eng.modo_remoto = True
        try:
            return eng.responder(texto)
        except Exception as ex:
            registrar_atividade("Erro ao executar: " + str(ex))
            return "Erro ao executar: {} ({})".format(texto, ex)
        finally:
            eng.modo_remoto = antigo


class ServidorControle:
    def __init__(self, engine, porta=8890, host="0.0.0.0", token=None):
        self.engine = engine
        self.porta = porta
        self.host = host
        self.token = token or "neoai"  # troque por um token forte
        self._httpd = None
        self._thread = None

    def iniciar(self):
        self.engine.modo_remoto = False

        try:
            self._httpd = ThreadingHTTPServer((self.host, self.porta),
                                              NeoHubHandler)
        except OSError as ex:
            return "Falha ao subir o servidor na porta {}: {}".format(self.porta, ex)
        self._httpd.engine = self.engine
        self._httpd.neoai_token = self.token
        self._httpd.executor = HubExecutor(self.engine)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        METADADOS.update(status="ativo", porta=self.porta,
                         iniciado_em=time.strftime("%Y-%m-%d %H:%M:%S"))
        ip = ip_local()
        linha = self.host
        registrar_atividade("Servidor de controle ATIVO na porta " +
                            str(self.porta) + " (token exigido)")
        return ("Controle remoto ATIVO: http://{}:{} (so com seu token).\n"
                "IPs para acessar: {}\n"
                "No OUTRO aparelho rode NeoAI e diga: "
                "'registra remoto nome ip {} {} seu_token'."
                .format(linha, self.porta, ip, ip, self.porta))

    def enderecos(self):
        return ip_local()


def ip_local():
    """Melhor esforco para descobrir o IP LAN do aparelho (sem libs)."""
    import socket
    import subprocess
    import re
    try:
        r = subprocess.run(["ip", "-4", "-o", "addr", "show"], capture_output=True,
                           text=True, timeout=5)
        ips = []
        for ln in r.stdout.splitlines():
            m = re.search(r"inet\s+(\d{1,3}(?:\.\d{1,3}){3})", ln)
            if m and not m.group(1).startswith("127."):
                ips.append(m.group(1))
        if ips:
            return ", ".join(dict.fromkeys(ips))
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "desconhecido"


def enviar_comando(ip, porta, token, texto, timeout=120):
    """Usa o hub de outro aparelho (notebook <-> celular). Retorna texto."""
    import urllib.request
    corpo = json.dumps({"token": token, "texto": texto}).encode("utf-8")
    url = "http://{}:{}/cmd".format(ip, porta)
    req = urllib.request.Request(url, data=corpo, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dados = json.loads(r.read().decode("utf-8"))
    if dados.get("ok"):
        return dados.get("resposta", "")
    return "ERRO remoto: " + dados.get("erro", "desconhecido")