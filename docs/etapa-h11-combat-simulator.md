# Etapa H.11 — Simulador automatizado de combate e métricas

## Status e escopo

Fundação local do simulador implementada e exercitada com dados sintéticos. Ela executa o fluxo H.4 real em uma sessão SQLite `:memory:`, reverte a transação de cada batalha e descarta a engine. Não abre rotas HTTP nem grava em banco/campanha/personagem do jogo. Nenhuma regra de dano ou recompensa foi reescalada.

O benchmark final executou **1.000 batalhas completas** do cenário `low-vs-basic`, com zero falhas: 1.000 vitórias, média/mediana de 7 turnos iniciados, média de 4 rodadas lógicas, 19 de dano efetivo total por batalha e desvio padrão zero. O resultado idêntico em todas as repetições é esperado: o motor H.4 atual não usa aleatoriedade no combate. Portanto, essa amostra prova execução em lote e estabilidade do pipeline, **não** equilíbrio estatístico nem variação entre seeds.

## Arquitetura e integração autoritativa

- `backend/app/services/combat_simulator.py` define cenários sintéticos, cria usuários/campanhas/personagens/inimigos/encontros somente em SQLite em memória, executa uma batalha, agrega lotes, faz replay e exporta JSON/CSV.
- O driver chama diretamente os resolutores de H.4 em `backend/app/api/combat.py`: `_resolve_player_action`, `_run_enemy_turn`, `_advance_turn`, `_tick_effects`, `_set_terminal` e a sequência de eventos. O jogador sintético escolhe uma ação segundo a política experimental; a validação, custo de mana, cooldown, dano, cura, efeitos e resultado são resolvidos pelo mesmo motor usado pela API.
- A fórmula e normalização vêm de `backend/app/services/combat_rules.py::calculate_damage`, `normalize_combat_attributes` e `uses_magic_power`; não existe uma fórmula alternativa no simulador.
- O seletor de candidatos de IA é compartilhado em `backend/app/services/combat_strategies.py`. A política `baseline` mantém a ordenação H.7: eliminação, dano efetivo, menor mana, dano calculado e desempate estável. Chamadas normais da API continuam usando `baseline`; estratégias experimentais só são passadas explicitamente pelo simulador.
- A fixture sintética inclui `reward` vazio/zero. Mesmo em vitória, o serviço central de recompensas não é chamado para conceder XP, ouro, itens ou habilidades.
- Não há dependência de frontend, sessão de jogador real, PostgreSQL, migration, worker ou fila. Não foi adicionada interface administrativa.

## Cenários e parâmetros

Os parâmetros completos e alteráveis ficam no código em `SYNTHETIC_SCENARIOS`; nomes e atributos também são copiados para cada resultado JSON. Todos os participantes têm atributos, HP/mana, nível, resistências, fraquezas, habilidades e velocidades sintéticos. `is_boss` identifica bosses no cenário; nenhum perfil persistente é consultado.

| Cenário | Cobertura |
|---|---|
| `low-vs-basic` | Personagem de nível baixo contra inimigo básico |
| `mid-vs-basic` | Nível intermediário contra inimigo básico |
| `high-vs-basic` | Nível alto contra inimigo básico |
| `player-vs-group` | Um personagem contra grupo de inimigos |
| `player-vs-boss` | Personagem contra boss |
| `party-vs-boss` | Grupo, magia e cura contra boss |
| `mixed-party` | Grupo com níveis diferentes |
| `high-resistance` | Resistência elemental alta |
| `elemental-weakness` | Fraqueza elemental |
| `magic-resource` | Consumo de mana e magia |
| `defense-and-healing` | Defesa, HP inicial parcial e cura |
| `special-effects` | Habilidade especial e dano contínuo |
| `limit-draw` | Limite de turnos sem vitória ou derrota |

Cada cenário aceita até 5 personagens e 12 inimigos, atributos finitos dentro dos limites do motor, uma lista de habilidades sintéticas e limite de turnos iniciados. `scenario_from_dict`/`scenario_to_dict` fornecem um contrato JSON reutilizável e validado; cenários inválidos são recusados antes de iniciar o lote.

## Seeds e reprodutibilidade

- A API do simulador exige seed inteira não negativa de 64 bits, registra-a no resultado e a usa para nomear IDs determinísticos de ações. IDs sintéticos de entidades derivam do `scenario_id`, dos índices e nomes, mantendo-se estáveis entre execuções.
- Relógio de cooldown é virtual e avança um segundo lógico por consulta de turno/ação; não depende do relógio da máquina. Timestamps de banco, UUIDs randômicos internos de eventos e tempo de execução não são exportados.
- As regras atuais de combate são determinísticas e não consomem RNG. Logo, seeds diferentes podem produzir resultados iguais; não se adicionou rolagem artificial para aparentar variância. Seeds só produzirão resultados diferentes quando uma regra real passar a usar aleatoriedade controlada.
- O replay é `replay_battle(report)`: revalida o cenário registrado e repete seed e estratégias. A reprodutibilidade é garantida para o mesmo cenário, versão de regras/simulador e código; alterações futuras do motor podem mudar resultados antigos.
- `simulator_version = 1.0.0` e `rules_version = h4-authoritative+h7-combat-rules` acompanham cada resultado.

## Estratégias comparáveis

`enemy_strategy` escolhe entre opções que o H.4 já considera disponíveis e válidas. A política atual `baseline` é preservada. As estratégias de pesquisa são:

- `effective_damage`: dano efetivo e eliminações antes de custo de mana.
- `mana_conservation`: prefere custo menor, depois dano/eliminação.
- `focus_low_hp`: prefere eliminar e então atacar alvos com menos HP atual.
- `elemental_weakness`: prioriza fraqueza elemental efetivamente explorável.
- `survival`: política experimental do grupo de personagens, usando cura quando o alvo está em metade do HP ou menos; como a IA H.4 inimiga não possui cura, `survival` do lado inimigo equivale à ordenação baseline.

`party_strategy` é uma política sintética para escolher ações de personagens, não uma IA de jogador existente. Estratégias não alteram a IA padrão da API. `compare_strategies` executa o mesmo conjunto de seeds para cada política e retorna os lotes separados; não declara uma estratégia “dominante” automaticamente.

## Métricas e convenções

Por batalha: resultado (`victory`, `defeat`, `turn_limit`/`draw`), turnos iniciados, rodadas lógicas, ações efetivamente resolvidas, eventos de dano, duração **lógica** (rodadas; não tempo de CPU), dano bruto e efetivo, sobre-dano por overkill, dano bruto/efetivo recebido, cura efetiva e desperdiçada, mana consumida e eficiências.

Por participante: IDs sintéticos da entidade e combatente, nome, lado, nível, HP inicial/final, mana inicial/consumida/restante, dano bruto/efetivo causado por ações, dano bruto/efetivo recebido, cura própria efetiva/desperdiçada, sobrevivência e rodada de derrota.

Por habilidade: usos, dano bruto/efetivo, cura efetiva/desperdiçada, mana total, dano efetivo por uso, dano por mana e cura por mana. O dano contínuo é relatado como dano efetivo/recebido do combate, mas não atribuído a uma habilidade/personagem causador: os eventos H.4 de `effect_tick` guardam o alvo e o dano, não o autor original. `damage_effective` do participante exclui esses ticks para não atribuí-los incorretamente.

- **Dano bruto** é o valor já calculado após defesa/resistência, mas antes do limite imposto pelo HP atual.
- **Dano efetivo** é `min(dano bruto, HP imediatamente anterior do alvo)`. Isso evita contar overkill como HP removido.
- **Cura efetiva** é o campo `healing` confirmado pelo motor H.4. **Cura desperdiçada** é `max(0, potência_base - cura efetiva)`.
- Mana consumida é a diferença entre mana inicial da simulação e mana final; não há regeneração no conjunto atual de regras.
- Ações são `action_resolved` mais `end_turn` efetivamente enviado pelo personagem; turnos inimigos sem alvo são eventos de turno encerrado, não ações.
- Precisão, evasão e crítico não existem nas regras H.4/H.7 auditadas, então não se inventam contadores de acerto/erro. `ineffective_damage_actions` permanece zero no motor atual, que causa dano mínimo 1 contra alvo vivo.

## Lotes, estatística e relatórios

`run_batch` recebe seeds explícitas, executa sequencialmente, informa progresso por callback, isola falhas individuais e agrega os resultados que completaram. Há limite de 10.000 batalhas, 10.000 turnos iniciados por cenário, timeout de 30 segundos por batalha e teto de 1.000.000 unidades estimadas (`batalhas × turnos × participantes`); trabalhos maiores devem ser divididos.

Agregados incluem contagem e taxa de vitória, distribuição de vitória/derrota/empate/limite, média, mediana, desvio padrão populacional, mínimo/máximo e percentis de nearest-rank p25/p50/p75/p90 para turnos, rodadas, ações, dano, cura, mana e dano por ação. Incluem agrupamento por participante (sobrevivência e totais) e habilidade (uso/eficiências). O campo `sample_sufficient_for_exploratory_comparison` indica apenas amostra de pelo menos 30; não é teste de significância. Com amostras pequenas, os agregados são descritivos.

`export_json` gera relatório hierárquico e `export_csv` uma linha por batalha, com colunas JSON para participantes, habilidades e eventos. Exemplo CSV com cabeçalho:

```csv
scenario_id,seed,simulator_version,rules_version,party_strategy,enemy_strategy,result,turns,...
```

## Como executar e repetir

Execute de um diretório temporário vazio para que o carregador de configuração da aplicação não procure um `.env` no diretório `backend`. Use a venv existente e o `PYTHONPATH`; nenhum comando do simulador precisa de uma URL de banco:

```sh
cd /tmp
PYTHONPATH=/caminho/para/site-rpg/backend APP_ENVIRONMENT=development \
  /caminho/para/site-rpg/backend/.venv/bin/python -m app.services.combat_simulator \
  --scenario low-vs-basic --battles 1000 --seed 0 --format json
```

Para CSV, use `--format csv`; `--output /tmp/relatorio.csv` grava explicitamente o relatório naquele arquivo. Para um cenário próprio, salve o objeto `scenario` de um relatório JSON, edite seus atributos sintéticos e passe `--scenario-file /tmp/cenario.json` (mutuamente exclusivo com `--scenario`). O exemplo `--seed 0 --battles 1000` executa seeds 0–999. Os caminhos acima são placeholders, não apontam para infraestrutura de banco.

Reexecução em Python:

```python
report = await simulate_battle(SYNTHETIC_SCENARIOS["low-vs-basic"], seed=41)
same_battle = await replay_battle(report)
assert export_json(report) == export_json(same_battle)
```

## Testes, evidências e limitações

`backend/tests/test_combat_simulator.py` testa vitória real pelo H.4, dano e overkill calculados manualmente, cura efetiva/desperdiçada e mana, limite exato de turnos, estratégia inimiga e custo de recurso, seeds/replay, exportação, agregação, falha isolada, callback de progresso, os cenários sintéticos e o uso exclusivo da URL `sqlite+aiosqlite://`. A suíte existente `test_combat.py` e `test_combat_rules.py` protege compatibilidade e fórmulas.

A comparação repetida de um cenário determinístico não mede variabilidade natural, probabilidade de vitória com RNG, intervalo de confiança ou poder estatístico. O alvo ainda não tem RNG em combate. Os dados iniciais são benchmarks transparentes, não balanceamento aprovado: exigem parâmetros representativos, metas de produto e cenários distintos antes de alteração de fórmulas/custos.

Não foram alterados frontend, banco PostgreSQL, `cronicas_do_reino_dev`, `cronicas_do_reino_test`, migrations, campanhas, contas, personagens, XP, recursos, inventários, credenciais ou `.env`. Nenhuma migration foi aplicada. A engine do simulador foi observada nos testes somente com `sqlite+aiosqlite://` em memória.

## Resultados de validação

- Testes H.11 + H.4 focados: **40 passed**.
- Suíte backend segura: **212 passed, 1 skipped, 12 deselected**. Os 12 casos que dependem de PostgreSQL foram excluídos; o único skip depende de permissões POSIX e não se aplica ao Windows.
- `compileall`: aprovado.
- `pip check`: nenhuma dependência quebrada.
- CLI de exportação CSV: executada com sucesso em cenário sintético.
- Benchmark: **1.000/1.000** batalhas concluídas sem falhas; 1.000 vitórias; média de 7 turnos iniciados, 4 rodadas lógicas, 19 de dano efetivo total e desvio padrão zero.
- Alembic: `d129a4c7e601` permanece como head; nenhuma conexão foi aberta e nenhuma migration foi aplicada.

O benchmark determinístico comprova execução repetível e estabilidade do pipeline, não balanceamento estatístico. Não houve alteração de frontend, portanto não foram executados testes TypeScript ou build frontend nesta etapa.
