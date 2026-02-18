# Design

## Context

O projeto precisa de uma forma operacional padronizada para instalacao e atualizacao em servidor remoto, sem depender de execucao manual ad-hoc. O time de TI do hospital precisa de automacao repetivel, com baixo risco de drift entre ambientes e com fluxo de suporte previsivel.

Hoje nao existe caminho oficial de provisionamento remoto para rodar `bot-api`, `bot-matrix` e `worker` com usuario de servico dedicado e Docker rootless. A mudanca tambem precisa preservar a arquitetura atual do sistema (sem alterar regras de negocio), focando apenas na camada de operacao/deploy.

Stakeholders principais:

- TI hospitalar (instalacao, upgrade, suporte inicial)
- equipe de desenvolvimento (padrao unico de deploy e troubleshooting)
- operacao do sistema em producao (estabilidade e rastreabilidade)

## Goals / Non-Goals

**Goals:**

- Definir automacao Ansible idempotente para bootstrap, deploy, upgrade e verificacao pos-deploy.
- Padronizar runtime com usuario de servico dedicado e Docker rootless no host alvo.
- Estruturar inventario, variaveis obrigatorias, templates de configuracao e passos de rollback.
- Fornecer documentacao operacional objetiva para TI executar o processo sem conhecimento interno do codigo.

**Non-Goals:**

- Alterar o workflow clinico, estados de caso ou prompts de LLM.
- Redesenhar arquitetura da aplicacao ou mudar contratos de API do bot.
- Cobrir orquestracao multi-host complexa (cluster) nesta primeira fase.

## Decisions

### Decision 1: Estruturar automacao em roles Ansible separadas por responsabilidade

- Choice: separar em roles para `base_host`, `rootless_docker`, `app_runtime`, `deploy` e `post_deploy_checks`.
- Rationale: melhora reuso, idempotencia e manutencao, alem de facilitar execucao parcial para troubleshooting.
- Alternative considered: playbook unico monolitico.
  - Rejected por dificultar testes por etapa e aumentar risco de regressao operacional.

### Decision 2: Runtime com usuario de servico dedicado e Docker rootless

- Choice: criar/gerenciar usuario de servico exclusivo, com runtime docker em modo rootless e unidades de usuario (systemd --user) para os servicos.
- Rationale: reduz superficie de risco ao evitar execucao da aplicacao como root e segue requisito operacional do projeto.
- Alternative considered: Docker rootful com servicos de sistema tradicionais.
  - Rejected por nao atender a diretriz de seguranca/operacao definida para o hospital.

### Decision 3: Configuracao via variaveis declarativas e templates versionados

- Choice: centralizar variaveis obrigatorias em `group_vars`/`host_vars` e gerar arquivos de ambiente a partir de templates.
- Rationale: cria contrato claro de configuracao, facilita auditoria de mudancas e reduz erro manual.
- Alternative considered: editar `.env` manualmente no servidor.
  - Rejected por baixa rastreabilidade e alta propensao a configuracao divergente.

### Decision 4: Deploy por imagem/tag explicita com validacao pos-deploy

- Choice: playbook de deploy recebe versao/tag explicita, atualiza servicos e executa checks deterministas (processos ativos, health endpoints, logs iniciais).
- Rationale: torna rollout/redeploy previsivel e facilita rollback para versao anterior conhecida.
- Alternative considered: deploy sempre em `latest`.
  - Rejected por reduzir reprodutibilidade e dificultar investigacao de incidentes.

### Decision 5: Runbook operacional como parte obrigatoria da entrega

- Choice: manter guia de operacao com pre-requisitos, inventario minimo, comandos de execucao, erros comuns e passos de rollback.
- Rationale: reduz dependencia de suporte direto de desenvolvimento e acelera onboarding da TI.
- Alternative considered: deixar apenas comentarios nos playbooks.
  - Rejected por nao ser suficiente para operacao de primeiro nivel.

## Risks / Trade-offs

- [Diferencas de distro/systemd no host alvo] -> Mitigation: validar pre-requisitos explicitamente no bootstrap e falhar cedo com mensagem clara.
- [Complexidade inicial maior que deploy manual] -> Mitigation: roles pequenas, comandos documentados e execucao por etapas.
- [Falhas por variaveis incompletas] -> Mitigation: checklist de variaveis obrigatorias e validacoes assertivas no inicio do playbook.
- [Problemas de permissao em rootless Docker] -> Mitigation: tarefas dedicadas para ambiente de usuario, PATH/daemon e teste de execucao antes do deploy da aplicacao.
- [Rollback incompleto em upgrade] -> Mitigation: estrategia de versao/tag fixa e playbook de rollback para restaurar ultima versao estavel.

## Migration Plan

1. Criar estrutura de automacao (`ansible/`) com inventario exemplo, roles, templates e variaveis default.
2. Implementar bootstrap do host para requisitos de sistema e criacao do usuario de servico.
3. Implementar role de Docker rootless e validacao funcional basica.
4. Implementar deploy dos servicos `bot-api`, `bot-matrix` e `worker` com configuracao por templates.
5. Implementar verificacoes pos-deploy e playbook de rollback por tag anterior.
6. Documentar fluxo operacional completo para TI (instalacao inicial, upgrade e suporte).
7. Executar teste de instalacao limpa e teste de upgrade em ambiente de homologacao.

Rollback strategy:

- Em caso de falha no deploy, executar playbook de rollback para a tag previamente estavel.
- Se o problema for de provisionamento, interromper rollout, manter versao atual em execucao e corrigir role especifica antes de nova tentativa.

## Open Questions

- Qual distro Linux (e versao) sera oficialmente suportada na primeira entrega de automacao?
- O registry de imagens sera privado ou publico, e qual mecanismo de autenticacao padrao sera exigido?
- Quais checks de saude serao obrigatorios para considerar o deploy aprovado em producao?
