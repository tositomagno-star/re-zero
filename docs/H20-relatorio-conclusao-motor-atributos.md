# H.20 - Relatório de conclusão do motor de atributos

## Resultado

Implementação concluída em `backend/app/services/attribute_engine.py`, sem integração com rotas ou
combate nesta etapa.

## Arquivos entregues

- `backend/app/services/attribute_engine.py`
- `backend/tests/test_attribute_engine.py`
- Atualização deste plano: `docs/H20-plano-implementacao-motor-atributos.md`

## Comportamento implementado

- reutilização de `normalize_combat_attributes` e `bounded_nonnegative_int`;
- resolução pura e determinística dos atributos-base;
- preservação das chaves JSON desconhecidas;
- suporte a aditivos, percentuais, multiplicadores, `set` autorizado e limites superiores;
- tratamento de aliases históricos com diagnóstico de conflitos;
- Decimal para cálculo intermediário e arredondamento final `ROUND_HALF_UP`;
- HP atual separado de HP máximo, e mana atual separada de mana máxima;
- saída com base, modificadores normalizados, etapas intermediárias, final, avisos e diagnósticos.

## Decisões técnicas conservadoras

Como o documento H.19 permanece vazio nesta revisão, o motor não define regras novas de jogo:

| Tema | Convenção técnica |
|---|---|
| Percentual | inteiro em escala percentual, aplicado após aditivos |
| Multiplicadores | fatores positivos multiplicados entre si em ordem determinística |
| Ordem | aditivos, percentuais, multiplicadores, override autorizado, limites e arredondamento |
| Arredondamento | `Decimal(...).quantize(..., ROUND_HALF_UP)` |
| Limite | `MAX_COMBAT_VALUE` por padrão; limites por atributo são opcionais |
| Aliases | valor canônico prevalece e conflitos são registrados em diagnóstico |
| Recursos | valores atuais são recebidos e copiados separadamente dos máximos derivados |

## Verificação

- Teste focado: `11 passed`.
- Suíte backend: `261 passed, 13 skipped`.
- Nenhuma falha relacionada ao motor ou às regras existentes de combate foi identificada.

## Preservação

Não foram modificados:

- modelos ou banco de dados;
- migrations ou arquivos de ambiente;
- rotas;
- snapshots ou resolução de combate;
- frontend;
- campanhas ou dados persistidos.

## Próximo passo

H.20 está concluído. Qualquer integração com inventário, efeitos ou combate permanece para etapas
posteriores e depende de autorização explícita.
