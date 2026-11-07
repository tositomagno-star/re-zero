# H.20 - Plano de implementação do motor central de atributos

**Status:** implementação concluída e verificada.  
**Data:** 2026-11-05

## 1. Objetivo

Preparar a implementação futura de um serviço isolado em
`backend/app/services/attribute_engine.py` capaz de calcular atributos finais a partir de
valores-base, modificadores aditivos, percentuais e multiplicadores.

Esta etapa não modifica:

- modelos SQLAlchemy ou banco de dados;
- migrations;
- rotas HTTP existentes;
- snapshots ou regras de combate;
- frontend;
- credenciais, ambiente ou arquivos `.env`;
- campanhas ou dados persistidos.

## 2. Estado dos documentos e decisões

O arquivo [H19](H19-planejamento-sistema-atributos-equipamentos.md) referenciado pelo escopo
H.20 existe nesta revisão, mas está vazio e não contém uma seção 14 nem decisões técnicas aprovadas.
Consequentemente, este plano não considera que exista uma aprovação externa de:

- base de cálculo percentual;
- combinação de multiplicadores;
- arredondamento;
- limites por atributo;
- precedência de aliases conflitantes.

Essas lacunas devem permanecer bloqueadas na implementação até aprovação explícita. A presença do
arquivo vazio não deve ser interpretada como evidência de regras aprovadas.

## 3. Contratos atuais relevantes

### 3.1 Atributos-base do personagem

Atualmente, `Character.attributes` é um JSON livre:

- não existe catálogo persistido de atributos-base;
- não existe sistema ponta a ponta de gasto de `attribute_points`;
- atributos combatíveis são normalizados por `normalize_combat_attributes`.

Os aliases consumidos atualmente por `backend/app/services/combat_rules.py` são:

| Atributo canônico | Nomes históricos aceitos |
|---|---|
| `attack` | `strength`, `forca` |
| `magic_attack` | `intellect`, `intelecto` |
| `defense` | `vitalidade` |
| `magic_defense` | `espirito` |
| `speed` | `agility`, `dexterity`, `agilidade` |

O canônico inglês não tem regra histórica de conflito quando ocorre junto de um alias.

### 3.2 Limites existentes

O único limite global comprovado é aplicado por `bounded_nonnegative_int`:

- booleanos são rejeitados;
- valores negativos tornam-se zero;
- NaN e infinito tornam-se zero;
- valores válidos são truncados para `MAX_COMBAT_VALUE`, atualmente
  `2_000_000_000`.

Esse limite não prova que todos os atributos devem utilizar o mesmo máximo nem que atributos-base e
modificados devam compartilhar o mesmo limite. A configuração futura deve ser explícita.

### 3.3 Recursos

`Character.hp` e `Character.max_hp`, assim como `Character.mana` e `Character.max_mana`, são
armazenados separadamente. O HP atual não deve ser derivado do HP máximo pelo motor de atributos.

O motor poderá calcular e expor o HP máximo, mas deverá receber e retornar o HP atual separadamente.
Qualquer ajuste que reduza um máximo não pode mutar o atual neste serviço.

## 4. Decisões indefinidas que bloqueiam fórmulas finais

### 4.1 Base dos modificadores percentuais

Não está definido se um percentual usa:

- somente o atributo-base;
- o valor após somas aditivas;
- o valor de outra origem/etapa;
- uma combinação específica de modificadores percentuais.

Portanto, o plano não fixa uma regra de jogo. Uma implementação futura deverá usar uma configuração
de base aprovada pelo contrato, por exemplo `base`, `after_flat` ou um identificador que venha do
contrato H.19, em vez de inferir a base durante o cálculo.

### 4.2 Ordem e combinação dos multiplicadores

Não está definido se os multiplicadores:

- são multiplicados uns pelos outros;
- são somados na forma `1 + multiplicador`;
- são acumulados por origem;
- possuem ordem com impactos diferentes;
- podem ser negativos ou menores que zero;
- podem exceder limites específicos por atributo.

Não deve haver heurística baseada na ordem da lista ou no tipo da origem. A política precisa ser
aprovada e representada no contrato.

### 4.3 Arredondamento

Não está definida uma política compartilhada para:

- arredondar percentuais;
- arredondar multiplicadores;
- arredondar atributos derivados;
- tratar meio ponto;
- acumular frações durante etapas intermediárias;
- emitir inteiro ou decimal.

A política atual de combate usa somente atributos normalizados como inteiros. Não se deve ampliar
essa política automaticamente para o novo motor. Até haver aprovação, o retorno deve preservar os
valores intermediários de modo racional e só aplicar a política configurada.

### 4.4 Limites dos atributos

Somente existe um limite técnico global de segurança. Não foi aprovado um mínimo/máximo de jogo para:

- `attack`;
- `magic_attack`;
- `defense`;
- `magic_defense`;
- `speed`;
- HP máximo;
- mana máxima.

O motor deve aceitar limites configurados por atributo, mas não deve inventar valores de jogo.

### 4.5 Aliases históricos conflitantes

Não está definido qual nome prevalece se, por exemplo, `attack` e `strength` estiverem presentes e
possuírem valores diferentes. A normalização existente escolhe por `combat_rules.py` a primeira
chave presente na prioridade de aliases:

`attack` → `strength` → `forca`.

Esse comportamento deve ser reutilizado sem recodificá-lo. A única ação futura admissível é tornar
esse conflito diagnosticável e decidir, no contrato aprovado, se:

- o valor canônico prevalece;
- a variante conflitante é rejeitada;
- a maior/menor variante prevalece;
- todos são considerados modificadores separados;
- os dados antigos são migrados explicitamente.

## 5. Arquivos a utilizar ou criar

### Arquivos existentes utilizados pelo motor

- `backend/app/services/combat_rules.py`
  - reutiliza `MAX_COMBAT_VALUE` e `bounded_nonnegative_int`;
  - reutiliza `normalize_combat_attributes`;
  - não deve ser copiado ou duplicado dentro do motor.

- `backend/app/models/entities.py`
  - origem somente para leitura do modelo de personagem em integrações futuras;
  - não é alterado nesta etapa.

- `backend/tests/test_combat_rules.py`
  - contém o comportamento atual de normalização, limites e aliases;
  - serve como referência de compatibilidade.

- `backend/app/services/progression.py`
  - contexto futuro de atributos-base e pontos;
  - não é chamado pelo motor nesta etapa.

### Arquivos futuros criados durante H.20 autorizado

- `backend/app/services/attribute_engine.py`

- `backend/tests/test_attribute_engine.py`

Nenhuma rota, migration, modelo, frontend, snapshot ou esquema existente deve ser alterado nesta etapa.

## 6. Estrutura proposta do serviço

O módulo deverá expor tipos Python explícitos e funções puras. Um desenho inicial compatível com o
projeto é:

```text
AttributeModifier
ModifierSource
AttributeLimits
AttributeResolution

normalize_attribute_modifiers(...)
resolve_attributes(...)
resolve_attribute(...)
```

Os detalhes de nome devem ser confirmados ao implementar. A responsabilidade central deverá ser
preservada: entrada JSON/objetos seguros, saída pura, sem acesso ao banco e sem mutação de modelos.

O serviço não deve:

- consultar SQLAlchemy ou APIs;
- adquirir locks;
- persistir atributos;
- atualizar HP atual ou mana atual;
- explicar origem visual ou administrativa;
- consultar efeitos expirados ou inventário;
- depender de relógio para efeitos futuros;
- alterar snapshots de combate.

## 7. Contrato de entrada

### 7.1 Parâmetros mínimos

```python
resolve_attributes(
    base_attributes: Mapping[str, object],
    modifiers: Iterable[object] = (),
    limits: Mapping[str, AttributeLimit] | None = None,
)
```

Os nomes definitivos podem ser ajustados com os padrões existentes do projeto. A assinatura não deve
aceitar um modelo `Character` no argumento principal, pois isso permitiria mutações acidentais.

### 7.2 Estrutura lógica de modificador

Campos mínimos requeridos pelo motor:

- `attribute`: chave normalizada;
- `operation`: `add`, `add_percent` ou `multiply`;
- `value`: valor numérico finito;
- `source`: origem estruturada, usada apenas para auditoria;
- `base` ou outra referência de cálculo, quando exigida pelo contrato aprovado;
- `order`/fase, quando houver precedência aprovada.

Origem mínima:

```json
{
  "type": "item",
  "id": "uuid-da-origem"
}
```

Fontes sem identificador podem existir apenas para dados-base ou cenários controlados. Se ids forem
aceitos em entradas do serviço, a validação fica no boundary futuro da API e não dentro do cálculo
aritmético puro.

### 7.3 Entradas inválidas

O motor deve distinguir:

- valor não numérico;
- booleano;
- NaN/infinito;
- operação desconhecida;
- atributo desconhecido;
- origem inválida;
- multiplicador fora da política aprovada;
- limite mínimo maior que máximo;
- ordem duplicada ou ambígua.

Os padrões existentes podem ser reutilizados no boundary: valores históricos inválidos são normalizados
de forma segura por `bounded_nonnegative_int`; contratos futuros e novos JSON podem ser rejeitados
com diagnóstico explícito.

## 8. Contrato de saída

Estrutura lógica:

```json
{
  "base": {
    "attack": 10,
    "magic_attack": 7,
    "defense": 4,
    "magic_defense": 4,
    "speed": 8
  },
  "modifiers": [
    {
      "attribute": "attack",
      "operation": "add",
      "value": 3,
      "source": {
        "type": "item",
        "id": "item-1"
      }
    }
  ],
  "intermediate": {
    "attack_after_flat": 13
  },
  "final": {
    "attack": 13,
    "magic_attack": 7,
    "defense": 4,
    "magic_defense": 4,
    "speed": 8
  },
  "warnings": [],
  "diagnostics": []
}
```

O formato Python poderá usar dataclasses/TypedDict; a saída não precisa conter serialização HTTP.
A compatibilidade da ficha e das rotas permanece fora de H.20.

Os valores de recurso não entram como atributos derivados sem decisão H.19:

- o `base.hp_current` ou valor atual não é recalculado;
- `base.hp_max` deve ser separado de `base.hp_current`;
- `base.mana_current` deve ser separado de `base.mana_max`.

## 9. Fórmulas que dependem de aprovação

### 9.1 Aditivos

O cálculo aditivo pode ser representado como:

```text
valor_apos_aditivos = base_normalizada + soma(aditivos_aprovados)
```

Essa forma é compatível com a estrutura atual, mas os limites máximos, o tratamento de números e a
possível precedência entre origens continuam pendentes.

### 9.2 Percentuais

A fórmula não deve ser implementada antes da aprovação da base:

```text
contribuicao_percentual =
    valor_da_base_aprovada * fator_percentual_aprovado
```

A representação decimal (`0.10`) ou percentual inteiro (`10`) também precisa ser aprovada. A entrada
deve ter um único significado para impedir interpretações diferentes.

### 9.3 Multiplicadores

A combinação não deve ser definida por inferência:

```text
valor_final =
    aplicar_multiplicadores_aprovados(
        valor_apos_fases_adicionais,
        multiplicadores_ordenados
    )
```

Só há duas decisões a confirmar antes da implementação: política de combinação e ordem. Exemplos não
devem ser incorporados como regra.

### 9.4 Arredondamento

O motor deverá ter uma estratégia declarada. O plano não escolhe uma política padrão além das opções
disponíveis no projeto e exige aprovação para:

- número decimal intermediário;
- inteiro decimal final;
- meia aproximação;
- arredondamento por atributo;
- coerção final.

### 9.5 Limites

```text
valor_limitado = clamp(valor_calculado, minimo_aprovado, maximo_aprovado)
```

Nenhum `clamp` é aplicado silenciosamente sem limites registrados. O limite global atual de combate
continua disponível como limite técnico de segurança, mas não é declarado regra universal.

## 10. Reutilização da normalização atual

O motor deverá chamar `normalize_combat_attributes(base_attributes)` e não reproduzir seus aliases ou
funções de conversão.

Para compatibilidade:

1. entradas de aliases existentes são normalizadas pelo módulo atual;
2. conflitos não são resolvidos pelo motor com regras novas;
3. conflitos são registrados como diagnóstico;
4. a saída base usa nomes canônicos reconhecidos pelo combate;
5. chaves desconhecidas não são descartadas por padrão do objeto de entrada; são preservadas apenas
   para diagnóstico até haver catálogo aprovado.

O motor não deve chamar rotas ou funções assíncronas de combate.

## 11. Preservação dos atributos-base

O serviço deverá:

- aceitar `Mapping`, nunca atribuir ao objeto recebido;
- copiar os atributos normalizados;
- copiar cada lista/dicionário de modificadores antes do processamento;
- não alterar o dicionário original;
- não definir campos derivados no objeto original;
- retornar uma estrutura nova.

O teste determinante é:

```python
snapshot_before = deepcopy(base_attributes)
resolve_attributes(base_attributes, modifiers)
assert base_attributes == snapshot_before
```

## 12. HP atual separado do máximo

A entrada estrutural futura deverá separar recursos:

```json
{
  "current": {
    "hp": 10,
    "mana": 4
  },
  "maximum": {
    "hp": 20,
    "mana": 10
  }
}
```

Na ausência de aplicação futura aprovada, o motor não escreve:

- `Character.hp`;
- `Character.max_hp`;
- `Character.mana`;
- `Character.max_mana`.

A saída máxima será calculada somente quando houver configuração clara de atributos derivados. A saída
atual será copiada ou derivada por uma política futura; H.20 não altera HP atual por efeito colateral.

## 13. Determinismo

O cálculo deverá ser determinístico:

- listas de modificadores são ordenadas por uma chave explícita aprovada;
- empates têm uma chave secundária estável;
- fontes equivalentes não podem depender da identidade do objeto Python;
- valores são validados antes da operação;
- números em ponto flutuante não participam de decisões ambíguas; decimal exato e/ou valores inteiros
  devem ser definidos pelo contrato;
- arredondamento é aplicado na fase registrada;
- o retorno não depende de banco, horário ou aleatoriedade.

Os testes deverão executar entradas iguais repetidamente e comparar estruturas serializáveis.

## 14. Testes unitários necessários

Os testes em `backend/tests/test_attribute_engine.py` deverão cobrir:

### Normalização

- aliases canônicos existentes;
- aliases em português existentes;
- fallback/detecção de precedência registrada;
- conflito entre valores;
- atributo desconhecido;
- valor inválido, booleano, negativo, NaN, infinito e fora do limite técnico.

### Aditivos

- lista vazia;
- múltiplos adicionadores;
- origem vazia;
- soma inteira;
- limites de segurança.

### Percentuais

- os testes ficam parametrizados pela base aprovada em H.19;
- não deverão presumir percentual decimal até existir decisão;
- representação de base, fator e intermediário;
- rejeição de representação ambígua.

### Multiplicadores

- combinatória definida pela política aprovada;
- ordem explícita;
- empates estáveis;
- multiplicadores inválidos;
- limites;
- ausência de mutação.

### Arredondamento

- cada modo aprovado é testado;
- valores positivos e negativos conforme política;
- meio ponto;
- intermediários fracionários;
- limite aplicado antes ou depois do arredondamento somente conforme decisão.

### Limites

- mínimo;
- máximo;
- mínimo igual máximo;
- mínimo maior que máximo invalidado;
- limite técnico global;
- limites diferentes por atributo.

### Preservação e recursos

- `base_attributes` não é mutado;
- modificadores de entrada não são mutados;
- HP atual não é alterado;
- HP máximo é separado de HP atual;
- mana atual não é recalculada pela mana máxima.

### Determinismo

- duas chamadas iguais produzem saída igual;
- alteração da ordem sem chave aprovada é rejeitada ou reproduz uma ordem estável;
- saída pode ser serializada em JSON.

### Compatibilidade com combate, sem integração

- os mesmos casos de `test_combat_rules.py` continuam passando;
- a normalização de ataque, defesa, atributos mágicos e velocidade permanece a mesma;
- este serviço não é chamado por nenhuma rota.

## 15. Riscos de compatibilidade

- aliases conflitantes podem ter sido persistidos e podem virar mudança silenciosa;
- `bounded_nonnegative_int` não distingue um inteiro válido de um float que deveria ser rejeitado;
- `MAX_COMBAT_VALUE` é um limite técnico, não necessariamente um limite de jogo;
- adicionar um novo canônico pode deixar dados antigos com duas chaves;
- percentuais podem ser interpretados em percentual inteiro ou decimal;
- multiplicadores podem ser cumulativos ou aditivos;
- arredondamentos podem acumular diferenças;
- valores derivados podem parecer persistentes na API mesmo sem integração;
- HP atual pode ser acidentalmente clonado ou truncado junto do máximo;
- um motor puramente com `dict` pode perder tipos sem validação;
- testes puros podem divergir da ordem dos modificadores da futura persistência.

## 16. Critérios de aceitação H.20

O desenvolvimento de H.20 pode começar somente após as decisões pendentes serem aprovadas.

Critérios técnicos:

- [ ] existe `backend/app/services/attribute_engine.py`;
- [ ] o módulo não acessa banco ou rotas;
- [ ] o módulo reutiliza `normalize_combat_attributes`;
- [ ] aditivos, percentuais e multiplicadores usam a política aprovada;
- [ ] percentuais têm base e representação aprovadas;
- [ ] multiplicadores têm ordem e combinação aprovadas;
- [ ] arredondamento é explícito;
- [ ] limites são explícitos por atributo;
- [ ] conflito de alias tem regra aprovada;
- [ ] atributos-base não são modificados;
- [ ] HP atual é separado do HP máximo;
- [ ] mana atual é separada da mana máxima;
- [ ] o cálculo é determinístico;
- [ ] a saída contém base, modificadores, intermediários e valores finais;
- [ ] a saída contém diagnósticos seguros;
- [ ] os testes unitários cobrem compatibilidade e casos inválidos;
- [ ] combate, rotas e frontend permanecem sem alterações;
- [ ] nenhuma migration ou alteração de modelo foi criada;
- [ ] os testes usam SQLite isolado apenas quando necessário, sem banco PostgreSQL de produção.

## 17. Ordem de preparação recomendada

1. Completar ou recuperar o documento H.19, incluindo a seção 14 de decisões aprovadas.
2. Aprovar:
   - representação dos percentuais;
   - base percentual;
   - combinação e ordem dos multiplicadores;
   - política de arredondamento;
   - limites por atributo;
   - conflito de aliases.
3. Implementar o módulo e os testes puros.
4. Executar somente os testes relacionados ao motor e às regras existentes de normalização.
5. Revisar compatibilidade sem conectar o serviço ao combate.
6. Só iniciar integração em H.23, conforme autorização posterior.

## 18. Resultado desta preparação

O motor H.20 foi implementado em `backend/app/services/attribute_engine.py` e coberto pelos testes de
`backend/tests/test_attribute_engine.py`. Na ausência do documento H.19 preenchido, foram adotadas
somente convenções técnicas conservadoras para viabilizar o serviço: percentuais em escala inteira
sobre o valor pós-aditivos, multiplicadores positivos combinados por produto, arredondamento
`ROUND_HALF_UP`, limite técnico global existente e precedência canônica para aliases conflitantes.
Essas convenções não alteram combate nem devem ser interpretadas como aprovação de novas regras de jogo.

## 19. Verificação executada

- Testes H.20: **11 aprovados**.
- Suíte completa do backend: **261 aprovados, 13 ignorados**.
- Nenhuma rota, modelo, migration, snapshot de combate, frontend ou configuração persistente foi alterado.
