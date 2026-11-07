# Etapa H.9 — Auditoria e desenho do bootstrap administrativo seguro

## Status e escopo

Auditoria de código e testes isolados concluídos; o bootstrap de produção **não foi implementado nem habilitado**. Não foram lidos `.env`/segredos, conectados bancos, consultadas contas, nem executados `create-admin` ou migrations.

Esta análise confirma o fluxo pelo código. Não permite afirmar se uma instalação específica já possui administrador, se suas migrations estão aplicadas, ou se o deploy atual está corretamente configurado.

## Estado atual confirmado no código

### Identidade e autorização

- `User.is_admin` é o único indicador de privilégio administrativo no modelo [entities.py](../backend/app/models/entities.py). É booleano não nulo, com default ORM `False`; `username_key` é único e normalizado.
- O cadastro público `POST /api/auth/register` constrói o usuário com `is_admin=False` explicitamente ([auth.py](../backend/app/api/auth.py)). O schema proíbe campos extras, portanto `is_admin`/role enviado pelo cliente não é aceito.
- A única ocorrência de `is_admin=True` no código de aplicação é a inserção de usuário novo no utilitário [cli.py](../backend/app/cli.py). Não há endpoint para promoção, atualização de roles ou atribuição administrativa derivada de perfil/campanha/identidade externa. `ExternalIdentity` não é consultada para conceder privilégio.
- `current_admin` exige cookie de audiência administrativa, sessão válida e não expirada, usuário ativo e `is_admin=True` ([dependencies.py](../backend/app/api/dependencies.py)). As rotas administrativas dependem desse guard. O endpoint de login administrativo só cria sessão depois de autenticar usuário ativo e autorizado.
- Uma sessão administrativa não é convertida em sessão de jogador: cookies e `audience` são separados (`rpg_admin_session` / `rpg_player_session`) e a consulta de sessão restringe a audiência.

### Senhas, sessões e proteção de login

- `RegisterRequest` e `AdminLoginRequest` exigem nome de usuário de 3–32 caracteres (`[A-Za-z0-9_]{3,32}`) e senha de 12–128 caracteres; e-mail não é identificador do login.
- A senha é transformada em hash scrypt com salt aleatório e comparada em tempo constante (`hmac.compare_digest`) em [security.py](../backend/app/core/security.py). O login usa um hash dummy para usuário inexistente e a mesma mensagem genérica para usuário inexistente, senha inválida, usuário inativo ou usuário sem flag admin.
- O token de sessão é aleatório; somente SHA-256 do token é persistido em `AuthSession`. Cookies são `HttpOnly`, `SameSite=Lax`, path `/` e `Secure` conforme configuração. A configuração recusa cookie não seguro fora de `APP_ENVIRONMENT=development`.
- O login limita tentativas persistidas por IP e username; operações de escrita autenticadas verificam o `Origin` quando fornecido. O uso de cookie e a proteção de origem reduzem risco CSRF, mas não substituem HTTPS, configuração correta de origens, proteção de XSS ou operação segura do host.
- Ausência de cookie/sessão inválida resulta em 401; usuário autenticado sem autorização administrativa resulta em 403 nas dependências. No login, a resposta permanece genérica para não revelar existência ou papel da conta.

### Fluxo de criação existente

- O registro aberto cria exclusivamente jogadores. Não promove um usuário comum, mesmo que o cliente envie propriedades extras.
- `python -m app.cli create-admin` é interativo, pede senha sem eco e grava hash scrypt. Antes da escrita, valida `cronicas_do_reino_test`, host loopback e schema de teste permitido; o target vem de variáveis explicitamente identificadas para testes. Não é um procedimento de produção.
- O helper `_create_admin` consulta a chave normalizada do username e recusa conflito, depois **cria uma nova linha** com `is_admin=True`. Não atualiza/promove um usuário existente.
- **O CLI atual não é uso único nem valida “primeiro admin”:** para um username distinto, não consulta se já existem outros administradores. A descrição do subcomando diz “first administrator”, mas isso não é imposto por código. A guarda de ambiente limita o impacto ao alvo local de teste autorizado; ainda assim, não se deve reutilizar o comando como solução de bootstrap operacional.
- As migrations iniciais criam `users` e `auth_sessions`; não há tabela/estado de bootstrap, concessão temporária ou trilha de consumo. Esta etapa não consulta o estado instalado em qualquer banco.

## Respostas de auditoria

1. **Como o sistema determina administrador?** `User.is_admin` booleano; a autenticação consulta esse campo e o estado ativo antes de emitir uma sessão administrativa, e cada rota protegida verifica de novo.
2. **Como se criam administradores hoje?** Somente pelo helper CLI, que escreve usuário novo, e somente para os targets locais de teste aceitos. Nenhum mecanismo de produção está implementado.
3. **Existe elevação indireta?** Não foi encontrada em rotas da aplicação: cadastro define `False`, schema rejeita campos extras e não existe endpoint de promoção. Acesso direto ao banco por operador/credencial de infraestrutura está fora da autorização HTTP e permanece uma autoridade operacional capaz de alterar esse campo.
4. **Proteções contra elevação?** Flag não controlada pelo usuário, username único, senha em hash, sessão administrativa separada, guards por endpoint e target guard no CLI. Testes cobrem cadastro comum não-admin, negação de login/admin session para jogador, target incorreto e recusa de conflito de username.
5. **Riscos do primeiro acesso?** Ausência de procedimento de produção; possível erro humano ao confundir o CLI de teste com o de produção; administração por alteração manual de dados sem trilha; `create-admin` não é singleton; uma futura rotina baseada apenas em “zero admins” poderia promover conta pública preexistente, permitir corrida, replay ou rebootstrap depois de remoção.
6. **Por que a validação de UI é limitada?** Não há credencial administrativa fornecida e não se deve consultar o banco real para descobrir contas. O teste pode cobrir os guards com SQLite/mock, mas não comprova existência de administrador nem uma sessão autorizada no ambiente instalado.

Não foi confirmada vulnerabilidade de elevação via API. A lacuna é de operação/bootstrap e não justifica enfraquecer guards nem criar cadastro administrativo público.

## Alternativas avaliadas

| Alternativa | Vantagens | Riscos/limitações | Decisão |
|---|---|---|---|
| Inserção SQL/manual ou alteração direta de `is_admin` | Sem endpoint público; operacionalmente imediata. | Hash/colunas podem ser preenchidos incorretamente; risco de alvo errado; auditoria, aprovação e atomicidade dependem do operador; incentiva workaround não reproduzível. | Não recomendar como runbook normal. |
| Promover o primeiro usuário comum quando `COUNT(admin)=0` | Simples e sem segredo adicional. | Usuários públicos podem existir antes do primeiro deploy; atacante pode se registrar antes; corrida concorrente; remoção de todos os admins reabre o fluxo; sem autorização explícita. | Rejeitar. |
| CLI com senha/segredo em argumento ou variável de ambiente e teste de zero admins | Fácil de automatizar. | Argumentos podem aparecer no histórico/process list; ambiente pode vazar em dumps, logs de CI, processos filhos e diagnósticos; replay, corrida e reinstalação após remoção não resolvidos pelo count. | Rejeitar nessa forma. |
| CLI explícito, segredo efêmero de secret manager, concessão hash persistente e consumo atômico | Fora da superfície HTTP; autorização da plataforma/operador; validade e alvo vinculados; estado persistente impede replay e rebootstrap; nova conta sem promover jogador. | Exige aprovação, integração de secret manager, migration e um provisionamento confiável da concessão; comprometimento do operador/secret manager ainda pode conceder acesso. | **Recomendada**, sujeita a revisão e implementação separadas. |
| SSO/IdP com grupo administrativo provisionado | Identidade central, MFA e desligamento centralizado; reduz senha local. | Mudança arquitetural e dependência operacional externa; precisa mapear identidade/grupo com segurança e definir bootstrap do IdP. | Alternativa estratégica futura, não substitui o primeiro acesso deste sistema sem trabalho adicional. |

## Arquitetura recomendada (proposta, não implementada)

Usar uma operação CLI explícita executada por operador autorizado, fora da API pública, autorizada por concessão de uso único emitida por processo de deploy/aprovação. A concessão deve ser aleatória com pelo menos 256 bits, curta, restrita ao ambiente/implantação e entregue pelo gerenciador de segredos ou canal protegido diretamente ao processo (stdin/FD protegido). Nunca receber token ou senha em argumentos de linha de comando; evitar variável de ambiente como primeira opção. Se a plataforma só permitir variável de ambiente, documentar o risco de exposição, minimizar o escopo/duração, não propagar para subprocessos e limpar o ambiente após uso.

Persistir somente o hash da concessão em tabela própria de bootstrap (nova migration, não preparada nesta etapa), com ambiente/alvo, expiração, instante de consumo, operador/referência de aprovação e ID do administrador criado. Não guardar o segredo em claro ou registrá-lo. A emissão da concessão deve usar identidade de deploy/operador e auditoria da plataforma; nenhum usuário HTTP comum deve poder emitir/ler uma concessão.

### Transação de consumo

1. Falhar fechado antes de escrita se a configuração, ambiente, host, banco, schema, TLS/target esperado ou versão de schema não corresponderem ao ambiente aprovado. Não confiar apenas em `APP_ENVIRONMENT`; validar a identidade real da conexão por allowlist operacional.
2. Obter e validar o segredo por canal protegido; aplicar limites de formato/tamanho e comparar hash de maneira segura. Erros exibidos/logados devem ser genéricos e sem segredo, hash de senha, token ou URL de conexão.
3. Iniciar uma transação e bloquear uma linha singleton de bootstrap (`SELECT ... FOR UPDATE`) ou usar mecanismo equivalente comprovadamente serializado na base-alvo.
4. Revalidar dentro do lock: concessão não consumida, não expirada, ambiente correspondente, instalação compatível e ausência de qualquer admin existente. Se já houver admin, não criar outro nesse fluxo; recuperação é operação diferente.
5. Criar uma **conta administrativa nova** com username único escolhido pelo operador. Nunca selecionar/promover por username um jogador preexistente. Se username estiver ocupado, abortar e pedir ao operador outra identificação, sem alterar a conta existente.
6. Na mesma transação, marcar a concessão como consumida e registrar evento de auditoria sem credenciais. Uma restrição única por concessão/ambiente e estado singleton protegem contra dois processos e contra nova concessão automática.
7. Commit atômico: usuário, consumo e auditoria são todos persistidos, ou nenhum deles. Depois do sucesso, revogar/desabilitar também o segredo na plataforma, como defesa adicional.

A restrição persistente de consumo precisa sobreviver à exclusão/indisponibilidade posterior de administradores. Não usar apenas `COUNT(is_admin)=0`: exigir também estado nunca consumido e concessão vigente. A implementação deve definir política para migração de instalações que já tenham administradores sem consultar nem reescrever permissões automaticamente.

### Operação e falhas

- **Quem:** operador de deploy autorizado, com aprovação conforme controle de mudança; não o visitante do site nem qualquer usuário registrado.
- **Quando/onde:** janela de implantação aprovada; ambiente-alvo explicitamente indicado; conexão autenticada ao banco daquele ambiente e TLS conforme política operacional. Nunca usar o comando test-only existente para produção.
- **Pré-condições:** backup/recuperação operacional disponível; migration aprovada e aplicada no ambiente-alvo em mudança separada; esquema suportado; nenhum admin existente para bootstrap inicial; concessão curta, válida, emitida para aquele ambiente; secret manager/identidade de operador acessível; username não ocupado.
- **Segredo:** gerado por CSPRNG fora do repositório, secreto no gerenciador, limitado a uma tentativa lógica, com expiração curta e hash persistido. Revogar após sucesso; se expirar, falhar e exigir nova aprovação/concessão. Sem fallback para credenciais padrão.
- **Concorrência/replay:** lock da linha singleton e atualização condicional `consumed_at IS NULL AND expires_at > now()` na mesma transação. Só um executor vence; qualquer repetição ou rebootstrap após consumo falha, mesmo que todos os admins sejam removidos.
- **Falha antes do commit:** rollback deixa conta, auditoria e consumo ausentes. Revogar o segredo, inspecionar estado por `request_id` e emitir nova concessão somente após confirmar rollback/ausência de commit.
- **Resultado incerto durante perda de conexão no commit:** não repetir cegamente. Consultar o estado de auditoria/consumo por ID de operação usando canal autorizado; considerar sucesso se o commit aconteceu. Caso contrário, revogar e emitir nova concessão.
- **Sucesso:** imprimir apenas status, ambiente não sensível e ID do novo usuário/operação; mostrar username somente ao operador se necessário. Nunca imprimir senha, token, hash, segredo de conexão ou conteúdo de variáveis secretas.
- **Recuperação:** processo break-glass separado, documentado, com aprovação reforçada e identidade da plataforma. Deve invalidar sessões existentes do administrador afetado, criar ou restaurar acesso sem auto-promoção e registrar auditoria. Não rearmar nem apagar a concessão consumida para contornar o bloqueio; definir rotação de credenciais pelo hash de senha, invalidação de sessões e revisão pós-incidente.

## Ameaças, controles e riscos residuais

| Ameaça | Controle proposto | Risco residual |
|---|---|---|
| Jogador se registra antes do primeiro admin e é promovido por conveniência | Criar usuário administrativo separado; não promover conta existente; exigir aprovação e concessão | Operador pode escolher username confusável; orientar conta nominativa, sem compartilhar credenciais |
| Token vaza de shell/CI/process list | Secret manager/FD protegido, nunca argv, TTL curto, logs redigidos | Acesso privilegiado a processo/host pode observar memória |
| Replay após bootstrap ou remoção de admins | Marcador persistente consumido que não é apagado com usuários/sessões | Operador com acesso direto à base pode alterar o marcador |
| Duas execuções simultâneas | Lock transacional singleton, consumo condicional, constraints únicas | Sem suporte/uso correto do lock no banco escolhido, deve falhar fechado |
| Target errado por variável de ambiente | Validar identidade da conexão contra allowlist do ambiente; confirmação do operador e revisão de deploy | DNS/proxy/credencial de infraestrutura comprometidos |
| Falha parcial ou conexão cai no commit | Usuário, consumo e auditoria na mesma transação; `request_id` para reconciliação | Resultado de commit incerto exige reconciliação manual, não retry imediato |
| Um admin existente e segunda execução | Bootstrap recusa; recuperação tem caminho separado | Exclusão acidental de único admin torna break-glass necessário |
| Segredo ou senha expostos em exceção/log | Erros sanitizados; logging estruturado por código/ID; testes de captura de logs | Stack traces de dependências/driver devem ser revisados na implementação |
| Tabela de bootstrap manipulada por acesso DB | Privilégio do usuário de aplicação minimizado; auditoria/segregação do operador | Acesso de owner/superuser continua capaz de alterar estado; fora do guard HTTP |

## Plano de testes seguros

Implementação futura deverá usar SQLite em memória ou arquivo temporário com schema isolado e mocks para secret manager/identidade, sem PostgreSQL real:

1. Uma concessão emitida, não expirada, para ambiente sintético cria um novo admin, salva somente hash de senha e consome a concessão.
2. Admin pré-existente faz bootstrap falhar sem gravar nova conta nem consumir outra concessão.
3. Reutilizar concessão consumida falha; ausência, token incorreto, expirado e ambiente divergente falham sem revelar qual condição de segredo ocorreu.
4. Duas tarefas concorrentes com o mesmo grant resultam em no máximo uma criação/consumo; usar teste de concorrência aderente ao lock real do banco em suite isolada antes de produção.
5. Exceção antes do commit desfaz usuário, consumo e auditoria; falha simulada de commit exige prova de rollback; simular resposta perdida e reconciliação por `request_id`.
6. Cadastro público sempre salva `is_admin=False`; envio de `is_admin=true` ou campos extras é rejeitado; login admin de jogador comum retorna a mesma resposta genérica de credencial inválida.
7. Capturar stdout/stderr/logs/erros e verificar ausência do token, senha, hashes e URL de banco.
8. Target/configuração inválidos, migrations ausentes, falha do secret manager e driver sem suporte ao lock são recusados sem escrita.
9. Username já utilizado por jogador provoca rollback e não altera essa conta.
10. Após consumo, remoção de todas as contas admin não permite re-bootstrap; recuperação requer fluxo e autorização separados.

Testes atuais dão evidência parcial: `test_auth.py` cobre cadastro comum, separação login/session e negação ao jogador; `test_test_environment.py` cobre validação do target, bloqueio de banco/schema não autorizado e conflito sem promoção. Não há testes atuais de consumo, replay, expiração, corrida de bootstrap, nem garantia de ausência de segredo em logs. Não foram adicionados testes de implementação futura porque nenhum bootstrap foi construído nesta etapa.

## Alterações nesta etapa

Somente este documento foi criado. A documentação H.8 e `docs/backend-requirements.md` foram conferidas; não foi necessário sobrescrever informações históricas. A nuance de que o CLI não verifica administradores existentes foi registrada aqui como confirmação adicional.

## Validação executada

`backend/.venv/Scripts/python.exe -m pytest -q tests/test_auth.py tests/test_test_environment.py` foi executado como um conjunto focado. Os testes de API usam o fixture SQLite in-memory; os testes de guarda usam mocks/configuração sintética. Nenhum teste marcado `postgres` foi selecionado, e nenhum target de banco externo foi conectado. `compileall` e `pip check` também foram executados. Não houve alteração de frontend/código nesta etapa.

| Verificação | Resultado |
|---|---|
| Testes focados de autenticação e guards de ambiente | **44 passed**, 0 falhas. |
| `python -m compileall -q app migrations tests` | Aprovado. |
| `python -m pip check` | Aprovado; nenhuma dependência quebrada. |

## Pendências para revisão antes de implementar

- Aprovar o modelo de operador/autorização da plataforma e quem pode emitir a concessão.
- Escolher o secret manager, método de entrega ao processo e auditoria de identidade.
- Definir o target de produção permitido, TLS, privilégios mínimos e revisão independente da migração.
- Projetar e revisar migration/tabela de grant e lock para o banco suportado; definir migração de instalações existentes.
- Definir prazo exato da concessão, política de rotação e break-glass com invalidação de sessões.
- Revisar mensagem/logging de todas as falhas de infraestrutura para garantir redaction.
- Implementar e testar primeiro contra SQLite isolado/mocks; depois executar em um ambiente de staging autorizado e documentar evidências. Nenhuma dessas ações foi realizada na H.9.

## Confirmação de limites

Nenhum PostgreSQL foi acessado; `cronicas_do_reino_dev` não foi consultado. Nenhuma migration/DDL foi aplicada. Nenhuma conta, senha, token, role, grant ou permissão foi criada ou modificada. `.env` e credenciais não foram lidos nem alterados. O comando `create-admin` não foi executado.

## Atualização posterior — H.10

O status acima registra corretamente a conclusão da H.9. Posteriormente, a H.10 implementou o desenho de concessão efêmera e consumo transacional por CLI, sem habilitar uma rota pública. A migration `d129a4c7e601` está preparada e ainda não aplicada. Não foram criadas contas nem acessado PostgreSQL. Veja [etapa-h10-admin-bootstrap-operations.md](./etapa-h10-admin-bootstrap-operations.md).
