# Tasks

## 1. Baseline Bilingue (Slice 1)

- [x] 1.1 Adicionar seletor de idioma no topo de `README.md` e criar `README.en.md` espelhado.
- [x] 1.2 Traduzir o conteudo de entrada para manter portugues como idioma padrao e ingles como espelho equivalente.
- [x] 1.3 Adicionar teste unitario para validar links de idioma e existencia dos dois READMEs.
- [x] 1.4 Executar verificacoes do slice (`uv run pytest` alvo, `uv run ruff check`, `markdownlint-cli2`).

## 2. Espelhamento de `docs/` (Slice 2)

- [x] 2.1 Traduzir para pt-BR os documentos em `docs/` (arquitetura, setup, seguranca, smoke e runbook).
- [x] 2.2 Criar espelho em ingles em `docs/en/` com os mesmos nomes e escopo.
- [x] 2.3 Inserir seletor PT/EN no topo de todos os arquivos de `docs/` e `docs/en/`.
- [x] 2.4 Atualizar links internos para manter navegacao consistente entre idiomas.
- [x] 2.5 Executar verificacoes do slice (`markdownlint-cli2` e testes relevantes).

## 3. Hardening de Sincronizacao (Slice 3)

- [x] 3.1 Incluir no `AGENTS.md` a regra obrigatoria de sincronizacao de traducao para `README` e `docs/`.
- [x] 3.2 Adicionar/ajustar teste automatizado para detectar drift basico de espelhamento PT/EN em `docs/`.
- [x] 3.3 Atualizar checklist operacional de contribuicao para documentacao bilingue.
- [x] 3.4 Executar verificacoes finais do change e registrar limitacoes, se houver.
