# Notas de Seguranca

Idioma: **Português (BR)** | [English](en/security.md)

## Tratamento de segredos

- Nunca commitar segredos reais, IDs de sala de produção, ou valores reais de homeserver.
- Manter segredos locais de runtime somente em `.env`.
- Manter `.env.example` apenas com placeholders sanitizados.
- Para bootstrap do primeiro admin, prefira `BOOTSTRAP_ADMIN_PASSWORD_FILE` em vez de senha em texto no ambiente.

## Modelo de auth (atual)

- Auth de callback webhook: validação de assinatura HMAC.
- Fundação de login: emissão de token opaco com hash persistido.
- Armazenamento de senha: apenas hash bcrypt (sem plaintext).
- Modelo de papéis: `admin` e `reader` explícitos.

## Checklist de segurança para repositório público

Antes de criar ou publicar um remoto:

1. Garantir que `.env.example` contenha apenas placeholders.
2. Rodar scans de segredo:
   - `gitleaks git .`
3. Confirmar que nenhum arquivo local de segredo está versionado:
   - `git ls-files | rg '^\.env$|^\.env\.'`
4. Revisar histórico de commits para vazamentos acidentais, se valores sensíveis já foram commitados.

## Se um vazamento de segredo for detectado

1. Rotacionar credenciais afetadas imediatamente.
2. Reescrever histórico local do git para remover valores vazados.
3. Rodar garbage-collect de objetos inalcançáveis.
4. Reescanear histórico antes de qualquer push.

## Reporte de incidentes de segurança

Até existir uma policy dedicada de segurança, reporte problemas de forma privada para mantenedores do repositório e evite abrir issues públicas com detalhes de exploração.
