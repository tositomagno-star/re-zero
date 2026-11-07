# Etapa H.10 — Implementação do bootstrap administrativo seguro

## Status

O fluxo de bootstrap foi implementado no CLI, fora da API pública, e validado com SQLite isolado e mocks. A migration `d129a4c7e601` está preparada, encadeada após `b74c2d91e5a0`, mas **não foi aplicada**. Nenhum banco PostgreSQL foi acessado; esta entrega não configura uma implantação nem cria uma conta administrativa real.

O repositório não contém Docker Compose nem uma plataforma de hospedagem configurada. A decisão operacional proposta é um perfil Linux Docker Compose, executado pelo responsável autorizado pelo deploy, com diretório temporário dedicado em `/run/admin-bootstrap`. Isso é uma recomendação futura, não uma infraestrutura existente ou implantada.

## Decisões de operação

| Tema | Decisão |
|---|---|
| Quem executa | Responsável autorizado pelo deploy, autenticado pelos controles do host/plataforma. O CLI registra o UID efetivo do processo; os logs de auditoria da plataforma são a evidência autoritativa da identidade humana. |
| Ambiente | Linux, em contêiner/serviço de backend de produção, com confirmação explícita do alvo. O CLI exige `APP_ENVIRONMENT=production`, `ADMIN_OPERATION_TARGET=production`, configuração explícita do banco esperado e `ADMIN_BOOTSTRAP_ENABLED=true`. |
| Entrega do segredo | Concessão aleatória de uso único, válida por 15 minutos, gravada somente em arquivo dentro de `/run/admin-bootstrap`, em tmpfs dedicado, diretório modo `0700` e arquivo modo `0600`. O CLI nunca imprime nem aceita o segredo em argumento. Não há integração com provedor de segredos nesta etapa. |
| Estado persistente | Somente SHA-256 da concessão, expiração/consumo, IDs e atores da operação; nunca o segredo em claro ou a senha. A criação do usuário e o consumo são uma transação. |
| PostgreSQL | A identidade configurada deve corresponder exatamente ao host e database esperados, e a conexão verifica database, schema e `search_path`. URLs de desenvolvimento/teste e hosts locais são recusados. O CLI lê `DATABASE_URL` do ambiente do processo; não carrega `.env`. |

O provisionamento do diretório tmpfs, sua propriedade/permissões, as variáveis esperadas e o acesso de deploy precisam ser revisados e configurados pelo operador antes de qualquer implantação. Valores abaixo são nomes de placeholders e não são credenciais reais.

## Estado confirmado no código

- `User.is_admin` permanece o atributo de autorização. Registro público e login não foram alterados; não há endpoint HTTP para emitir concessão, criar primeiro admin ou promover usuários.
- `prepare-admin-bootstrap` cria concessão somente quando a tabela de estado existe, ainda não foi concluída e não há administrador. A operação bloqueia reemissão enquanto há concessão válida.
- `bootstrap-admin` cria uma **nova** conta administrativa. Se já houver admin, se o username estiver ocupado, se a concessão for ausente/inválida/expirada/consumida ou se o bootstrap já tiver sido concluído, a operação recusa. Nenhuma conta de jogador é promovida.
- A senha é solicitada por prompt sem eco e armazenada usando o hash scrypt existente. Username e senha mantêm os limites do login administrativo.
- A concessão tem 256 bits aleatórios, é comparada por hash em tempo constante e não aparece nos eventos/logs. O arquivo só é aceito diretamente em `/run/admin-bootstrap`, sem symlink, com proprietário do processo e permissões seguras.
- Um `UPDATE` condicional consome a concessão dentro da transação que grava usuário, estado concluído e evento de auditoria. Rollback reverte o consumo e a conta. Locks de linha e atualização condicional previnem sucesso concorrente; o teste SQLite verifica que só uma execução vence.
- `admin_bootstrap_state` é uma linha singleton. `admin_bootstrap_events` registra emissão e criação sem dados de autenticação. O downgrade da migration recusa remover as tabelas se existir qualquer evento, preservando o bloqueio contra replay.
- `create-admin` continua sendo somente para targets locais de teste e recusa `APP_ENVIRONMENT=production`.

## Pré-condições e sequência operacional futura

Não execute estes exemplos nesta etapa. Primeiro, aprovar a migration e o procedimento de implantação; configurar explicitamente em ambiente de produção `DATABASE_URL`, `APP_ENVIRONMENT=production`, `ADMIN_OPERATION_TARGET=production`, `ADMIN_EXPECTED_DATABASE`, `ADMIN_EXPECTED_DATABASE_HOST` e `ADMIN_EXPECTED_DATABASE_SCHEMA`. Para migration, habilitar também `ADMIN_MIGRATIONS_ENABLED=true`; para bootstrap, habilitar `ADMIN_BOOTSTRAP_ENABLED=true`. O processo deve receber apenas as flags necessárias para a operação corrente.

1. Fazer backup e validar o plano de recuperação; confirmar ambiente, host, database, schema, permissões e janela de mudança.
2. Aplicar a migration apenas em procedimento separado e aprovado. A configuração requer confirmação explícita de target de produção:

   ```text
   docker compose exec -e ADMIN_OPERATION_TARGET=production -e ADMIN_MIGRATIONS_ENABLED=true backend python -m alembic upgrade head
   ```

3. Garantir que o serviço Linux tenha `/run/admin-bootstrap` em tmpfs, pertencente ao UID operador e com modo `0700`. Emitir a concessão:

   ```text
   docker compose exec -e ADMIN_OPERATION_TARGET=production -e ADMIN_BOOTSTRAP_ENABLED=true backend python -m app.cli prepare-admin-bootstrap --confirm-environment production --secret-file /run/admin-bootstrap/first-admin.token
   ```

4. No mesmo serviço, antes dos 15 minutos, ler o arquivo apenas pelo CLI e fornecer um username novo e senha forte nos prompts ocultos:

   ```text
   docker compose exec -e ADMIN_OPERATION_TARGET=production -e ADMIN_BOOTSTRAP_ENABLED=true backend python -m app.cli bootstrap-admin --confirm-environment production --secret-file /run/admin-bootstrap/first-admin.token
   ```

5. Confirmar o resultado pelo ID de operação/usuário exibido e pelo evento de auditoria da plataforma/aplicação, sem registrar senha ou segredo. Depois validar login administrativo por procedimento autorizado e remover/desmontar o tmpfs ao encerrar a operação.

Os comandos são ilustrativos para o perfil Linux Compose recomendado: não há serviço Compose `backend` neste repositório hoje. Não devem ser executados até que os valores e a infraestrutura sejam revistos. A migration não é aplicada automaticamente pelo CLI de bootstrap.

## Falhas, concorrência e recuperação

- Falha de validação antes da transação não grava conta nem consome a concessão.
- Falha na escrita/commit da emissão tenta remover o arquivo que esta operação acabou de criar; a transação não persiste o hash se o commit falhar.
- Falha na criação do admin reverte a transação; a concessão pode ser repetida até expirar. Não emitir outra enquanto a autorização atual ainda for válida.
- Após sucesso, a concessão fica consumida permanentemente e o arquivo é removido. Remover o admin depois **não** permite rebootstrap. O downgrade da migration também fica bloqueado pela trilha de emissão.
- Em concorrência, somente uma transação pode consumir o hash vigente. Uma segunda chamada deve falhar sem criar outro admin.
- Se o processo cair entre gravação do arquivo e confirmação do banco, o arquivo poderá permanecer no tmpfs sem concessão válida; o operador deve apagá-lo após verificar o estado pelo canal operacional aprovado. Se a limpeza automática após sucesso falhar, o CLI avisa para remoção manual; o segredo já está consumido.
- Recuperação de acesso após o bootstrap não está implementada aqui. Exige procedimento break-glass separado, aprovação reforçada, identidade auditável, rotação de senha/hash e invalidação das sessões afetadas. Não rearmar nem apagar o marcador de bootstrap para recuperar acesso.

## Testes e evidências

`backend/tests/test_admin_bootstrap.py` cobre criação e login administrativo sintético, recusa se já houver admin, token inválido/expirado/reutilizado, rollback, conflito com usuário comum sem promoção, concorrência, validação do target de produção, recusa do CLI antigo em produção e upgrade/downgrade da migration em SQLite. Os testes usam somente SQLite temporário/in-memory e credenciais sintéticas locais; não se conectam a PostgreSQL.

| Verificação final | Resultado |
|---|---|
| `pytest -m "not postgres" -q` | **198 passed, 1 skipped, 12 deselected**. O skip é o teste de permissões POSIX do arquivo, incompatível com o Windows desta sessão; os 12 testes marcados para PostgreSQL foram excluídos. A execução final ocorreu em diretório temporário vazio com `APP_ENVIRONMENT=development`. |
| `compileall -q app migrations tests` | Aprovado. |
| `pip check` | Aprovado; nenhuma dependência quebrada. |
| `alembic heads` | `d129a4c7e601` é o único head; não abriu conexão. |
| Pylance nos arquivos Python alterados | Sem diagnósticos nos arquivos implementados/testados. |

Validação automatizada não comprova instalação da migration nem funcionamento de conexão no deploy. A tela de login/assets e uma conta real não foram testadas nesta etapa; isso requer ambiente autorizado e credencial legítima.

## Riscos residuais e pendências

- A segurança depende da identidade e dos controles do operador/host, do acesso de deploy, da configuração do DNS/host do banco, do tmpfs e do segredo de conexão já fornecido ao processo. O endereço/host validado não substitui controles de rede, TLS, firewall ou credenciais DB restritas.
- O UID do processo é informativo e pode identificar apenas o UID do contêiner; os registros do provedor/host devem ser preservados para atribuição humana.
- Não há integração com secret manager, política institucional de aprovações, implantação Docker Compose, telemetria central ou runbook break-glass.
- A migration e o caminho Alembic com target explícito de produção precisam ser revisados/aprovados e executados separadamente pelo responsável de banco. Não testar esse caminho apontando a banco real nesta entrega.
- Antes da produção, revisar permissões SQL do usuário de aplicação, proteção/retention dos eventos, conectividade/TLS, backup, migração de instalações que já tenham administradores e comportamento operacional de incidentes.

## Alterações efetivas nesta etapa

- Adicionados serviço de emissão/consumo transacional, comandos CLI de produção explicitamente guardados, validação de target, modelos e migration ainda não aplicada.
- O CLI não lê `.env`, não aceita senha/segredo em argv e não imprime concessão.
- Adicionados testes isolados para bootstrap e migration.
- Não foi criado nem alterado usuário, senha, role, grant ou permissão. Nenhuma conexão PostgreSQL, migration real ou alteração de dados ocorreu; `cronicas_do_reino_dev` não foi conectado.
- Nenhum arquivo `.env` foi aberto manualmente ou modificado. Uma execução preliminar de testes a partir do diretório `backend` importou `app.main`, cujo `Settings` existente usa `env_file=".env"`; portanto o loader pode ter tentado ler o arquivo relativo àquele diretório. A execução final da suíte foi feita de diretório temporário vazio, com `APP_ENVIRONMENT=development`, sem resolver o `.env` do projeto. Nenhum valor de configuração foi exibido. Nenhum comando de bootstrap foi executado.
