# H.15 — Consolidação de relatórios quantitativos de combate

> **Escopo sintético.** Este relatório não certifica o balanceamento canônico, não recomenda alterações de regras e não escolhe uma nova IA oficial.

## Visão executiva

- **H.11:** 1,000 batalhas no benchmark `low-vs-basic`, 1,000 vitórias e 0 falhas; 4 rodadas lógicas médias e 19 dano efetivo médio.
- **H.12:** 45 de 45 configurações concluídas, 45 casos e 0 falhas.
- **H.13:** 6 habilidades sintéticas, 26 contrastes por contexto e 3 observações de seleção de IA.
- **H.14:** 210 batalhas em 7 cenários e 6 políticas; 0 falhas; nenhum desfecho mudou em 175 pares contra baseline.
- Os totais das etapas **não são somados**: as populações e unidades de análise diferem.

## Metodologia e rastreabilidade

Os dados são extraídos dos relatórios H.11–H.14 existentes; este consolidador não executa batalhas, não recalcula fórmulas do motor e não acessa bancos. Cada tabela permanece separada por fase e cenário.

| Etapa | Fonte original | Unidade e escopo |
|---|---|---|
| H.11 | [etapa-h11-combat-simulator.md](etapa-h11-combat-simulator.md) | Benchmark e metodologia do simulador H.11. |
| H.12 | [etapa-h12-combat-balance-analysis.json](etapa-h12-combat-balance-analysis.json) | 45 cenários/configurações comparativas; uma execução final por caso. |
| H.13 | [etapa-h13-skill-balance-analysis.json](etapa-h13-skill-balance-analysis.json) | 6 habilidades sintéticas e 26 comparações por contexto. |
| H.14 | [etapa-h14-ai-strategy-comparison.json](etapa-h14-ai-strategy-comparison.json) | 7 cenários, 6 políticas e 5 seeds determinísticas pareadas. |

### H.11 — Benchmark documentado

| Cenário | Batalhas | Vitórias | Taxa | Turnos iniciados média/mediana | Rodadas médias | Dano efetivo médio | Desvio padrão reportado |
|---|---:|---:|---:|---:|---:|---:|---:|
| `low-vs-basic` | 1000 | 1000 | 100.00% | 7 | 4 | 19 | 0 |

A taxa e a dispersão descrevem o cenário determinístico repetido; não são estimativas de taxa populacional.

### H.12 — Resultados por configuração

| Caso | Família | Vitórias | Derrotas | Sobrevivência do grupo | Turnos médios (mediana) | Dano efetivo médio (mediana; p25–p90) | Mana média | n |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `h11-low-vs-basic` | h11-synthetic-scenarios | 1 | 0 | 100.00% | 7.00 (7) | 19.00 (19; 19–19) | 0.00 | 1 |
| `h11-mid-vs-basic` | h11-synthetic-scenarios | 1 | 0 | 100.00% | 9.00 (9) | 50.00 (50; 50–50) | 0.00 | 1 |
| `h11-high-vs-basic` | h11-synthetic-scenarios | 1 | 0 | 100.00% | 1.00 (1) | 26.00 (26; 26–26) | 0.00 | 1 |
| `h11-player-vs-group` | h11-synthetic-scenarios | 1 | 0 | 100.00% | 15.00 (15) | 81.00 (81; 81–81) | 0.00 | 1 |
| `h11-player-vs-boss` | h11-synthetic-scenarios | 0 | 1 | 0.00% | 40.00 (40) | 280.00 (280; 280–280) | 0.00 | 1 |
| `h11-party-vs-boss` | h11-synthetic-scenarios | 0 | 1 | 0.00% | 72.00 (72) | 498.00 (498; 498–498) | 25.00 | 1 |
| `h11-mixed-party` | h11-synthetic-scenarios | 1 | 0 | 50.00% | 10.00 (10) | 100.00 (100; 100–100) | 0.00 | 1 |
| `h11-high-resistance` | h11-synthetic-scenarios | 0 | 1 | 0.00% | 12.00 (12) | 149.00 (149; 149–149) | 30.00 | 1 |
| `h11-elemental-weakness` | h11-synthetic-scenarios | 1 | 0 | 100.00% | 3.00 (3) | 100.00 (100; 100–100) | 10.00 | 1 |
| `h11-magic-resource` | h11-synthetic-scenarios | 0 | 1 | 0.00% | 22.00 (22) | 148.00 (148; 148–148) | 14.00 | 1 |
| `h11-defense-and-healing` | h11-synthetic-scenarios | 0 | 0 | 50.00% | 100.00 (100) | 199.00 (199; 199–199) | 0.00 | 1 |
| `h11-special-effects` | h11-synthetic-scenarios | 0 | 1 | 0.00% | 22.00 (22) | 175.00 (175; 175–175) | 20.00 | 1 |
| `h11-limit-draw` | h11-synthetic-scenarios | 0 | 0 | 100.00% | 4.00 (4) | 4.00 (4; 4–4) | 0.00 | 1 |
| `healing-survival-policy` | healing-strategy | 0 | 0 | 50.00% | 100.00 (100) | 248.00 (248; 248–248) | 18.00 | 1 |
| `level-00001` | level-matrix | 1 | 0 | 100.00% | 7.00 (7) | 19.00 (19; 19–19) | 0.00 | 1 |
| `level-00005` | level-matrix | 1 | 0 | 100.00% | 7.00 (7) | 19.00 (19; 19–19) | 0.00 | 1 |
| `level-00015` | level-matrix | 1 | 0 | 100.00% | 7.00 (7) | 19.00 (19; 19–19) | 0.00 | 1 |
| `level-00050` | level-matrix | 1 | 0 | 100.00% | 7.00 (7) | 19.00 (19; 19–19) | 0.00 | 1 |
| `level-00100` | level-matrix | 1 | 0 | 100.00% | 7.00 (7) | 19.00 (19; 19–19) | 0.00 | 1 |
| `level-01000` | level-matrix | 1 | 0 | 100.00% | 7.00 (7) | 19.00 (19; 19–19) | 0.00 | 1 |
| `level-10000` | level-matrix | 1 | 0 | 100.00% | 7.00 (7) | 19.00 (19; 19–19) | 0.00 | 1 |
| `archetype-physical` | archetypes | 1 | 0 | 100.00% | 17.00 (17) | 106.00 (106; 106–106) | 0.00 | 1 |
| `archetype-magic` | archetypes | 1 | 0 | 100.00% | 11.00 (11) | 100.00 (100; 100–100) | 20.00 | 1 |
| `archetype-defensive` | archetypes | 1 | 0 | 100.00% | 45.00 (45) | 112.00 (112; 112–112) | 0.00 | 1 |
| `enemy-baseline` | enemy-archetypes | 1 | 0 | 100.00% | 13.00 (13) | 87.00 (87; 87–87) | 0.00 | 1 |
| `enemy-high-hp` | enemy-archetypes | 1 | 0 | 100.00% | 27.00 (27) | 176.00 (176; 176–176) | 0.00 | 1 |
| `enemy-high-attack` | enemy-archetypes | 1 | 0 | 100.00% | 13.00 (13) | 147.00 (147; 147–147) | 0.00 | 1 |
| `enemy-high-defense` | enemy-archetypes | 0 | 1 | 0.00% | 100.00 (100) | 150.00 (150; 150–150) | 0.00 | 1 |
| `enemy-high-speed` | enemy-archetypes | 1 | 0 | 100.00% | 14.00 (14) | 89.00 (89; 89–89) | 0.00 | 1 |
| `boss-party-1` | boss-party-scaling | 0 | 1 | 0.00% | 20.00 (20) | 100.00 (100; 100–100) | 0.00 | 1 |
| `boss-party-2` | boss-party-scaling | 0 | 1 | 0.00% | 50.00 (50) | 220.00 (220; 220–220) | 0.00 | 1 |
| `boss-party-3` | boss-party-scaling | 0 | 1 | 0.00% | 90.00 (90) | 360.00 (360; 360–360) | 0.00 | 1 |
| `boss-party-4` | boss-party-scaling | 0 | 1 | 0.00% | 140.00 (140) | 520.00 (520; 520–520) | 0.00 | 1 |
| `boss-party-5` | boss-party-scaling | 1 | 0 | 60.00% | 136.00 (136) | 428.00 (428; 428–428) | 0.00 | 1 |
| `equipment-none` | equipment-deltas | 1 | 0 | 100.00% | 29.00 (29) | 118.00 (118; 118–118) | 0.00 | 1 |
| `equipment-weapon-plus-6-attack` | equipment-deltas | 1 | 0 | 100.00% | 15.00 (15) | 104.00 (104; 104–104) | 0.00 | 1 |
| `equipment-armor-plus-6-defense` | equipment-deltas | 1 | 0 | 100.00% | 29.00 (29) | 104.00 (104; 104–104) | 0.00 | 1 |
| `skill-no-skill` | skill-comparison | 1 | 0 | 100.00% | 29.00 (29) | 118.00 (118; 118–118) | 0.00 | 1 |
| `skill-physical-skill` | skill-comparison | 1 | 0 | 100.00% | 9.00 (9) | 98.00 (98; 98–98) | 20.00 | 1 |
| `skill-magic-skill` | skill-comparison | 1 | 0 | 100.00% | 9.00 (9) | 98.00 (98; 98–98) | 20.00 | 1 |
| `skill-damage-over-time` | skill-comparison | 1 | 0 | 100.00% | 15.00 (15) | 104.00 (104; 104–104) | 20.00 | 1 |
| `group-offensive` | group-compositions | 1 | 0 | 66.67% | 45.00 (45) | 375.00 (375; 375–375) | 0.00 | 1 |
| `group-defensive` | group-compositions | 1 | 0 | 33.33% | 371.00 (371) | 482.00 (482; 482–482) | 0.00 | 1 |
| `group-magic-focused` | group-compositions | 1 | 0 | 100.00% | 17.00 (17) | 300.00 (300; 300–300) | 52.00 | 1 |
| `group-balanced` | group-compositions | 0 | 1 | 0.00% | 108.00 (108) | 390.00 (390; 390–390) | 0.00 | 1 |

As estatísticas de H.12 são exatas para as configurações determinísticas observadas; há uma execução final por caso. Percentis nearest-rank p25/p50/p75/p90 descrevem as observações da fonte e não representam dispersão populacional.

### H.13 — Habilidades (cada linha sintética; não ordenar como ranking canônico)

| Habilidade sintética | Tipo | Usos | Dano efetivo direto | Mediana por uso | Dano/mana | Dano/turno | Custo médio | Efeitos | Contextos | Classificação exploratória |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Golpe calibrado | physical | 17 | 122 | 7.00 | 1.79 | 1.04 | 4.00 | 0 | 5 | potencialmente forte |
| Orbe arcano | arcane | 14 | 162 | 12.00 | 2.89 | 1.93 | 4.00 | 0 | 5 | potencialmente forte |
| Chama controlada | fire | 14 | 162 | 12.00 | 2.89 | 1.93 | 4.00 | 0 | 5 | potencialmente forte |
| Veneno gradual | poison | 17 | 74 | 4.00 | 1.09 | 0.65 | 4.00 | 10 | 5 | potencialmente forte |
| Restauração sintética | heal | 3 | 0 | n/d | n/d | n/d | 4.00 | 0 | 1 | dados insuficientes |
| Técnica de mana restrita | arcane | 0 | 0 | n/d | n/d | 0.00 | n/d | 0 | 5 | dados insuficientes |

H.13 registrou 17 de 26 contrastes com benefício pareado conforme seu critério exploratório; essa contagem não equivale a significância, e as comparações compartilham contextos/seed determinísticos. Cura, efeitos e dano direto têm utilidades distintas.

### H.14 — Comparação de políticas, separada por cenário

Barras de taxa de vitória são comparáveis apenas dentro do mesmo cenário; cada ponto equivale a uma batalha dentre cinco.

#### Nível baixo contra inimigo básico (`low-vs-basic`)

Composição: 1 jogador(es) × 1 inimigo(s); amostras determinísticas pareadas: 5.

| Política | Vitórias/5 | Gráfico | Taxa | Sobrevivência | Dano efetivo do grupo | Dano recebido | Mana IA | Efeitos IA | Rodadas médias |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5/5 | `#####` | 100.00% | 100.00% | 16.00 | 3.00 | 0.00 | 0.00 | 4.00 |
| aggressive | 5/5 | `#####` | 100.00% | 100.00% | 16.00 | 3.00 | 0.00 | 0.00 | 4.00 |
| conservative | 5/5 | `#####` | 100.00% | 100.00% | 16.00 | 3.00 | 0.00 | 0.00 | 4.00 |
| economic | 5/5 | `#####` | 100.00% | 100.00% | 16.00 | 3.00 | 0.00 | 0.00 | 4.00 |
| tactical | 5/5 | `#####` | 100.00% | 100.00% | 16.00 | 3.00 | 0.00 | 0.00 | 4.00 |
| adaptive | 5/5 | `#####` | 100.00% | 100.00% | 16.00 | 3.00 | 0.00 | 0.00 | 4.00 |

#### Personagem contra grupo de inimigos (`player-vs-group`)

Composição: 1 jogador(es) × 3 inimigo(s); amostras determinísticas pareadas: 5.

| Política | Vitórias/5 | Gráfico | Taxa | Sobrevivência | Dano efetivo do grupo | Dano recebido | Mana IA | Efeitos IA | Rodadas médias |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5/5 | `#####` | 100.00% | 100.00% | 72.00 | 9.00 | 0.00 | 0.00 | 6.00 |
| aggressive | 5/5 | `#####` | 100.00% | 100.00% | 72.00 | 9.00 | 0.00 | 0.00 | 6.00 |
| conservative | 5/5 | `#####` | 100.00% | 100.00% | 72.00 | 9.00 | 0.00 | 0.00 | 6.00 |
| economic | 5/5 | `#####` | 100.00% | 100.00% | 72.00 | 9.00 | 0.00 | 0.00 | 6.00 |
| tactical | 5/5 | `#####` | 100.00% | 100.00% | 72.00 | 9.00 | 0.00 | 0.00 | 6.00 |
| adaptive | 5/5 | `#####` | 100.00% | 100.00% | 72.00 | 9.00 | 0.00 | 0.00 | 6.00 |

#### Grupo de jogadores contra boss (`party-vs-boss`)

Composição: 3 jogador(es) × 1 inimigo(s); amostras determinísticas pareadas: 5.

| Política | Vitórias/5 | Gráfico | Taxa | Sobrevivência | Dano efetivo do grupo | Dano recebido | Mana IA | Efeitos IA | Rodadas médias |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0/5 | `-----` | 0% | 0.00% | 253.00 | 245.00 | 0.00 | 0.00 | 28.00 |
| aggressive | 0/5 | `-----` | 0% | 0.00% | 253.00 | 245.00 | 0.00 | 0.00 | 28.00 |
| conservative | 0/5 | `-----` | 0% | 0.00% | 268.00 | 245.00 | 0.00 | 0.00 | 28.00 |
| economic | 0/5 | `-----` | 0% | 0.00% | 253.00 | 245.00 | 0.00 | 0.00 | 28.00 |
| tactical | 0/5 | `-----` | 0% | 0.00% | 253.00 | 245.00 | 0.00 | 0.00 | 28.00 |
| adaptive | 0/5 | `-----` | 0% | 0.00% | 253.00 | 245.00 | 0.00 | 0.00 | 28.00 |

#### Defesa e cura (`defense-and-healing`)

Composição: 2 jogador(es) × 1 inimigo(s); amostras determinísticas pareadas: 5.

| Política | Vitórias/5 | Gráfico | Taxa | Sobrevivência | Dano efetivo do grupo | Dano recebido | Mana IA | Efeitos IA | Rodadas médias |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0/5 | `-----` | 0% | 50.00% | 101.00 | 98.00 | 0.00 | 0.00 | 46.00 |
| aggressive | 0/5 | `-----` | 0% | 50.00% | 101.00 | 98.00 | 0.00 | 0.00 | 46.00 |
| conservative | 0/5 | `-----` | 0% | 100.00% | 101.00 | 33.00 | 0.00 | 0.00 | 34.00 |
| economic | 0/5 | `-----` | 0% | 50.00% | 101.00 | 98.00 | 0.00 | 0.00 | 46.00 |
| tactical | 0/5 | `-----` | 0% | 50.00% | 101.00 | 98.00 | 0.00 | 0.00 | 46.00 |
| adaptive | 0/5 | `-----` | 0% | 50.00% | 101.00 | 98.00 | 0.00 | 0.00 | 46.00 |

#### H.14: fraqueza elemental e ameaça a grupo (`h14-elemental-threat`)

Composição: 2 jogador(es) × 1 inimigo(s); amostras determinísticas pareadas: 5.

| Política | Vitórias/5 | Gráfico | Taxa | Sobrevivência | Dano efetivo do grupo | Dano recebido | Mana IA | Efeitos IA | Rodadas médias |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0/5 | `-----` | 0% | 100.00% | 240.00 | 148.00 | 30.00 | 0.00 | 10.00 |
| aggressive | 0/5 | `-----` | 0% | 100.00% | 240.00 | 148.00 | 30.00 | 0.00 | 10.00 |
| conservative | 0/5 | `-----` | 0% | 100.00% | 240.00 | 10.00 | 0.00 | 0.00 | 10.00 |
| economic | 0/5 | `-----` | 0% | 100.00% | 240.00 | 10.00 | 0.00 | 0.00 | 10.00 |
| tactical | 0/5 | `-----` | 0% | 100.00% | 240.00 | 148.00 | 30.00 | 0.00 | 10.00 |
| adaptive | 0/5 | `-----` | 0% | 100.00% | 240.00 | 125.00 | 25.00 | 0.00 | 10.00 |

#### H.14: decisão sob orçamento de mana (`h14-mana-budget`)

Composição: 2 jogador(es) × 1 inimigo(s); amostras determinísticas pareadas: 5.

| Política | Vitórias/5 | Gráfico | Taxa | Sobrevivência | Dano efetivo do grupo | Dano recebido | Mana IA | Efeitos IA | Rodadas médias |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0/5 | `-----` | 0% | 100.00% | 60.00 | 95.00 | 18.00 | 0.00 | 10.00 |
| aggressive | 0/5 | `-----` | 0% | 100.00% | 60.00 | 95.00 | 18.00 | 0.00 | 10.00 |
| conservative | 0/5 | `-----` | 0% | 100.00% | 60.00 | 40.00 | 0.00 | 0.00 | 10.00 |
| economic | 0/5 | `-----` | 0% | 100.00% | 60.00 | 40.00 | 0.00 | 0.00 | 10.00 |
| tactical | 0/5 | `-----` | 0% | 100.00% | 60.00 | 95.00 | 18.00 | 0.00 | 10.00 |
| adaptive | 0/5 | `-----` | 0% | 100.00% | 60.00 | 82.00 | 16.00 | 0.00 | 10.00 |

#### H.14: aplicação de efeito e alvo já afetado (`h14-effect-priority`)

Composição: 2 jogador(es) × 1 inimigo(s); amostras determinísticas pareadas: 5.

| Política | Vitórias/5 | Gráfico | Taxa | Sobrevivência | Dano efetivo do grupo | Dano recebido | Mana IA | Efeitos IA | Rodadas médias |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0/5 | `-----` | 0% | 100.00% | 60.00 | 112.00 | 24.00 | 0.00 | 10.00 |
| aggressive | 0/5 | `-----` | 0% | 100.00% | 60.00 | 112.00 | 24.00 | 0.00 | 10.00 |
| conservative | 0/5 | `-----` | 0% | 100.00% | 60.00 | 10.00 | 0.00 | 0.00 | 10.00 |
| economic | 0/5 | `-----` | 0% | 100.00% | 60.00 | 10.00 | 0.00 | 0.00 | 10.00 |
| tactical | 0/5 | `-----` | 0% | 100.00% | 60.00 | 100.00 | 24.00 | 4.00 | 10.00 |
| adaptive | 0/5 | `-----` | 0% | 100.00% | 60.00 | 83.00 | 20.00 | 4.00 | 10.00 |

Em H.14, 0 de 175 comparações pareadas contra baseline mudaram o desfecho. A política pode alterar ação, alvo, recursos ou duração sem alterar vitória/derrota; não se declara superioridade. Os intervalos Wilson de origem são nominais e não inferenciais.

## Recomendações

Não há recomendação crítica sustentada pelas fontes. Prioridades abaixo indicam ordem de investigação, não severidade canônica.

| Prioridade | Recomendação | Evidência | Cenários | Métricas | Amostras | Confiança | Próximo experimento |
|---|---|---|---|---|---|---|---|
| alta | Validar a duração/derrota no contraste de defesa | `{"baseline_party_damage_received":12,"baseline_result":"victory","baseline_turns":13,"high_defense_party_damage_received":100,"high_defense_result":"defeat","high_defense_turns":100}` | `["enemy-baseline", "enemy-high-defense"]` | `{"baseline_party_damage_received":12,"baseline_result":"victory","baseline_turns":13,"high_defense_party_damage_received":100,"high_defense_result":"defeat","high_defense_turns":100}` | `{"enemy-baseline":1,"enemy-high-defense":1}` | Baixa: evidência sintética determinística; a maioria dos contrastes citados tem uma execução por configuração. | Executar o contraste pareado em snapshot canônico autorizado, controlando nível, ficha, equipamento, grupo e política. |
| alta | Investigar a sensibilidade de boss ao tamanho do grupo | `{"five_player_damage_received":208,"five_player_result":"victory","five_player_turns":136,"four_player_damage_received":320,"four_player_result":"defeat","four_player_turns":140}` | `["boss-party-4", "boss-party-5"]` | `{"five_player_damage_received":208,"five_player_result":"victory","five_player_turns":136,"four_player_damage_received":320,"four_player_result":"defeat","four_player_turns":140}` | `{"boss-party-4":1,"boss-party-5":1}` | Baixa: evidência sintética determinística; a maioria dos contrastes citados tem uma execução por configuração. | Repetir com encontros autorizados e separar tamanho, cura, iniciativa, equipamentos e composição. |
| média | Comparar ganhos de ataque e defesa de equipamentos | `{"attack_delta_party_damage_received":14,"attack_delta_turns":15,"baseline_party_damage_received":28,"baseline_turns":29,"defense_delta_party_damage_received":14,"defense_delta_turns":29}` | `["equipment-none", "equipment-weapon-plus-6-attack", "equipment-armor-plus-6-defense"]` | `{"attack_delta_party_damage_received":14,"attack_delta_turns":15,"baseline_party_damage_received":28,"baseline_turns":29,"defense_delta_party_damage_received":14,"defense_delta_turns":29}` | `{"equipment-armor-plus-6-defense":1,"equipment-none":1,"equipment-weapon-plus-6-attack":1}` | Baixa: evidência sintética determinística; a maioria dos contrastes citados tem uma execução por configuração. | Comparar itens do catálogo autorizado por slot, raridade, custo e requisitos, mantendo o restante da ficha constante. |
| média | Verificar a eficiência relativa de habilidades diretas | `{"baseline_party_damage_received":28,"baseline_turns":29,"magic_skill_mana":20,"magic_skill_turns":9,"physical_skill_mana":20,"physical_skill_party_damage_received":8,"physical_skill_turns":9}` | `["skill-no-skill", "skill-physical-skill", "skill-magic-skill"]` | `{"baseline_party_damage_received":28,"baseline_turns":29,"magic_skill_mana":20,"magic_skill_turns":9,"physical_skill_mana":20,"physical_skill_party_damage_received":8,"physical_skill_turns":9}` | `{"skill-magic-skill":1,"skill-no-skill":1,"skill-physical-skill":1}` | Baixa: evidência sintética determinística; a maioria dos contrastes citados tem uma execução por configuração. | Comparar habilidades publicadas contra alvos neutros e resistentes, com mana disponível, cooldown e uso controlados. |
| observação | Ampliar contextos de comparação das políticas de IA | `{"paired_comparisons_against_baseline":175,"outcome_changes":0}` | `["low-vs-basic", "player-vs-group", "party-vs-boss", "defense-and-healing", "h14-elemental-threat", "h14-mana-budget", "h14-effect-priority"]` | `["desfecho pareado","dano recebido","mana consumida","efeitos"]` | `{"battles":210,"scenarios":7,"seeds_per_scenario":5}` | Baixa para generalização; alta apenas para reprodutibilidade do lote. | Adicionar cenários sintéticos que isolem decisões e, após autorização, avaliar um snapshot canônico; manter baseline oficial. |
| dados insuficientes | Não concluir balanceamento do catálogo canônico | `{"canonical_entities_loaded":false,"canonical_skill_count":null,"canonical_equipment_count":null}` | `[]` | `"Sem métricas de conteúdo canônico."` | `{"canonical_trials":0,"synthetic_skills_in_h13":6}` | Alta quanto à limitação: fontes H.12/H.13/H.14 declaram escopo sintético. | Obter snapshot canônico sanitizado e versionado em ambiente isolado, com autorização explícita e metas de design definidas. |

## Validade das conclusões

### Fatos demonstrados por simulações sintéticas

- H.11 executou 1.000 batalhas do benchmark low-vs-basic sem falhas; todas foram vitórias e o desvio padrão observado foi zero.
- H.12 completou 45 de 45 configurações sintéticas, com uma execução final por configuração e zero falhas.
- H.13 avaliou 6 habilidades sintéticas em 26 comparações de contexto; as classificações não descrevem o catálogo real.
- H.14 completou 210 batalhas sintéticas em 7 cenários e 6 políticas sem falhas; 0 de 175 comparações pareadas mudaram o desfecho.

### Hipóteses que precisam de novos experimentos

- Os contrastes sintéticos de defesa, tamanho de grupo contra boss, equipamento e custo/eficiência de habilidade merecem validação controlada.
- As diferenças de seleção de ação/alvo e de recursos entre políticas H.14 podem orientar cenários experimentais adicionais.

### Conclusões dependentes do catálogo canônico

- Taxas de vitória, duração e sobrevivência com personagens, inimigos e bosses publicados.
- Curva de valor de equipamentos existentes e seus custos, slots e requisitos.
- Eficiência, disponibilidade e utilização das habilidades canônicas.
- Adequação da estratégia oficial ou parâmetros oficiais de combate.

### Questões sem evidência suficiente

- Dominância, fraqueza ou desequilíbrio canônico.
- Inferência estatística populacional: o motor é determinístico e seeds repetidas não são ensaios aleatórios independentes.
- Comparação agregada de dano/eficiência entre cenários com composições ou condições diferentes.
- Impacto da progressão em builds reais: H.12 manteve atributos não derivados de HP/mana sem distribuição de pontos.

## Limitações e próximos passos

- Nenhum relatório fonte usa entidades canônicas; H.12 não encontrou catálogo versionado no repositório.
- H.11/H.12/H.13/H.14 são desenhos e unidades de análise diferentes; os números não devem ser somados.
- Wilson em H.12/H.14 é nominal/descritivo; não é intervalo inferencial válido para repetições determinísticas.
- H.13 usa métricas diretas e não atribui com segurança dano contínuo ao autor; cura e efeitos não são comparáveis apenas por dano/mana.
- H.14 baseline continua referência e padrão; o relatório não seleciona política oficial.
- Não há visualizações gráficas binárias; este relatório usa tabelas e barras textuais para evitar dependências e misturas de cenários.
- Próximo passo seguro: obter autorização e um snapshot canônico sanitizado/versionado em ambiente isolado, definir metas de design e executar comparações controladas sem alterar regras nesta etapa.
- CSVs detalhados: `etapa-h15-combat-scenarios.csv`, `etapa-h15-combat-skills.csv`, `etapa-h15-combat-strategies.csv` e `etapa-h15-combat-recommendations.csv`.
