# Etapa 5.3 — Gestão de missões e base para combate

## Funcionalidades entregues

- Painel administrativo com criação/edição de missões por campanha, publicação,
  despublicação, objetivos, regra de conclusão (todos ou pelo menos um),
  recompensas de XP/ouro/itens/habilidades e lista de atribuições/estado.
- Atribuição administrativa somente a personagens ativos que tenham vínculo
  válido com a campanha selecionada. Repetir a atribuição não cria outra linha.
- Jogadores consultam missões publicadas e missões em andamento/concluídas da
  própria campanha e personagem, aceitam missões disponíveis e veem metas,
  progresso e recompensas. A ficha recupera o estado persistido após reload.
- O jogador não possui endpoint de progresso/conclusão. Objetivos avançam pelo
  resultado de uma escolha narrativa resolvida no backend. `complete_quest_ids`
  só conclui a missão após validar seus objetivos.
- Condições e recompensas são copiadas para `CharacterQuest.progress` na
  atribuição; atualizações futuras do catálogo não alteram a missão já
  atribuída. A progressão, a conclusão e as recompensas mantêm a transação e as
  chaves idempotentes existentes.
- IDs de objetivo e regras são validados no schema administrativo. Updates
  narrativos repetidos são deduplicados por hash da decisão/origem/objetivo.

## Persistência e alterações de banco

As tabelas existentes `quests` e `character_quests` foram reutilizadas. Os
objetivos/condições, recompensas, snapshots e progresso ficam nas colunas JSON
existentes. Não foi necessário novo campo/tabela e nenhuma migration, DDL,
operação destrutiva ou conexão PostgreSQL foi executada.

## Arquivos

- Backend: `backend/app/api/admin_content.py`,
  `backend/app/api/campaigns.py`, `backend/app/schemas/campaigns.py`,
  `backend/app/schemas/quests.py`, `backend/app/services/narrative.py`,
  `backend/app/services/progression.py`.
- Testes backend: `backend/tests/test_admin_content.py`,
  `backend/tests/test_campaigns.py`, `backend/tests/test_narrative.py`.
- Frontend: `src/components/admin/AdminApp.tsx`,
  `src/components/admin/MissionManagementPage.tsx`,
  `src/components/admin/StoryPage.tsx`,
  `src/components/player/CharacterSheet.tsx`, `src/lib/auth-api.ts`,
  `src/services/dataService.ts`, `src/types/entities.ts`.
- Testes frontend: `src/test/mission-management.test.tsx`,
  `src/test/player-onboarding.test.tsx`.
- Documentação: `README.md`, `docs/admin-content-api.md`,
  `docs/character-progression.md`, `docs/narrative-progression.md` e este
  documento. A arquitetura de combate proposta está abaixo.

## Proposta técnica para combate (não implementado)

### Estado observado

- `Character` tem HP/mana atuais e máximos, nível e `attributes` JSON; o modelo
  não impõe um vocabulário de atributos ofensivos/defensivos.
- `Skill` possui custo de mana, alvo, recarga, requisitos e `effects` JSON,
  mas os efeitos ainda não têm contrato mecânico validado.
- `Item` possui `effects`, `attributes`, requisitos e informação de
  equipamento; não há resolução ativa de efeitos no combate.
- `Enemy` oferece nível, HP, ataque, defesa, velocidade, resistências,
  fraquezas, habilidades e recompensas. `DropRule` já expressa chance em pontos
  base.
- `Encounter` e `Combatant` existem, com configuração JSON, iniciativa, HP
  atual e condições, mas não há serviço, rotas ou fluxo de turno de combate.
- `Combatant` impede mais de uma instância do mesmo inimigo por encontro pela
  restrição única `(encounter_id, enemy_id)`. Combates com cópias do mesmo tipo
  exigirão uma migração para identidade de instância/slot.
- `CharacterRewardGrant` e `apply_character_reward` já suportam XP, ouro,
  itens, habilidades e idempotência; esse deve continuar sendo o único caminho
  de concessão.

### Arquitetura sugerida

1. Criar um serviço de domínio isolado (`combat.py`) e schemas estritos para
   iniciar encontro, ação do turno e estado público. Nenhum endpoint aceitará
   HP, mana, dano ou recompensa calculados pelo cliente.
2. Ao iniciar, bloquear campanha/encontro, validar sessão e participantes
   ativos, e gravar um snapshot imutável dos personagens, monstros, habilidades
   e equipamentos participantes. A iniciativa e o estado atual do turno devem
   ser persistidos; reenvio de uma ação recebe resposta idempotente.
3. Resolver ordem, alvo, alcance, custo de mana, cooldown e efeitos apenas no
   backend. Ações inválidas ou de combatente fora do turno não alteram o
   estado. Atualizações de HP, mana, condições e turno são atômicas.
4. Registrar eventos com sequência monotônica por encontro para permitir
   auditoria, reload e sincronização entre sessões. Locks por encontro/campanha
   e unicidade da chave de ação protegem requisições simultâneas.
5. Determinar vitória/derrota ao resolver cada ação. Somente a transição
   terminal autoritativa pode conceder XP/loot via `apply_character_reward`,
   usando chave derivada do encontro e personagem; `DropRule` fornece chance e
   limites de quantidade sem concessão no frontend.

### Regras ainda sem decisão de balanceamento

Não há hoje fórmula única compatível com os JSONs de atributos/efeitos. Para a
próxima etapa, centralizar em `combat_rules.py` uma configuração versionada
para:

- iniciativa (por exemplo, rolagem controlada pelo servidor mais velocidade,
  com desempate estável);
- ataque físico/mágico, defesa e dano mínimo/máximo;
- aplicação e ordem de resistências/fraquezas;
- semântica de efeitos de habilidade e itens, alvos/área e duração;
- recuperação/custos e limites de mana/cooldown;
- condição de vitória/derrota e regra de fuga/empate.

Como proposta inicial a discutir, usar `d20 + velocidade` para iniciativa e
`max(dano_mínimo, ataque + potência_da_habilidade - defesa)` antes de aplicar
resistência/fraqueza. Isso **não foi implementado nem usado para alterar
personagens**. A semântica atual dos atributos e do JSON `effects` precisa ser
definida antes de adotar essa fórmula.

### Possíveis mudanças futuras de schema

- Uma tabela `combat_events` com chave única por `(encounter_id, sequence)` e
  `(encounter_id, idempotency_key)` para histórico confiável.
- Uma identidade de instância em `Combatant` e alteração da unicidade atual
  para permitir múltiplos exemplares de um inimigo.
- Campos explícitos de rodada/turno/versão de estado se não forem mantidos no
  snapshot de `Encounter.configuration`.

Qualquer migration fica para a etapa de combate e só deve ser aplicada em
ambiente autorizado. Nenhuma alteração de schema foi aplicada nesta etapa.

## Verificações

- Backend seguro (SQLite): `146 passed, 12 deselected` com
  `pytest -q -m "not postgres"`; os testes PostgreSQL foram excluídos.
- Frontend: `51 passed` em 7 arquivos de teste (`npm test`).
- TypeScript: `npm exec -- tsc --noEmit` concluído com código 0.
- Build: `npm run build` concluído com código 0. O Vite exibiu um aviso
  informativo sobre resolução nativa de aliases; a compilação terminou.
- ESLint: `npm run lint` concluído com código 0, sem erros e com 7 avisos
  `react-refresh/only-export-components` em componentes existentes.
- Python: `python -m compileall -q app` concluído com código 0.
- Validação visual manual em navegador/resoluções: não executada.

O pytest foi executado com `APP_ENVIRONMENT=development` para satisfazer a
validação local de configuração do cookie; os testes não-postgres criaram e
usaram o banco SQLite isolado definido pelo fixture. Nenhum teste PostgreSQL
foi iniciado.

## Limites de segurança e pendências

- Nenhum banco PostgreSQL, em especial `cronicas_do_reino_dev`, foi acessado;
  credenciais, perfis, roles e permissões não foram alterados.
- Não foram executadas migrations, DDL, TRUNCATE, DELETE ou DROP.
- A edição das escolhas narrativas referencia UUIDs e IDs de objetivo em texto;
  um seletor visual de missões/objetivos pode melhorar essa UX depois.
- O combate não foi implementado nem validado. Persistência de eventos,
  múltiplas instâncias de inimigos e regras de balanceamento dependem da
  definição técnica e da migration futura.
