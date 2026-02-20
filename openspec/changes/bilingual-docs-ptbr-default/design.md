# Design

## Context

O repositorio atualmente publica `README.md` e arquivos em `docs/` sem uma
estrategia formal de idiomas. Para o contexto de implantacao hospitalar no
Brasil, o idioma principal precisa ser portugues, mantendo ingles como idioma
secundario para colaboracao tecnica.

## Goals / Non-Goals

**Goals:**

- Definir portugues como idioma padrao de leitura no GitHub.
- Disponibilizar espelho em ingles para todo conteudo essencial de operacao.
- Garantir navegacao explicita entre PT/EN no topo dos documentos.
- Formalizar regra de sincronizacao de traducoes no `AGENTS.md`.
- Introduzir verificacao automatizada minima para detectar drift basico.

**Non-Goals:**

- Traduzir historico arquivado completo de `openspec/changes/archive`.
- Alterar comportamento funcional do runtime da aplicacao.
- Introduzir pipeline complexo de i18n para documentacao.

## Decisions

### Decision 1: `README.md` sera o canonical em portugues

- Choice: manter `README.md` em pt-BR e criar `README.en.md` espelhado.
- Rationale: GitHub sempre renderiza `README.md` como landing page padrao.
- Alternative considered: manter ingles em `README.md` e criar `README.pt-BR.md`.
  - Rejected por contrariar a audiencia principal e aumentar friccao.

### Decision 2: `docs/` sera portugues e `docs/en/` sera espelho em ingles

- Choice: traduzir os arquivos existentes de `docs/` para pt-BR e adicionar
  equivalentes em `docs/en/` com mesmos nomes.
- Rationale: preserva caminhos atuais de referencia interna com idioma primario.
- Alternative considered: criar `docs/pt-BR/` e mover tudo para subpastas por idioma.
  - Rejected por maior churn e risco desnecessario de links quebrados.

### Decision 3: Seletor de idioma no topo de cada documento

- Choice: inserir linha de navegacao PT/EN no inicio de `README` e cada doc.
- Rationale: descoberta imediata da traducao e menor ambiguidade de idioma.
- Alternative considered: pagina indice central de idiomas sem links em cada doc.
  - Rejected por pior ergonomia durante leitura direta de arquivos.

### Decision 4: Governanca de sincronizacao no `AGENTS.md`

- Choice: adicionar regra mandatória: alterou doc PT ou EN, atualiza par no
  mesmo slice/PR, com excecao explicitamente registrada quando inevitavel.
- Rationale: evita drift silencioso de traducoes.
- Alternative considered: apenas orientacao informal no README.
  - Rejected por baixa enforceability operacional.

### Decision 5: Verificacao automatizada minima para README e docs espelhados

- Choice: adicionar teste unitario de baixo custo para validar existencia de
  arquivos espelhados e links de idioma no topo.
- Rationale: detecta regressao rapida sem dependencia de ferramentas externas.
- Alternative considered: sem automacao, apenas revisao manual.
  - Rejected por alto risco de inconsistencias recorrentes.

## Risks / Trade-offs

- [Drift de conteudo entre PT e EN] -> Mitigation: regra no `AGENTS.md`,
  checklist e teste automatizado minimo.
- [Aumento de custo de manutencao editorial] -> Mitigation: estrutura simples
  (somente dois idiomas) e espelhamento de paths.
- [Termos tecnicos inconsistentes entre idiomas] -> Mitigation: manter glossario
  curto em `docs/` e revisar em cada PR de documentacao.

## Migration Plan

1. Criar baseline bilingue no `README` (PT default + EN mirror).
2. Traduzir `docs/` para pt-BR e criar `docs/en/` com espelho em ingles.
3. Adicionar regra de sincronizacao no `AGENTS.md`.
4. Adicionar e executar verificacao automatizada e `markdownlint`.

Rollback strategy:

- Reverter commits de documentacao por slice sem impacto no runtime.
- Preservar links existentes sempre que possivel para minimizar quebra externa.

## Open Questions

- Definir se o limite minimo de qualidade de traducao sera somente semantico ou
  com revisao terminologica formal por dominio clinico.
