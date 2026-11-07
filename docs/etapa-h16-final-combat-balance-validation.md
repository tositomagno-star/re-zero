# H.16 — Validação final do balanceamento de combate

> **Conclusão:** a etapa valida reprodutibilidade e regressões em cenários sintéticos; não certifica o catálogo canônico nem autoriza ajustes nas regras.

## 1. Auditoria H.11–H.15

- H.11: benchmark documentado de 1.000 batalhas do cenário `low-vs-basic`, determinístico.
- H.12: 45 configurações sintéticas, uma execução final por caso; 11 casos representativos foram reexecutados em cinco seeds.
- H.13: 6 habilidades, 26 contrastes e 0 ensaios aleatórios independentes; classificações exploratórias.
- H.14: 210 batalhas, 7 cenários, 6 políticas e 175 pares contra baseline; nenhum desfecho mudou no conjunto anterior.
- H.15: não agrega populações incompatíveis. A auditoria identificou e corrigiu o mapeamento de classificação/confiança e mediana/contextos da H.13.
- As recomendações de defesa, boss, equipamentos e habilidades têm uma execução por condição na H.12 original. Replays confirmam reprodução, não elevam o n estatístico.

### Força da evidência das recomendações H.15

| Recomendação | Evidência | Decisão H.16 |
|---|---|---|
| synthetic-enemy-defense-threshold | insufficient-for-change: Uma execução por condição no H.12; cinco replays confirmatórios são determinísticos e não aumentam o tamanho efetivo da amostra. | none |
| synthetic-boss-party-size-threshold | insufficient-for-change: Um caso por tamanho de grupo no H.12; contraste confunde tamanho com desfecho nesse cenário sintético e não há catálogo canônico. | none |
| synthetic-equipment-deltas | insufficient-for-change: Deltas isolados sintéticos com uma execução original; não representam itens, slots, custos ou requisitos publicados. | none |
| synthetic-direct-skill-efficiency | insufficient-for-change: H.12 mede casos sintéticos pontuais e H.13 0 ensaios aleatórios independentes; não alterar potência nem custo. | none |
| h14-policy-outcomes | no-official-change: 0 de 175 pares mudaram o desfecho; mudanças de escolha/recursos são comportamentais e determinísticas. | none |
| canonical-catalog-unassessed | pending-authorized-catalog: As fontes declaram que o catálogo canônico não foi acessado. | none |

## 2. Estado das regras e fluxo autoritativo

- Dano, normalização de atributos e classificação mágica reutilizam `combat_rules.py`; não há fórmula paralela no simulador.
- O cálculo central preserva piso de 1, limite máximo, resistência em metade, fraqueza em dobro e precedência da resistência se ambas coincidirem.
- O simulador invoca os resolutores de combate da API H.4/H.7 em SQLite `:memory:`; custo de mana, alvo, cooldown, efeitos e resultado permanecem sob validação do servidor.
- Turnos/ações usam eventos e chaves idempotentes; conclusão de vitória continua integrando `progression` para concessão única de recompensas.
- Progressão continua no serviço existente; cenários de equipamento H.12 alteram somente atributos sintéticos, sem representar itens persistentes.
- A API mantém baseline como padrão. Estratégias alternativas só são enviadas explicitamente pelo simulador.
- O frontend consome e apresenta eventos confirmados pela API; nenhuma alteração de frontend foi necessária.

## 3. Simulações finais

| Matriz | Execuções | Seeds | Resultado | Reprodutibilidade |
|---|---:|---|---|---|
| H.11 `low-vs-basic` | 1000 | 2000–2999 | {'victory': 1000, 'defeat': 0, 'draw': 0, 'turn_limit': 0} | confere do benchmark documentado |
| H.12 recomendações | 55 | [100, 101, 102, 103, 104] | 11 casos, seed 100 confere: True | determinístico; sem inferência |
| H.14 matriz inteira | 210 | fonte H.14 | 0 falhas | 0 divergências nas métricas comparadas |

### H.11 benchmark reexecutado

| Métrica | Valor |
|---|---:|
| Vitórias | 1000/1000 |
| Taxa descritiva | 100.0% |
| Turnos (média/mediana) | 7.0/7.0 |
| Rodadas lógicas (média/mediana) | 4.0/4.0 |
| Dano efetivo do grupo (média/mediana) | 16.0/16.0 |
| Dano efetivo total (ambos os lados e efeitos; média/mediana) | 19.0/19.0 |
| Sobrevivência do grupo (média) | 100.0% |
| Sobreviventes do grupo (média) | 1.0 |
| Mana consumida pelo grupo (média) | 0.0 |
| Falhas | 0 |

### Casos H.12 repetidos

| Caso | n replay | Desfecho original/replay seed 100 | Confere | Turnos média | Dano total médio | Métricas iguais entre seeds |
|---|---:|---|---|---:|---:|---|
| `enemy-baseline` | 5 | victory/victory | True | 13.0 | 87.0 | True |
| `enemy-high-defense` | 5 | defeat/defeat | True | 100.0 | 150.0 | True |
| `boss-party-4` | 5 | defeat/defeat | True | 140.0 | 520.0 | True |
| `boss-party-5` | 5 | victory/victory | True | 136.0 | 428.0 | True |
| `equipment-none` | 5 | victory/victory | True | 29.0 | 118.0 | True |
| `equipment-weapon-plus-6-attack` | 5 | victory/victory | True | 15.0 | 104.0 | True |
| `equipment-armor-plus-6-defense` | 5 | victory/victory | True | 29.0 | 104.0 | True |
| `skill-no-skill` | 5 | victory/victory | True | 29.0 | 118.0 | True |
| `skill-physical-skill` | 5 | victory/victory | True | 9.0 | 98.0 | True |
| `skill-magic-skill` | 5 | victory/victory | True | 9.0 | 98.0 | True |
| `skill-damage-over-time` | 5 | victory/victory | True | 15.0 | 104.0 | True |

### H.14 — Condições e recursos por cenário/política

| Cenário | Política | n | Vitórias | Sobrevivência média | Sobreviventes | Dano de grupo | Dano recebido | Mana IA | Cura grupo | Rodadas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `defense-and-healing` | adaptive | 5 | 0 | 50.0% | 1.0 | 101.0 | 98.0 | 0.0 | 0.0 | 46.0 |
| `defense-and-healing` | aggressive | 5 | 0 | 50.0% | 1.0 | 101.0 | 98.0 | 0.0 | 0.0 | 46.0 |
| `defense-and-healing` | baseline | 5 | 0 | 50.0% | 1.0 | 101.0 | 98.0 | 0.0 | 0.0 | 46.0 |
| `defense-and-healing` | conservative | 5 | 0 | 100.0% | 2.0 | 101.0 | 33.0 | 0.0 | 0.0 | 34.0 |
| `defense-and-healing` | economic | 5 | 0 | 50.0% | 1.0 | 101.0 | 98.0 | 0.0 | 0.0 | 46.0 |
| `defense-and-healing` | tactical | 5 | 0 | 50.0% | 1.0 | 101.0 | 98.0 | 0.0 | 0.0 | 46.0 |
| `h14-effect-priority` | adaptive | 5 | 0 | 100.0% | 2.0 | 60.0 | 83.0 | 20.0 | 0.0 | 10.0 |
| `h14-effect-priority` | aggressive | 5 | 0 | 100.0% | 2.0 | 60.0 | 112.0 | 24.0 | 0.0 | 10.0 |
| `h14-effect-priority` | baseline | 5 | 0 | 100.0% | 2.0 | 60.0 | 112.0 | 24.0 | 0.0 | 10.0 |
| `h14-effect-priority` | conservative | 5 | 0 | 100.0% | 2.0 | 60.0 | 10.0 | 0.0 | 0.0 | 10.0 |
| `h14-effect-priority` | economic | 5 | 0 | 100.0% | 2.0 | 60.0 | 10.0 | 0.0 | 0.0 | 10.0 |
| `h14-effect-priority` | tactical | 5 | 0 | 100.0% | 2.0 | 60.0 | 100.0 | 24.0 | 0.0 | 10.0 |
| `h14-elemental-threat` | adaptive | 5 | 0 | 100.0% | 2.0 | 240.0 | 125.0 | 25.0 | 0.0 | 10.0 |
| `h14-elemental-threat` | aggressive | 5 | 0 | 100.0% | 2.0 | 240.0 | 148.0 | 30.0 | 0.0 | 10.0 |
| `h14-elemental-threat` | baseline | 5 | 0 | 100.0% | 2.0 | 240.0 | 148.0 | 30.0 | 0.0 | 10.0 |
| `h14-elemental-threat` | conservative | 5 | 0 | 100.0% | 2.0 | 240.0 | 10.0 | 0.0 | 0.0 | 10.0 |
| `h14-elemental-threat` | economic | 5 | 0 | 100.0% | 2.0 | 240.0 | 10.0 | 0.0 | 0.0 | 10.0 |
| `h14-elemental-threat` | tactical | 5 | 0 | 100.0% | 2.0 | 240.0 | 148.0 | 30.0 | 0.0 | 10.0 |
| `h14-mana-budget` | adaptive | 5 | 0 | 100.0% | 2.0 | 60.0 | 82.0 | 16.0 | 0.0 | 10.0 |
| `h14-mana-budget` | aggressive | 5 | 0 | 100.0% | 2.0 | 60.0 | 95.0 | 18.0 | 0.0 | 10.0 |
| `h14-mana-budget` | baseline | 5 | 0 | 100.0% | 2.0 | 60.0 | 95.0 | 18.0 | 0.0 | 10.0 |
| `h14-mana-budget` | conservative | 5 | 0 | 100.0% | 2.0 | 60.0 | 40.0 | 0.0 | 0.0 | 10.0 |
| `h14-mana-budget` | economic | 5 | 0 | 100.0% | 2.0 | 60.0 | 40.0 | 0.0 | 0.0 | 10.0 |
| `h14-mana-budget` | tactical | 5 | 0 | 100.0% | 2.0 | 60.0 | 95.0 | 18.0 | 0.0 | 10.0 |
| `low-vs-basic` | adaptive | 5 | 5 | 100.0% | 1.0 | 16.0 | 3.0 | 0.0 | 0.0 | 4.0 |
| `low-vs-basic` | aggressive | 5 | 5 | 100.0% | 1.0 | 16.0 | 3.0 | 0.0 | 0.0 | 4.0 |
| `low-vs-basic` | baseline | 5 | 5 | 100.0% | 1.0 | 16.0 | 3.0 | 0.0 | 0.0 | 4.0 |
| `low-vs-basic` | conservative | 5 | 5 | 100.0% | 1.0 | 16.0 | 3.0 | 0.0 | 0.0 | 4.0 |
| `low-vs-basic` | economic | 5 | 5 | 100.0% | 1.0 | 16.0 | 3.0 | 0.0 | 0.0 | 4.0 |
| `low-vs-basic` | tactical | 5 | 5 | 100.0% | 1.0 | 16.0 | 3.0 | 0.0 | 0.0 | 4.0 |
| `party-vs-boss` | adaptive | 5 | 0 | 0.0% | 0.0 | 253.0 | 245.0 | 0.0 | 0.0 | 28.0 |
| `party-vs-boss` | aggressive | 5 | 0 | 0.0% | 0.0 | 253.0 | 245.0 | 0.0 | 0.0 | 28.0 |
| `party-vs-boss` | baseline | 5 | 0 | 0.0% | 0.0 | 253.0 | 245.0 | 0.0 | 0.0 | 28.0 |
| `party-vs-boss` | conservative | 5 | 0 | 0.0% | 0.0 | 268.0 | 245.0 | 0.0 | 0.0 | 28.0 |
| `party-vs-boss` | economic | 5 | 0 | 0.0% | 0.0 | 253.0 | 245.0 | 0.0 | 0.0 | 28.0 |
| `party-vs-boss` | tactical | 5 | 0 | 0.0% | 0.0 | 253.0 | 245.0 | 0.0 | 0.0 | 28.0 |
| `player-vs-group` | adaptive | 5 | 5 | 100.0% | 1.0 | 72.0 | 9.0 | 0.0 | 0.0 | 6.0 |
| `player-vs-group` | aggressive | 5 | 5 | 100.0% | 1.0 | 72.0 | 9.0 | 0.0 | 0.0 | 6.0 |
| `player-vs-group` | baseline | 5 | 5 | 100.0% | 1.0 | 72.0 | 9.0 | 0.0 | 0.0 | 6.0 |
| `player-vs-group` | conservative | 5 | 5 | 100.0% | 1.0 | 72.0 | 9.0 | 0.0 | 0.0 | 6.0 |
| `player-vs-group` | economic | 5 | 5 | 100.0% | 1.0 | 72.0 | 9.0 | 0.0 | 0.0 | 6.0 |
| `player-vs-group` | tactical | 5 | 5 | 100.0% | 1.0 | 72.0 | 9.0 | 0.0 | 0.0 | 6.0 |

Os cenários/políticas não foram agregados entre si. Em cada repetição, dano, HP/mana, cura, alvos, ações, usos de habilidade e aplicações de efeitos foram registrados no JSON/CSV. A repetição determinística não constitui uma amostra estatística independente.

## 4. Ajustes realizados e propostas

Nenhum ajuste canônico foi aplicado. Foi corrigido apenas o mapeamento de campos no consolidador H.15, sem alteração de simulador ou regras.

| Tema | Comportamento atual | Proposta pendente | Impacto esperado | Risco | Testes necessários |
|---|---|---|---|---|---|
| Defesa e duração | Defesa reduz dano segundo a regra central; há piso mínimo de dano. | Validar a faixa publicada e uma meta de duração antes de propor qualquer ajuste. | Pode revelar combates de atrito em certas relações de ataque/defesa. | Uma alteração indiscriminada pode invalidar resistências e inimigos de alto nível. | Casos pareados em snapshot canônico, limites de dano, defesa e testes H.4/H.7. |
| Escala de boss por grupo | O dano e turnos são resolvidos pelo motor; tamanho do grupo muda participantes e ações. | Separar tamanho do grupo, cura, iniciativa e equipamento em encontros canônicos autorizados. | Identificar se o limiar observado decorre da composição ou do boss. | Alterar HP/dano do boss sem controlar os fatores pode piorar outro grupo. | Matriz canônica por tamanho/composição com métricas de sobrevivência e duração. |
| Eficiência de equipamento | Atributos de combate vêm do snapshot; H.12 alterou somente deltas sintéticos. | Comparar itens publicados por slot, custo, requisito e progressão. | Medir custo-benefício sem inferir de um delta abstrato. | Itens e economia reais não estão representados nos testes. | Ablation de um item por vez em catálogo sanitizado e testes de snapshot. |
| Custo e potência de habilidades | O backend valida elegibilidade, consome mana e resolve dano/efeito. | Avaliar habilidades publicadas por resistência, cooldown, alcance e orçamento de mana. | Distinguir skill pouco usada de skill fraca e medir utilidade não-dano. | Reduzir custos/potência baseado em skills sintéticas afetaria progressão canônica. | Matriz de usos possíveis, controle pareado, mana, cura e efeitos, sem alterar regras. |
| Política de IA | Baseline é o padrão; alternativas H.14 são selecionadas explicitamente no simulador. | Manter baseline e ampliar evidência comportamental em cenários autorizados. | Nenhuma substituição recomendada com 0/175 desfechos diferentes e seeds determinísticas. | Uma política pode mudar recursos e alvo sem mudar resultado no conjunto atual. | Comparações pareadas por contexto em catálogo canônico e revisão do comportamento. |

## 5. Regressões verificadas

A suíte abaixo cobre reproduções e contratos do motor, sem conexão PostgreSQL:

- Determinismo, replay por seed, limites e agregação: `test_combat_simulator.py`.
- Dano central, defesa, resistências, fraquezas e limites numéricos: `test_combat_rules.py`.
- Custo de mana, resistência server-side, rejeição de dano/targets fornecidos pelo cliente, turnos, eventos, idempotência e recompensas únicas: `test_combat.py`.
- Progressão, rewards transacionais e idempotência concorrente: `test_progression.py`.
- Exports, comparação pareada e políticas experimentais sem mudar default: testes H.12–H.15.
- Eventos de combate apresentados no frontend cobertos pelos testes do painel; nenhum arquivo de frontend foi alterado.

A contagem dos testes é apresentada no resumo de entrega; o JSON registra dados de simulação, não o log do pytest.

## 6. Validade das conclusões

### Conclusões comprovadas com dados sintéticos

- O benchmark H.11 foi reexecutado 1.000 vezes sem falhas e reproduziu vitória, duração e dano determinísticos.
- Onze casos H.12 selecionados foram reexecutados em cinco seeds cada; seed 100 confere com a saída documentada e os resultados são reproduzíveis.
- A matriz H.14 completa foi reexecutada: 210 batalhas, 0 falhas e comparação das métricas principais sem divergência do JSON publicado.
- Testes existentes cobrem fórmulas, piso/limite de dano, resistência, mana, efeitos, turno, replay, persistência de ações, idempotência e recompensa.

### Conclusões ainda hipotéticas

- O contraste de defesa pode causar duração excessiva em certas fichas.
- O boss sintético pode ter limiar de vitória sensível a tamanho e composição do grupo.
- Deltas de equipamento e habilidades sintéticas podem não refletir o catálogo disponível.
- Políticas alternativas podem oferecer trade-offs de mana, alvo ou efeitos em outros encontros.

### Pendências dependentes do catálogo canônico

- Taxas de vitória/duração contra personagens, inimigos e bosses publicados.
- Eficiência e progressão de equipamentos reais.
- Equilíbrio de habilidades publicadas, custos, cooldowns e efeitos.
- Adequação de parâmetros oficiais e substituição da estratégia baseline.

### Sem evidência suficiente

- Afirmar que o combate canônico está equilibrado ou desequilibrado.
- Afirmar superioridade estatística de uma política de IA.
- Ajustar fórmulas, atributos, habilidade, custo, resistência ou HP do boss.

## 7. Limitações e riscos restantes

- H.12 tem uma execução por configuração; seus casos não sustentam estimativa de variabilidade.
- H.13 é sintético e determinístico; a classificação exploratória não fundamenta ajuste de habilidade.
- H.14 usa seeds determinísticas; 0/175 desfechos pareados diferentes não prova equivalência geral.
- Nenhum catálogo canônico foi consultado; propostas que dependem de dados reais permanecem pendentes.
- Repetições do H.16 são testes de regressão/reprodução, não amostras independentes.
- Dano contínuo não é atribuído com segurança ao ator original pelos eventos do motor; métricas de skill não o contam como dano direto.
- A simulação sintética não cobre validade de todas as skills, builds, composições ou ciclos reais de campanha.
- H.14 não encontrou diferença de resultado por política nos cenários avaliados, mas isso não demonstra equivalência em cenários não testados.

## 8. Segurança e validação canônica

- PostgreSQL e bancos `cronicas_do_reino_dev`/`cronicas_do_reino_test`: não acessados.
- Migrations: não aplicadas; verificação Alembic somente leitura.
- Dados persistentes, credenciais, roles, permissões e fórmulas oficiais: não modificados.
- O catálogo canônico permanece sem validação autorizada. O baseline continua a IA oficial.

Artefatos detalhados: `etapa-h16-final-combat-balance-validation.json` e `etapa-h16-final-combat-balance-validation.csv`.
