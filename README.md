# Crônicas do Reino

Plataforma em construção para RPG de fantasia. O frontend usa TanStack Start/Router, React, TypeScript, Tailwind CSS e componentes Radix/shadcn. O backend inicial fica em `backend/` e usa FastAPI, SQLAlchemy assíncrono, Alembic e PostgreSQL.

## Frontend

Requisitos: Node.js e npm.

```powershell
npm install
npm run dev
```

Para validar as alterações:

```powershell
npm test
npm run lint
npm run build
```

Rotas atuais: `/` é a página pública, `/admin` é o Painel do Mestre, `/play` lista as campanhas reais do jogador, `/campaigns/:campaignId` é o lobby autenticado, `/login` e `/register` são os formulários de jogador e `/admin/login` é o acesso separado do administrador. História, NPCs, itens, monstros, habilidades, transações, recompensas, drops e configurações oficiais do painel usam a API; eventos recentes e algumas preferências visuais continuam demonstrativos/locais. Campanhas, jogadores e personagens são telas somente de consulta no painel.

## Backend inicial

Requisitos: Python 3.11+ e PostgreSQL. Em um terminal PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edite `backend/.env` com a URL do banco de desenvolvimento. O exemplo também define uma URL separada para o banco local exclusivo de testes PostgreSQL. Os testes comuns continuam usando SQLite; somente os testes marcados executam contra `TEST_DATABASE_URL`. As instruções de instalação, inicialização e preparação do PostgreSQL estão em [`docs/postgresql-development.md`](./docs/postgresql-development.md). Neste ambiente, PostgreSQL já está instalado e ativo; `.env` real não deve ser compartilhado nem enviado ao Git.

Em uma instalação nova, com autorização e antes de iniciar o uso, aplique as migrações por procedimento separado. Para desenvolvimento local, crie o administrador exclusivamente pelo comando restrito `create-local-admin`, que verifica o destino `cronicas_do_reino_dev` antes de pedir credenciais; `create-admin` é reservado aos schemas isolados de teste. Não há credenciais padrão. Não execute migrações como parte da validação visual da Etapa G:

```powershell
Set-Location backend
$env:APP_ENVIRONMENT = "development"
.\.venv\Scripts\python.exe -m app.cli create-local-admin
uvicorn app.main:app --reload
```

O procedimento de criação local, os limites de destino e os prompts seguros estão em [`docs/postgresql-development.md`](./docs/postgresql-development.md). Migrações não são executadas pelo comando de criação do administrador.

O backend oferece cadastro/login de jogador, sessão por cookie, login administrativo separado, logout e limitação persistida de tentativas. As rotas administrativas de conteúdo exigem uma sessão admin também no servidor. A API responde em `http://127.0.0.1:8000/health`; a documentação OpenAPI fica em `/docs`. Na Etapa G, a suíte backend passou com 38 testes (incluindo os 10 testes PostgreSQL) na validação anterior à correção final de frontend. Após essa correção, a suíte frontend passou com 11 testes, TypeScript e build passaram e ESLint terminou sem erros e com 7 avisos preexistentes. A validação visual confirmou login administrativo sintético, leitura de capítulos e partidas com três, quatro e cinco participantes; a recuperação após reload foi confirmada para a sessão de cinco participantes. A comparação read-only da metadata Alembic não encontrou diferenças, mas o schema visual de teste não possui `alembic_version` e, portanto, não registra uma revisão. Nenhuma migration foi executada. As limitações visuais e o registro completo da Etapa G, incluindo a preparação sem implementação da Etapa H, estão em [`docs/multiplayer-visual-validation.md`](./docs/multiplayer-visual-validation.md).

Campanhas podem ser criadas por jogadores autenticados, com código permanente, proprietário como participante e personagem inicial próprio. Jogadores entram por código; sair mantém a associação e permite reentrada, com a vaga do proprietário reservada enquanto estiver fora. O lobby lista participantes/personagens, permite alterar o próprio nome de personagem e marcar preparação. Só o proprietário inicia a sala; ele não recebe poderes de mestre durante a partida. Ao iniciar, a API carrega o primeiro capítulo publicado e a cena inicial, congela o conteúdo oficial em um snapshot persistente e abre a votação configurada para a campanha. Votos, consequências narrativas e histórico ficam no banco; reentrar recupera o progresso. A interface consulta a API por polling, sem WebSockets. Os detalhes e as decisões de regra estão em [`docs/narrative-progression.md`](./docs/narrative-progression.md).

A progressão dos personagens concede XP, evolução, ouro, itens e habilidades do catálogo pelo backend, com idempotência e histórico persistido na ficha. Escolhas narrativas podem avançar objetivos e concluir missões publicadas atribuídas ao personagem na mesma transação da decisão vencedora. O Painel do Mestre inclui gestão de missões e atribuição a personagens ativos da campanha. O sistema de combate por turnos está implementado com configuração administrativa, animações, resolução autoritativa do backend, idempotência e estratégias de IA; os fundamentos estão em [`docs/etapa5-missions-combat-foundation.md`](./docs/etapa5-missions-combat-foundation.md), o motor está em [`docs/etapa-h4-combat-engine.md`](./docs/etapa-h4-combat-engine.md) e a progressão em [`docs/character-progression.md`](./docs/character-progression.md).

O Painel do Mestre também possui uma Biblioteca de Assets para imagens persistentes, metadados e associações com entidades, com uploads validados no backend e GIFs analisados sem alterar os arquivos originais. A arquitetura, endpoints, configuração de volume persistente e pendências da Etapa H.1 estão em [`docs/etapa-h1-asset-library.md`](./docs/etapa-h1-asset-library.md).

O frontend usa `http://127.0.0.1:8000` por padrão. Para outra origem, configure `VITE_API_URL` no ambiente do frontend e inclua essa origem em `FRONTEND_ORIGINS` no backend. Execute os testes backend comuns dentro de `backend/` com `py -m pytest`; testes específicos de PostgreSQL exigem a URL local descartável e `py -m pytest -m postgres`. Testes PostgreSQL ignorados não contam como validação do banco.

Para experimentar duas contas, inicie API e frontend e abra duas sessões de navegador isoladas (por exemplo, uma janela normal e uma janela privada). Cadastre/entre com a primeira conta, crie uma campanha e compartilhe o código. Na segunda sessão, cadastre/entre com outra conta e use o código em `/play`; ambas devem ver a sala e seus personagens. Com três participantes ativos, a primeira conta poderá iniciar. Saia e entre novamente usando o código para confirmar que a sala e o personagem persistem. Os navegadores precisam apontar para a mesma API e banco.

Ainda não existe CRUD administrativo de campanhas, IA narrativa completa, condições de cena executáveis, WebSockets ou integração real com Discord. Regras comerciais e transações são armazenadas, mas ainda não executam compra/venda. Eventos de atividade e algumas preferências visuais permanecem locais. A API administrativa e seus modelos estão descritos em [`docs/admin-content-api.md`](./docs/admin-content-api.md); requisitos futuros estão em [`docs/backend-requirements.md`](./docs/backend-requirements.md). O esquema ORM fica em `backend/app/models/`; para futuras mudanças de esquema:

```powershell
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

## Dados e arquitetura

Os registros oficiais conectados não usam `localStorage` como fonte de persistência. A demonstração continua isolada e pode ser restaurada em **Configurações**, sem substituir dados oficiais do servidor.

Veja [`docs/platform-architecture.md`](./docs/platform-architecture.md) para a arquitetura atual e [`docs/backend-requirements.md`](./docs/backend-requirements.md) para entidades e operações futuras da API.
