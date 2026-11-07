# Etapa H.14 — Comparação de estratégias alternativas da IA

**Escopo:** cenários sintéticos executados no motor H.4/H.7 por meio do simulador H.11. A IA oficial continua inalterada.

## Resumo

- Políticas avaliadas: baseline, aggressive, conservative, economic, tactical, adaptive.
- Cenários: **7**; batalhas: **210**.
- A taxa de vitória refere-se ao grupo jogador contra a IA: `party/player group victory against the enemy AI`.
- Seeds pareadas: `140, 141, 142, 143, 144`.
- Versão das políticas: `h14-experimental-ai-v1`.
- Os resultados são separados por cenário, sem misturar tamanhos de grupo ou dificuldades.

| Política | Regra de seleção experimental |
|---|---|
| baseline | H.4 baseline atual; permanece a referência e o padrão oficial. |
| aggressive | Prioriza eliminação e dano efetivo; não altera a resolução. |
| conservative | Prioriza eliminar alvos de maior ameaça (ataque + magia + velocidade), depois custo e dano. |
| economic | Minimiza custo de mana antes de dano e eliminação. |
| tactical | Prioriza fraqueza elemental, novo efeito aplicável, eliminação e dano. |
| adaptive | Com mana acima de 25% do máximo usa prioridade tática; abaixo disso usa prioridade econômica. |

## Resultados por cenário

### Nível baixo contra inimigo básico

Composição: 1 jogador(es) × 1 inimigo(s). Cenário `low-vs-basic`.

| Estratégia IA | Vitórias do grupo | Derrotas | Empates | Limite | Taxa de vitória do grupo | IC Wilson 95% nominal | Sobrevivência grupo | HP grupo restante | Dano grupo | Dano recebido pelo grupo | Mana IA usada/restante | Dano efetivo IA | Mana IA por habilidade | Dano IA/habilidade/mana | Cura grupo | Efeitos IA | Rodadas | Jogadores derrotados | Inimigos derrotados | Foco do alvo IA | Falhas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 21.00 | 16.00 | 3.00 | 0.00/0.00 | 3.00 | 0.00 | n/d | 0.00 | 0.00 | 4.00 | 0.00 | 1.00 | 100% | 0 |
| aggressive | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 21.00 | 16.00 | 3.00 | 0.00/0.00 | 3.00 | 0.00 | n/d | 0.00 | 0.00 | 4.00 | 0.00 | 1.00 | 100% | 0 |
| conservative | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 21.00 | 16.00 | 3.00 | 0.00/0.00 | 3.00 | 0.00 | n/d | 0.00 | 0.00 | 4.00 | 0.00 | 1.00 | 100% | 0 |
| economic | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 21.00 | 16.00 | 3.00 | 0.00/0.00 | 3.00 | 0.00 | n/d | 0.00 | 0.00 | 4.00 | 0.00 | 1.00 | 100% | 0 |
| tactical | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 21.00 | 16.00 | 3.00 | 0.00/0.00 | 3.00 | 0.00 | n/d | 0.00 | 0.00 | 4.00 | 0.00 | 1.00 | 100% | 0 |
| adaptive | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 21.00 | 16.00 | 3.00 | 0.00/0.00 | 3.00 | 0.00 | n/d | 0.00 | 0.00 | 4.00 | 0.00 | 1.00 | 100% | 0 |

#### Comparação pareada com baseline

| Estratégia | Pares | Mesmo resultado | Vitórias adicionadas | Vitórias perdidas | Delta médio de rodadas |
|---|---:|---:|---:|---:|---:|
| aggressive | 5 | 5 | 0 | 0 | 0.00 |
| conservative | 5 | 5 | 0 | 0 | 0.00 |
| economic | 5 | 5 | 0 | 0 | 0.00 |
| tactical | 5 | 5 | 0 | 0 | 0.00 |
| adaptive | 5 | 5 | 0 | 0 | 0.00 |

#### Seleção de alvos e ações

- **baseline:** alvos IA `{"Aprendiz": 15}`; ações IA `{"attack": 15}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **aggressive:** alvos IA `{"Aprendiz": 15}`; ações IA `{"attack": 15}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **conservative:** alvos IA `{"Aprendiz": 15}`; ações IA `{"attack": 15}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **economic:** alvos IA `{"Aprendiz": 15}`; ações IA `{"attack": 15}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **tactical:** alvos IA `{"Aprendiz": 15}`; ações IA `{"attack": 15}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **adaptive:** alvos IA `{"Aprendiz": 15}`; ações IA `{"attack": 15}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.

### Personagem contra grupo de inimigos

Composição: 1 jogador(es) × 3 inimigo(s). Cenário `player-vs-group`.

| Estratégia IA | Vitórias do grupo | Derrotas | Empates | Limite | Taxa de vitória do grupo | IC Wilson 95% nominal | Sobrevivência grupo | HP grupo restante | Dano grupo | Dano recebido pelo grupo | Mana IA usada/restante | Dano efetivo IA | Mana IA por habilidade | Dano IA/habilidade/mana | Cura grupo | Efeitos IA | Rodadas | Jogadores derrotados | Inimigos derrotados | Foco do alvo IA | Falhas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 76.00 | 72.00 | 9.00 | 0.00/0.00 | 9.00 | 0.00 | n/d | 0.00 | 0.00 | 6.00 | 0.00 | 3.00 | 100% | 0 |
| aggressive | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 76.00 | 72.00 | 9.00 | 0.00/0.00 | 9.00 | 0.00 | n/d | 0.00 | 0.00 | 6.00 | 0.00 | 3.00 | 100% | 0 |
| conservative | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 76.00 | 72.00 | 9.00 | 0.00/0.00 | 9.00 | 0.00 | n/d | 0.00 | 0.00 | 6.00 | 0.00 | 3.00 | 100% | 0 |
| economic | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 76.00 | 72.00 | 9.00 | 0.00/0.00 | 9.00 | 0.00 | n/d | 0.00 | 0.00 | 6.00 | 0.00 | 3.00 | 100% | 0 |
| tactical | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 76.00 | 72.00 | 9.00 | 0.00/0.00 | 9.00 | 0.00 | n/d | 0.00 | 0.00 | 6.00 | 0.00 | 3.00 | 100% | 0 |
| adaptive | 5 | 0 | 0 | 0 | 100% | 57%–100% | 100% | 76.00 | 72.00 | 9.00 | 0.00/0.00 | 9.00 | 0.00 | n/d | 0.00 | 0.00 | 6.00 | 0.00 | 3.00 | 100% | 0 |

#### Comparação pareada com baseline

| Estratégia | Pares | Mesmo resultado | Vitórias adicionadas | Vitórias perdidas | Delta médio de rodadas |
|---|---:|---:|---:|---:|---:|
| aggressive | 5 | 5 | 0 | 0 | 0.00 |
| conservative | 5 | 5 | 0 | 0 | 0.00 |
| economic | 5 | 5 | 0 | 0 | 0.00 |
| tactical | 5 | 5 | 0 | 0 | 0.00 |
| adaptive | 5 | 5 | 0 | 0 | 0.00 |

#### Seleção de alvos e ações

- **baseline:** alvos IA `{"Guardião": 45}`; ações IA `{"attack": 45}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `33%`; turnos sem ação válida `0`.
- **aggressive:** alvos IA `{"Guardião": 45}`; ações IA `{"attack": 45}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `33%`; turnos sem ação válida `0`.
- **conservative:** alvos IA `{"Guardião": 45}`; ações IA `{"attack": 45}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `33%`; turnos sem ação válida `0`.
- **economic:** alvos IA `{"Guardião": 45}`; ações IA `{"attack": 45}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `33%`; turnos sem ação válida `0`.
- **tactical:** alvos IA `{"Guardião": 45}`; ações IA `{"attack": 45}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `33%`; turnos sem ação válida `0`.
- **adaptive:** alvos IA `{"Guardião": 45}`; ações IA `{"attack": 45}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `33%`; turnos sem ação válida `0`.

### Grupo de jogadores contra boss

Composição: 3 jogador(es) × 1 inimigo(s). Cenário `party-vs-boss`.

| Estratégia IA | Vitórias do grupo | Derrotas | Empates | Limite | Taxa de vitória do grupo | IC Wilson 95% nominal | Sobrevivência grupo | HP grupo restante | Dano grupo | Dano recebido pelo grupo | Mana IA usada/restante | Dano efetivo IA | Mana IA por habilidade | Dano IA/habilidade/mana | Cura grupo | Efeitos IA | Rodadas | Jogadores derrotados | Inimigos derrotados | Foco do alvo IA | Falhas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0 | 5 | 0 | 0 | 0% | 0%–43% | 0% | 0.00 | 253.00 | 245.00 | 0.00/20.00 | 245.00 | 0.00 | n/d | 0.00 | 0.00 | 28.00 | 3.00 | 0.00 | 61% | 0 |
| aggressive | 0 | 5 | 0 | 0 | 0% | 0%–43% | 0% | 0.00 | 253.00 | 245.00 | 0.00/20.00 | 245.00 | 0.00 | n/d | 0.00 | 0.00 | 28.00 | 3.00 | 0.00 | 61% | 0 |
| conservative | 0 | 5 | 0 | 0 | 0% | 0%–43% | 0% | 0.00 | 268.00 | 245.00 | 0.00/20.00 | 245.00 | 0.00 | n/d | 0.00 | 0.00 | 28.00 | 3.00 | 0.00 | 61% | 0 |
| economic | 0 | 5 | 0 | 0 | 0% | 0%–43% | 0% | 0.00 | 253.00 | 245.00 | 0.00/20.00 | 245.00 | 0.00 | n/d | 0.00 | 0.00 | 28.00 | 3.00 | 0.00 | 61% | 0 |
| tactical | 0 | 5 | 0 | 0 | 0% | 0%–43% | 0% | 0.00 | 253.00 | 245.00 | 0.00/20.00 | 245.00 | 0.00 | n/d | 0.00 | 0.00 | 28.00 | 3.00 | 0.00 | 61% | 0 |
| adaptive | 0 | 5 | 0 | 0 | 0% | 0%–43% | 0% | 0.00 | 253.00 | 245.00 | 0.00/20.00 | 245.00 | 0.00 | n/d | 0.00 | 0.00 | 28.00 | 3.00 | 0.00 | 61% | 0 |

#### Comparação pareada com baseline

| Estratégia | Pares | Mesmo resultado | Vitórias adicionadas | Vitórias perdidas | Delta médio de rodadas |
|---|---:|---:|---:|---:|---:|
| aggressive | 5 | 5 | 0 | 0 | 0.00 |
| conservative | 5 | 5 | 0 | 0 | 0.00 |
| economic | 5 | 5 | 0 | 0 | 0.00 |
| tactical | 5 | 5 | 0 | 0 | 0.00 |
| adaptive | 5 | 5 | 0 | 0 | 0.00 |

#### Seleção de alvos e ações

- **baseline:** alvos IA `{"Arcanista": 25, "Curandeira": 30, "Vanguarda": 85}`; ações IA `{"attack": 140}`; habilidades IA `{}`; foco médio `61%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **aggressive:** alvos IA `{"Arcanista": 25, "Curandeira": 30, "Vanguarda": 85}`; ações IA `{"attack": 140}`; habilidades IA `{}`; foco médio `61%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **conservative:** alvos IA `{"Vanguarda": 85, "Arcanista": 25, "Curandeira": 30}`; ações IA `{"attack": 140}`; habilidades IA `{}`; foco médio `61%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **economic:** alvos IA `{"Arcanista": 25, "Curandeira": 30, "Vanguarda": 85}`; ações IA `{"attack": 140}`; habilidades IA `{}`; foco médio `61%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **tactical:** alvos IA `{"Arcanista": 25, "Curandeira": 30, "Vanguarda": 85}`; ações IA `{"attack": 140}`; habilidades IA `{}`; foco médio `61%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **adaptive:** alvos IA `{"Arcanista": 25, "Curandeira": 30, "Vanguarda": 85}`; ações IA `{"attack": 140}`; habilidades IA `{}`; foco médio `61%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.

### Defesa e cura

Composição: 2 jogador(es) × 1 inimigo(s). Cenário `defense-and-healing`.

| Estratégia IA | Vitórias do grupo | Derrotas | Empates | Limite | Taxa de vitória do grupo | IC Wilson 95% nominal | Sobrevivência grupo | HP grupo restante | Dano grupo | Dano recebido pelo grupo | Mana IA usada/restante | Dano efetivo IA | Mana IA por habilidade | Dano IA/habilidade/mana | Cura grupo | Efeitos IA | Rodadas | Jogadores derrotados | Inimigos derrotados | Foco do alvo IA | Falhas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0 | 0 | 0 | 5 | 0% | 0%–43% | 50% | 74.00 | 101.00 | 98.00 | 0.00/0.00 | 98.00 | 0.00 | n/d | 0.00 | 0.00 | 46.00 | 1.00 | 0.00 | 80% | 0 |
| aggressive | 0 | 0 | 0 | 5 | 0% | 0%–43% | 50% | 74.00 | 101.00 | 98.00 | 0.00/0.00 | 98.00 | 0.00 | n/d | 0.00 | 0.00 | 46.00 | 1.00 | 0.00 | 80% | 0 |
| conservative | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 139.00 | 101.00 | 33.00 | 0.00/0.00 | 33.00 | 0.00 | n/d | 0.00 | 0.00 | 34.00 | 0.00 | 0.00 | 100% | 0 |
| economic | 0 | 0 | 0 | 5 | 0% | 0%–43% | 50% | 74.00 | 101.00 | 98.00 | 0.00/0.00 | 98.00 | 0.00 | n/d | 0.00 | 0.00 | 46.00 | 1.00 | 0.00 | 80% | 0 |
| tactical | 0 | 0 | 0 | 5 | 0% | 0%–43% | 50% | 74.00 | 101.00 | 98.00 | 0.00/0.00 | 98.00 | 0.00 | n/d | 0.00 | 0.00 | 46.00 | 1.00 | 0.00 | 80% | 0 |
| adaptive | 0 | 0 | 0 | 5 | 0% | 0%–43% | 50% | 74.00 | 101.00 | 98.00 | 0.00/0.00 | 98.00 | 0.00 | n/d | 0.00 | 0.00 | 46.00 | 1.00 | 0.00 | 80% | 0 |

#### Comparação pareada com baseline

| Estratégia | Pares | Mesmo resultado | Vitórias adicionadas | Vitórias perdidas | Delta médio de rodadas |
|---|---:|---:|---:|---:|---:|
| aggressive | 5 | 5 | 0 | 0 | 0.00 |
| conservative | 5 | 5 | 0 | 0 | -12.00 |
| economic | 5 | 5 | 0 | 0 | 0.00 |
| tactical | 5 | 5 | 0 | 0 | 0.00 |
| adaptive | 5 | 5 | 0 | 0 | 0.00 |

#### Seleção de alvos e ações

- **baseline:** alvos IA `{"Aliada": 45, "Protetor": 180}`; ações IA `{"attack": 225}`; habilidades IA `{}`; foco médio `80%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **aggressive:** alvos IA `{"Aliada": 45, "Protetor": 180}`; ações IA `{"attack": 225}`; habilidades IA `{}`; foco médio `80%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **conservative:** alvos IA `{"Protetor": 165}`; ações IA `{"attack": 165}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **economic:** alvos IA `{"Aliada": 45, "Protetor": 180}`; ações IA `{"attack": 225}`; habilidades IA `{}`; foco médio `80%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **tactical:** alvos IA `{"Aliada": 45, "Protetor": 180}`; ações IA `{"attack": 225}`; habilidades IA `{}`; foco médio `80%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **adaptive:** alvos IA `{"Aliada": 45, "Protetor": 180}`; ações IA `{"attack": 225}`; habilidades IA `{}`; foco médio `80%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.

### H.14: fraqueza elemental e ameaça a grupo

Composição: 2 jogador(es) × 1 inimigo(s). Cenário `h14-elemental-threat`.

| Estratégia IA | Vitórias do grupo | Derrotas | Empates | Limite | Taxa de vitória do grupo | IC Wilson 95% nominal | Sobrevivência grupo | HP grupo restante | Dano grupo | Dano recebido pelo grupo | Mana IA usada/restante | Dano efetivo IA | Mana IA por habilidade | Dano IA/habilidade/mana | Cura grupo | Efeitos IA | Rodadas | Jogadores derrotados | Inimigos derrotados | Foco do alvo IA | Falhas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 332.00 | 240.00 | 148.00 | 30.00/0.00 | 148.00 | 30.00 | 4.80 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 60% | 0 |
| aggressive | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 332.00 | 240.00 | 148.00 | 30.00/0.00 | 148.00 | 30.00 | 4.80 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 60% | 0 |
| conservative | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 470.00 | 240.00 | 10.00 | 0.00/30.00 | 10.00 | 0.00 | n/d | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| economic | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 470.00 | 240.00 | 10.00 | 0.00/30.00 | 10.00 | 0.00 | n/d | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| tactical | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 332.00 | 240.00 | 148.00 | 30.00/0.00 | 148.00 | 30.00 | 4.80 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 60% | 0 |
| adaptive | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 355.00 | 240.00 | 125.00 | 25.00/5.00 | 125.00 | 25.00 | 4.80 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 50% | 0 |

#### Comparação pareada com baseline

| Estratégia | Pares | Mesmo resultado | Vitórias adicionadas | Vitórias perdidas | Delta médio de rodadas |
|---|---:|---:|---:|---:|---:|
| aggressive | 5 | 5 | 0 | 0 | 0.00 |
| conservative | 5 | 5 | 0 | 0 | 0.00 |
| economic | 5 | 5 | 0 | 0 | 0.00 |
| tactical | 5 | 5 | 0 | 0 | 0.00 |
| adaptive | 5 | 5 | 0 | 0 | 0.00 |

#### Seleção de alvos e ações

- **baseline:** alvos IA `{"Alvo vulnerável": 30, "Alvo resistente": 20}`; ações IA `{"skill": 30, "attack": 20}`; habilidades IA `{"Chama fraca": {"uses": 30, "effective_damage": 720, "healing": 0, "mana_cost": 150, "effect_application_count": 0, "damage_per_mana": 4.8, "healing_per_mana": 0.0}}`; foco médio `60%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **aggressive:** alvos IA `{"Alvo vulnerável": 30, "Alvo resistente": 20}`; ações IA `{"skill": 30, "attack": 20}`; habilidades IA `{"Chama fraca": {"uses": 30, "effective_damage": 720, "healing": 0, "mana_cost": 150, "effect_application_count": 0, "damage_per_mana": 4.8, "healing_per_mana": 0.0}}`; foco médio `60%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **conservative:** alvos IA `{"Alvo resistente": 50}`; ações IA `{"attack": 50}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **economic:** alvos IA `{"Alvo resistente": 50}`; ações IA `{"attack": 50}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **tactical:** alvos IA `{"Alvo vulnerável": 30, "Alvo resistente": 20}`; ações IA `{"skill": 30, "attack": 20}`; habilidades IA `{"Chama fraca": {"uses": 30, "effective_damage": 720, "healing": 0, "mana_cost": 150, "effect_application_count": 0, "damage_per_mana": 4.8, "healing_per_mana": 0.0}}`; foco médio `60%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **adaptive:** alvos IA `{"Alvo vulnerável": 25, "Alvo resistente": 25}`; ações IA `{"skill": 25, "attack": 25}`; habilidades IA `{"Chama fraca": {"uses": 25, "effective_damage": 600, "healing": 0, "mana_cost": 125, "effect_application_count": 0, "damage_per_mana": 4.8, "healing_per_mana": 0.0}}`; foco médio `50%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.

### H.14: decisão sob orçamento de mana

Composição: 2 jogador(es) × 1 inimigo(s). Cenário `h14-mana-budget`.

| Estratégia IA | Vitórias do grupo | Derrotas | Empates | Limite | Taxa de vitória do grupo | IC Wilson 95% nominal | Sobrevivência grupo | HP grupo restante | Dano grupo | Dano recebido pelo grupo | Mana IA usada/restante | Dano efetivo IA | Mana IA por habilidade | Dano IA/habilidade/mana | Cura grupo | Efeitos IA | Rodadas | Jogadores derrotados | Inimigos derrotados | Foco do alvo IA | Falhas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 605.00 | 60.00 | 95.00 | 18.00/0.00 | 95.00 | 18.00 | 3.72 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| aggressive | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 605.00 | 60.00 | 95.00 | 18.00/0.00 | 95.00 | 18.00 | 3.72 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| conservative | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 660.00 | 60.00 | 40.00 | 0.00/18.00 | 40.00 | 0.00 | n/d | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| economic | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 660.00 | 60.00 | 40.00 | 0.00/18.00 | 40.00 | 0.00 | n/d | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| tactical | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 605.00 | 60.00 | 95.00 | 18.00/0.00 | 95.00 | 18.00 | 3.72 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| adaptive | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 618.00 | 60.00 | 82.00 | 16.00/2.00 | 82.00 | 16.00 | 3.12 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |

#### Comparação pareada com baseline

| Estratégia | Pares | Mesmo resultado | Vitórias adicionadas | Vitórias perdidas | Delta médio de rodadas |
|---|---:|---:|---:|---:|---:|
| aggressive | 5 | 5 | 0 | 0 | 0.00 |
| conservative | 5 | 5 | 0 | 0 | 0.00 |
| economic | 5 | 5 | 0 | 0 | 0.00 |
| tactical | 5 | 5 | 0 | 0 | 0.00 |
| adaptive | 5 | 5 | 0 | 0 | 0.00 |

#### Seleção de alvos e ações

- **baseline:** alvos IA `{"Alvo durável A": 50}`; ações IA `{"skill": 15, "attack": 35}`; habilidades IA `{"Rajada custosa": {"uses": 10, "effective_damage": 250, "healing": 0, "mana_cost": 80, "effect_application_count": 0, "damage_per_mana": 3.125, "healing_per_mana": 0.0}, "Raio econômico": {"uses": 5, "effective_damage": 85, "healing": 0, "mana_cost": 10, "effect_application_count": 0, "damage_per_mana": 8.5, "healing_per_mana": 0.0}}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **aggressive:** alvos IA `{"Alvo durável A": 50}`; ações IA `{"skill": 15, "attack": 35}`; habilidades IA `{"Rajada custosa": {"uses": 10, "effective_damage": 250, "healing": 0, "mana_cost": 80, "effect_application_count": 0, "damage_per_mana": 3.125, "healing_per_mana": 0.0}, "Raio econômico": {"uses": 5, "effective_damage": 85, "healing": 0, "mana_cost": 10, "effect_application_count": 0, "damage_per_mana": 8.5, "healing_per_mana": 0.0}}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **conservative:** alvos IA `{"Alvo durável A": 50}`; ações IA `{"attack": 50}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **economic:** alvos IA `{"Alvo durável A": 50}`; ações IA `{"attack": 50}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **tactical:** alvos IA `{"Alvo durável A": 50}`; ações IA `{"skill": 15, "attack": 35}`; habilidades IA `{"Rajada custosa": {"uses": 10, "effective_damage": 250, "healing": 0, "mana_cost": 80, "effect_application_count": 0, "damage_per_mana": 3.125, "healing_per_mana": 0.0}, "Raio econômico": {"uses": 5, "effective_damage": 85, "healing": 0, "mana_cost": 10, "effect_application_count": 0, "damage_per_mana": 8.5, "healing_per_mana": 0.0}}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **adaptive:** alvos IA `{"Alvo durável A": 50}`; ações IA `{"skill": 10, "attack": 40}`; habilidades IA `{"Rajada custosa": {"uses": 10, "effective_damage": 250, "healing": 0, "mana_cost": 80, "effect_application_count": 0, "damage_per_mana": 3.125, "healing_per_mana": 0.0}}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.

### H.14: aplicação de efeito e alvo já afetado

Composição: 2 jogador(es) × 1 inimigo(s). Cenário `h14-effect-priority`.

| Estratégia IA | Vitórias do grupo | Derrotas | Empates | Limite | Taxa de vitória do grupo | IC Wilson 95% nominal | Sobrevivência grupo | HP grupo restante | Dano grupo | Dano recebido pelo grupo | Mana IA usada/restante | Dano efetivo IA | Mana IA por habilidade | Dano IA/habilidade/mana | Cura grupo | Efeitos IA | Rodadas | Jogadores derrotados | Inimigos derrotados | Foco do alvo IA | Falhas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 488.00 | 60.00 | 112.00 | 24.00/0.00 | 112.00 | 24.00 | 4.50 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| aggressive | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 488.00 | 60.00 | 112.00 | 24.00/0.00 | 112.00 | 24.00 | 4.50 | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| conservative | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 590.00 | 60.00 | 10.00 | 0.00/24.00 | 10.00 | 0.00 | n/d | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| economic | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 590.00 | 60.00 | 10.00 | 0.00/24.00 | 10.00 | 0.00 | n/d | 0.00 | 0.00 | 10.00 | 0.00 | 0.00 | 100% | 0 |
| tactical | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 500.00 | 60.00 | 100.00 | 24.00/0.00 | 100.00 | 24.00 | 2.00 | 0.00 | 4.00 | 10.00 | 0.00 | 0.00 | 80% | 0 |
| adaptive | 0 | 0 | 0 | 5 | 0% | 0%–43% | 100% | 517.00 | 60.00 | 83.00 | 20.00/4.00 | 83.00 | 20.00 | 1.50 | 0.00 | 4.00 | 10.00 | 0.00 | 0.00 | 80% | 0 |

#### Comparação pareada com baseline

| Estratégia | Pares | Mesmo resultado | Vitórias adicionadas | Vitórias perdidas | Delta médio de rodadas |
|---|---:|---:|---:|---:|---:|
| aggressive | 5 | 5 | 0 | 0 | 0.00 |
| conservative | 5 | 5 | 0 | 0 | 0.00 |
| economic | 5 | 5 | 0 | 0 | 0.00 |
| tactical | 5 | 5 | 0 | 0 | 0.00 |
| adaptive | 5 | 5 | 0 | 0 | 0.00 |

#### Seleção de alvos e ações

- **baseline:** alvos IA `{"Defensor A": 50}`; ações IA `{"skill": 30, "attack": 20}`; habilidades IA `{"Pulso arcano": {"uses": 30, "effective_damage": 540, "healing": 0, "mana_cost": 120, "effect_application_count": 0, "damage_per_mana": 4.5, "healing_per_mana": 0.0}}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **aggressive:** alvos IA `{"Defensor A": 50}`; ações IA `{"skill": 30, "attack": 20}`; habilidades IA `{"Pulso arcano": {"uses": 30, "effective_damage": 540, "healing": 0, "mana_cost": 120, "effect_application_count": 0, "damage_per_mana": 4.5, "healing_per_mana": 0.0}}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **conservative:** alvos IA `{"Defensor A": 50}`; ações IA `{"attack": 50}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **economic:** alvos IA `{"Defensor A": 50}`; ações IA `{"attack": 50}`; habilidades IA `{}`; foco médio `100%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **tactical:** alvos IA `{"Defensor A": 40, "Defensor B": 10}`; ações IA `{"skill": 30, "attack": 20}`; habilidades IA `{"Toxina persistente": {"uses": 20, "effective_damage": 60, "healing": 0, "mana_cost": 80, "effect_application_count": 20, "damage_per_mana": 0.75, "healing_per_mana": 0.0}, "Pulso arcano": {"uses": 10, "effective_damage": 180, "healing": 0, "mana_cost": 40, "effect_application_count": 0, "damage_per_mana": 4.5, "healing_per_mana": 0.0}}`; foco médio `80%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.
- **adaptive:** alvos IA `{"Defensor A": 40, "Defensor B": 10}`; ações IA `{"skill": 25, "attack": 25}`; habilidades IA `{"Toxina persistente": {"uses": 20, "effective_damage": 60, "healing": 0, "mana_cost": 80, "effect_application_count": 20, "damage_per_mana": 0.75, "healing_per_mana": 0.0}, "Pulso arcano": {"uses": 5, "effective_damage": 90, "healing": 0, "mana_cost": 20, "effect_application_count": 0, "damage_per_mana": 4.5, "healing_per_mana": 0.0}}`; foco médio `80%`; foco de alvo do grupo `100%`; turnos sem ação válida `0`.

## Resultados sintéticos observados

- Em 175 pares de estratégia contra baseline, 0 tiveram resultado de batalha diferente; os seeds repetem execuções determinísticas e não são amostras independentes.
- No cenário sintético de efeitos, baseline aplicou em média 0.0 efeitos/batalha e tactical 4.0; a comparação não alterou as regras de dano contínuo.
- No orçamento sintético de mana, baseline consumiu em média 18.0 mana por batalha e economic 0.0; o resultado de batalha deve ser lido no contexto e na tabela pareada desse cenário.
- No encontro elemental sintético, a contagem de alvos escolhidos pela política tática foi {"Alvo vulnerável": 30, "Alvo resistente": 20}.
- Contra o boss sintético, conservadora e baseline tiveram {'victory': 0, 'defeat': 5, 'draw': 0, 'turn_limit': 0} e {'victory': 0, 'defeat': 5, 'draw': 0, 'turn_limit': 0} respectivamente; seleção diferente não melhorou o resultado nesse contexto.

## Hipóteses

- Políticas econômicas podem preservar mana enquanto prolongam a exposição ao dano.
- A prioridade de ameaça da política conservadora pode ser útil contra composições com inimigos de alto ataque.
- A política adaptativa pode combinar eficiência de alvo e custo quando há restrição de mana.

## Limitações estatísticas e do motor

A amostra por cenário é pequena e determinística; não se declara superioridade nem significância estatística. Pares descrevem diferenças observadas, não estimativas populacionais.

- A IA oficial permanece baseline; as estratégias H.14 são escolhas explícitas do simulador.
- O motor atual não oferece ação defensiva explícita, então 'conservative' conserva mana e prioriza ameaças, sem criar defesa.
- Os seeds pareados são reproduzíveis, mas o motor não usa RNG; repetir seeds não gera ensaios independentes.
- O intervalo de Wilson é apresentado somente como referência nominal descritiva e não como inferência válida para estes seeds determinísticos.
- O motor registra ações resolvidas, mas não registra tentativas inválidas rejeitadas; falhas de simulação são reportadas separadamente.
- Os agregados de habilidades H.11 são agrupados por nome de exibição; nomes iguais entre os lados podem ser combinados e não ocorreram nos cenários H.14.
- Dano contínuo fica contabilizado como dano recebido pelo grupo alvo, mas não pode ser atribuído ao autor original pelas métricas de participante do motor.
- Ações em área, cooperação coordenada, controle de condições avançado e inteligência de grupo não fazem parte do contrato atual do motor.

Os intervalos de Wilson são nominais e não devem ser interpretados como intervalos inferenciais: o motor é determinístico e seeds diferentes só mudam identificadores. Nenhuma estratégia é declarada superior ou adotada como política oficial.

## Estratégias para investigação posterior

- Repetir a matriz com catálogo canônico somente após autorização explícita de acesso aos dados, fora desta etapa.
- Ampliar cenários sintéticos de grupo para testar ameaça, seleção de alvo e habilidades de cura/efeito.
- Instrumentar rejeições e ações inelegíveis no simulador antes de tirar conclusões sobre falhas de decisão.
- Adicionar uma ação defensiva formal ao motor apenas em etapa própria, com revisão das regras; H.14 não altera o motor.

## Artefatos

Dados completos: `etapa-h14-ai-strategy-comparison.json`; métricas por batalha/estratégia: `etapa-h14-ai-strategy-comparison.csv`.
