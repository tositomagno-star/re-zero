# Etapa H.7 — Balanceamento e evolução do combate

## Status

**Regras compartilhadas e lacunas de atributos corrigidas; balanceamento integral ainda não certificado.** Foram adicionados cálculos reproduzíveis e uma seleção tática determinística para a IA. Os cenários abaixo são microbenchmarks da fórmula, não uma simulação de duração média de batalhas reais.

## Auditoria das regras existentes

A auditoria tomou as etapas H.1–H.6 como contratos. O fluxo continua usando os snapshots de combate H.4, animações H.1/H.2 e perfis/associações H.3; não foi criado um segundo motor.

- A resolução autoritativa já acontecia no backend. A fórmula física era `max(1, ataque + dano_base - defesa)`, com resistência que reduz pela metade e fraqueza que duplica até o teto seguro.
- Jogadores e IA mantinham trechos separados dessa fórmula. Ambos agora chamam `calculate_damage`, em `backend/app/services/combat_rules.py`.
- Os formulários H.3 de personagens salvam `forca`, `agilidade`, `intelecto`, `vitalidade` e `espirito`. O snapshot H.4 não reconhecia esses nomes e podia descartar atributos inseridos pela interface.
- O snapshot do inimigo já utilizava `Enemy.attack`, `Enemy.defense` e `Enemy.speed`, mas não aplicava todos os aliases existentes nos atributos numéricos do perfil H.3.
- A IA considerava dano-base ao escolher habilidades, sem comparar o dano efetivo após defesa e resistência. A decisão passou a avaliar o resultado autoritativo contra cada alvo alcançável.
- Cura e dano contínuo com duração, cooldowns, validação de mana/alcance/alvo, turnos, idempotência e recompensas já existiam. Foram preservados. Críticos, precisão/evasão, buff/debuff genérico, imunidades e área não eram regras implementadas e não foram inventados.

## Atributos, fórmulas e limites

Os aliases são lidos na ordem mostrada, preservando prioridade aos campos canônicos e compatibilidade com fichas antigas.

| Saída do combate | Aliases de personagem/perfil | Fallback |
|---|---|---|
| Ataque físico | `attack`, `strength`, `forca` | Personagem: 0. Inimigo: `Enemy.attack`. |
| Poder mágico | `magic_attack`, `intellect`, `intelecto` | Personagem: ataque físico. Inimigo: `Enemy.attack`, para preservar o comportamento anterior. |
| Defesa física | `defense`, `vitalidade` | Personagem: 0. Inimigo: `Enemy.defense`. |
| Defesa mágica | `magic_defense`, `espirito` | Personagem: defesa física. Inimigo: `Enemy.defense`. |
| Iniciativa | `speed`, `agility`, `dexterity`, `agilidade` | Personagem: 0. Inimigo: `Enemy.speed`. |

O significado de `intelecto`, `vitalidade` e `espirito` é formalizado aqui como poder mágico, defesa física e defesa mágica, respectivamente. Isso corrige a diferença entre o formulário existente e o snapshot; não altera a ficha armazenada.

Uma habilidade é classificada como mágica se sua categoria ou tipo for `arcane`, `fire`, `ice`, `lightning`, `magic`, `magia`, `magica`, `mágica` ou `spell`. O serviço compartilhado aplica:

1. `dano_bruto = max(1, poder + dano_base_da_habilidade - defesa_correspondente)`.
2. Resistência ao tipo: `max(1, floor(dano_bruto / 2))`.
3. Fraqueza ao tipo, se não houver resistência: `min(2.000.000.000, 2 * dano_bruto)`.
4. Sem modificador: `dano_bruto`.

Ataques sem habilidade usam dano-base zero. Resistência tem precedência se um tipo constar simultaneamente como resistência e fraqueza, igual à regra anterior. Valores booleanos, inválidos, negativos ou floats não finitos usam o fallback; valores aceitos são truncados para inteiro e limitados a `2.000.000.000`. Não foram introduzidas chances probabilísticas.

## IA e regras não alteradas

Em cada turno, a IA considera ataques físicos e habilidades disponíveis (mana suficiente, sem cooldown, não curativas) contra personagens vivos e alcançáveis. Para cada par ação/alvo, pontua, nesta ordem:

1. Eliminar o alvo.
2. Dano que pode efetivamente reduzir o HP atual.
3. Menor custo de mana.
4. Dano calculado antes do limite pelo HP restante.
5. IDs lexicograficamente menores da habilidade e do alvo, para desempate estável.

O poder, defesa e dano elemental usados nessa comparação são os mesmos da resolução da ação. A IA continua encerrando o turno quando não há candidato válido. Decisão, custos, HP, efeitos, recompensas e persistência continuam no servidor; eventos visuais não controlam dano.

## Cenários quantitativos reproduzíveis

`backend/tests/test_combat_rules.py::test_synthetic_tiers_measure_hits_and_mana_without_claiming_battle_duration` executa estes três casos fixos usando `calculate_damage`. Cada linha compara dano por acerto e quantidade de acertos necessários para atingir o HP do alvo:

| Cenário sintético | HP alvo | Dano físico | Só físico (acertos) | Dano mágico | Só mágico (acertos) | Estratégia mista (ações) | Mana gasta |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 50 | 2 | 25 | 9 | 6 | 15 | 12 |
| B | 90 | 5 | 18 | 12 | 8 | 14 | 12 |
| C | 160 | 8 | 20 | 15 | 11 | 17 | 20 |

Parâmetros por cenário (ataque físico, poder mágico, defesa física, defesa mágica, dano-base mágico, mana e custo por magia): A `(5, 8, 3, 4, 5, 12, 4)`; B `(12, 12, 7, 8, 8, 12, 4)`; C `(20, 18, 12, 15, 12, 20, 5)`. Não há resistências nem fraquezas. A rota mista usa toda a mana disponível em magias antes de completar com ataques físicos; ações são arredondadas para cima. **Não** conta iniciativa, turnos da IA, efeitos, cura, cooldowns ou duração real. Logo, os resultados não são duração média nem prova de equilíbrio entre níveis.

O resultado não justificou mudar números de armas, habilidades, custos ou recompensas: os cenários são deliberadamente artificiais e faltam dados de batalhas representativas e critérios de produto. Os ajustes realizados corrigem consistência e seleção da IA sem arbitrariamente reescalar conteúdo.

## Mudanças e testes

- Criado `backend/app/services/combat_rules.py` para normalização segura, aliases, classificação de poder mágico e fórmula comum.
- `backend/app/api/combat.py` agora constrói snapshots de personagens e inimigos com os aliases reconhecidos, usa a fórmula compartilhada na resolução e pontua escolhas da IA pelo dano efetivo.
- `backend/tests/test_combat_rules.py` cobre aliases/precedência, valores extremos, mínimo/teto, resistência/fraqueza, classificação mágica e cenários quantitativos.
- `backend/tests/test_combat.py` valida os snapshots de atributos H.3 e uma ação da IA em que uma habilidade de menor dano-base causa mais dano efetivo por usar defesa mágica baixa, enquanto a ação física de maior dano-base é reduzida pela defesa física. O evento selecionado mantém a animação e velocidade cadastradas.
- Foram preservados mana, cura/dano contínuo, cooldown, idempotência, regras de turno, persistência de snapshots, recompensas e a separação entre resolução e animação.

## Limitações e recomendações

- Os mapeamentos em português corrigem a incompatibilidade com os formulários existentes, mas a semântica de `vitalidade` e `espirito` não era especificada em documentação anterior. Confirmar esses significados com o responsável pelo design do jogo antes de tratar a tabela como regra final de produto.
- Ainda não foi medido tempo médio de combate por nível nem viabilidade estratégica com custo de mana, progressão, grupos variados, efeitos simultâneos, cura e inimigos representativos. Fazer simulações sintéticas adicionais depois que os parâmetros e metas de duração forem definidos.
- Precisão, evasão, crítico, resistências específicas de personagens, buffs/debuffs genéricos e IA de cura/ameaça continuam fora das regras implementadas. Não são simulados nem anunciados como disponíveis.
- A seleção da IA continua determinística e sem IA generativa. Cooldowns, custos, turnos, recompensas e integração visual existentes permanecem sob a autoridade do backend.
- Não houve validação administrativa visual nesta etapa. Ela não é necessária para os testes de backend desta alteração, e a limitação de sessão administrativa da H.6 permanece.

## Proteção do ambiente

Os testes desta etapa usam o fixture SQLite isolado do backend e não executam os testes marcados `postgres`. Não houve conexão a PostgreSQL, acesso a `cronicas_do_reino_dev`, execução de migrations, DDL, alteração de `.env`, credenciais, roles, grants ou dados de usuário. A revisão `b74c2d91e5a0` não foi aplicada por esta etapa.

## Validação automatizada

Testes automatizados não equivalem a validação visual real nem a uma simulação integrada de duração de batalhas.

| Verificação | Resultado |
|---|---|
| Backend SQLite: `python -m pytest -m "not postgres" -q` | **188 passed**, **12 deselected**, 0 falhas. |
| Testes frontend: `npm.cmd run test` | **58 passed**, 11 arquivos aprovados, 0 falhas. |
| TypeScript: `npx.cmd tsc --noEmit` | Aprovado, sem diagnósticos. |
| Build: `npm.cmd run build` | Aprovado; aviso informativo existente sobre `vite-tsconfig-paths`. |
| Compileall: `python -m compileall -q app migrations tests` | Aprovado. |
| Dependências Python: `python -m pip check` | Aprovado; nenhuma dependência quebrada. |
| Dependências Node: `npm.cmd ls --depth=0` | Aprovado; terminou sem erro. |
| ESLint: `npm.cmd run lint` | 0 erros, **7 warnings** `react-refresh/only-export-components` em arquivos compartilhados/UI já existentes. |
