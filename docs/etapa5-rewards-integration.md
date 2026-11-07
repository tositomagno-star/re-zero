# Etapa 5.2 — Integração de recompensas com aventuras

## Entrega

A resolução autoritativa do voto vencedor agora integra a progressão existente:

- Escolhas publicadas podem apontar para até 100 `world_reward_ids` e
  `complete_quest_ids`, sem duplicatas.
- O backend resolve IDs e valores a partir do snapshot narrativo e dos modelos
  oficiais. Recompensas precisam estar ativas; missões precisam estar
  publicadas e pertencer à campanha.
- Cada personagem de participante ativo e elegível recebe uma recompensa de
  catálogo. Uma recompensa de missão só é processada para personagem com a
  missão atribuída e em andamento; os demais não recebem a recompensa da
  missão.
- XP, evolução, ouro, itens, habilidades definidas pelo sistema de progressão,
  conclusão da missão e eventos narrativos são aplicados na transação do voto.
  Erro em qualquer concessão reverte a decisão e todas as recompensas.
- Chaves idempotentes derivadas da decisão, origem e personagem impedem
  duplicação em repetições. Locks por campanha/ personagem protegem operações
  simultâneas no mesmo processo; o banco mantém a restrição única e o
  `SELECT FOR UPDATE` onde suportado.
- O histórico guarda tipo, ID e nome da origem no payload persistido da
  recompensa. A API devolve esses dados e os itens na ficha; registros legados
  sem identificação de origem continuam compatíveis.
- A interface mostra XP, ouro e itens concedidos no evento da aventura e a ficha
  identifica a origem e os itens no histórico.

Não foram adicionados modelos paralelos, colunas nem alterações de schema. Os
IDs e nomes da origem ficam no `reward_payload` JSON existente. Nenhuma
migration ou DDL foi executado. Para implantar a progressão em um banco ainda
não preparado, continua necessária a migration já criada
`a41b9e2d7c10_character_progression`; ela não foi aplicada nesta execução.

## Arquivos alterados

- Backend: `app/services/narrative.py`, `app/services/progression.py`,
  `app/api/campaigns.py`, `app/schemas/campaigns.py`.
- Testes backend: `tests/test_narrative.py`, `tests/test_progression.py`.
- Frontend: `src/components/admin/StoryPage.tsx`,
  `src/components/player/CampaignPages.tsx`,
  `src/components/player/CharacterSheet.tsx`, `src/lib/auth-api.ts`,
  `src/services/dataService.ts`, `src/types/entities.ts`.
- Testes frontend: `src/test/campaign-api.test.ts`,
  `src/test/player-onboarding.test.tsx`, `src/test/story-admin.test.tsx`.
- Documentação: `README.md`, `docs/admin-content-api.md`,
  `docs/character-progression.md`, `docs/narrative-progression.md` e este
  relatório.

## Regras e limitações

O formato de consequências aceita somente referências de conteúdo publicadas
pelo servidor, não quantidades fornecidas pelo cliente. Uma consequência
inválida ou recompensa indisponível falha integralmente. O conteúdo é
distribuído aos personagens dos participantes ativos congelados como elegíveis
na sessão. Conclusão de missão não significa que ela foi automaticamente
atribuída: sem vínculo em andamento, não há concessão daquela missão.

A gestão administrativa de missões e atribuições foi adicionada na etapa 5.3;
consulte [`etapa5-missions-combat-foundation.md`](./etapa5-missions-combat-foundation.md).
O editor narrativo ainda referencia IDs/UUIDs explicitamente. Recompensas de
combate não foram implementadas porque o combate não está implementado. Não foi
feita validação visual manual em browsers independentes nem teste PostgreSQL
nesta execução.

## Verificações

Executadas sem usar PostgreSQL:

- Backend: `py -m pytest -q -m "not postgres"` — **142 passaram, 12 foram
  excluídos**, em 29,20 s.
- Compilação Python: `py -m compileall -q app tests` — **sucesso**.
- Frontend: `vitest run` — **48 testes passaram em 6 arquivos**.
- TypeScript: `tsc --noEmit` — **sucesso**.
- Build: `vite build` — **sucesso**. O Vite emitiu apenas aviso informativo
  sobre `vite-tsconfig-paths`.
- ESLint: `eslint src` — **0 erros e 7 avisos** preexistentes de
  `react-refresh/only-export-components`.

Os 12 testes PostgreSQL foram explicitamente excluídos. O perfil MCP e o
isolamento do banco de teste continuam sem comprovação suficiente para escrita.
Não foram iniciados servidores ou browsers para validação de integração real.

## Integridade e próximos passos

Nenhuma migration, DDL, TRUNCATE, DELETE, DROP, grant ou mudança de credencial
foi executada. `cronicas_do_reino_dev` não foi acessado nem alterado; os testes
executados usaram a configuração segura local SQLite. Credenciais e permissões
permaneceram intocadas.

Próximas pendências: integrar recompensas quando existir o sistema de combate; validar concorrência entre
workers em PostgreSQL somente após comprovar o isolamento; e realizar validação
visual e integrada em sessões de navegador independentes.
