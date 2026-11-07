# Etapa H.3 — Gerenciamento de entidades

## Escopo e compatibilidade

O painel reaproveita o catálogo e os contratos já existentes em
`backend/app/api/admin_content.py`: `Character`, `NonPlayerCharacter`, `Enemy`, `Item`,
`Skill`, `CharacterItem`, `CharacterSkill` e `DropRule` continuam sendo as entidades
canônicas. A H.3 não cria fichas de jogador nem inventários paralelos. Para personagens
jogáveis, a configuração H.3 só aceita personagens existentes; o CRUD de personagens continua
respeitando proprietário, progressão, inventário e campanha.

As telas administrativas preexistentes continuam responsáveis pelo cadastro dos registros-base:

- **Personagens e NPCs**: personagem jogável existente e NPCs.
- **Criaturas e monstros**: inimigos, atributos, habilidades legadas e recompensas existentes.
- **Magias e habilidades**: catálogo de habilidades.
- **Itens e equipamentos**: catálogo e inventário/equipamento de itens existente.

Cada tela ganhou o painel **Configuração visual e de combate** para persistir o perfil H.3.
O conteúdo novo usa os IDs do registro-base selecionado e mantém campos específicos em um perfil
com FK; não duplica o registro-base.

NPCs, inimigos, itens e habilidades podem ser duplicados pelos formulários CRUD existentes. Um
perfil de configuração também pode ser copiado para outra entidade do mesmo tipo. Personagens
jogáveis não são duplicados no painel, pois cada ficha precisa conservar seu proprietário e
vínculos de campanha.

## Modelo persistente

A revisão Alembic `f19b7c2d4a61` (encadeada após H.2, `ea42d7b190c3`) cria:

- `entity_content_profiles`: exatamente uma FK para personagem, NPC, inimigo, item ou habilidade;
  disponibilidade (`draft`, `available`, `archived`), escala, orientação, posição normalizada,
  atributos numéricos e configurações JSON específicas.
- `entity_content_asset_bindings`: referências com FK para assets H.1 e um slot visual por perfil.
- `entity_content_animation_bindings`: referências com FK para configurações H.2 e um slot por perfil.
- `entity_content_skill_associations`: habilidades associadas a NPCs/inimigos, posição e
  `attack_speed_override` opcional.
- `entity_content_equipment_associations`: itens de equipamento associados ao perfil de NPC.

As FKs impedem referências inexistentes; assets, animações, habilidades e itens referenciados usam
`RESTRICT` para que exclusões sejam recusadas enquanto houver uso. Os slots GIF aceitam somente
`image/gif` e `.gif`; os slots de imagem exigem tipo `image/*`. O backend verifica a disponibilidade
do arquivo no storage. Assets privados podem ser associados por sessão administrativa; a resposta
do perfil não revela URL nem caminho físico, e previews continuam sob os endpoints protegidos da H.1.

As configurações específicas são validadas com schemas estritos no backend:

- Personagem: `actor_type=playable_character`; sem nova ficha ou atributos de campanha.
- NPC: `actor_type` `npc`, `ally` ou `hostile`.
- Inimigo: categoria `common`, `special`, `miniboss` ou `boss`, velocidade padrão de ataque,
  moeda e recompensas especiais configuráveis. XP, drops e recompensas existentes continuam nos
  campos/serviços canônicos.
- Item/arma: tipo, ataque, defesa, alcance, velocidade, efeitos e modo de exibição
  (`with_character`, `follow_character`, `during_strike`, `effect_only`).
- Habilidade: tipo extensível, dano, alcance, alvo, velocidade, duração de deslocamento,
  tempo de impacto, direção e trajetória. Os tempos são campos separados e a execução real não é
  delegada ao editor administrativo.

Trajetórias aceitas: `right_to_center`, `left_to_center`, `right_to_left`, `left_to_right`,
`bottom_to_top`, `top_to_bottom`, `origin_to_target`, `direct_impact` e `area_effect`.
Posições de arena são normalizadas entre 0 e 1; não persistem pixels.

## Contratos administrativos

Todos os endpoints exigem sessão administrativa. Escritas verificam a origem da solicitação.

| Método | Endpoint | Uso |
|---|---|---|
| `GET` | `/api/admin/content/profiles/{entity_type}` | Lista perfis de um tipo (`character`, `npc`, `enemy`, `item`, `skill`). |
| `GET` | `/api/admin/content/profiles/lookup/{entity_type}/{entity_id}` | Recupera o perfil ou `null`. |
| `PUT` | `/api/admin/content/profiles/{entity_type}/{entity_id}` | Cria/atualiza o perfil de uma entidade-base existente; valida campos e todas as referências no backend. |
| `DELETE` | `/api/admin/content/profiles/{entity_type}/{entity_id}?confirm=true` | Remove somente a configuração H.3 após confirmação; preserva o registro-base. |

O corpo de escrita contém `availability`, `scale`, `orientation`, `default_position`, `attributes`,
`settings`, `assets`, `animations`, `skills` e `equipment_ids`. O campo `settings` é validado
conforme o tipo; chaves desconhecidas não são aceitas nos objetos tipados. Uma habilidade de
ataque pode informar `attack_speed_override` positivo; `null` significa usar o padrão da entidade.
O executor de combate ainda deve aplicar essa precedência na futura integração com o combate real.

## Formulários administrativos

No VS Code/site, abrir a área administrativa e acessar **Personagens e NPCs**, **Criaturas e
monstros**, **Itens e equipamentos** ou **Magias e habilidades**. Cadastrar/editar o registro-base
no formulário existente e, em seguida, selecionar esse registro no novo painel de configuração:

1. Escolher rascunho, disponível ou arquivado.
2. Selecionar assets da Biblioteca H.1 por slot e configurações do Editor H.2 por papel.
3. Ajustar escala, orientação e posição normalizada.
4. Em inimigos/NPCs, associar habilidades; a velocidade individual sobrescreve a velocidade padrão
   quando preenchida.
5. Em inimigos, salvar categoria, velocidade padrão, moeda e recompensas especiais. XP e drops
   continuam nos formulários/sistemas existentes.
6. Salvar. Configurações disponíveis exigem referências visuais mínimas, habilidades publicadas e
   itens ativos nas recompensas/equipamentos.

Um perfil existente pode ser duplicado para outra entidade do mesmo tipo. A exclusão confirmada
remove apenas o perfil e as associações dele; não apaga ficha, campanha, inventário ou registro
canônico.

## Disponibilidade e proteção contra regressões

Perfis incompletos não podem ser marcados como disponíveis. O estado também sincroniza as flags de
NPCs, itens, habilidades e inimigos já utilizadas pelo catálogo; personagens jogáveis não têm o
status de campanha alterado pelo perfil visual. Registros legados sem perfil continuam sendo lidos
pelos endpoints existentes.

Exclusões de assets e animações agora também consideram as FKs de perfil H.3 e retornam conflito
quando há associação. A substituição de um arquivo usado como GIF recusa formatos não GIF. O
asset privado não é tornado público pela associação.

## Testes

- Backend: `backend/tests/test_admin_entity_profiles.py`, SQLite isolado; cobre autorização,
  persistência/recuperação, validação de coordenadas e trajetória, asset inexistente/privado/
  indisponível, velocidade específica por ataque e exclusão confirmada.
- Compatibilidade: testes existentes de conteúdo administrativo.
- Frontend: `src/test/entity-profile-editor.test.tsx`, cobrindo configuração de boss, seleção de
  asset, velocidade por ataque, payload de persistência e erro de carregamento.
- Backend seguro: `python -m pytest -q -m "not postgres"` — **162 passed, 12 deselected**.
- Frontend: `npm test` — **10 arquivos, 57 testes aprovados**.
- TypeScript: `npm exec -- tsc --noEmit` — aprovado.
- Build: `npm run build` — aprovado; Vite mostrou um aviso informativo sobre o plugin
  `vite-tsconfig-paths`.
- ESLint: `npm run lint` — **0 erros, 7 warnings** preexistentes de Fast Refresh em componentes
  compartilhados; nenhum warning nos arquivos H.3.
- Python: `compileall` — aprovado; `pip check` — **No broken requirements found**.
- Dependências frontend: `npm ls --depth=0` — código de saída 0, sem dependências ausentes.
- Migration: `alembic history` — aprovado; H.3 aparece como head após H.2. Nenhuma migration foi
  aplicada.
- Não houve smoke test visual em navegador nem conexão ao PostgreSQL.

## Limitações e próximas integrações

- Esta etapa configura catálogo e associações; não implementa IA, dano, aplicação de efeitos,
  seleção de inimigos em batalhas reais nem execução de recompensas.
- A associação de habilidades H.3 é persistida em tabela própria, sem alterar o JSON legado de
  habilidades do inimigo. A próxima integração de combate deve ler essa tabela e preferir o
  override por habilidade ao padrão do inimigo.
- A interface não cria personagens jogáveis sem proprietário nem manipula personagens de campanha.
- A migration está preparada, mas não foi aplicada a PostgreSQL; o CRUD H.3 requer que a migration
  seja aplicada pelo processo de release autorizado.
- Não foi feita validação visual em navegador nesta implementação; os testes de interface são
  automatizados.
