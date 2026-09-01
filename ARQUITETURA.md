# NeoIA unlock - Arquitetura do Sistema

> Documento de arquitetura e vias tecnicas. Leia antes de estender o sistema.

## 0. Declaracao honesta (limitações)

NeoIA e construida **100% do zero**, com NLP de regras e algoritmos proprios.
Nao usa nenhum modelo de linguagem pre-treinado (nada de Ollama, Qwen, Llama,
Mistral, GPT, Claude, Grok, Gemini, DeepSeek ou GGUF).

**Limite fisico honesto:** paridade com sistemas como Grok/xAI nao e alcancavel
apenas com regras e algoritmos proprios. Modelos como Grok sao redes neurais
com bilhoes de parametros treinadas em dados massivos. O que esta arquitetura
entrega e um sistema deterministico, auditavel, leve e 100% offline, com:
- raciocinio por intencao + regras + memoria
- equipe de agentes que trocam duvidas
- busca web (Wikipedia/DuckDuckGo) para conhecimento factual
- aprendizado persistente no Obsidian

Nao simulamos nem afirmamos equivalencia com Grok. Isso nao e um defeito: e
uma escolha de arquitetura (privacidade, tamanho, auditabilidade, zero custo).

## 1. Visao de alto nivel

```
                    +---------------------+
    Usuario/Termux  |   neoai.py (CLI)    |
        |           +----------+----------+
        v                      |
  +---------------+            v
  |  Engenho      |  +--------------------+      +------------------+
  |  (engine.py)  |->| Equipe de agentes   |<---->| Pesquisa web     |
  |  intencao     |  | (agents.py)          |      | (Wikipedia/DDG)  |
  |  resposta     |  +--------------------+      +------------------+
  +-------+-------+            v
          |          +--------------------+
          |          | Planejador passo-a |
          |          | passo (planner.py) |
          |          +---------+----------+
          v                    v
  +-----------------+   +------------------+
  |  Executor       |   | Memoria          |
  |  (comandos/apps)|   | (vault Obsidian) |
  +-----------------+   | ou Downloads     |
                        +------------------+
                          +-----------------+
                          | Seguranca       |
                          | (cofre cripto)  |
                          +-----------------+
```

## 2. Componentes tecnicos

### 2.1 `core/platform.py` - deteccao de plataforma
- Detecta Linux, Windows, Termux (Android) e mapeia home/Downloads.
- Detecta iPhone/iOS (sinais de sistema: MobileGestalt, SystemVersion.plist).

### 2.2 `core/iphone_guard.py` - recusa a dispositivos Apple
- A IA recusa-se a operar em iPhone/iOS (requisito do usuario).

### 2.3 `core/engine.py` - o "cerebro" (raciocinio e decisoes)
- Tokenizacao com acentos, stemming de portugues, similaridade de Levenshtein.
- Deteccao de intencao por gatilhos/regras + pesos.
- Respostas compostas por templates, memoria e conhecimento.
- Matematicas avaliadas com AST (seguro, sem eval()).
- Execucao de funcoes via planejador + executor + confirmacao humana.

### 2.4 `core/agents.py` - equipe de 3 agentes
- **Conhecimento**: definicoes/fatos gerais embutidos.
- **Pratica**: receitas de comandos/acoes ("como", "instalar", "listar").
- **Memoria**: recupera o que ja foi guardado/experienciado.
- Fluxo: consulta cada agente; quem nao souber pede ajuda aos que sabem;
  se ninguem souber, busca web e retorna.

### 2.5 `core/planner.py` - planejamento passo a passo
- Quebra tarefa em passos (listar, abrir, executar script, instalar, sistema).
- Memoriza planos bem-sucedidos (chave por tag da frase) e reutiliza.
- Sempre pede confirmacao antes de cada passo.

### 2.6 `core/executor.py` - execucao cross-platform
- Shell unico por SO (cmd no Windows, /bin/sh no Linux/Termux).
- Classifica comandos como seguro/perigoso.
- Abre apps Android via `am start -n <pkg>/<activity>` (sem root).

### 2.7 `core/memory.py` - memoria persistente
- Motor Obsidian: detecta vault (pasta com `.obsidian`); senao usa Downloads.
- Escreve `neobrain.json`, notas `.md`, indice, e migra dados do Downloads
  quando Obsidian e detectado.
- Estruturado por: memorias {chave: dados}, fatos [], conversas [], planos {}.

### 2.8 `core/security.py` - criptografia e auditoria
- Derivacao de chave por PBKDF2 caseiro (hash em iteracoes) + salt.
- Cifra simetrica: XOR + rotacao, com MAC de autenticacao (detecta senha errada).
- `Cofre`: credenciais guardadas cifradas (nunca texto puro).
- Auditoria: varre o codigo em busca de segredos em texto puro.

## 3. O que vem a seguir (plano de evolucao)

- [ ] **Memoria Obsidian conectada**: notas com YAML frontmatter, tags, links
      `[[...]]` bidirecionais e indice de backlinks (grafo de conhecimento).
- [ ] **Busca semantica local**: TF-IDF + indice invertido dos .md do vault.
- [ ] **Raciocinio multi-passada**: pensar -> planejar -> verificar antes de agir.
- [ ] **Controle mais fino**: perfil de permissao por categoria (leitura,
      escrita, rede, apps) com revogacao.
- [ ] **Auto-melhoria v2**: auditoria + correcao automatica de armadilhas
      comuns (segredos em puro, comandos perigosos em planos).

## 4. Seguranca e permissoes (design)

1. **Confirma humana**: toda execucao pede `[s/N]` por passo. Pode-se trocar o
   callback `aprovador` por aprovacao programatica (ex: interface web).
2. **Categorias**: comandos de leitura (seguros) vs escrita/efeito (sempre
   confirmar). Lista `PERIGOSO_SUBSTRINGS` em executor.py.
3. **Cofre**: credenciais somente com senha mestra, cifradas e com MAC.
4. **Recusa de uso de ataque**: a NeoIA nao cria nem facilita ferramentas de
   ataque a terceiros (phishing, roubo de credenciais de bancos, invasao).
   Isso protege o proprio usuario (risco legal) e e inegociavel.

## 5. Sobre "controle total" e "conectar contas"

- **Controle local**: funcional (abrir apps, arquivos, terminal, listar,
  instalar). Mouse/teclado/tela (OCR) exigem libs e permissoes especificas por
  SO, e ainda NAO estao implementados por seguranca e escopo.
- **Rede (SSH/RDP/VNC)**: nao implementado. Exigiria porta aberta + auth forte;
  alto risco. Planejado apenas se necessario e com chaves, jamais senha.
- **Contas**: cofre guarda credenciais cifradas. Interacao autonoma com
  Gmail/Discord/bancos exige integracao por API/OAuth por site, sob permissao.
  Bancos: NAO suportado (vetor de golpe; recomendacao forte de nunca colocar
  credenciais bancarias em qualquer IA).

## 6. Como contribuir/estender
- Mude intencoes e gatilhos em `core/engine.py`
- Adicione receitas em `core/agents.py` (AgentePratica)
- Adicione apps em `core/executor.py` (APPS_ANDROID)
- Estenda notas/grafo em `core/memory.py`
- Rode: `python3 neoai.py` (teste manual) e `python3 -m compileall core`