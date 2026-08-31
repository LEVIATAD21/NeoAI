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
- **Pensa antes de executar**: planeja passo a passo e pede confirmação antes de
  cada comando (seguro).
- **Aprende os caminhos**: memoriza o passo-a-passo de execuções bem-sucedidas e
  reutiliza depois (na memória permanente).
- **Time de 3 agentes** que trocam dúvidas entre si antes de responder.
- **Pesquisa na internet** (DuckDuckGo) quando ninguém sabe, e guarda o que aprendeu
  na memória.

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
| `quanto é 5 + 3?` | Calcula |
| `lista as pastas` | Lista arquivos |
| `roda o script X.py` | Executa o script |
| `abre o arquivo X` | Mostra o conteúdo |
| `instala Y` | Instala o pacote |
| `informações do sistema` | Detalhes do hardware |
| `quem é você?` | Sobre a NeoAI |
| `tchau` | Despedida |
| `ajuda` | Lista os comandos |

Toda execução pede sua confirmação antes de rodar cada passo.

## Segurança
- Bloqueia/recusa rodar em **iPhone/iOS**.
- Pedidos de execução são **confirmados pelo usuário** antes de cada comando.
