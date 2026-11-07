# Arquitetura inicial da plataforma

## Limites por área

| Área               | Rota                           | Situação atual                                                                                                    |
| ------------------ | ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Entrada pública    | `/`                            | Página institucional com links para as áreas em construção.                                                       |
| Painel do mestre   | `/admin`, `/admin/login`       | Sessão administrativa; história e catálogos oficiais usam API protegida no servidor. |
| Área do jogador    | `/play`                        | Lista campanhas reais do jogador por meio da API autenticada.                                                     |
| Lobby e partida    | `/campaigns/:campaignId`       | Lobby persistente e progressão narrativa por cenas, escolhas, votação e histórico; polling a cada cinco segundos. |
| Entrar / cadastrar | `/login`, `/register`          | Formulários conectados à API para login/cadastro por username e PIN de seis dígitos.                              |
| API                | `backend/`                     | FastAPI com autenticação, campanhas/lobby, endpoints administrativos de conteúdo, leituras de conteúdo publicado e SQLAlchemy. |
| PostgreSQL         | configurado por `DATABASE_URL` | Banco oficial configurável; PostgreSQL real não estava instalado/disponível para validação nesta etapa.            |

## Fronteiras e responsabilidades

- **Frontend:** TanStack Start/Router e React. `src/lib/auth-api.ts` cuida de autenticação/campanhas e `src/services/dataService.ts` roteia as coleções oficiais do painel para a API. Eventos de atividade e algumas preferências visuais continuam demonstrativos; falhas da API nas coleções oficiais são exibidas, sem fallback silencioso.
- **Painel administrativo:** `/admin` consulta a sessão administrativa antes de renderizar o painel; os endpoints de conteúdo validam novamente a sessão e a origem no servidor. Campanhas, jogadores e personagens são apenas consultas administrativas.
- **API:** `backend/app/main.py` registra autenticação, campanhas/lobby, progressão narrativa, saúde e conteúdo. Rotas administrativas de capítulo/cena, NPC, item, monstro, habilidade, drop, recompensa, configuração e transação exigem `current_admin`. Partida e votação exigem participante ativo e validação no servidor. O contrato administrativo está em `docs/admin-content-api.md`; a progressão está em `docs/narrative-progression.md`.
- **Persistência:** SQLAlchemy assíncrono mapeia o esquema para PostgreSQL e Alembic mantém migrações incrementais. `GameSession.state` mantém snapshot/configuração/progresso, `StoryVote` mantém o voto atual por jogador/rodada, e `GameEvent` registra mudanças e resultados. Testes comuns usam SQLite; testes marcados `postgres` só usam o banco local exclusivo configurado em `TEST_DATABASE_URL`. PostgreSQL real ainda precisa ser validado.
- **Atualização do lobby:** polling a cada cinco segundos e heartbeat a cada quinze segundos. O estado de conexão expira após 45 segundos; é somente uma aproximação de presença. WebSockets ficam para etapa futura.
- **Progressão narrativa:** o início carrega o primeiro capítulo publicado/ativo e sua primeira cena ativa, congelando capítulos, cenas e escolhas na sessão. A votação e a apuração são transacionais, com bloqueio da sessão no PostgreSQL e eventos idempotentes. O frontend faz polling; não há WebSocket.
- **Integrações:** há metadados para preparar vínculos de Discord. OAuth, bot, tokens e segredos não são implementados nem armazenados nesse esquema.

## Modelo inicial

Os modelos em `backend/app/models/entities.py` cobrem:

- contas, perfis e identificadores externos (`User`, `PlayerProfile`, `ExternalIdentity`);
- campanhas, membros, convites e personagens;
- capítulos, nós narrativos, escolhas e votos;
- itens, inventários, habilidades e habilidades de personagens;
- criaturas, encontros, combatentes e sessões/eventos;
- transações, notificações e metadados de guild/canais Discord.
- NPCs, diálogos, relacionamentos com personagens, missões e regras de drop.

As regras que atravessam relacionamentos — autorização de campanha, propriedade de personagens, validação de escolhas, votação e aplicação de recompensas — são validadas na API. Consequências ainda são registradas como conteúdo narrativo; não alteram atributos ou inventário. Chaves estrangeiras e restrições SQL são complementares, não substitutas dessas regras.

## Etapas seguintes

1. Validar conexão, migrações e transações concorrentes no PostgreSQL real usando um banco de teste descartável; não foi possível nesta etapa porque PostgreSQL e Docker não estão disponíveis. Consulte `docs/postgresql-development.md`.
2. Definir e implementar a gramática de condições narrativas e o contrato para efeitos mecânicos de consequência, sem misturá-los com esta progressão narrativa.
3. Decidir se sessões poderão ser reiniciadas e quais estratégias adicionais de desempate serão aceitas.
4. Definir eventos WebSocket autenticados/autorizados se o polling deixar de atender à experiência necessária.
5. Implementar combate, economia, auditoria, recompensas e integrações em etapas com testes de domínio e concorrência.

Cada etapa deve manter a demonstração claramente identificada e não migrar dados fictícios como dados reais. Consulte também `docs/backend-requirements.md` para o contrato funcional futuro.
