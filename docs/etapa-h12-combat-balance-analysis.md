# Etapa H.12 — Análise comparativa de balanceamento

**Status: parcial.** A execução quantitativa sintética foi concluída e é reproduzível, mas a análise de conteúdo canônico não foi possível sem consultar o banco persistente, proibido nesta etapa. Não encontrei um catálogo canônico versionado nos arquivos do repositório. Os resultados abaixo são achados sobre cenários sintéticos, não certificação de equilíbrio das campanhas ou do catálogo publicado. Nenhuma regra ou atributo de combate foi alterado.

## 1. Resumo executivo

- Matriz final: **45 cenários**, **45 batalhas concluídas**, **0 falhas**, seed `100` em cada configuração, **25 contrastes pareados**.
- Versões: simulador `1.0.0`; regras `h4-authoritative+h7-combat-rules`.
- Piloto de desempenho: **360 batalhas** (12 configurações sintéticas × seeds 100–129), sem falhas. As distribuições de resultado e médias de turnos permaneceram iguais entre seeds nos casos observados. O motor não usa RNG para decidir ações ou resolver combate; seed só torna os IDs de ação distintos.
- As 45 configurações finais são determinísticas e têm uma execução cada. Essa execução é suficiente para observar o resultado exato daquela configuração, mas não permite generalização estatística nem intervalo inferencial.
- Observações sintéticas a investigar: a configuração de inimigo com defesa 15 venceu por desgaste enquanto a referência com defesa 5 perdeu; quatro participantes perderam para o boss sintético que cinco derrotaram; o bônus de ataque sintético encurtou uma batalha de 29 para 15 turnos.
- **Não foi possível auditar personagens, inimigos, bosses, itens ou habilidades canônicos.** Não há catálogo de produção versionado nos arquivos do repositório, e consultá-lo exigiria acessar banco persistente. Assim, nenhuma entidade real foi classificada como desequilibrada.

Arquivos quantitativos: [JSON completo](./etapa-h12-combat-balance-analysis.json), [CSV por batalha](./etapa-h12-combat-balance-analysis.csv) e [tabela Markdown gerada](./etapa-h12-combat-balance-analysis-data.md). O gerador está em [combat_balance_analysis.py](../backend/app/services/combat_balance_analysis.py).

## 2. Metodologia

1. Reutilizei `SYNTHETIC_SCENARIOS` e `run_batch` da H.11; cada batalha chama os resolutores autoritativos H.4/H.7 e usa uma sessão SQLite `:memory:` isolada, revertida ao fim.
2. Executei os 13 cenários H.11, uma matriz controlada de níveis, três arquétipos estatísticos, cinco variantes de inimigo, cinco tamanhos de grupo contra o mesmo boss sintético, três deltas de equipamento, quatro variantes de habilidade, quatro composições de grupo e um contraste da política de cura.
3. Usei seed `100` em todos os casos finais, mesma estratégia de grupo (`effective_damage`) e de inimigo (`baseline`), exceto no contraste explicitamente rotulado `survival`. Os 25 pares compartilham seed e cenário-base quando aplicável.
4. Os agregados H.11 incluem média, mediana, desvio padrão populacional, mínimo/máximo e percentis nearest-rank p25/p50/p75/p90. Para `n=1`, esses valores são descritivos de uma execução e o desvio é zero por construção. O relatório JSON também registra contagens, taxa de vitória, parâmetros completos, versões e observações.
5. O gerador calcula Wilson nominal para taxa de vitória e o sinaliza como **não válido para inferência** nesta análise. Batalhas repetidas por seed não são ensaios aleatórios independentes. Para médias, nenhum intervalo inferencial é reportado. Nenhuma diferença é declarada estatisticamente significativa.
6. Piloto de 30 seeds foi realizado para 12 configurações de nível, boss, grupo e magia para estimar custo e verificar estabilidade. A distribuição de resultados e média de turnos observadas foram iguais entre seeds em cada configuração. Os resultados finais usam uma repetição por configuração porque repetir uma simulação determinística não acrescentaria evidência.

| Configuração do piloto | n | Resultado em todas as execuções | Média de turnos |
|---|---:|---|---:|
| Nível 1 controlado | 30 | Vitória | 7 |
| Nível 10.000 controlado | 30 | Vitória | 7 |
| Habilidade mágica controlada | 30 | Vitória | 9 |
| Boss vs. 1 jogador | 30 | Derrota | 20 |
| Boss vs. 2 jogadores | 30 | Derrota | 50 |
| Boss vs. 3 jogadores | 30 | Derrota | 90 |
| Boss vs. 4 jogadores | 30 | Derrota | 140 |
| Boss vs. 5 jogadores | 30 | Vitória | 136 |
| Grupo ofensivo | 30 | Vitória | 45 |
| Grupo defensivo | 30 | Vitória | 371 |
| Grupo foco em magia | 30 | Vitória | 17 |
| Grupo equilibrado sintético | 30 | Derrota | 108 |

As 360 execuções do piloto tiveram zero falhas. A tabela registra somente as métricas que o lote piloto imprimiu; as demais métricas são fornecidas pelo dataset final com seed `100`.

### Reproduzir

Execute de um diretório temporário, para evitar carregar configuração local do projeto:

```powershell
$env:APP_ENVIRONMENT = 'development'
$env:PYTHONPATH = 'C:\caminho\site-rpg\backend'
Set-Location $env:TEMP
& 'C:\caminho\site-rpg\backend\.venv\Scripts\python.exe' `
  -m app.services.combat_balance_analysis `
  --output-dir 'C:\caminho\site-rpg\docs'
```

Uma execução é o padrão. O piloto pode ser repetido com `--seed-start 100 --seed-count 30`, lembrando que os seeds não criam aleatoriedade no motor atual.

## 3. Limitações

- **Dados canônicos ausentes:** modelos e rotas confirmam que o conteúdo fica em entidades SQL (`Character`, `Enemy`, `Item`, `Skill`, `EntityContentProfile` e associações). Não encontrei arquivo de seed/catálogo do jogo no código. Não foi feita consulta a PostgreSQL ou a qualquer banco persistente para preencher essa lacuna.
- **Progressão individual:** `Character.character_class` é texto opcional, sem enumeração de classes ou atributos automáticos por classe. O serviço de progressão define máximo 10.000, XP necessário igual a `100 × nível`, +5 HP máximo, +2 mana máximo e +1 ponto de atributo por nível. A distribuição dos pontos depende do jogador; não há uma progressão canônica de ataque/defesa para simular sem dados reais.
- **Equipamentos:** o snapshot H.4 soma ataque, defesa e alcance do item/perfil. O teste altera apenas deltas sintéticos de ataque/defesa; não representa itens, custos, slots ou requisitos publicados.
- **Habilidades:** os snapshots extraem custo/cooldown do modelo e potência/efeitos do modelo/perfil. O catálogo e as associações publicadas não foram lidos. As habilidades desta matriz são sintéticas.
- **Regras ausentes:** precisão, evasão, crítico, controle, área e imunidades genéricas não integram as regras H.4/H.7 auditadas. Não foram simuladas. O dano contínuo não fica atribuído ao autor original nos eventos H.4, limitação já registrada na H.11.
- **Estratégia:** a IA H.4 inimiga continua `baseline`; `survival` é política experimental para o lado jogador, não comportamento de jogador real nem IA padrão do jogo. A comparação de cura é um cenário H.11, não uma avaliação de toda build curandeira.
- **Validade externa:** parâmetros dos cenários H.11 e das novas matrizes são sintéticos, de magnitudes declaradas pelo próprio cenário. Não representam escala de raridade, custo econômico, experiência média ou composição típica de campanha.
- Não houve navegador, frontend ou testes de UI envolvidos; a análise é exclusivamente de backend e dados.

## 4. Progressão por nível

A matriz deriva HP e mana a partir de uma ficha-base sintética de nível 1 usando os incrementos efetivamente definidos pelo serviço de progressão; ataque, defesa, velocidade e habilidades ficaram constantes, e os pontos de atributo permaneceram sem distribuição. Todos enfrentaram o mesmo alvo sintético.

| Nível | HP máximo sintético | Mana máxima sintética | Dano do grupo | Dano recebido pelo grupo | Turnos | Resultado |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 24 | 6 | 16 | 3 | 7 | Vitória |
| 5 | 44 | 14 | 16 | 3 | 7 | Vitória |
| 15 | 94 | 34 | 16 | 3 | 7 | Vitória |
| 50 | 269 | 104 | 16 | 3 | 7 | Vitória |
| 100 | 519 | 204 | 16 | 3 | 7 | Vitória |
| 1.000 | 5.019 | 2.004 | 16 | 3 | 7 | Vitória |
| 10.000 | 50.019 | 20.004 | 16 | 3 | 7 | Vitória |

**Fato:** com atributos de combate idênticos, o nível por si só não muda o dano ou a ordem do combate nesta regra; HP e mana aumentam pelos incrementos de progressão. **Não é uma curva de poder de personagens reais.** A invariância de turno resulta também do alvo fraco e não testa limiares de sobrevivência. Investigar a distribuição de pontos, atributos por classe/construção e inimigos compatíveis com faixas de nível quando houver um snapshot autorizado do conteúdo.

## 5. Comparação de personagens e arquétipos

Não há classes formais para comparar. Foram usadas três distribuições sintéticas de atributos no mesmo nível, com HP/mana, inimigo e seed iguais. A configuração mágica tem uma habilidade adicional e, portanto, não é uma comparação de orçamento total perfeitamente equivalente.

| Configuração sintética | Resultado | Turnos | Dano do grupo | Recebido pelo grupo | Mana |
|---|---|---:|---:|---:|---:|
| Física | Vitória | 17 | 90 | 16 | 0 |
| Mágica + feitiço de custo 5 | Vitória | 11 | 90 | 10 | 20 |
| Defensiva | Vitória | 45 | 90 | 22 | 0 |

Neste encontro, a habilidade mágica terminou mais cedo e com menos dano recebido, consumindo 20 de mana; isso não prova domínio geral. A composição defensiva sobreviveu, mas prolongou a batalha. A comparação não inclui cura, variedade de inimigos ou custos/raridades de equipamento. Contribuição de grupo e papéis funcionais não foram reduzidos a dano bruto.

## 6. Comparação de inimigos

Inimigos variaram uma dimensão por vez contra o mesmo aventureiro de nível 10. A referência tem HP 75, ataque 10, defesa 5 e velocidade 8. As outras variantes alteram somente o atributo indicado.

| Variante sintética | Resultado do jogador | Turnos | Dano do grupo | Dano recebido pelo grupo |
|---|---|---:|---:|---:|
| Referência | Vitória | 13 | 75 | 12 |
| HP 150 | Vitória | 27 | 150 | 26 |
| Ataque 20 | Vitória | 13 | 75 | 72 |
| Defesa 15 | Derrota | 100 | 50 | 100 |
| Velocidade 15 | Vitória | 14 | 75 | 14 |

Aumentar defesa de 5 para 15, mantendo os outros parâmetros, mudou a vitória para derrota ao fim da troca de ataques (dano mínimo 1). É um **limiar sintético** que merece comparação com a distribuição real de ataque/defesa; não se associa a nenhum inimigo cadastrado. A mudança isolada de ataque elevou dano recebido de 12 para 72 sem mudar a duração, no cenário limitado a um único oponente e sem cura.

## 7. Comparação de bosses

Um mesmo boss sintético (HP 220, ataque 16, defesa 12, velocidade 8) enfrentou grupos de 1–5 combatentes idênticos (HP 80, ataque 14, defesa 8, nível 10). O modelo limita a campanha a cinco jogadores; a rota H.4 inicia o encontro com todos os membros ativos e não aplica mínimo de jogadores no início da batalha, então os grupos sintéticos de 1–2 também são compatíveis com o fluxo de combate existente.

| Jogadores | Resultado | Turnos | Rodadas | Dano do grupo | Dano recebido pelo grupo |
|---:|---|---:|---:|---:|---:|
| 1 | Derrota | 20 | 10 | 20 | 80 |
| 2 | Derrota | 50 | 20 | 60 | 160 |
| 3 | Derrota | 90 | 30 | 120 | 240 |
| 4 | Derrota | 140 | 40 | 200 | 320 |
| 5 | Vitória | 136 | 27 | 220 | 208 |

O salto de quatro para cinco membros altera o resultado nesta configuração fixa. Os dados não incluem cura, classes reais, equipamentos ou seleção de ameaças e não calibram um boss publicado. Não se pode concluir que bosses canônicos exijam cinco jogadores.

## 8. Equipamentos e armas

Foi aplicada a mesma ficha e o mesmo alvo; os únicos deltas foram os atributos sintéticos previstos no snapshot H.4.

| Equipamento sintético | Resultado | Turnos | Dano do grupo | Recebido pelo grupo |
|---|---|---:|---:|---:|
| Sem delta | Vitória | 29 | 90 | 28 |
| +6 ataque | Vitória | 15 | 90 | 14 |
| +6 defesa | Vitória | 29 | 90 | 14 |

O bônus de ataque dobrou a cadência de conclusão neste adversário; o bônus de defesa reduziu pela metade o dano recebido sem encurtar o combate. São deltas artificiais, sem preço, raridade, requisito ou item real. Não há evidência para classificar qualquer arma como dominante.

## 9. Habilidades

Mesmo personagem, alvo, nível e recursos; a única alteração é a habilidade disponível. Métricas contam resultado de combate confirmado pelo backend. Mana consumida reflete cinco usos de custo 4 nas habilidades selecionadas.

| Variante | Resultado | Turnos | Dano do grupo | Recebido pelo grupo | Cura efetiva | Mana |
|---|---|---:|---:|---:|---:|---:|
| Sem habilidade | Vitória | 29 | 90 | 28 | 0 | 0 |
| Habilidade física, base 12/custo 4 | Vitória | 9 | 90 | 8 | 0 | 20 |
| Habilidade mágica, base 12/custo 4 | Vitória | 9 | 90 | 8 | 0 | 20 |
| Dano contínuo, base 5/custo 4 | Vitória | 15 | 72 | 14 | 0 | 20 |

No alvo sem resistência e com defesas iguais, as habilidades física e mágica foram equivalentes nos resultados observados. A política experimental preferiu a potência direta às alternativas de ataque, o que reduziu turnos mas consumiu mana. Dano contínuo não recebe atribuição correta ao lançador nos eventos H.4; por isso, o dano direto do personagem não contém todos os ticks e não deve ser comparado isoladamente ao total de dano da batalha.

### Cura

No cenário H.11 `defense-and-healing`, a política `effective_damage` encerrou com `turn_limit`, 0 de cura e 0 mana gastos. Com a política sintética `survival`, o grupo também atingiu o limite, mas registrou 72 de cura efetiva e 18 de mana; causou 94 de dano e recebeu 154. É um exemplo de que cura prolonga a sobrevivência sem garantir vitória naquele cenário; não comprova defeito no motor nem a eficiência de habilidades canônicas.

## 10. Composições de grupo

Três membros de cada configuração sintética enfrentaram o mesmo boss de HP 260. Os arquétipos não foram normalizados por orçamento total ou custo de equipamento; as diferenças são descritivas, não uma classificação justa de “melhor classe”.

| Configuração | Resultado | Turnos | Dano do grupo | Recebido pelo grupo | Cura | Mana |
|---|---|---:|---:|---:|---:|---:|
| Ofensiva | Vitória | 45 | 260 | 115 | 0 | 0 |
| Defensiva | Vitória | 371 | 260 | 222 | 0 | 0 |
| Foco em magia | Vitória | 17 | 260 | 40 | 0 | 52 |
| Equilibrada sintética | Derrota | 108 | 144 | 246 | 0 | 0 |

A composição mágica consumiu 52 de mana para encerrar em menos turnos; a defensiva demorou 371 turnos, mas venceu. A composição “equilibrada” perdeu, mas não foi construída com orçamento equiparado; resultado inconclusivo para qualquer hipótese sobre funções de grupo reais.

## 11. Desequilíbrios identificados

Classificação abaixo é de **sinais sintéticos para triagem**, não de conteúdo canônico. “Fato” descreve a execução; “hipótese” não foi provada.

| Prioridade | Severidade indicativa | Fato medido | Hipótese a verificar | Ação de investigação |
|---:|---|---|---|---|
| 1 | Alta — sintético | Contra a referência, o jogador vence em 13 turnos; com apenas defesa do inimigo alterada de 5 para 15, perde após 100 turnos. | Faixas reais de defesa podem cruzar o dano mínimo e criar combates de atrito. | Parear inimigos publicados e builds por nível, conferir distribuição de ataque/defesa e revisar durações-alvo. |
| 2 | Alta — sintético | Quatro combatentes idênticos perdem para o boss; cinco vencem. | O limiar pode decorrer do HP/defesa e da cadência de turnos, não de regra específica de boss. | Reexecutar com grupos e parâmetros de campanha reais, incluindo composição e cura. |
| 3 | Moderada — sintético | +6 ataque reduziu 29→15 turnos; +6 defesa reduziu dano recebido 28→14, mantendo 29 turnos. | Deltas de itens de mesma raridade/custo podem produzir valores de sobrevivência diferentes. | Comparar itens existentes por raridade, slot, requisito e preço efetivamente cadastrado. |
| 4 | Moderada — sintético | Habilidade direta terminou em 9 turnos versus 29 sem habilidade, com consumo de 20 mana; dano mágico e físico empataram no alvo sem resistências. | Potência/custo e defesas podem tornar skills diretas mais eficientes que ataques, especialmente em alvos sem resistência. | Medir o catálogo real por nível, cooldown, tipo de defesa, resistência e quantidade de usos disponíveis. |
| 5 | Baixa/observacional | Com atributos iguais, nível de 1 a 10.000 não mudou turnos nem dano no cenário; HP/mana cresceram conforme progressão. | A força de nível depende da distribuição de pontos e da seleção de conteúdo compatível, não de multiplicador do combate. | Validar fichas reais por faixa e a alocação manual dos pontos antes de concluir. |
| 6 | Inconclusiva | A política `survival` curou 72 com 18 mana mas não venceu o cenário; `effective_damage` também não venceu. | O limiar de cura ou o cenário pode não representar encontros em que suporte tenha valor. | Comparar em múltiplos encontros, com HP inicial, função do grupo e estratégia de referência definidos. |

Não há achado crítico comprovado. A gravidade para entidades do jogo permanece **inconclusiva** enquanto os resultados forem apenas sintéticos.

## 12. Recomendações

1. Não alterar fórmulas, atributos ou conteúdo por causa desta matriz sintética.
2. Obter um snapshot autorizado, versionado e sanitizado do catálogo canônico (personagens/builds, inimigos, bosses, equipamentos e habilidades) em um ambiente de teste isolado; não extrair de `cronicas_do_reino_dev` nem de `cronicas_do_reino_test`.
3. Definir objetivos de design antes de rotular resultados: duração aceitável por faixa, taxa esperada de vitória, custo de mana, tamanho normal de grupo e papel de boss.
4. Para atributos e equipamento, criar pares que mantenham ficha, nível, slot, custo e conteúdo constantes; incorporar resistências e requisitos reais.
5. Para bosses, comparar grupos de 1–5 somente quando esses tamanhos forem regras válidas para o encontro, com e sem cura, e registrar participantes derrotados e recursos.
6. Se balanceamento probabilístico for necessário, primeiro introduzir RNG autoritativo e controlável por seed de forma deliberada; depois dimensionar amostras independentes e intervalos (Wilson para proporções e método apropriado para médias). Não simular variância adicionando aleatoriedade apenas à análise.

## 13. Resultados inconclusivos

- Número e identidade de personagens/classes jogáveis, inimigos e bosses ativos/publicados: **não consultados**.
- Taxas de vitória/duração contra o cadastro canônico: **não medidas**.
- Equipamentos reais, custo-benefício e evolução de armas: **não medidos**.
- Habilidades publicadas, efeitos de controle, custo/cooldown e sua distribuição por nível: **não medidos**.
- Dominância estatística, intervalos de confiança e generalização: **não estimáveis** com a regra determinística atual e `n=1` por configuração final. Wilson nominal no JSON é explicitamente inválido para inferência.
- A H.12, portanto, permanece parcial até receber um conjunto canônico autorizado e metas de design.

## 14. Próximas investigações priorizadas

1. **Defesa e duração:** reproduzir o contraste sintético de defesa 5→15 com entidades e fichas publicadas, sob ataque e nível equivalentes.
2. **Escala de boss por participantes:** investigar o limiar sintético entre quatro e cinco, separando efeitos de HP, iniciativa, dano por participante e derrotas.
3. **Eficiência de habilidades:** comparar skills físicas/mágicas e dano contínuo com o catálogo real, mana disponível, cooldown e resistências.
4. **Impacto de equipamento:** comparar itens de slots/raridades/custos reais e evitar atribuir benefício ao atributo sem controlar a ficha.
5. **Progressão:** mapear distribuição real de atributos e pontos acumulados por faixa; a matriz atual só confirma os incrementos de HP/mana/pontos do serviço.
6. **Cura e sobrevivência:** estudar cenários múltiplos e pareados para separar mitigação, duração e vitória, incluindo estratégias diferentes sem alterar a IA padrão.

## Validação, alterações e integridade

| Verificação | Resultado |
|---|---|
| Suíte backend segura (`-m "not postgres"`) | **220 passed, 1 skipped, 12 deselected** |
| Testes focados H.11 + H.12 + regras H.4/H.7 | **48 passed** |
| `compileall` em `backend/app` e `backend/tests` | Aprovado |
| `pip check` | Nenhuma dependência quebrada |
| Alembic `heads` | `d129a4c7e601`; somente leitura |
| Exportações | JSON, CSV (45 linhas de dados) e Markdown gerados; 45/45 execuções, zero falhas |

Alterações desta etapa: novo serviço de análise/reprodutibilidade, testes estatísticos e de exportação, este relatório e os três exports. Não houve mudança no motor H.4/H.7, frontend ou `.env`. PostgreSQL, `cronicas_do_reino_dev`, `cronicas_do_reino_test` e outros bancos persistentes não foram acessados; migrations não foram aplicadas; dados, contas, itens, fórmulas e atributos reais não foram alterados.
