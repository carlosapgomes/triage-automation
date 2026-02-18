# Tasks

## 1. Estrutura base da automacao

- [ ] 1.1 Criar estrutura `ansible/` com `inventory/`, `group_vars/`, `host_vars/`, `playbooks/`, `roles/` e `templates/`.
- [ ] 1.2 Definir variaveis obrigatorias e defaults para deploy remoto (incluindo usuario de servico, tags de imagem e parametros de runtime).
- [ ] 1.3 Adicionar validacoes iniciais no bootstrap para falhar cedo quando variaveis obrigatorias estiverem ausentes.

## 2. Bootstrap de host e Docker rootless

- [ ] 2.1 Implementar role `base_host` para preparar dependencias de sistema exigidas.
- [ ] 2.2 Implementar role para criacao/gestao do usuario de servico dedicado.
- [ ] 2.3 Implementar role `rootless_docker` com configuracao de runtime rootless no contexto do usuario de servico.
- [ ] 2.4 Adicionar tarefas de verificacao funcional do Docker rootless antes do deploy da aplicacao.

## 3. Deploy de servicos com idempotencia

- [ ] 3.1 Implementar role `app_runtime` para gerar arquivos de configuracao via templates (ambiente/segredos por variavel).
- [ ] 3.2 Implementar role `deploy` para subir `bot-api`, `bot-matrix` e `worker` em modo rootless no usuario dedicado.
- [ ] 3.3 Garantir idempotencia do deploy (reexecucao com mesmos inputs sem efeitos colaterais destrutivos).
- [ ] 3.4 Garantir compatibilidade dos comandos de runtime suportados com o caminho oficial via Ansible.

## 4. Upgrade versionado e rollback

- [ ] 4.1 Implementar deploy por versao/tag explicita de imagem.
- [ ] 4.2 Implementar playbook de upgrade com validacao pos-deploy.
- [ ] 4.3 Implementar playbook de rollback para retornar a versao estavel anterior.

## 5. Validacoes pos-deploy

- [ ] 5.1 Implementar role `post_deploy_checks` com checks deterministas de processo, logs iniciais e saude dos servicos.
- [ ] 5.2 Definir criterios objetivos de sucesso/falha para aprovar deploy em producao.
- [ ] 5.3 Adicionar verificacao de execucao dos servicos sob usuario nao-root.

## 6. Runbook operacional para TI

- [ ] 6.1 Documentar instalacao inicial com pre-requisitos, inventario minimo e comandos oficiais.
- [ ] 6.2 Documentar fluxo de upgrade e rollback alinhado aos playbooks.
- [ ] 6.3 Documentar troubleshooting de primeiro nivel e limites de escalonamento para desenvolvimento.

## 7. Verificacao do slice e fechamento do change

- [ ] 7.1 Executar `ansible-playbook -i <inventory> <playbook> --syntax-check` para os playbooks principais.
- [ ] 7.2 Validar lint dos artefatos markdown alterados com `markdownlint-cli2`.
- [ ] 7.3 Atualizar checklist de progresso OpenSpec e registrar observacoes operacionais relevantes.
