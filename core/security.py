"""Segurança e criptografia da NeoIA (feita do zero, sem dependências externas).

Inclui:
1. Criptografia simétrica própria: chave derivada de frase-senha + salt, com
   confusão/difusão (XOR + rotações). Suficiente para cofre local de credenciais.
2. Cofre de credenciais: guarda tokens/senhas criptografados em arquivo, nunca
   em texto puro.
3. Auditoria de código: procura segredos em texto puro no próprio código-fonte.

AVISO HONESTO: criptografia caseira não é equivalente a TLS/AES auditado. Isso
protege contra leitura casual do arquivo e é melhor que senha em texto puro,
mas criptografia de ponta a ponta real (rede) exige TLS, que já existe no HTTPS
usado para a web.
"""
import base64
import hashlib
import json
import os
import re
import time


# ---------------------- primitivas próprias ----------------------

def _derivar_chave(senha, salt, iteracoes=10000):
    """Deriva uma chave determinística a partir de senha+salt (PBKDF2 caseiro)."""
    chave = senha.encode("utf-8") + salt
    for _ in range(iteracoes):
        chave = hashlib.sha256(chave).digest() + hashlib.sha256(
            chave[::-1] + salt).digest()
    return hashlib.sha256(chave + salt).digest()


def _expandir_chave(chave, tamanho):
    """Expande a chave derivada para o tamanho do bloco de dados."""
    chave_estend = b""
    bloco = chave
    while len(chave_estend) < tamanho:
        bloco = hashlib.sha256(bloco + chave).digest()
        chave_estend += bloco
    return chave_estend[:tamanho]


def cifrar(dados, senha):
    """Cifra bytes para base64 usando XOR com chave expandida e rotações."""
    salt = os.urandom(16)
    chave = _derivar_chave(senha, salt)
    chave_exp = _expandir_chave(chave, len(dados))
    # XOR com rotação ((x + i) % 256) para dar difusão
    cifrado = bytearray()
    for i, b in enumerate(dados):
        c = (b ^ chave_exp[i]) % 256
        c = ((c + i) % 256) if i % 3 else ((c - i) % 256)
        cifrado.append(c)
    # MAC: autentica conteúdo para detectar senha errada/adulteracao
    mac = hashlib.sha256(bytes(cifrado) + chave).hexdigest()
    return {
        "v": 1,
        "salt": base64.b64encode(salt).decode(),
        "dados": base64.b64encode(bytes(cifrado)).decode(),
        "iter": 10000,
        "mac": mac,
    }


def decifrar(payload, senha):
    """Decifra o payload gerado por cifrar(). Retorna (dados, Ok/None)."""
    salt = base64.b64decode(payload["salt"])
    dados = base64.b64decode(payload["dados"])
    chave = _derivar_chave(senha, salt)
    # verifica MAC antes de decifrar (senha errada -> acusa)
    mac_esperado = payload.get("mac")
    if mac_esperado:
        mac_atual = hashlib.sha256(dados + chave).hexdigest()
        if mac_atual != mac_esperado:
            return None
    chave_exp = _expandir_chave(chave, len(dados))
    claro = bytearray()
    for i, b in enumerate(dados):
        c = b
        c = ((c - i) % 256) if i % 3 else ((c + i) % 256)
        claro.append(c ^ chave_exp[i])
    return bytes(claro)


# ---------------------- cofre de credenciais ----------------------

class Cofre:
    """Cofre de credenciais criptografadas em arquivo JSON."""

    def __init__(self, memory, senha_mestra=None):
        self.memory = memory
        self.path = os.path.join(memory.vault_dir, "cofre.json")
        self.senha_mestra = senha_mestra

    def _ler(self):
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _escrever(self, dados):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

    def guardar(self, servico, valor, senha_mestra=None):
        """Criptografa e guarda uma credencial. Requer senha mestra."""
        sm = senha_mestra or self.senha_mestra
        if not sm:
            return False, "Defina uma senha mestra para criptografar (ex: 'defina senha mestra X')."
        cofre = self._ler()
        cofre[servico.lower()] = cifrar(valor.encode("utf-8"), sm)
        self._escrever(cofre)
        return True, "Credencial '{}' guardada criptografada (nunca em texto puro).".format(servico)

    def obter(self, servico, senha_mestra=None):
        """Recupera uma credencial decifrada."""
        sm = senha_mestra or self.senha_mestra
        if not sm:
            return None, "Senha mestra necessaria."
        cofre = self._ler()
        payload = cofre.get(servico.lower())
        if not payload:
            return None, "Nao ha credencial para '{}'.".format(servico)
        try:
            claro = decifrar(payload, sm)
            if claro is None:
                return None, "Falha ao autenticar/decifrar (senha mestra errada?)."
            return claro.decode("utf-8"), None
        except Exception:
            return None, "Falha ao decifrar (senha mestra errada?)."

    def revogar(self, servico, senha_mestra=None):
        """Remove uma credencial do cofre."""
        sm = senha_mestra or self.senha_mestra
        if not sm:
            return False, "Senha mestra necessaria."
        cofre = self._ler()
        if servico.lower() in cofre:
            del cofre[servico.lower()]
            self._escrever(cofre)
            return True, "Credencial '{}' revogada.".format(servico)
        return False, "Credencial '{}' nao existe.".format(servico)

    def listar(self):
        """Lista quais servicos tem credenciais (sem revelar segredos)."""
        cofre = self._ler()
        return list(cofre.keys()) if cofre else []


# ---------------------- auditoria de código ----------------------

PADROES_SEGREDO = [
    (re.compile(r"\b(token|apikey|api_key|senha|password|secret|credencial)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
     "possivel segredo em texto puro"),
    (re.compile(r"am\s+start|curl\s+-k", re.IGNORECASE),
     "comando sensivel detectado"),
]

def auditar_codigo(raiz):
    """Varre .py/.md em busca de segredos em texto puro. Retorna lista de avisos."""
    avisos = []
    for base, _, arqs in os.walk(raiz):
        if ".git" in base or "__pycache__" in base:
            continue
        for arq in arqs:
            if not arq.endswith((".py", ".md", ".json")):
                continue
            caminho = os.path.join(base, arq)
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    conteudo = f.read()
            except Exception:
                continue
            for lin, linha in enumerate(conteudo.splitlines(), 1):
                linha = linha.strip()
                if not linha or linha.startswith("#"):
                    continue
                for padrao, desc in PADROES_SEGREDO:
                    if padrao.search(linha):
                        avisos.append("{}:{} -> {}".format(caminho, lin, desc))
                        break
    return avisos