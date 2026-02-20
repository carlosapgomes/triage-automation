# Notas de Seguranca

Idioma: **Portugues (BR)** | [English](en/security.md)

## Tratamento de segredos

- Nunca commitar segredos reais, IDs de sala de producao, ou valores reais de homeserver.
- Manter segredos locais de runtime somente em `.env`.
- Manter `.env.example` apenas com placeholders sanitizados.
- Para bootstrap do primeiro admin, prefira `BOOTSTRAP_ADMIN_PASSWORD_FILE` em vez de senha em texto no ambiente.

## Modelo de auth (atual)

- Auth de callback webhook: validacao de assinatura HMAC.
- Fundacao de login: emissao de token opaco com hash persistido.
- Armazenamento de senha: apenas hash bcrypt (sem plaintext).
- Modelo de papeis: `admin` e `reader` explicitos.

## Checklist de seguranca para repositorio publico

Antes de criar ou publicar um remoto:

1. Garantir que `.env.example` contenha apenas placeholders.
2. Rodar scans de segredo:
   - `gitleaks git .`
3. Confirmar que nenhum arquivo local de segredo esta versionado:
   - `git ls-files | rg '^\.env$|^\.env\.'`
4. Revisar historico de commits para vazamentos acidentais, se valores sensiveis ja foram commitados.

## Se um vazamento de segredo for detectado

1. Rotacionar credenciais afetadas imediatamente.
2. Reescrever historico local do git para remover valores vazados.
3. Rodar garbage-collect de objetos inalcancaveis.
4. Reescanear historico antes de qualquer push.

## Reporte de incidentes de seguranca

Ate existir uma policy dedicada de seguranca, reporte problemas de forma privada para mantenedores do repositorio e evite abrir issues publicas com detalhes de exploracao.
