# PostgreSQL local para desenvolvimento e testes

## Auditoria do projeto

- `backend/app/core/config.py` carrega `DATABASE_URL` por `pydantic-settings`; o `.env` é relativo ao diretório de trabalho. Execute Alembic e a API a partir de `backend/`.
- `backend/app/db/session.py` cria o engine assíncrono com `create_async_engine(..., pool_pre_ping=True)`; o driver previsto é `postgresql+asyncpg`.
- `backend/migrations/env.py` substitui a URL do `alembic.ini` por `get_settings().database_url` e usa `async_engine_from_config`; o `alembic.ini` contém apenas uma URL de fallback.
- Os testes sem marcador PostgreSQL usam SQLite em memória. Os testes marcados `postgres` usam somente o banco local `cronicas_do_reino_test`, a role `cronicas_local` e o schema isolado `test_asset_h_7e4c91a2d603`; recusam qualquer outro destino. A fixture confirma a revisão Alembic e as tabelas antes de executar e limpa os dados das tabelas desse schema antes e depois de cada teste. Um `TEST_DATABASE_URL` configurado não muda o banco usado pelos testes SQLite nem pela aplicação.
- `test_join_code_invalid_duplicate_and_full_room`, `test_campaign_access_requires_active_membership_and_player_role`, `test_lobby_readiness_and_presence_are_shared_with_participants`, `test_campaign_start_checks_owner_and_minimum_then_persists_session_event`, `test_postgres_concurrent_joins_preserve_seven_player_limit`, `test_postgres_full_multiplayer_narrative_flow_and_campaign_isolation`, `test_simultaneous_last_votes_create_one_final_decision`, `test_concurrent_vote_change_and_other_player_vote_preserve_both_ballots`, `test_concurrent_deadline_closure_applies_consequence_and_advances_once` e `test_duplicate_simultaneous_vote_creates_one_ballot_and_event` cobrem fluxo multiplayer, limite/concorrência de entrada, lobby, acesso e votação.
- Nenhum arquivo Docker/Compose foi encontrado.
- Na auditoria da Etapa E2, foi detectado PostgreSQL 18 no Windows, com o serviço `postgresql-x64-18` em execução e a porta local 5432 aberta.
- Após conferir que os nomes estavam livres, foram criados `cronicas_do_reino_dev` e `cronicas_do_reino_test`, ambos de propriedade de `cronicas_local`. A criação foi confirmada no SQL Shell.
- A conexão do administrador foi confirmada pelo usuário no SQL Shell. A conexão do engine assíncrono da aplicação foi validada nos bancos com PostgreSQL 18.6.
- `cronicas_do_reino_dev` está na revisão Alembic `91d4a0b7c8e2` (head); `alembic check` não encontrou operações pendentes. O Alembic emite um aviso conhecido de ciclo de FKs entre campanhas, capítulos e cenas.
- O schema migrado contém 39 tabelas, 97 índices, 61 chaves estrangeiras e colunas UUID e JSON. A role `cronicas_local` não é superusuária e não pode criar bancos ou roles.
- Os quatro testes PostgreSQL de concorrência passaram. A suíte completa, com `TEST_DATABASE_URL` configurada, passou 36 testes sem ignorados.
- Os testes PostgreSQL usam `Base.metadata.create_all` em schemas isolados preservados após a execução; por isso não foi necessário executar migrações no banco de teste.
- A Etapa F executou 10 testes PostgreSQL específicos; a suíte completa passou com 38 testes e nenhum ignorado. Como a limpeza destrutiva foi desabilitada, 54 schemas `test_<uuid>` criados durante as execuções ficaram preservados no banco `cronicas_do_reino_test`.
- Na Etapa G, `TEST_DATABASE_URL` foi validada para `cronicas_do_reino_test`, distinta de `DATABASE_URL` (`cronicas_do_reino_dev`); a suíte passou com 38 testes, incluindo os 10 marcados `postgres`, sem executar migrações. Um cenário ASGI adicional, com seis contas sintéticas e lobby/votação em schema isolado, validou salas de dois e cinco participantes, limite, presença, reconexão, personagens, votação 3–2 e isolamento. Os resultados da API não substituem o teste visual em navegadores.
- `alembic check`, direcionado explicitamente ao banco de teste, terminou com `Target database is not up to date` porque o schema `public` não contém revisão Alembic. O comando não executa migrações; nenhuma migração foi aplicada nesta etapa.
- Esses cenários adicionaram schemas preservados ao banco de teste: após a última conferência havia 67 schemas. Nenhum schema foi removido. A persistência foi validada ao recriar o pool e autenticar novas sessões, mas o processo do backend não foi reiniciado; essa etapa visual continua pendente.
- Em 6 de novembro de 2026, o schema PostgreSQL isolado foi atualizado para a revisão `c83d42e7a901`; a suíte backend completa passou com 291 testes, sem ignorados.

## Instalar e iniciar PostgreSQL no Windows

Para instalar PostgreSQL no Windows, use o instalador oficial: <https://www.postgresql.org/download/windows/>. Nesta máquina, o PostgreSQL 18 já está instalado e o serviço `postgresql-x64-18` está ativo na porta 5432. Use `services.msc` para verificar ou iniciar/parar o serviço.

Os bancos desta máquina já foram criados após a verificação de que estavam livres. Não execute novamente os comandos de criação abaixo nela. Em uma instalação nova, primeiro consulte os bancos e a role para garantir que os nomes estão livres; não apague nem recrie recursos existentes. A role da aplicação deve ser sem superusuário e sem permissão para criar bancos:

```powershell
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres
```

No prompt do SQL Shell, depois de conferir que a role e os bancos não existem, crie a role, defina sua senha mascarada com `\password cronicas_local` e crie os bancos com `OWNER cronicas_local`. Não conceda `SUPERUSER`, `CREATEDB` ou `CREATEROLE`. `cronicas_do_reino_dev` é para a aplicação; `cronicas_do_reino_test` é exclusivamente para integração. Nunca use bancos pessoais, existentes ou de produção.

Neste ambiente, o arquivo local `backend/.env` está configurado e é ignorado pelo Git. Em uma instalação nova, copie o `.env.example` e substitua `REPLACE_WITH_URL_ENCODED_PASSWORD` pela senha local da role `cronicas_local`, sem compartilhar ou registrar a senha. Para evitar codificação especial, prefira uma senha longa com letras e números; se ela contiver caracteres reservados em URL, aplique percent-encoding. O `.env.example` contém somente placeholders:

```powershell
notepad backend\.env
```

O `DATABASE_URL` aponta para o banco de desenvolvimento. `TEST_DATABASE_URL` é reservada aos testes que pedem explicitamente PostgreSQL; os testes comuns continuam usando SQLite. Ambos usam o usuário restrito `cronicas_local`; a senha não deve ser colocada no frontend.

Use **Services**/`services.msc` para iniciar ou parar o serviço PostgreSQL instalado. Para confirmar conexão e servidor:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 5432 -U cronicas_local -d cronicas_do_reino_dev -c "SELECT version();"
```

### Criar administrador no desenvolvimento local

O comando `create-local-admin` funciona somente com `APP_ENVIRONMENT=development` e a URL efetiva apontando para `postgresql+asyncpg` em endereço IP loopback, porta `5432` e banco exatamente `cronicas_do_reino_dev`. Antes de pedir credenciais, ele confirma a identidade real do servidor, database, role configurada e schema `public`. O comando falha em produção, no banco de testes, em servidores remotos ou em destinos não reconhecidos.

No PowerShell:

```powershell
Set-Location backend
$env:APP_ENVIRONMENT = "development"
.\.venv\Scripts\python.exe -m app.cli create-local-admin
```

Informe um username novo (3–32 letras, números ou `_`) e digite a senha (12–128 caracteres) nos prompts interativos ocultos. O CLI cria uma conta nova com o hash scrypt já usado pela autenticação; não promove contas existentes nem altera permissões PostgreSQL. Não passe senhas em argumentos, não use `create-admin` (reservado a schemas isolados de teste) e não execute migrations automaticamente. Se o schema `public` ou a tabela `users` ainda não existir, interrompa e avalie as migrations separadamente; o comando não as aplica.

## Migrações e execução

No PowerShell:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
alembic check
uvicorn app.main:app --reload
```

Para validar as migrações em um banco vazio **descartável de teste**, use o valor de `TEST_DATABASE_URL` somente para o processo Alembic:

```powershell
$previousDatabaseUrl = $env:DATABASE_URL
$testDatabaseUrl = Get-Content .env | Where-Object { $_ -match '^TEST_DATABASE_URL=' } | Select-Object -First 1
$testDatabaseUrl = $testDatabaseUrl -replace '^TEST_DATABASE_URL=', ''
if ($testDatabaseUrl -notmatch '/cronicas_do_reino_test$') { throw 'Refusing to migrate a non-test database.' }
$env:DATABASE_URL = $testDatabaseUrl
alembic upgrade head
alembic check
alembic downgrade base
alembic upgrade head
if ($null -eq $previousDatabaseUrl) {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
} else {
    $env:DATABASE_URL = $previousDatabaseUrl
}
```

Esses comandos só devem ser executados depois de verificar que a URL termina em `/cronicas_do_reino_test`. Não execute `downgrade` em `cronicas_do_reino_dev` nem em bancos existentes. A aplicação não usa `TEST_DATABASE_URL` para conectar.

`alembic check` executado contra SQLite não substitui o check do PostgreSQL. Neste projeto, SQLite não reflete o `MATCH SIMPLE` da chave estrangeira composta declarada em `campaign_members`; a comparação sinaliza uma diferença embora a migração e o modelo declarem a mesma regra PostgreSQL. Alembic também avisa do ciclo de FKs entre campanhas, capítulos e cenas. A validação PostgreSQL deve confirmar o resultado nesses pontos; migrações antigas não foram alteradas para suprimir esse diagnóstico.

## Testes

Os testes comuns permanecem em SQLite:

```powershell
Set-Location backend
py -m pytest
```

O relatório marca os testes PostgreSQL como ignorados quando `TEST_DATABASE_URL` ou `TEST_ASSET_SCHEMA` não estão no ambiente do processo; isso **não** conta como validação PostgreSQL. A fixture exige que o schema dedicado esteja na revisão Alembic atual e limpa os dados das tabelas desse schema. No PowerShell, carregue os valores locais sem exibi-los, aplique as migrations somente ao banco de teste e rode os testes:

```powershell
Set-Location backend
$testLine = Get-Content .env | Where-Object { $_ -match '^TEST_DATABASE_URL=' } | Select-Object -First 1
$devLine = Get-Content .env | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
$schemaLine = Get-Content .env | Where-Object { $_ -match '^TEST_ASSET_SCHEMA=' } | Select-Object -First 1
$env:TEST_DATABASE_URL = $testLine -replace '^TEST_DATABASE_URL=', ''
$env:TEST_ASSET_SCHEMA = $schemaLine -replace '^TEST_ASSET_SCHEMA=', ''
$env:DATABASE_URL = $env:TEST_DATABASE_URL
.\.venv\Scripts\python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL test migration failed.' }
$env:DATABASE_URL = $devLine -replace '^DATABASE_URL=', ''
.\.venv\Scripts\python.exe -m pytest -m postgres
```

Também é possível executar toda a suíte: os testes sem marcador continuarão em SQLite; os marcados usam somente o schema PostgreSQL de teste validado acima. Não conceda permissão de `CREATE` nesse banco a usuários não confiáveis.
