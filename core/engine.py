"""Motor de IA feito do ZERO com NLP puro (sem nenhum modelo de linguagem).

Nada de Ollama, OpenCode, Kimi, QWEN, GGUF, HuggingFace ou qualquer rede neural
pré-treinada. Todo o processamento é baseado em regras e algoritmos próprios:
- Tokenização (com suporte a acentos/português)
- Normalização / stemming léxico simples
- Análise de intenção por correspondência de palavras-chave e pesos
- Extração de entidades simples
- Sistema de conhecimento e raciocínio baseado em regras
- Gerador de resposta por composição de templates + memória
"""
import ast
import math
import os
import re
import time
import difflib

from core.executor import Executor
from core.planner import Planejador
from core.agents import EquipeAgentes
from core.security import Cofre, auditar_codigo, cifrar, decifrar
from core import netctrl
from core import mapper as mapper_mod


# ---------------------- normalization / tokenization ----------------------

STOPWORDS = {
    "a", "o", "e", "de", "do", "da", "dos", "das", "um", "uma", "uns", "umas",
    "em", "no", "na", "nos", "nas", "para", "por", "com", "sem", "sobre",
    "que", "qual", "quem", "onde", "quando", "como", "porque", "porque",
    "se", "mas", "ou", "os", "as", "ao", "aos", "eh", "é", "e", "to", "voce",
    "vc", "tu", "eu", "ele", "ela", "nós", "nos", "voces", "seu", "sua", "meu",
    "minha", "isto", "isso", "aquilo", "este", "esta", "the", "is", "a", "to",
}

ARTIGOS = {"a", "o", "as", "os", "um", "uma"}
PREPOSICOES = {"de", "do", "da", "em", "no", "na", "para", "por", "com", "sem"}

ACENTOS = {
    "á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a",
    "é": "e", "ê": "e", "è": "e", "ë": "e",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ö": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ç": "c", "ñ": "n",
}


def remover_acentos(texto):
    return "".join(ACENTOS.get(c, c) for c in texto.lower())


def stem(t):
    """Stemming léxico leve em português (regras próprias, sem lib)."""
    t = t.lower()
    # sufixos comuns do plural
    if t.endswith("oes") and len(t) > 4:
        return t[:-2]
    if t.endswith("ens") and len(t) > 4:
        return t
    if t.endswith("ões") and len(t) > 4:
        return t[:-2] + "ao"
    if t.endswith("ães") and len(t) > 4:
        return t[:-2] + "ao"
    if t.endswith("s") and not t.endswith("ss") and len(t) > 3:
        t = t[:-1]
    # sufixos verbais simples
    for suf in ("ando", "endo", "indo"):
        if t.endswith(suf) and len(t) > 5:
            return t[:-len(suf)]
    for suf in ("aria", "aria", "er", "ir", "ar", "ava", "era"):
        if t.endswith(suf) and len(t) > 4:
            return t[:-len(suf)]
    if t.endswith("mente") and len(t) > 6:
        return t[:-5]
    return t


def tokenizar(texto):
    texto = texto.lower()
    tokens = re.findall(r"[a-zà-ÿ0-9]+", texto, re.IGNORECASE)
    return [stem(t) for t in tokens]


def palavras_limpas(texto):
    """Remove stopwords e artigos, retorna lista de stems significativos."""
    toks = tokenizar(texto)
    limpo = []
    for t in toks:
        if t in STOPWORDS or len(t) < 2:
            continue
        if t in ARTIGOS or t in PREPOSICOES:
            continue
        if t not in limpo:
            limpo.append(t)
    return limpo


def distancia_levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(atual[-1] + 1,
                             anterior[j] + 1,
                             anterior[j - 1] + (ca != cb)))
        anterior = atual
    return anterior[-1]


def similaridade(a, b):
    if not a or not b:
        return 0.0
    m = max(len(a), len(b))
    return 1.0 - distancia_levenshtein(a, b) / m


# ---------------------- intenções e padrões ----------------------

class Intencao:
    SAUDACAO = "saudacao"
    DESPEDIDA = "despedida"
    AJUDA = "ajuda"
    MEMORIA_LER = "memoria_ler"
    MEMORIA_GRAVAR = "memoria_gravar"
    MEMORIA_ESQUECER = "memoria_esquecer"
    CONHECIMENTO = "conhecimento"
    MATH = "matematica"
    TEMPO = "tempo_atual"
    SISTEMA = "sistema"
    COMPARAR = "comparar"
    LISTAR_MEMORIAS = "listar_memorias"
    EXPORTAR = "exportar"
    QUEM_SOU = "quem_sou"
    FALAR = "falar"
    SEGURANCA = "seguranca"
    REMOTO = "remoto"
    MAPEAR = "mapear"
    SERVIR = "servir"
    EXECUTAR = "executar"
    DESCONHECIDO = "desconhecido"


VERBOS_MEMORIA = {
    "lembr", "memoriz", "guarde", "guard", "salv", "anot",
    "memoria", "record", "gravar", "registr", "nota",
}
VERBOS_ESQUECER = {"esquec", "apag", "remov", "delete", "limpa-limp"}
VERBOS_LER = {"lembra", "memoria", "recordou", "saber", "viu", "anotou",
              "guardou"}

NUMERO_PT = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
    "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
    "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
    "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 40,
    "cinquenta": 50, "cem": 100, "cento": 100, "mil": 1000,
}

OPERADORES = {
    "mais": "+", "soma": "+", "+": "+", "menos": "-", "subtrai": "-",
    "-": "-", "vezes": "*", "multiplica": "*", "x": "*", "*": "*",
    "dividido": "/", "divide": "/", "/": "/",
}


def extrair_numero(token):
    if token.isdigit():
        return float(token)
    if token in NUMERO_PT:
        return float(NUMERO_PT[token])
    # números por extenso compostos
    return None


def parse_math(texto):
    """Tenta transformar uma frase matemática numa expressão avaliável (string).

    Suporta: raiz quadrada ('raiz de', 'sqrt'), porcentagem ('%', 'porcento'),
    e operadores (mais/+, menos/-, vezes/*, dividido por/, etc.).
    Retorna (expressao_str, descricao) ou (None, None)."""
    tl = texto.lower()

    # raiz quadrada: 'raiz de 9', 'raiz quadrada de 9', 'sqrt(9)'
    m_sqrt = re.search(r"ra[ií]z(?: quadrada)?\s*(?:de|quadrada de)\s*([\d.,]+)", tl)
    if m_sqrt:
        num = m_sqrt.group(1).replace(",", ".")
        return "sqrt({})".format(num), "raiz quadrada de " + m_sqrt.group(1)

    # normaliza palavras de operador para símbolos
    expr = texto
    expr = re.sub(r"\bmais\b", "+", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bsoma\b", "+", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bmenos\b", "-", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bvezes\b", "*", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bmultiplicad\w*\s+por\b", "*", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bdiv[id]id\w*\s+por\b", "/", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bporcent\w*\b", "%", expr, flags=re.IGNORECASE)
    expr = re.sub(r"x(?=[\d\s])", "*", expr, flags=re.IGNORECASE)

    # remove palavras que não são parte da expressão
    expr = re.sub(r"quanto\s+e|quanto\s+eh|quanto|calcule|calcula|me\s+da|e\s+a\s+conta|conta\s+de",
                  "", expr, flags=re.IGNORECASE)

    # extrai números e operadores permitidos
    expr_limpa = re.findall(r"[\d.,]+\s*[+\-*/%]?|\s*[+\-*/%]\s*", expr)
    expr_str = "".join(e.strip() for e in expr_limpa).strip()

    # valida se sobrou algo numérico-e-operadores
    if not re.search(r"\d", expr_str):
        return None, None
    if re.search(r"[+\-*/%]{2,}", expr_str.replace("**", "")):
        # operadores duplos inválidos (exceto ** que não usamos)
        if not re.search(r"[+*]\s*-\s*\d", expr_str):
            pass
    # guarda contra letras/eval perigoso
    if re.search(r"[a-zA-Z]", expr_str):
        return None, None
    return expr_str, expr_str


def avaliar_math(expr):
    """Avalia de forma segura uma expressão com + - * / % e sqrt().

    Usa ast para construir uma árvore e avaliar apenas nós numéricos e
    operadores permitidos — nunca eval() arbitrário."""
    ops = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.Mod: lambda a, b: a * (b / 100.0) if False else a % b,
        ast.Pow: pow,
    }
    # substitui % no texto por mod para o parser, mas % nessse contexto é por cento
    expr_mod = expr.replace("%", "%")
    # expressões com % precisam de tratamento especial: numerador * denominador /100
    if "%" in expr:
        expr_mod = expr.replace("%", "/100")
    tree = safe_parse(expr_mod)
    if tree is None:
        return None
    return eval_node(tree.body, ops)


def safe_parse(expr):
    try:
        return ast.parse(expr, mode="eval")
    except Exception:
        return None


def eval_node(node, ops):
    if isinstance(node, ast.Expression):
        return eval_node(node.body, ops)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in ops:
        left = eval_node(node.left, ops)
        right = eval_node(node.right, ops)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Div) and right == 0:
            raise ZeroDivisionError
        return ops[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = eval_node(node.operand, ops)
        return -v if v is not None else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == "sqrt":
        arg = eval_node(node.args[0], ops)
        return math.sqrt(arg) if arg is not None and arg >= 0 else None
    return None


# ---------------------- conhecimento ----------------------

CONHECIMENTO_BASE = {
    "neo": "NeoAI - a inteligencia criada do zero, sem nenhum modelo de "
           "linguagem pre-treinado. Funciona com NLP puro por regras.",
    "olá": "Ola! Sou a NeoAI, uma inteligencia construida do zero.",
    "oi": "Ola! Como posso ajudar?",
    "hello": "Hello! I am NeoAI, built from scratch.",
    "ai": "Sou uma IA criada do zero, sem dependencia de modelos de linguagem.",
    "captachos": "Linguagem natural pura, tudo feito por regras proprias.",
}


# ---------------------- motor principal ----------------------

class NeoEngine:
    def __init__(self, memory, platform):
        self.memory = memory
        self.platform = platform
        self.nome = "NeoAI"
        self.conhecimento = dict(CONHECIMENTO_BASE)
        self.executor = Executor(platform)
        self.planejador = Planejador(memory, self.executor, platform)
        self.equipe = EquipeAgentes(memory)
        self.cofre = Cofre(memory)
        self.servidor = None
        self.modo_remoto = False  # True = comandos remotos so executam o seguro
        self.takeover = False     # True = mestre assumiu o controle manual
        self.aprovador = None  # callback(comando, explicacao, seguro) -> bool

    # ---- intenção ----

    def detectar_intencao(self, texto):
        t = remover_acentos(texto.lower())

        if any(g in t for g in ("oi", "ola", "bom dia", "boa tarde", "boa noite",
                                 "hello", "hey", "eai", "e ai", "falai")):
            return Intencao.SAUDACAO
        if any(g in t for g in ("tchau", "ate logo", "adeus", "falou", "vlw",
                                 "obrigado ate", "ate mais")):
            return Intencao.DESPEDIDA
        if any(g in t for g in ("o que voce faz", "comandos", "ajuda", "help",
                                 "como funciona", "o que sabe")):
            return Intencao.AJUDA
        if any(g in t for g in ("esqueca", "apague", "remova", "limpe a mem",
                                 "delete da memoria")):
            return Intencao.MEMORIA_ESQUECER
        if any(g in t for g in ("lembre-se", "memorize", "guarde isso",
                                 "salve na memoria", "grave", "anota",
                                 "registre", "guarde na memoria", "lear")):
            return Intencao.MEMORIA_GRAVAR
        if any(g in t for g in ("o que voce lembra", "o que voce anotou",
                                "liste a memoria", "quais memorias",
                                "lista de memorias", "mostre a memorias",
                                "quais coisas", "liste o que")):
            return Intencao.LISTAR_MEMORIAS
        if any(g in t for g in ("exporta", "exportar", "backup", "gerar arquivo")):
            return Intencao.EXPORTAR
        if any(g in t for g in ("quem e voce", "quem sao voce", "o que e voce",
                                "voce e oque", "quem criou", "sua origem",
                                "como foi feita", "como voce funciona")):
            return Intencao.QUEM_SOU
        if any(g in t for g in ("que horas", "hora atual", "data de hoje",
                                "dia de hoje", "que dia")):
            return Intencao.TEMPO
        if any(g in t for g in ("sistema", "sobre o sistema",
                                "sistema operacional", "plataforma",
                                "qual dispositivo", "onde estou",
                                "qual o sistema", "info do sistema",
                                "informacoes do sistema")):
            return Intencao.SISTEMA
        if any(g in t for g in ("lembra de", "voce lembra", "o que sei sobre",
                                "o que voce sabe sobre", "me fala sobre")):
            return Intencao.MEMORIA_LER
        if any(g in t for g in ("compare", "comparar", "qual e maior",
                                "qual e menor", "qual e melhor")):
            return Intencao.COMPARAR

        # SEGURANCA: senhas/credenciais/criptografia/auditoria
        if any(g in t for g in ("senha mestra", "credencia", "criptografia",
                                "criptografa", "cofre", "guardar token",
                                "auditar", "auditoria", "seguranca",
                                "auto-melhoria", "auto melhorar")):
            return Intencao.SEGURANCA

        # REMOTO: controlar/consultar o OUTRO aparelho (notebook <-> celular)
        if any(g in t for g in ("manda pro cel", "manda para o cel",
                                "envia pro cel", "envia para o cel",
                                "controla meu cel", "mexe no meu cel",
                                "manda pro notebook", "manda pro pc",
                                "controla meu notebook", "controla meu pc",
                                "registra remoto", "adiciona remoto",
                                "conecta no")):
            return Intencao.REMOTO

        # SERVIR: abrir o servidor de controle para receber comandos remotos
        if any(g in t for g in ("servir na porta", "sobe o servidor",
                                "abrir o servidor", "inicia o servidor",
                                "modo servidor", "controle remoto ativa",
                                "ativa o servidor",
                                "assumir controle", "libera controle",
                                "liberar controle", "controle automatico")):
            return Intencao.SERVIR

        # MAPEAR: aprender o dispositivo de ponta a ponta
        if any(g in t for g in ("conhece meu cel", "conheca meu cel",
                                "aprende meu cel", "aprende o cel",
                                "mapeia", "explora o cel", "explore o cel",
                                "conhece meu dispositivo",
                                "conhece meu notebook",
                                "quais rotas", "o que aprendeu",
                                "resumo das rotas", "conhece o aparelho")):
            return Intencao.MAPEAR

        # EXECUTAR: pedidos imperativos de ação no dispositivo
        # detecta abertura de apps do Android (ex: 'abre meu zap', 'roda o whatsapp')
        m_abre = re.match(r"^(abra|abre|roda|inicia|executa|execute)\s+(meu|me|o|a)\s+(\S+)",
                          t)
        if m_abre and self.executor.encontrar_app(m_abre.group(3)):
            return Intencao.EXECUTAR
        # detecta abertura de sites (ex: 'abre o site youtube.com', 'acessa a pagina gmail.com/...')
        m_site = re.search(r"(abre|abra|acessa|acesse|visita|visite|entra no|entrar no)\s+(?:o |a )?(?:site |url |pagina |link )?([a-zA-Z0-9][a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?:/\S*)?)",
                           t)
        if m_site and m_site.group(2) and len(m_site.group(2)) >= 4:
            return Intencao.EXECUTAR
        if any(g in t for g in ("lista as pastas", "liste as pastas",
                                "listar as pastas", "o que tem aqui",
                                "o que tem nessa pasta", "mostra os arquivos",
                                "exibe a pasta", "informacoes do sistema",
                                "info do sistema", "detalhes do sistema",
                                "abre o arquivo", "abra o arquivo",
                                "abre o programa", "abra o programa",
                                "execute", "executa", "roda o script",
                                "instala", "instale", "cd para",
                                "entre na pasta", "entrar na pasta",
                                "mostra o conteudo", "mostre o conteudo",
                                "roda o python", "execute o")):
            return Intencao.EXECUTAR

        expr, desc = parse_math(texto)
        if expr is not None:
            return Intencao.MATH
        if any(g in t for g in ("quanto e", "calcule", "matematica",
                                "me da a conta")):
            return Intencao.MATH

        # conhecimento
        limpo = palavras_limpas(texto)
        for chave in self.conhecimento:
            stem_key = stem(chave)
            for p in limpo:
                if similaridade(p, stem_key) >= 0.85 or p == stem_key:
                    return Intencao.CONHECIMENTO
        for fato in self.memory.get_fatos():
            for p in limpo:
                for wq in palavras_limpas(fato["texto"]):
                    if p == wq:
                        return Intencao.MEMORIA_LER

        return Intencao.DESCONHECIDO

    # ---- execução ----

    def responder(self, texto):
        texto = texto.strip()
        if not texto:
            return "... diga algo. (digite 'ajuda')"

        intencao = self.detectar_intencao(texto)
        self.memory.add_conversa(texto, "")
        resultado = self._executar(intencao, texto)
        self.memory.add_conversa(texto, resultado)
        return resultado

    def _executar(self, intencao, texto):
        if intencao == Intencao.SAUDACAO:
            self.memory.add_fato("usuario cumprimentou a IA")
            return "Ola! Sou a {}. Tudo normal por aqui. Digite 'ajuda' para ver o que faco.".format(self.nome)
        if intencao == Intencao.DESPEDIDA:
            self.memory.add_fato("usuario se despediu")
            return "Ate a proxima! Estarei aqui quando precisar."
        if intencao == Intencao.AJUDA:
            return self._texto_ajuda()
        if intencao == Intencao.QUEM_SOU:
            return self._quem_sou()
        if intencao == Intencao.MATH:
            return self._calcular(texto)
        if intencao == Intencao.TEMPO:
            return "Agora sao {:02d}:{:02d} de {}/{}/{}.".format(
                time.localtime().tm_hour, time.localtime().tm_min,
                time.localtime().tm_mday, time.localtime().tm_mon,
                time.localtime().tm_year)
        if intencao == Intencao.SISTEMA:
            return "Rodo em: {} (Termux: {}, Android: {}, iPhone: {}, Root: {}, Download: {}).".format(
                self.platform.os_name, self.platform.is_termux,
                self.platform.is_android, self.platform.is_iphone,
                self.platform.is_root,
                self.platform.download_dir)
        if intencao == Intencao.MEMORIA_GRAVAR:
            return self._gravar(texto)
        if intencao == Intencao.MEMORIA_LER:
            return self._ler(texto)
        if intencao == Intencao.MEMORIA_ESQUECER:
            return self._esquecer(texto)
        if intencao == Intencao.LISTAR_MEMORIAS:
            return self._listar()
        if intencao == Intencao.EXPORTAR:
            p = self.memory.export_tudo()
            return "Memoria exportada para: " + p
        if intencao == Intencao.CONHECIMENTO:
            return self._conhecimento(texto)
        if intencao == Intencao.COMPARAR:
            return "Me diga o que quer comparar de forma explicita, ex: 'compare A e B'."
        if intencao == Intencao.SEGURANCA:
            return self._seguranca(texto)
        if intencao == Intencao.MAPEAR:
            return self._mapear(texto)
        if intencao == Intencao.REMOTO:
            return self._remoto(texto)
        if intencao == Intencao.SERVIR:
            return self._servir(texto)
        if intencao == Intencao.EXECUTAR:
            return self._lidar_execucao(texto)
        return self._desconhecido(texto)

    # ---- execução de funções no dispositivo ----

    def _aprovar_comando(self, comando, explicacao, seguro):
        """Pedido de confirmação ao usuário. Pode ser substituído por um
        callback de aprovação programática (configurável)."""
        if callable(self.aprovador):
            return self.aprovador(comando, explicacao, seguro)
        if self.modo_remoto:
            # comandos recebidos do OUTRO aparelho: so o seguro executa
            # sozinho; o resto fica para o mestre assumir/liberar.
            return bool(seguro)
        # padrão: pede confirmação no terminal
        try:
            r = input("Executar: '{}'  ({})? [s/N] ".format(comando, explicacao))
            return r.strip().lower() in ("s", "sim", "y", "yes")
        except Exception:
            return False

    def _refletir_antes_de_executar(self, texto):
        """NeoAI pensa antes de agir: consulta os 3 agentes, troca duvidas
        e decide a melhor forma de executar. Retorna lista de linhas."""
        linhas = ["[Pensando] NeoAI reflete antes de executar: '{}'...".format(texto)]
        # Consulta o time de agentes (sem pesquisa web para ser rapido e nao
        # depender de internet ao executar)
        pensamento, resposta = self.equipe.pensar(texto, pesquisar_web=False)
        linhas.append(pensamento)
        # Melhora a decisao de execucao se o agente der uma dica pratica
        if resposta:
            linhas.append("[Visao do time] {}".format(resposta))
        linhas.append("")
        return linhas

    def _lidar_execucao(self, texto):
        # 0) NeoAI PENSAR antes de executar: reflete com o time de agentes
        linhas = self._refletir_antes_de_executar(texto)
        if linhas is None:
            return None

        # 1) planejar passo a passo (usando caminhos aprendidos se houver)
        plano = self.planejador.planejar(texto)
        if plano is None:
            linhas.append("Nao consegui montar um plano para '{}'. Tente ser "
                          "mais explicito, ex: 'lista as pastas', 'abre o "
                          "arquivo X', 'roda o script Y.py'.".format(texto))
            return "\n".join(linhas)

        respostas = list(linhas)
        todos_ok = True
        for i, passo in enumerate(plano.passos, 1):
            comando = passo["comando"]
            explicacao = passo["explicacao"]
            seguro = bool(passo.get("seguro"))

            respostas.append("[{}/{}] {}: `{}`".format(
                i, len(plano.passos), explicacao, comando))

            # confirmação: sempre pede antes de executar
            if not self._aprovar_comando(comando, explicacao, seguro):
                respostas.append("  -> Passo {} negado pelo usuario. Nada executado.".format(i))
                todos_ok = False
                break

            # caso especial: abrir app do Android
            if comando.startswith("APP::"):
                resultado = self.executor.abrir_app(comando[5:])
                if resultado:
                    respostas.append("  " + resultado)
                    self._aprender_rota_app(comando[5:], resultado)
                    continue
                respostas.append("  -> nao consegui abrir o app (so Termux/Android).")
                todos_ok = False
                break

            # caso especial: abrir site (aprende a rota para uso futuro)
            if comando.startswith("SITE::"):
                resultado = self.executor.abrir_site(comando[6:])
                if resultado:
                    respostas.append("  " + resultado)
                    self._aprender_rota_site(comando[6:])
                    continue
                respostas.append("  -> nao consegui abrir esse site.")
                todos_ok = False
                break

            codigo, stdout, stderr = self.executor.executar(comando)
            saida = (stdout or stderr or "").strip()
            if saida:
                # limita saída longa
                if len(saida) > 1500:
                    saida = saida[:1500] + "... [truncado]"
                respostas.append("  saida: " + saida)
            if codigo != 0:
                respostas.append("  -> erro (codigo {}).".format(codigo))
                todos_ok = False
                break

        if todos_ok:
            # 2) aprender o caminho na memória permanente
            self.planejador.registrar_sucesso(texto, plano.passos)
            respostas.append("")
            respostas.append("[Memorizado] Vou lembrar esse passo-a-passo para "
                             "executar a mesma tarefa no futuro.")
        else:
            respostas.append("")
            respostas.append("[Parado] Execucao incompleta. Nao memorizei o "
                             "caminho porque nao terminou com sucesso.")

        return "\n".join(respostas)

    # ---- ações ----

    def _texto_ajuda(self):
        return ("Comandos que entendo:\n"
                "- 'oi', 'ola': saudacao\n"
                "- 'lembre-se que ...' / 'guarde que ...': salvo na memoria\n"
                "- 'o que voce lembra?': listo memorias\n"
                "- 'esqueça ...' / 'apague ...': apago\n"
                "- 'exportar': gero backup da memoria\n"
                "- 'quanto e 5 + 3?': matematicas\n"
                "- 'quem e voce?': minhas informacoes\n"
                "- 'sistema': mostro onde rodo\n"
                "- 'lista as pastas': listo arquivos\n"
                "- 'roda o script X.py': executo o script\n"
                "- 'abre o arquivo X': mostro o arquivo\n"
                "- 'abre o site X': abro o site no navegador (e aprendo a rota)\n"
                "- 'abre o whatsapp': abro app do Android (Termux)\n"
                "- 'instala Y': instalo o pacote\n"
                "- 'informacoes do sistema': detalhes do hardware\n"
                "- 'conhece meu celular': aprendo o aparelho de ponta a ponta\n"
                "- 'quais rotas': mostro o que ja decorei do aparelho\n"
                "- 'servir na porta 8890': ligo o controle remoto (notebook<->celular)\n"
                "- 'registra remoto cel 192.168.x.x 8890 token': cadastro o outro aparelho\n"
                "- 'manda pro cel: <comando>': executo no celular (pelo notebook) e vice-versa\n"
                "- 'assumir controle' / 'libera controle': voce toma/dá a mão\n"
                "- 'defina senha mestra X': senha para criptografar credenciais\n"
                "- 'guarde credencial github <valor>': criptografa e guarda\n"
                "- 'auditar codigo' / 'auto-melhoria': checo e melhoro meu proprio codigo\n"
                "- 'tchau': despedida\n"
                "Obs: memorias vao para o Obsidian (se presente) ou Downloads.\n"
                "Execucoes pedem sua confirmacao antes de rodar cada passo, e eu\n"
                "memorizo o passo-a-passo para aprender os caminhos.")

    def _quem_sou(self):
        local = "Obsidian (vault)" if self.memory.using_obsidian else "Downloads"
        return ("Sou a NeoAI, uma inteligencia criada 100% do zero com NLP puro "
                "(regras proprias, sem nenhum modelo de linguagem: nada de Ollama, "
                "OpenCode, Kimi, QWEN ou GGUF).\n"
                "Minha memoria ficam em: {}.".format(local))

    def _gravar(self, texto):
        # remove palavras de comando para extrair o fato
        limpo = remover_acentos(texto)
        for c in ["lembre-se que ", "lembre-se ", "guarde que ", "guarde ",
                  "memorize que ", "memorize ", "grave que ", "grave ",
                  "anote que ", "anote ", "registre que ", "registre ",
                  "salve na memoria que ", "salve na memoria ",
                  "lembre se de que ", "lembre se de ", "guarde isso ",
                  "lembre que "]:
            limpo = limpo.replace(c, "")
        limpo = limpo.strip(" ,;:.!?")
        # limpa pronomes/artigos residuais no começo
        for art in ARTIGOS:
            if limpo.startswith(art + " "):
                limpo = limpo[len(art) + 1:]
                break
        chave = "fato"
        if limpo:
            self.memory.add_memoria(chave + "_" + str(int(time.time())), limpo)
            self.memory.add_fato(limpo)
            onde = "no Obsidian" if self.memory.using_obsidian else "na pasta Downloads"
            return "Anotado! Guardei '{}' {}.".format(limpo, onde)
        return "Nao entendi o que guardar. Diga tipo 'lembre-se que o codigo e X'."

    def _ler(self, texto):
        # procura memorias que correspondam às palavras da pergunta
        pergunta = palavras_limpas(texto)
        brain = self.memory.load_brain()
        memorias = brain.get("memorias", {})
        if not memorias:
            return "Nao tenho memorias salvas ainda. Diga 'lembre-se que ...'"
        melhores = []
        for chave, m in memorias.items():
            conteudo = m["conteudo"]
            score = 0
            for p in pergunta:
                for wc in palavras_limpas(conteudo):
                    if p == wc:
                        score += 1
            if score > 0 or any(p == stem(chave.split("_")[-1]) for p in pergunta):
                melhores.append((score, conteudo))
        if not melhores:
            return ("Nao encontrei nada correspondente. Minhas memorias: " +
                    ", ".join(list(memorias.values())[:5]))
        melhores.sort(reverse=True, key=lambda x: x[0])
        respostas = [c for _, c in melhores[:3]]
        return "Sobre isso, lembro: " + "; ".join(respostas)

    def _esquecer(self, texto):
        limpo = remover_acentos(texto)
        alvo = ""
        for c in ["esqueça ", "apague ", "remova ", "delete da memoria ",
                  "limpe a memoria de ", "esquecer "]:
            if c in limpo:
                alvo = limpo.split(c, 1)[1]
                break
        brain = self.memory.load_brain()
        memorias = brain.get("memorias", {})
        alvo_limpo = palavras_limpas(alvo)
        a_remover = []
        for chave, m in memorias.items():
            if any(p in palavras_limpas(m["conteudo"]) for p in alvo_limpo):
                a_remover.append(chave)
        for chave in a_remover:
            del memorias[chave]
        brain["memorias"] = memorias
        self.memory.save_brain(brain)
        if a_remover:
            return "Apaguei {} memorias.".format(len(a_remover))
        return "Nao encontrei nenhuma memoria para apagar."

    def _listar(self):
        brain = self.memory.load_brain()
        memorias = brain.get("memorias", {})
        if not memorias:
            return "Nao tenho memorias salvas ainda."
        linhas = ["Memorias salvas ({}) em {}:".format(
            len(memorias),
            "Obsidian" if self.memory.using_obsidian else "Downloads")]
        for chave, m in list(memorias.items()):
            linhas.append("- " + m["conteudo"])
        return "\n".join(linhas)

    def _calcular(self, texto):
        expr, desc = parse_math(texto)
        if expr is None:
            return "Nao consegui montar a conta. Ex: 'quanto e 5 + 3?', 'raiz de 9'."
        try:
            resultado = avaliar_math(expr)
        except ZeroDivisionError:
            return "Nao posso dividir por zero!"
        except Exception:
            return "Nao consegui calcular '{}'. Tente ex: '5 + 3 * 2'.".format(texto)
        if resultado is None:
            return "Nao consegui calcular '{}'.".format(texto)
        if float(resultado).is_integer():
            return "{} = {}".format(expr, int(resultado))
        return "{} = {:.2f}".format(expr, resultado)

    def _conhecimento(self, texto):
        limpo = palavras_limpas(texto)
        melhor = None
        melhor_score = 0
        for chave, valor in self.conhecimento.items():
            sk = stem(chave)
            for p in limpo:
                if p == sk or similaridade(p, sk) >= 0.85:
                    if 1 > melhor_score:
                        melhor, melhor_score = valor, 1
        for fato in self.memory.get_fatos():
            for p in limpo:
                for wq in palavras_limpas(fato["texto"]):
                    if p == wq:
                        return "Sobre {}, lembro: {}".format(
                            " ".join(limpo[:3]), fato["texto"])
        if melhor:
            return melhor
        return None

    def _seguranca(self, texto):
        tl = remover_acentos(texto.lower())

        # definir senha mestra
        m = re.search(r"(?:defin[aei](?:r)?|mud[aei]|troc[aei]).{0,20}senha mestra\s+(.+)", texto, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"senha mestra\s+(?:para\s+|de\s+)?(.+)", texto, flags=re.IGNORECASE)
        if m:
            senha = m.group(1).strip().strip(" !?.")
            if len(senha) < 4:
                return "A senha mestra precisa ter pelo menos 4 caracteres."
            self.cofre.senha_mestra = senha
            self.memory.add_fato("Usuario definiu senha mestra (criptografada, nunca em texto puro).")
            return ("Senha mestra definida. Cuidado: perca a senha e as credenciais "
                    "criptografadas ficam inacessiveis (nem eu consigo recuperar). "
                    "Use-a para: 'guarde credencial github <valor>'.")

        # guardar credencial
        m = re.search(r"(?:guarde|guardar|salve|salvar|armazen[aei])\s+(?:a\s+)?credencial\s+([\w.\-]+)\s+(.+)", texto, flags=re.IGNORECASE)
        if m:
            servico = m.group(1).lower()
            valor = m.group(2).strip().strip(" !?.")
            ok, msg = self.cofre.guardar(servico, valor)
            return "Criptografia: " + msg

        # listar credenciais
        if "list" in tl or "quais" in tl:
            servicos = self.cofre.listar()
            if servicos:
                return "Cofre contem credenciais para: " + ", ".join(servicos) + \
                       " (criptografadas). Nao revelo valores."
            return "Cofre vazio. Guarde com: 'guarde credencial github <valor>'."

        # revogar credencial
        m = re.search(r"(?:revog[aei]r?|apag[aei]|remov[aei])\s+(?:a\s+)?credencial\s+([\w.\-]+)", texto, flags=re.IGNORECASE)
        if m:
            ok, msg = self.cofre.revogar(m.group(1))
            return "Criptografia: " + msg

        # auditar codigo / auto-melhoria
        if "audit" in tl or "auto-melhoria" in tl or "auto melhoria" in tl:
            if "auto" in tl:
                return self._auto_melhoria()
            avisos = auditar_codigo(self.platform.home)
            if not avisos:
                return "Auditoria concluida: nenhum segredo em texto puro encontrado."
            return ("Auditoria concluida. {} possivei(s) segredo(s)/aviso(s):\n".format(len(avisos))
                    + "\n".join(" - " + a for a in avisos[:10]))

        if "criptograf" in tl:
            return ("Tenho criptografia propria (XOR+rotacao com chave derivada de "
                    "senha mestra via PBKDF2 caseiro + MAC de autenticacao). "
                    "Credenciais ficam no cofre.json, nunca em texto puro. "
                    "Honesto: criptografia caseira nao e TLS, mas ja e muito "
                    "melhor que senha em texto puro.")

        return ("Comandos de seguranca: 'defina senha mestra X', "
                "'guarde credencial github <valor>', 'liste credenciais', "
                "'revogue credencial github', 'auditar codigo', 'auto-melhoria'.")

    # ---- aprendizado de rotas (memoria permanente) ----

    def _aprender_rota_app(self, nome, resultado):
        """Decorou a rota do app: guarda para o dia a dia."""
        info = self.executor.encontrar_app(nome)
        if info:
            mapper_mod.registrar_rota_app(self.memory, info["nome"],
                                          info["pkg"])

    def _aprender_rota_site(self, url):
        mapper_mod.registrar_rota_site(
            self.memory, url.replace("https://", "").replace("http://", ""))

    # ---- mapeamento do dispositivo (conhecer de ponta a ponta) ----

    def _mapear(self, texto):
        if any(g in texto for g in ("rotas", "aprendeu", "resumo")):
            return mapper_mod.relatorio_rotas(self.memory)
        achados = mapper_mod.mapear(self.platform, self.memory, self.executor)
        if not achados:
            return "Nao consegui mapear nada por aqui. Pode ser dispositivo sem Termux."
        resumo = "\n".join(" - " + a for a in achados)
        return ("Mapeei o dispositivo (memoria gravada, inclusive no "
                "Obsidian).\n" + resumo +
                "\nAgora eu conheco suas rotas: apps, pastas e sites que "
                "voce costuma usar. Diga 'quais rotas' para ver.")

    # ---- controle remoto (notebook <-> celular) ----

    def _registrado(self, nome):
        remotos = self.memory.get("remotos") or {}
        return remotos.get(nome)

    def _remoto(self, texto):
        tl = texto.lower()

        # registrar um aparelho
        m = re.search(r"registra remoto\s+(\S+)\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d+)\s+(\S+)",
                      texto, flags=re.IGNORECASE)
        if m:
            nome, ip, porta, token = m.group(1), m.group(2), m.group(3), m.group(4)
            remotos = self.memory.get("remotos") or {}
            remotos[nome] = {"ip": ip, "porta": int(porta), "token": token}
            self.memory.set("remotos", remotos)
            self.memory.add_fato("Aparelho remoto '{}' registrado (ip {}, porta {}).".format(
                nome, ip, porta))
            return ("Registrado! De agora em diante eu sei como falar com "
                    "'{}' no endereco {}:{}. Diga 'manda pro {}: <comando>'."
                    .format(nome, ip, porta, nome))

        # descobrir qual aparelho remoto estamos falando
        alvo = m_nome = None
        for n in (self.memory.get("remotos") or {}):
            if n in tl:
                alvo = self.memory.get("remotos")[n]
                m_nome = n
                break
        if not alvo:
            return ("Nao conheco esse aparelho ainda. Registre primeiro: "
                    "'registra remoto cel 192.168.x.x 8890 seu_token'. "
                    "(depois de ligar o servidor no outro aparelho)")

        # extrair o comando depois da expressao (a partir do nome do aparelho)
        idx = texto.lower().find(m_nome.lower())
        if idx < 0:
            return "Nao entendi para qual aparelho mandar."
        resto = texto[idx + len(m_nome):].strip(" :,;")
        comando = resto.strip()
        if not comando:
            return "O que devo mandar fazer no '{}'? Ex: 'manda pro {}: abra o whatsapp'.".format(
                m_nome, m_nome)
        netctrl.registrar_atividade("Enviando comando para '{}': {}".format(m_nome, comando))
        try:
            resultado = netctrl.enviar_comando(alvo["ip"], alvo["porta"],
                                               alvo["token"], comando)
            return ("Resposta de '{}':\n{}".format(m_nome, resultado))
        except Exception as ex:
            return ("Nao consegui falar com '{}'. Confira se o servidor esta "
                    "ativo la, o ip/porta/token e a rede (mesmo Wi-Fi). "
                    "Erro: {}".format(m_nome, ex))

    def _servir(self, texto):
        tl = texto.lower()
        if "assumir" in tl or "libera" in tl or "liberar" in tl:
            if "assumir" in tl:
                self.takeover = True
                return ("Voce (mestre) assumiu o controle. Acoes automaticas "
                        "pausadas ate voce liberar. Para devolver, diga "
                        "'libera controle'.")
            self.takeover = False
            return "Controle liberado. NeoAI pode agir de novo."

        m = re.search(r"(\d{4,5})", tl)
        porta = int(m.group(1)) if m else 8890
        if self.servidor:
            return ("Ja esta servindo na porta {}. Para ver no navegador "
                    "use o painel (com token). Se quiser porta nova, reinicie:\n"
                    "- servidor: http://<ip>:{}  | chave do painel: token"
                    .format(self.servidor.porta, self.servidor.porta))
        # token: defina um forte via 'defina senha mestra X' ou padrao
        token = getattr(self.cofre, "senha_mestra", None) or "neoai-mudar"
        self.servidor = netctrl.ServidorControle(self, porta=porta,
                                                 host="0.0.0.0", token=token)
        return self.servidor.iniciar()

    def _auto_melhoria(self):
        """Primeira versao de auto-melhoria: auditoria do proprio codigo +
        verificacao de boas praticas, e guarda o resultado na memoria."""
        base = os.path.dirname(os.path.abspath(__file__))
        raiz = os.path.join(base, "..")
        avisos = auditar_codigo(raiz)
        relatorio = []
        relatorio.append("Auto-melhoria (v1) - auditoria do proprio codigo:")
        if avisos:
            relatorio.append("- {} possivel(is) segredo(s) em texto puro.".format(len(avisos)))
            for a in avisos[:8]:
                relatorio.append("   * " + a)
        else:
            relatorio.append("- Nenhum segredo em texto puro.")
        relatorio.append("- Sugestao: faca backups do vault, defina senha mestra,")
        relatorio.append("  e mantenha o codigo atualizado (git pull).")
        conteudo = "\n".join(relatorio)
        self.memory.add_memoria("auto_melhoria_" + str(int(time.time())), conteudo)
        return conteudo

    def _desconhecido(self, texto):
        # NeoAI pensa: consulta os 3 agentes, troca duvidas e pesquisa web.
        pen, resposta = self.equipe.pensar(texto)
        if resposta:
            return pen + "\n\n" + resposta
        return ("Nao consegui entender ou nao encontrei resposta confiavel para "
                "'{}' (e a busca na internet nao trouxe resultado).\n"
                "Tente reformular, ou digite 'ajuda' para ver o que sei fazer.").format(texto)
