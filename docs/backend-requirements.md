# Requisitos do backend

Este documento descreve o contrato de dados e as operações esperadas para a API em Python/FastAPI com PostgreSQL. Cadastro/login, campanhas/lobby, progressão narrativa básica, serviço interno inicial de evolução de personagens e conteúdo administrativo estão implementados; as rotas e os modelos do Painel do Mestre estão documentados em [admin-content-api.md](./admin-content-api.md), a progressão narrativa em [narrative-progression.md](./narrative-progression.md) e a progressão de personagens em [character-progression.md](./character-progression.md). O painel consulta o servidor para história, NPCs, itens, monstros, habilidades, regras de drop, recompensas, economia e configurações do universo. Eventos de atividade e algumas preferências visuais continuam demonstrativos/locais. As migrações e os testes ainda precisam de validação em PostgreSQL real.

O mapeamento de usuários, autenticação, campanhas, personagens, história, sessões/eventos, inventário, habilidades, encontros, transações, notificações e metadados de integração Discord está em `backend/app/models/entities.py`. O esquema é um ponto de partida e deve ser revisto antes de uso em produção.

## Requisitos transversais

- Usar UUIDs estáveis para chaves primárias. Os identificadores com prefixo da demonstração não devem ser usados como mecanismo de autorização.
- Registrar `created_at` e `updated_at` em entidades editáveis e guardar datas em UTC.
- Validar tipos, limites numéricos, relacionamentos e payloads com modelos Pydantic.
- Usar paginação e filtros no servidor para coleções extensas; não depender de carregar o banco inteiro no navegador.
- Aplicar autorização por campanha e papel do usuário. Não há jogador com papel de mestre: o sistema valida decisões narrativas; o proprietário mantém apenas as permissões de lobby existentes.
- Executar alterações relacionadas em transações PostgreSQL. Retornar erros HTTP claros para registros inexistentes, conflitos, dados inválidos e falta de permissão.
- Aplicar exclusão lógica ou regras explícitas de retenção quando o histórico de campanha, auditoria, economia ou votação precisar ser preservado.
- Não armazenar tokens de Discord no painel. Integrações e segredos pertencem à configuração segura do servidor.

## Entidades e campos principais

| Entidade                 | Campos principais                                                                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Usuário/administrador    | `id`, `username`, `username_key`, e-mail opcional, hash de senha, nome de exibição, papel, estado da conta                                          |
| Sessão de autenticação   | `id`, `user_id`, hash do token, público (`player`/`admin`), expiração, revogação                                                                    |
| Limite de autenticação   | chave do identificador, início da janela, quantidade de tentativas, bloqueio até                                                                    |
| Campanha                 | `id`, `title`, `description`, `status`, `min_players`, `max_players`, `current_chapter_id`, `world_state`, timestamps                               |
| Participante             | `id`, `campaign_id`, `display_name`, `discord_user_id` opcional, `status`, `joined_at`; o ID externo do Discord é dado de vínculo, não autenticação |
| Sessão narrativa         | `id`, `campaign_id`, `current_node_id`, `status`, snapshot/configuração/progresso JSON, início/fim                                               |
| Evento da sessão         | `id`, `session_id`, sequência única, ator, tipo, payload e chave idempotente                                                                      |
| Capítulo                 | `id`, `campaign_id`, `position`, `title`, `summary`, `narrative`, `status`, timestamps                                                              |
| Cena                     | `id`, `chapter_id`, `position`, `title`, `narrative`                                                                                                |
| Diálogo                  | `id`, `scene_id`, `position`, `speaker`, `line`                                                                                                     |
| Escolha                  | `id`, `scene_id`, `position`, `label`, `next_scene_id` opcional, `condition` opcional, `effect`                                                     |
| Voto                     | `id`, `choice_id`, `user_id`, `session_id`, cena e rodada; manter no máximo um voto atual por participante e rodada                               |
| Personagem               | `id`, `participant_id`, `campaign_id`, `name`, `level`, `xp`, HP e mana atuais/máximos, classe, atributos estruturados, moedas, história            |
| NPC                      | `id`, `campaign_id` opcional, `name`, descrição, personalidade, papel, relação, estado de conteúdo provisório                                       |
| Relação NPC-participante | `npc_id`, `participant_id`, descrição/estado de relacionamento; chave composta ou ID próprio                                                        |
| Diálogo de NPC           | `id`, `npc_id`, `position`, `speaker`, `line`                                                                                                       |
| Missão                   | `id`, `campaign_id`, `npc_id` opcional, título, descrição, estado, condições, timestamps                                                            |
| Criatura                 | `id`, `name`, descrição, nível, HP, ataque, defesa, velocidade, XP concedido, estado de conteúdo provisório                                         |
| Habilidade de criatura   | `creature_id`, `name`/`skill_id` e ordem                                                                                                            |
| Resistência/fraqueza     | `creature_id`, tipo ou elemento, categoria (`resistencia`/`fraqueza`)                                                                               |
| Habilidade               | `id`, `name`, categoria, descrição, custo de mana, potência, tipo de potência, efeitos, alvo, nível mínimo, recarga, estado de publicação           |
| Item                     | `id`, `name`, descrição, categoria, raridade, preço, peso, bônus, efeitos, nível mínimo, estoque                                                    |
| Equipamento              | `character_id`, `item_id`, slot opcional, dados de condição/durabilidade quando aplicável                                                           |
| Entrada de inventário    | `character_id`, `item_id`, quantidade; chave única composta por personagem e item                                                                   |
| Transação                | `id`, `character_id`, tipo, descrição, valor assinado, moeda, data, participante/admin responsável e referência opcional                            |
| Recompensa de missão     | `id`, `quest_id`, ouro, XP e itens; armazenar itens em tabela associativa com quantidade                                                            |
| Regra de drop            | `id`, `creature_id`, `item_id`, chance entre 0 e 100, quantidade mínima/máxima                                                                      |
| Registro de atividade    | `id`, `campaign_id`, ator, tipo, mensagem/dados estruturados, data                                                                                  |
| Auditoria                | `id`, ator, campanha, entidade e registro afetados, operação, resumo antes/depois, data                                                             |

## Relacionamentos e integridade

- Uma campanha possui participantes, capítulos, NPCs, missões, transações e eventos.
- Um participante pertence a uma campanha e pode possuir vários personagens.
- Um personagem pertence a um participante e a uma campanha. Inventário e equipamentos apontam para itens; habilidades aprendidas apontam para habilidades.
- Um capítulo contém cenas ordenadas. Cenas contêm diálogos e escolhas também ordenados; o destino de escolha, quando definido, referencia outra cena.
- Capítulos associam NPCs e encontros com criaturas por tabelas de junção.
- Missões e recompensas pertencem à campanha; recompensas e drops referenciam itens.
- Votos vinculam participante, escolha e rodada/sessão de votação. A API deve rejeitar votos para campanhas ou escolhas não acessíveis ao participante.
- Aplicar restrições para `min_players <= max_players`, níveis e quantidades positivos, HP/mana dentro dos máximos e chances de drop entre 0 e 100.
- Índices recomendados: chaves estrangeiras, `(campaign_id, status)`, `(chapter_id, position)`, `(scene_id, position)`, `(participant_id, campaign_id)`, `(character_id, item_id)` e datas do histórico.

## Autenticação implementada na Etapa A

- Cadastro público de jogador em `POST /api/auth/register` com nome de usuário único e senha de 12 a 128 caracteres. Não é necessário e-mail; a senha não é armazenada em texto puro.
- Login e consulta de sessão de jogador em `POST /api/auth/login` e `GET /api/auth/session`; login administrativo e sessão separados em `POST /api/auth/admin/login` e `GET /api/auth/admin/session`.
- Logout revoga a sessão no servidor em `POST /api/auth/logout` ou `POST /api/auth/admin/logout`. Os tokens opacos são entregues em cookies `HttpOnly`; somente o hash do token é persistido. Sessões administrativas e de jogador têm públicos e durações separados.
- Limitação persistida por IP e usuário: cinco tentativas em quinze minutos acionam bloqueio de quinze minutos, configurável por ambiente. Requisições de escrita também verificam a origem configurada.
- `python -m app.cli create-admin` pede nome de usuário e senha de pelo menos 12 caracteres de forma oculta, mas sua implementação valida e aceita exclusivamente os alvos PostgreSQL locais de teste autorizados (`cronicas_do_reino_test` e schemas de teste). Não é um procedimento de bootstrap de produção e não deve ser apontado a outro banco. O cadastro público sempre define `is_admin=false`; não existe promoção pelo próprio usuário.
- A H.10 adiciona `prepare-admin-bootstrap` e `bootstrap-admin`, comandos de operação que permanecem fora da API pública, exigem target de produção explicitamente habilitado e criam somente um usuário novo. A concessão temporária e consumida é persistida como hash na migration `d129a4c7e601`, ainda não aplicada. O fluxo exige Linux, arquivo temporário protegido em `/run/admin-bootstrap` e aprovação/configuração operacional; não é uma credencial padrão nem deve ser executado antes da revisão do runbook [H.10](./etapa-h10-admin-bootstrap-operations.md). O CLI lê `DATABASE_URL` do ambiente do processo e não carrega `.env`.
- **Bootstrap administrativo de produção não implementado.** Não há credencial padrão nem criação automática. Até existir um procedimento operacional aprovado e específico para o ambiente de produção, o administrador precisa ser provisionado por um fluxo seguro de operação fora do cadastro público; não usar o comando de teste nem alterar permissões manualmente como substituto.
- Configuração por ambiente: `DATABASE_URL`, `FRONTEND_ORIGINS`, `APP_ENVIRONMENT`, `COOKIE_SECURE`, `PLAYER_SESSION_HOURS`, `ADMIN_SESSION_HOURS`, `AUTH_RATE_LIMIT_ATTEMPTS`, `AUTH_RATE_LIMIT_MINUTES` e `AUTH_LOCKOUT_MINUTES`. Defina `APP_ENVIRONMENT=development` para desenvolvimento local com HTTP e `COOKIE_SECURE=false`. Em produção, defina `APP_ENVIRONMENT=production` e `COOKIE_SECURE=true`; a aplicação falha na inicialização se `COOKIE_SECURE=false` fora do desenvolvimento explicitamente identificado. Se `APP_ENVIRONMENT` estiver ausente, cookies inseguros também são rejeitados; com valor inválido, a configuração falha na validação.
- A autenticação está implementada, mas recuperação de conta e gestão de sessões/dispositivos não fazem parte desta etapa. O Painel do Mestre persiste conteúdo oficial no servidor; campanhas, jogadores e personagens são telas somente de consulta, conforme o fluxo de criação e gestão dos jogadores.

## Campanhas persistentes e lobby implementados na Etapa B

| Método | Endpoint                        | Regra principal                                                                                              |
| ------ | ------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `POST` | `/api/campaigns`                | Cria campanha privada, código único `RZ-#####`, proprietário como participante e personagem inicial próprio. |
| `GET`  | `/api/campaigns`                | Lista campanhas próprias ou associadas; inclui estado de associação para retornar a salas deixadas.          |
| `GET`  | `/api/campaigns/{id}`           | Retorna o lobby apenas a um participante ativo.                                                              |
| `GET`  | `/api/campaigns/{id}/members`   | Lista participantes ativos da campanha a membros ativos.                                                     |
| `POST` | `/api/campaigns/join`           | Entra com código; verifica validade, estado, capacidade e associação duplicada.                              |
| `POST` | `/api/campaigns/{id}/leave`     | Marca participante como ausente sem apagar personagem nem código. A vaga do proprietário fica reservada.     |
| `POST` | `/api/campaigns/{id}/ready`     | Altera somente a preparação do próprio participante enquanto aguarda.                                        |
| `POST` | `/api/campaigns/{id}/presence`  | Atualiza heartbeat do participante autenticado.                                                              |
| `POST` | `/api/campaigns/{id}/character` | Altera somente o nome do personagem próprio associado à campanha.                                            |
| `POST` | `/api/campaigns/{id}/start`     | Somente o proprietário inicia; servidor valida mínimo/máximo e personagens, cria sessão e evento inicial.    |

- Os estados novos são `waiting`, `in_progress` e `closed`. O limite total configurável na criação é de 3 a 5 participantes; o mínimo é 3. O proprietário conta como participante e sua vaga é reservada ao sair.
- O proprietário é o criador da sala, mas não recebe papel ou permissões de mestre do jogo. O código de entrada é permanente e serve como convite compartilhável.
- Participantes e personagens são persistidos em `campaign_members` e `characters`. O vínculo composto exige que o personagem pertença à mesma campanha e conta associada. Campos existentes para HP, mana, atributos, itens e habilidades e tabelas de sessão/eventos continuam sendo a base para a progressão posterior.
- `current_chapter_id`, `current_node_id` e `last_activity_at` ficam na campanha. O início agora seleciona conteúdo publicado, congela seu snapshot em `GameSession.state` e registra `campaign_started`. Votos, decisões, consequências narrativas e avanço são persistidos; inventário e combate ainda não têm operações HTTP.
- O lobby atualiza por polling e heartbeat (45 segundos para considerar uma conexão ativa); essa presença é aproximada e não é uma sessão WebSocket. O banco permanece a fonte oficial dos dados.
- A busca de código inválido usa os limites persistidos de tentativas do backend para reduzir enumeração. Campanhas fechadas não aceitam novos participantes.
- As migrações não foram aplicadas em PostgreSQL neste ambiente porque nenhum executável/serviço está disponível localmente; o resultado de SQLite não deve ser interpretado como validação PostgreSQL.

## Progressão narrativa e votação da Etapa D

| Método | Endpoint                            | Regra principal |
| ------ | ----------------------------------- | --------------- |
| `POST` | `/api/campaigns/{id}/start`         | Cria snapshot da história publicada, seleciona capítulo/cena iniciais e abre a primeira votação. |
| `GET`  | `/api/campaigns/{id}/game`          | Retorna cena/sessão persistentes, escolhas, personagens, votação, resultado e histórico. |
| `POST` | `/api/campaigns/{id}/game/vote`     | Valida associação ativa, sessão, rodada e escolha; registra ou altera o voto conforme configuração. |

- A campanha guarda `voting_settings`: `allow_vote_change`, `deadline_seconds` opcional e `tie_breaker` (`unresolved` ou `choice_order`). A configuração é copiada para a sessão no início e não muda retroativamente.
- A contagem maior vence; em empate, `choice_order` escolhe a menor posição cadastrada, enquanto `unresolved` registra o resultado sem aplicar consequência ou avançar.
- A votação encerra com todos os participantes elegíveis ou com o prazo. O polling detecta prazo vencido; não existe worker de temporizadores.
- A apuração e o avanço ocorrem numa transação com `GameSession` bloqueada; eventos e decisões têm chaves idempotentes. O teste simultâneo exige PostgreSQL e é ignorado em SQLite, que não suporta `SELECT FOR UPDATE`.
- Consequências textuais cadastradas são copiadas para o estado e histórico uma única vez; efeitos sobre personagem, inventário, XP, combate ou economia não são executados.
- As expressões de condições ainda não têm gramática/avaliador e não filtram as escolhas. Destino explícito inativo impede o início; destino vazio avança em ordem para a próxima cena ou capítulo publicado.
- Consulte [`narrative-progression.md`](./narrative-progression.md) para detalhes, políticas escolhidas e pendências.

## Operações administrativas comuns

Para campanhas, capítulos, cenas, participantes, personagens, NPCs, criaturas, habilidades, itens, recompensas e regras de drop, oferecer operações equivalentes a:

- **Criar:** validar campos e permissões, atribuir ID no servidor e validar todos os relacionamentos antes de persistir.
- **Consultar:** obter registro por ID e listar com paginação, ordenação, busca e filtros de domínio; limitar resultados à campanha autorizada.
- **Atualizar:** aceitar somente campos editáveis, verificar relações e limites, atualizar `updated_at` e preservar a consistência de dados associados.
- **Excluir:** verificar referências; aplicar exclusão lógica ou rejeitar com conflito quando há dependências/histórico que não podem ser descartados.

O contrato de lista deve retornar resultados e metadados de paginação. Respostas não devem expor dados privados de outros participantes nem segredos de integração.

## Operações específicas de campanhas

- Criar campanha com limites padrão de 3 a 5 participantes, status inicial planejado e administrador proprietário.
- Consultar campanhas visíveis ao administrador/participante; filtrar por status e pesquisar título.
- Atualizar descrição, status, limites, estado do mundo e capítulo atual. Confirmar que o capítulo atual pertence à campanha.
- Adicionar/remover participante, alterar estado de participação e listar personagens associados.
- Iniciar, pausar, concluir ou reabrir uma campanha com validação explícita de transição e evento de auditoria.
- Remover uma campanha somente após definir o tratamento dos seus capítulos, votos, transações e personagens.

## Operações de personagens e inventário

- Criar/consultar/editar personagem verificando participante e campanha; atualizar atributos, HP, mana, XP, nível e moedas com regras de domínio configuráveis.
- Consultar ficha detalhada com equipamentos, inventário, habilidades aprendidas e histórico de transações.
- Adicionar, atualizar quantidade e remover item do inventário; impedir quantidade negativa e verificar estoque/regras se a origem for compra ou drop.
- Equipar/desequipar item validando categoria, requisitos, propriedade e slots exclusivos.
- Aplicar recompensa de ouro/XP/itens atomicamente e registrar transação/auditoria correspondente.
- Permitir transferência entre personagens somente se a regra da campanha habilitar e sempre registrar origem e destino.

## Operações futuras de autoria e regras de história

- Criar, consultar, atualizar e ordenar capítulos e cenas; ordenar diálogos, escolhas e associações de NPCs/encontros.
- Validar que o destino de uma escolha pertence à mesma campanha e que condições/efeitos têm formato aceito pelo motor de regras. Não executar texto arbitrário fornecido pelo usuário.
- Publicar/recolher capítulo ou cena respeitando permissões e manter registro de alterações.
- Definir e implementar a gramática de condições antes de filtrar opções.
- Definir um formato estruturado para efeitos mecânicos de consequência antes de alterar atributos ou inventário.
- Decidir quais novas regras de desempate e transições de sessão podem ser configuradas sem conceder poderes de mestre a um jogador.

## Operações futuras de combate e recompensas

- Criar encontro a partir de criaturas e quantidades; persistir instância do combate, participantes, ordem de turno e estado temporário sem alterar o bestiário base.
- Validar uso de habilidade por nível, alvo, custo de mana, recarga, alcance e estado atual; resolver dano, cura, resistências, fraquezas e efeitos em uma transação consistente.
- Registrar início/fim de turno e combate, alterações de HP/mana e resultados de forma auditável e idempotente.
- Consultar e configurar tabela de drop; sortear resultados no servidor com fonte segura de aleatoriedade e persistir os itens concedidos.
- Conceder XP, moedas e itens ao terminar encontro/missão sem duplicação em retries; gerar transações e atualizar inventários atomicamente.
- Manter regras de combate configuráveis por campanha e versionadas para que alterações futuras não mudem retroativamente resultados já concluídos.

## Separação entre dados do servidor e demonstração

- `src/services/dataService.ts` consulta a API para campanhas, jogadores, personagens, capítulos, NPCs, monstros, habilidades, itens, transações, recompensas e regras de drop. Erros nessas coleções devem permanecer visíveis; não substituir a resposta por dados locais.
- Eventos recentes e algumas preferências da interface ainda usam dados locais de demonstração. A restauração da demonstração não limpa nem substitui conteúdo do servidor.
- O tipo da interface chama `startChapterId` o capítulo que a API representa como capítulo corrente; revisar essa semântica quando houver fluxo de progressão de história.
- A demonstração contém dados ilustrativos, inclusive conteúdo provisório. Não migrá-los como dados de usuários reais nem combiná-los silenciosamente com o catálogo PostgreSQL.
- Componentes devem continuar desacoplados da persistência, com UUIDs do servidor, estados explícitos de carregamento/erro e filtros/paginação no backend quando as coleções crescerem.
