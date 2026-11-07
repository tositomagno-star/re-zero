# Etapa H.13 — Identificação de habilidades dominantes e fracas

**Escopo:** exclusivamente sintético; não representa o catálogo canônico. Nenhuma regra de combate foi alterada.

## Resumo

- Habilidades sintéticas avaliadas: **6**.
- Comparações pareadas por contexto: **26**.
- Decisões de IA registradas: **3**.
- Seed: `130`; o motor é determinístico e não usa RNG.
- Cada comparação é uma batalha pareada por cenário e seed; repetir seeds não aumenta a evidência independente.
- Nenhuma conclusão de balanceamento canônico foi feita.

## Classificações exploratórias

| Habilidade sintética | Tipo | Usos | Dano efetivo direto | Dano direto/mana | Dano direto/turno | Custo médio de mana/uso | Efeitos | Contextos | Classificação |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Golpe calibrado | physical / physical | 17 | 122 | 1.79 | 1.04 | 4.00 | 0 | 5 | potencialmente forte |
| Orbe arcano | magic / arcane | 14 | 162 | 2.89 | 1.93 | 4.00 | 0 | 5 | potencialmente forte |
| Chama controlada | magic / fire | 14 | 162 | 2.89 | 1.93 | 4.00 | 0 | 5 | potencialmente forte |
| Veneno gradual | special / poison | 17 | 74 | 1.09 | 0.65 | 4.00 | 10 | 5 | potencialmente forte |
| Restauração sintética | healing / heal | 3 | 0 | n/d | n/d | 4.00 | 0 | 1 | dados insuficientes |
| Técnica de mana restrita | magic / arcane | 0 | 0 | n/d | 0.00 | n/d | 0 | 5 | dados insuficientes |

Todas as classificações são provisórias e referem-se somente aos contrastes sintéticos testados. As amostras determinísticas não sustentam inferência estatística nem conclusões sobre habilidades publicadas.

## Comparações por contexto

| Habilidade | Contexto | Usos | Dano efetivo direto | Dano/mana | Efeitos aplicados | Rodadas controle → habilidade | Delta de rodadas | Resultado controle → habilidade | Sobrevivência do grupo (controle → habilidade) |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| Golpe calibrado | Alvo neutro | 5 | 35 | 1.75 | 0 | 40 → 30 | +25.0% | turn_limit → victory | 100% → 100% |
| Golpe calibrado | Resistência ao tipo da habilidade | 5 | 15 | 0.75 | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Golpe calibrado | Fraqueza ao tipo da habilidade | 5 | 60 | 3.00 | 0 | 30 → 5 | +83.3% | victory → victory | 100% → 100% |
| Golpe calibrado | Defesa e resistência mágica elevadas | 0 | 0 | n/d | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Golpe calibrado | Alvo com pouco HP e risco de overkill | 2 | 12 | 1.50 | 0 | 12 → 2 | +83.3% | victory → victory | 100% → 100% |
| Orbe arcano | Alvo neutro | 5 | 60 | 3.00 | 0 | 40 → 5 | +87.5% | turn_limit → victory | 100% → 100% |
| Orbe arcano | Resistência ao tipo da habilidade | 5 | 30 | 1.50 | 0 | 40 → 35 | +12.5% | turn_limit → victory | 100% → 100% |
| Orbe arcano | Fraqueza ao tipo da habilidade | 3 | 60 | 5.00 | 0 | 40 → 3 | +92.5% | turn_limit → victory | 100% → 100% |
| Orbe arcano | Defesa e resistência mágica elevadas | 0 | 0 | n/d | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Orbe arcano | Alvo com pouco HP e risco de overkill | 1 | 12 | 3.00 | 0 | 12 → 1 | +91.7% | victory → victory | 100% → 100% |
| Chama controlada | Alvo neutro | 5 | 60 | 3.00 | 0 | 40 → 5 | +87.5% | turn_limit → victory | 100% → 100% |
| Chama controlada | Resistência ao tipo da habilidade | 5 | 30 | 1.50 | 0 | 40 → 35 | +12.5% | turn_limit → victory | 100% → 100% |
| Chama controlada | Fraqueza ao tipo da habilidade | 3 | 60 | 5.00 | 0 | 40 → 3 | +92.5% | turn_limit → victory | 100% → 100% |
| Chama controlada | Defesa e resistência mágica elevadas | 0 | 0 | n/d | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Chama controlada | Alvo com pouco HP e risco de overkill | 1 | 12 | 3.00 | 0 | 12 → 1 | +91.7% | victory → victory | 100% → 100% |
| Veneno gradual | Alvo neutro | 5 | 20 | 1.00 | 3 | 40 → 27 | +32.5% | turn_limit → victory | 100% → 100% |
| Veneno gradual | Resistência ao tipo da habilidade | 5 | 10 | 0.50 | 3 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Veneno gradual | Fraqueza ao tipo da habilidade | 5 | 36 | 1.80 | 3 | 40 → 5 | +87.5% | turn_limit → victory | 100% → 100% |
| Veneno gradual | Defesa e resistência mágica elevadas | 0 | 0 | n/d | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Veneno gradual | Alvo com pouco HP e risco de overkill | 2 | 8 | 1.00 | 1 | 12 → 2 | +83.3% | victory → victory | 100% → 100% |
| Técnica de mana restrita | Alvo neutro | 0 | 0 | n/d | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Técnica de mana restrita | Resistência ao tipo da habilidade | 0 | 0 | n/d | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Técnica de mana restrita | Fraqueza ao tipo da habilidade | 0 | 0 | n/d | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Técnica de mana restrita | Defesa e resistência mágica elevadas | 0 | 0 | n/d | 0 | 40 → 40 | +0.0% | turn_limit → turn_limit | 100% → 100% |
| Técnica de mana restrita | Alvo com pouco HP e risco de overkill | 0 | 0 | n/d | 0 | 12 → 12 | +0.0% | victory → victory | 100% → 100% |
| Restauração sintética | Aliado começa com 25% de HP | 3 | 0 | n/d | 0 | 18 → 14 | +22.2% | defeat → turn_limit | 0% → 100% |

## Escolhas da IA

| Caso sintético | Estratégia | Primeira habilidade escolhida | Frequência de escolha no caso | Candidatas elegíveis no primeiro turno | Elegíveis não escolhidas |
|---|---|---|---|---|---|
| enemy-elemental-choice | baseline | Projétil arcano | Explosão de fogo: 50%, Projétil arcano: 50% | Explosão de fogo, Projétil arcano | Explosão de fogo |
| enemy-elemental-choice | elemental_weakness | Explosão de fogo | Explosão de fogo: 50%, Projétil arcano: 50% | Explosão de fogo, Projétil arcano | Projétil arcano |
| enemy-mana-choice | baseline | Feitiço econômico | Feitiço econômico: 100%, Feitiço caro: 0% | Feitiço econômico, Feitiço caro | Feitiço caro |

## Limitações

- O motor não modela acerto, erro, precisão, evasão ou críticos; taxa de acerto não se aplica.
- Tentativas rejeitadas e motivos de inelegibilidade durante turnos posteriores não são persistidos nos eventos do simulador.
- Dano contínuo é registrado como efeito do alvo sem atribuição confiável ao conjurador; não é creditado ao dano efetivo direto da habilidade.
- Contribuição causal de vitória por habilidade não é uma métrica do motor; o contraste pareado de resultado/turnos é apenas evidência exploratória.
- Alvos por uso contam alvos diretos de ação; alvos dos efeitos são informados separadamente.
- A habilidade selecionada pode ser impedida por custo, cooldown, alcance, alvo inválido ou estratégia; só a insuficiência inicial de mana e elegibilidade do primeiro turno nos casos definidos são inferíveis.
- Não foram acessados PostgreSQL, `cronicas_do_reino_dev` ou `cronicas_do_reino_test`.
- Não foram executadas migrations, nem alterados dados persistentes ou regras canônicas.
- Os nomes e atributos deste estudo são sintéticos; ausência de catálogo canônico impede conclusões sobre conteúdo real.

## Fatos observados, hipóteses e conclusões

### Fatos nos testes sintéticos

- 17 de 26 contrastes mostraram benefício pareado (resultado melhor, ou mesmo resultado com mais dano efetivo ou menos rodadas); são observações determinísticas.
- Foram observadas 10 aplicações de efeitos e 60 pontos de cura efetiva no conjunto sintético.
- Na escolha elemental, baseline selecionou Projétil arcano e elemental_weakness selecionou Explosão de fogo.
- No cenário de custo, baseline selecionou Feitiço econômico entre habilidades sintéticas de mesmo dano e custos diferentes.
- As métricas não permitem inferir uso real nem balanceamento do catálogo canônico.

### Hipóteses para investigação

- Fraquezas, resistências, defesa e HP do alvo alteram eficiência direta e podem alterar a escolha da IA.
- A eficiência observada de efeitos contínuos é subestimada no dano por mana por falta de atribuição de ticks no motor.

### Conclusão canônica

Nenhuma habilidade canônica pode ser classificada: o catálogo canônico não foi lido.

### Critérios provisórios

- **potentially_dominant:** provisório: pelo menos 5 contextos, 30 usos observados, redução mediana de turnos >=25%, benefício em >=80% dos contextos pareados e nenhum contexto pior
- **potentially_strong:** provisório: pelo menos 3 contextos, benefício em >=60% e nenhum contexto pior
- **potentially_weak:** provisório: pelo menos 3 contextos e 3 usos, benefício pareado inferior a 10% em >=60% dos casos e nenhum benefício >=10%
- **within_range:** provisório: pelo menos 3 contextos, resultados iguais e variações de dano e rodadas inferiores a 10% em todos
- **insufficient:** demais situações ou habilidade sem uso observado

Os limiares são critérios experimentais para explorar estes dados sintéticos, não regras oficiais. A contagem de usos descreve ações observadas, não ensaios estatísticos independentes. Benefício pareado significa resultado melhor; ou, com o mesmo resultado, dano efetivo do grupo ou rodadas melhores em pelo menos 10%.

## Artefatos

Os dados completos estão em `etapa-h13-skill-balance-analysis.json` e as linhas comparáveis em `etapa-h13-skill-balance-analysis.csv`.
