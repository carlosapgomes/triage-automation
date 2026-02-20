# Proposal

## Why

A audiencia principal do ATS esta no Brasil e precisa de documentacao em portugues
como padrao para reduzir friccao operacional na implantacao e manutencao.
Ao mesmo tempo, o projeto precisa manter documentacao em ingles para colaboracao
externa e padronizacao internacional.

## What Changes

- Tornar `README.md` o ponto de entrada padrao em portugues (pt-BR).
- Criar `README.en.md` como versao espelhada em ingles com seletor de idioma no topo.
- Tornar `docs/` a arvore padrao em portugues e criar espelho em `docs/en/`.
- Incluir seletor de idioma no topo de todos os arquivos de documentacao
  (`README` e arquivos em `docs/` / `docs/en/`).
- Estabelecer regra operacional para sincronizacao obrigatoria PT/EN no `AGENTS.md`.
- Adicionar verificacoes automatizadas simples para prevenir drift de idioma.

## Capabilities

### New Capabilities

- `bilingual-documentation-governance`: padroniza estrutura, navegacao e processo
  de sincronizacao da documentacao bilingue com pt-BR como idioma primario.

### Modified Capabilities

- `manual-e2e-readiness`: atualizar orientacoes e links da documentacao operacional
  para estrutura bilingue sem perder cobertura de validacao manual.

## Impact

- Arquivos Markdown de entrada e operacao (`README` e `docs/*`).
- Fluxo de contribuicao para qualquer alteracao de documentacao.
- Checklists de manutencao e governanca de sincronizacao PT/EN.
