# Inventário de funcionalidades do RPG

## Objetivo

Este inventário diferencia estrutura, funcionamento por backend, cobertura automatizada, validação por DOM/API e confirmação visual. Não substitui testes nem demonstrações. Itens marcados como implementados têm suporte de código; itens marcados como pendentes podem já ter partes implementadas.

## Núcleo multiplayer

| Funcionalidade | Implementação | Backend | Testes | DOM/API | Visual | Situação |
|---|---:|---:|---:|---:|---:|---|
| Cadastro/login | Sim | Sim | Sim | Sim | Parcial | Operacional |
| Sessão jogador | Sim | Sim | Sim | Sim | Parcial | Operacional |
| Sessão admin | Sim | Sim | Sim | Sim | Sim | Operacional |
| Criar campanha | Sim | Sim | Sim | Sim | Não conhecido | Implementada |
| Entrar por código | Sim | Sim | Sim | Sim | Não conhecido | Implementada |
| Lobby/presença | Sim | Sim | Sim | Sim | Não conhecido | Implementada |
| Início com 3 jogadores | Sim | Sim | Sim | Sim | Não conhecido | Implementada |
| Máximo de 5 jogadores | Sim | Sim | Sim | Sim | Não conhecido | Implementada |
| Narrativa e votação | Sim | Sim | Sim | Sim | Não conhecido | Implementada |

## Personagem e progressão

| Funcionalidade | Persistência | Autoridade | Interface | Testes | Situação |
|---|---:|---:|---:|---:|---|
| Ficha e atributos | Sim | Backend | Sim | Sim | Implementada |
| HP/mana máximo e atual | Sim | Backend | Sim | Sim | Implementada |
| Nível, XP e atributos | Sim | Backend | Sim | Sim | Implementada |
| Ouro | Sim | Backend | Sim | Sim | Implementada |
| Missões atribuídas | Sim | Backend | Sim | Sim | Implementada |
| Recompensas | Sim | Backend | Sim | Sim | Implementada |
| Ancestralidade/classe | Sim | Backend | Sim | Sim | Implementada |
| Histórico narrativo | Sim | Backend | Sim | Sim | Implementada |

## Inventário, equipamentos, itens e habilidades

| Funcionalidade | Persistência | CRUD admin | Backend autoritativo | Testes | Situação |
|---|---:|---:|---:|---:|---|
| Inventário por personagem | Sim | API | Sim | Sim | Implementado |
| Quantidade empilhável | Sim | Sim | Sim | Sim | Implementado |
| Equipar/desequipar | Sim | Parcial | Sim | Sim | Implementado, exige validação ponta a ponta de cada efeito |
| Slots | Sim | Parcial | Sim | Sim | Implementado |
| Itens | Sim | Sim | Sim | Sim | Implementado |
| Preço/estoque/peso | Sim | Sim | Sim | Sim | Implementado |
| Efeitos e atributos JSON | Sim | Sim | Parcialmente por contrato | Sim | Implementado parcialmente |
| Habilidades | Sim | Sim | Sim | Sim | Implementado |
| Custo/recarga mana | Sim | Sim | Sim | Sim | Implementado |
| Requisitos JSON | Sim | Sim | Parcialmente por contrato | Sim | Implementado parcialmente |
| Drops | Sim | Sim | Sim | Sim | Implementado |
| Compra/venda comercial | Estrutura de transação | Parcial | Não comprovado | Parcial | Não concluído |

## Combate

| Funcionalidade | Backend | Testes | DOM/API | Visual |
|---|---:|---:|---:|---:|
| Seleção de ação | Sim | Sim | Sim | Jogador positivo |
| Idempotência por action_id | Sim | Sim | Sim | Indiretamente positivo |
| Dano após resolução | Sim | Sim | Sim | Positivo |
| Atualização de HP | Sim | Sim | Sim | Positivo |
| Turnos | Sim | Sim | Sim | Parcial por evidência histórica |
| Repetição de resolução | Sim | Sim | Sim | Positivo por ação única |
| Boss COMUM | Sim | Sim | Sim | Positivo |
| Boss MÉDIO | Sim | Sim | Sim | Pendente |
| Boss DIFÍCIL | Sim | Sim | Sim | Pendente |
| Boss HARD | Sim | Sim | Sim | Positivo |
| Configuração de ataque Admin | Sim | Sim | Sim | Positivo |
| Configuração de boss Admin | Sim | Sim | Sim | Positivo |

## Conteúdo administrativo

- Campanhas: leitura administrativa, sem CRUD amplo completo.
- Jogadores/personagens: consulta e gestão parcial.
- Capítulos, NPCs, itens, monstros, habilidades, drops, recompensas, economia e universo: CRUD ou configuração por API.
- Assets: upload, metadados, associações e persistência.
- Animações: editor persistente.
- Perfis de entidades: GIFs, ataque, delays, duração, dano, dificuldade, máximo de ataques e interrupção.
- Economia: configuração e transações presentes; compra/venda de jogabilidade não comprovada ponta a ponta.

## Funcionalidades ausentes ou futuras

- Modo solo.
- WebSockets para eventos multiplayer.
- IA narrativa completa.
- Condições de cena executáveis.
- Discord OAuth/bot real.
- Compra/venda comercial completa.
- Edição administrativa ampla de campanhas.

## Lacunas a fechar antes de ampliar conteúdo

1. Contrato único para efeitos JSON de itens e habilidades.
2. Garantia de que requisitos são aplicados ao tentar equipar, aprender ou usar.
3. Validação de cada efeito de equipamento sobre atributos, HP, mana e combate.
4. Definição da economia considerada parte do lançamento.
5. Decisão sobre realtime e fallback de polling.
6. Evidência visual final de MÉDIO e DIFÍCIL.

## Matriz detalhada de propriedades

### Itens

| Propriedade | Persistência | Admin | Efeito comprovado |
|---|---|---|---|
| Nome, descrição, categoria, raridade | Sim | Sim | Catálogo/ficha |
| Preço | Sim | Sim | Catálogo; execução de compra não ponta a ponta |
| Peso | Sim | Sim | Nenhum cálculo de carga comprovado |
| Estoque | Sim | Sim | Nenhum checkout de estoque comprovado ponta a ponta |
| Empilhável | Sim | Sim | Identificador persistido; política de limite não comprovada |
| Uso | Sim | Sim | Nenhum executor universal comprovado |
| Requisitos | Sim | Sim | Estrutura persistida; aplicação não comprovada de forma única |
| Atributos | Sim | Sim | Somente ataque/defesa são consumidos pelo snapshot de combate |
| Efeitos | Sim | Sim | Ataque/defesa; outros efeitos dependem de contrato/efeito específico |
| Equipado | Sim | Gestão parcial | Bônus de ataque/defesa/snapshot visual |
| Slot | Sim | Gestão parcial | Persistido; não comprovada política completa de slots válidos |

### Equipamentos

- Ataque físico: comprovado no snapshot de combate quando equipado.
- Defesa física: comprovada no snapshot de combate quando equipado.
- Alcance de arma: comprovado no perfil.
- GIF/visual do equipamento: binding existente.
- Buffs temporários: não comprovados.
- Atributos genéricos adicionais: não há aplicação autoritativa comum comprovada.
- Requisitos de uso: JSON persistido, aplicação ponta a ponta não comprovada.

### Habilidades

| Propriedade | Persistência | Backend | Situação |
|---|---|---|---|
| Mana | Sim | Desconto e bloqueio | Comprovado |
| Cooldown | Sim | Estado de recarga | Comprovado |
| Dano base | Sim | Cálculo | Comprovado |
| Cura | Sim | Aplicação de HP | Comprovado |
| Alvo | Sim | Validação de alvo | Parcial para tipos suportados |
| Área | Schema admite configuração | Executor rejeita target não suportado | NÃO COMPROVADO |
| Dano por turno | Sim em efeitos adicionais | Aplicação limitada | Comprovado em escopo específico |
| Buff/debuff genérico | Estrutura JSON parcial | Sem contrato universal | NÃO COMPROVADO |
| Requisitos | Sim | Sem aplicação única demonstrada | NÃO COMPROVADO |

### Requisitos de lançamento

- Confirmar valores oficialmente suportados de itens e habilidades.
- Separar campos demonstrativos de campos mecanicamente executados.
- Impedir que o Admin anuncie atributos sem consumidor backend.
- Testar limites de inventário, empilhamento, peso, slots, equipamento e consumo em SQLite.

## Fechamento da matriz geral

O inventário acima é um mapa de evidências, não uma afirmação automática de completude. Persistência, CRUD administrativo, cobertura automatizada e efeito autoritativo são avaliados separadamente.

Consequentemente:

- um campo existente em `effects`, `attributes` ou `requirements` não prova que a regra esteja ativa;
- um item equipável não prova que todos os seus atributos JSON tenham efeito;
- uma habilidade cadastrada não prova que o executor valide todos os seus requisitos;
- uma transação administrativa registrada não prova compra/venda do jogador ponta a ponta;
- uma animação configurada não prova que o resultado visual ocorreu em tempo real.

As lacunas desta matriz devem ser fechadas por testes SQLite e validação funcional antes de serem classificadas como recursos completos de lançamento.

## Confirmação dos contratos JSON realizada em 2026-11-05

### Itens equipados

No snapshot autoritativo de combate, itens equipados são consumidos por:

- `attributes.attack` ou `effects.attack` para ataque;
- `attributes.defense` ou `effects.defense` para defesa;
- `settings.reach` para alcance.

Também são retornados `animation_display` e a animação vinculada ao perfil visual. Outros campos JSON e instruções de uso não possuem consumidor único confirmado nesta leitura.

### Habilidades

O snapshot autoritativo confirma o consumo de:

- custo de mana;
- cooldown;
- categoria/alvo;
- `effects.power` como dano-base;
- `settings.additional_effects`;
- alcance;
- animações e perfil visual.

O dano efetivo continua sendo resolvido pelo backend; o frontend serve apenas como apresentação. Campos adicionais em `effects` ou `requirements` não devem ser considerados completos até haver uma regra de consumidor, validação e teste explícitos.

### Evidência de testes

Esta inspeção é complementar às suites executadas: backend com 250 aprovações, 13 ignorações; frontend com 60 aprovações em 11 arquivos. Os resultados passam, mas não substituem evidência de cada efeito JSON.
