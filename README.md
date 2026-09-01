# NeoAI

Sistema inteligente criado **100% do zero** com processamento de linguagem natural (NLP)
próprio, baseado em regras e algoritmos próprios.
**Não usa nenhum modelo de linguagem base** — nada de Ollama, OpenCode, Kimi, QWEN ou GGUF.

Roda em **Linux, Windows e Termux (Android, sem root)**.
**Recusa-se a rodar em iPhone/iOS** (Apple).

## Funcionalidades

- **NLP próprio do zero**: tokenização com acentos, stemming em português, similaridade
  de Levenshtein, detecção de intenção por regras.
- **Memória persistente e conectada**:
  - Se houver um **vault do Obsidian** (pasta com `.obsidian`) no dispositivo, usa **somente ele**.
  - Caso contrário, usa a **pasta Downloads**.
  - Quando o Obsidian aparece depois, **migra** os dados do Downloads para dentro dele.
- **Executa funções reais** no dispositivo: lista pastas, abre/executa arquivos,
  roda scripts Python/Shell, instala pacotes, mostra informações do sistema.
- **Abre apps do Android e sites**: via Termux (`am start`, `termux-open-url`) e
  aprende a rota de cada um para reusar depois.
- **Conhece o aparelho de ponta a ponta**: mapeia apps, pastas e rotas do dia a
  dia e guarda tudo na memória (`conhece meu celular`, `quais rotas`).
- **Controle remoto notebook <-> celular**: um aparelho expõe uma porta (servidor
  HTTP com token), o outro registra e manda comandos (`manda pro cel: ...`,
  `manda pro notebook: ...`). Painel web mostra o que está acontecendo e tem o
  botão **assumir controle** para você intervir manualmente (ex.: CAPTCHA).
- **Pensa antes de executar**: planeja passo a passo e pede confirmação antes de
  cada comando (seguro).
- **Aprende os caminhos**: memoriza o passo-a-passo de execuções bem-sucedidas e
  reutiliza depois (na memória permanente).
- **Time de 3 agentes** que trocam dúvidas entre si antes de responder.
- **Pesquisa na internet** (Wikipedia/DuckDuckGo) quando ninguém sabe.
- **Criptografia e cofre**: credenciais guardadas cifradas (senha mestra), com
  auditoria do próprio código (`auto-melhoria`).

## Instalação

### Termux (Android)
```bash
pkg update && pkg install -y python
termux-setup-storage    # permitir acesso ao storage (para Obsidian/Downloads)
```

### Linux / Windows
Requer apenas `python3` (biblioteca padrão, sem dependências externas).

## Como rodar
```bash
git clone <URL-do-repositorio>.git
cd NeoAI
python3 neoai.py
```

## Comandos que a NeoAI entende

| Você digita | O que ela faz |
|---|---|
| `oi` / `ola` | Saudação |
| `lembre-se que ...` | Salva na memória |
| `o que você lembra?` | Lista memórias |
| `esqueça ...` | Apaga memória |
| `quanto é 5 + 3?` | Calcula (raiz, porcentagem, precedência) |
| `lista as pastas` | Lista arquivos |
| `roda o script X.py` | Executa o script |
| `abre o arquivo X` | Mostra o conteúdo |
| `abre o whatsapp` / `roda o telegram` | Abre app Android (Termux) |
| `abre o site gmail.com` | Abre o site no navegador e aprende a rota |
| `instala Y` | Instala o pacote |
| `informações do sistema` | Detalhes do hardware |
| `conhece meu celular` / `quais rotas` | Mapeia o dispositivo e mostra o que sabe |
| `servir na porta 8890` | Liga o controle remoto (notebook<->celular) |
| `registra remoto cel IP PORTA TOKEN` | Cadastro do outro aparelho |
| `manda pro cel: <comando>` | Executa no outro aparelho via rede |
| `assumir controle` / `libera controle` | Mestre intervém / libera |
| `defina senha mestra X` | Define a senha do cofre criptografado |
| `guarde credencial X <valor>` | Criptografa e guarda (nunca em texto puro) |
| `auditar codigo` / `auto-melhoria` | Checa vulnerabilidades no próprio código |
| `quem é você?` | Sobre a NeoAI |
| `ajuda` | Lista os comandos |
| `tchau` | Despedida |

Toda execução pede sua confirmação antes de rodar cada passo.

## Segurança
- Bloqueia/recusa rodar em **iPhone/iOS**.
- Pedidos de execução são **confirmados pelo usuário** antes de cada comando
  (ou o comando remoto roda apenas o que é seguro, por decisão do `modo_remoto`).
- Controle remoto exige **token** e roda, por padrão, só na sua rede local.
- Com o botão **assumir controle**, você interrompe qualquer ação automática.
- Credenciais ficam **criptografadas** no cofre (senha mestra), nunca em texto puro.

## Controle remoto (notebook <-> celular) em passos
1. No aparelho que vai **executar** (ex.: no celular):
   ```
   python3 neoai.py --servir --porta 8890
   ```
   Anote o IP exibido (ex.: `192.168.0.10`) e defina um token (senha mestra).
2. No outro aparelho (ex.: no notebook):
   ```
   python3 neoai.py
   > registra remoto cel 192.168.0.10 8890 SEU_TOKEN
   > manda pro cel: lista as pastas
   >
   ```
3. Para ver e intervir: abra no navegador `http://IP:8890/painel` com o token
   e use o botão **assumir controle** (útil pra pular CAPTCHA etc.).
