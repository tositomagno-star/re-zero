# API de conteúdo do Painel do Mestre

Este documento registra os endpoints e os modelos administrativos implementados. A migração incremental é `91d4a0b7c8e2_official_admin_content`, descendente de `4e0f6a1a1b2c`.

## Autorização e convenções

- Todas as rotas sob `/api/admin/content` exigem uma sessão administrativa (`current_admin`); uma conta de jogador não é suficiente.
- Requisições de escrita também validam origem (`require_same_origin`). As rotas usam os cookies de sessão existentes e não aceitam tokens enviados pelo frontend.
- Payloads são validados por esquemas Pydantic estritos (`extra="forbid"`). UUIDs identificam os registros do servidor.
- `POST` de recursos retorna `201`; exclusões bem-sucedidas retornam `204`; registros inexistentes retornam `404`, referências inválidas ou payload inválido retornam `422`, e conteúdo histórico que não pode ser removido retorna `409`.
- As atualizações de capítulos enviam a estrutura de cenas, diálogos e escolhas; as posições da lista definem a ordem. Escolhas/cenas referenciadas por votos ou por snapshot de sessão em andamento não podem ser removidas ou substituídas.

## Endpoints administrativos

| Método | Rota | Operação |
| --- | --- | --- |
| `GET` | `/api/admin/content/chapters` | Lista capítulos globais, cenas, diálogos, escolhas e associações. |
| `POST` | `/api/admin/content/chapters` | Cria capítulo e estrutura narrativa aninhada. |
| `PUT` | `/api/admin/content/chapters/{chapter_id}` | Atualiza capítulo e reordena/substitui suas cenas. |
| `DELETE` | `/api/admin/content/chapters/{chapter_id}` | Exclui capítulo se não estiver em uso; caso contrário retorna conflito. |
| `GET` | `/api/admin/content/campaigns` | Lista campanhas para referência administrativa; não permite alterá-las. |
| `GET`, `POST` | `/api/admin/content/quests` | Lista missões com atribuições/estado ou cria missão de uma campanha. |
| `PUT` | `/api/admin/content/quests/{quest_id}` | Edita missão, publicação, objetivos/condições e recompensas; missão atribuída não pode ser movida para outra campanha. |
| `GET` | `/api/admin/content/quests/targets?campaign_id={id}` | Lista personagens ativos vinculados à campanha para atribuição. |
| `POST` | `/api/admin/content/quests/{quest_id}/assign` | Atribui missão publicada a personagens ativos dessa campanha; repetição não duplica associações. |
| `GET`, `POST` | `/api/admin/content/npcs` | Lista ou cria NPCs e diálogos. |
| `PUT`, `DELETE` | `/api/admin/content/npcs/{npc_id}` | Atualiza ou exclui NPC. |
| `GET`, `POST` | `/api/admin/content/items` | Lista ou cria itens/equipamentos. |
| `PUT`, `DELETE` | `/api/admin/content/items/{item_id}` | Atualiza, exclui ou desativa item referenciado por inventário/drop. |
| `GET`, `POST` | `/api/admin/content/monsters` | Lista ou cria monstros. |
| `PUT`, `DELETE` | `/api/admin/content/monsters/{monster_id}` | Atualiza, exclui ou desativa monstro referenciado por combate. |
| `POST` | `/api/admin/content/monsters/images` | Recebe o corpo binário de uma imagem `image/png`, até 5 MiB. |
| `GET`, `POST` | `/api/admin/content/skills` | Lista ou cria habilidades. |
| `PUT`, `DELETE` | `/api/admin/content/skills/{skill_id}` | Atualiza ou exclui/desativa habilidade. |
| `GET`, `POST` | `/api/admin/content/drops` | Lista ou cria regra de drop. |
| `PUT`, `DELETE` | `/api/admin/content/drops/{drop_id}` | Atualiza ou exclui regra de drop. |
| `GET`, `PUT` | `/api/admin/content/economy/config` | Consulta/salva configuração comercial do universo em JSON. |
| `GET`, `PUT` | `/api/admin/content/settings/universe` | Consulta/salva configurações do universo em JSON. |
| `GET`, `POST` | `/api/admin/content/rewards` | Lista ou cria modelos de recompensas. |
| `PUT`, `DELETE` | `/api/admin/content/rewards/{reward_id}` | Atualiza ou desativa modelo de recompensa. |
| `GET`, `POST` | `/api/admin/content/transactions` | Consulta ou registra uma transação administrativa; o registro é somente de histórico. |
| `GET` | `/api/admin/content/players` | Lista jogadores para consulta administrativa. |
| `GET` | `/api/admin/content/characters` | Lista fichas, inventário, equipamentos e habilidades para consulta administrativa. |

## Biblioteca de Assets

A biblioteca administrativa e seus endpoints estão descritos em [`asset-library.md`](./asset-library.md). A revisão inicial é `c2f6d8a41b90_asset_library`, descendente de `91d4a0b7c8e2`; a revisão H.1 `d7b13c9a5e42_asset_analysis_metadata` acrescenta classificação detalhada, análise e publicação privada/pública. Nenhuma delas foi executada nesta etapa.

### Formatos principais

- **Capítulo:** `title`, `summary`, `narrative`, `position`, `status`, `is_active`, `npc_ids`, `enemy_ids` e `scenes`.
- **Cena:** `title`, `narrative`, `position`, `is_active`, `dialogues`, `choices`, `npc_ids`, `enemy_ids` e `conditions`.
- **Diálogo:** `speaker`, `line` e `conditions`. **Escolha:** `label`, `next_node_id`, `position`, `conditions` e `consequences`.
- **NPC:** nome, descrição, personalidade, papel, campanha opcional, relações com jogadores, diálogos, missões textuais, condições, publicação e estado ativo.
- **Item:** nome, descrição, categoria, raridade, preço, peso, requisitos, atributos, efeitos, estoque, utilização, empilhamento, imagem e estado ativo.
- **Monstro:** nível, HP, ataque, defesa, velocidade, XP, dificuldade, habilidades, resistências, fraquezas, chance de aparição, recompensas, imagem e estado ativo. Chance usa pontos-base no contrato (`0..10000`).
- **Habilidade:** categoria, descrição, custo de mana, efeitos, alvo, requisitos, recarga, publicação e estado ativo.
- **Drop:** `enemy_id`, `item_id`, chance em pontos-base, quantidade mínima e máxima.
- **Recompensa:** título, descrição, ouro, XP, IDs de itens e estado ativo.
- **Missão:** campanha, título/descrição, publicação, objetivos e condição all/any em `conditions` JSON, e XP/ouro/itens/habilidades em `rewards` JSON. Atribuições e progresso usam `CharacterQuest`; recompensa e condições são congeladas no momento da atribuição/início.
- **Transação:** `character_id`, tipo, descrição e valor positivo. Esta rota registra histórico e não executa compra, venda nem altera o saldo do personagem.
- **Configurações:** objeto JSON validado como dicionário. As regras comerciais guardam moedas, percentual de acréscimo, percentual de revenda e descrição das regras.

## Consulta de conteúdo para jogadores

As rotas abaixo exigem uma sessão de jogador. Elas são somente leitura e retornam o conteúdo publicado/ativo, preservando também conteúdo já referenciado por progresso, inventário ou combate:

| Método | Rota | Operação |
| --- | --- | --- |
| `GET` | `/api/content/chapters` | Lista capítulos globais publicados ou em uso. |
| `GET` | `/api/content/items` | Lista itens ativos e itens presentes em inventários. |
| `GET` | `/api/content/monsters` | Lista monstros ativos e monstros em combate. |
| `GET` | `/api/content/skills` | Lista habilidades publicadas/ativas e habilidades já aprendidas. |
| `GET` | `/api/content/npcs` | Lista NPCs globais publicados ou ligados à história. |
| `GET` | `/api/content/campaigns/{campaign_id}/npcs` | Lista NPCs publicados visíveis aos participantes ativos da campanha; a falta de vínculo retorna `404`. |
| `GET` | `/api/content/monster-images/{name}` | Serve PNG do armazenamento local do servidor. |

## Persistência e integridade

A migração adiciona suporte para capítulos globais (`campaign_id = NULL`), narrativas/ativação, relações entre capítulos e NPCs/monstros, campos ampliados de NPCs/itens/monstros/habilidades, versões anteriores de itens/monstros, configurações do universo e modelos de recompensa. Tabelas de associação usam chaves estrangeiras para manter a integridade.

Itens presentes em inventários e monstros em combate são versionados ao editar: a versão anterior é desativada e a edição cria um novo registro ligado por `previous_version_id`. Exclusões de conteúdo ainda referenciado são bloqueadas ou substituídas por desativação. Sessões narrativas em andamento leem seu snapshot persistido e protegem cenas/escolhas que ainda podem ser usadas; alterações posteriores não reescrevem o snapshot nem as decisões registradas.

PNGs são validados no servidor (assinatura, chunks/CRC, dimensões até 8192 px e limite de 5 MiB) e gravados em `backend/uploads/monsters`. Em produção, esse diretório precisa de volume persistente e política de backup.

## Limites atuais

- Campanhas, jogadores e personagens no painel são consultas somente leitura; a gestão de campanhas/personagens continua nos fluxos de jogador.
- Economia e configurações são armazenadas, mas ainda não dirigem operações reais de compra/venda nem recompensas de combate.
- Eventos recentes e algumas preferências de interface continuam sendo dados/preferências locais de demonstração; não são fonte oficial do catálogo.
- Combate e distribuição de XP/drops de combate continuam fora de escopo. Consequências de escolhas podem referenciar recompensas do catálogo e missões atribuídas; veja o fluxo e seus limites em [`narrative-progression.md`](./narrative-progression.md).
- Os testes e a migração disponíveis foram executados com SQLite. PostgreSQL não está instalado/disponível neste ambiente e ainda precisa de validação real.
