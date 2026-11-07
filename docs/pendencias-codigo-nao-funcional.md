# Pendencias de codigo nao funcional

Data: 2026-11-05

Este documento registra funcionalidades que possuem estrutura, interface, modelo ou
integracao parcial no codigo, mas ainda nao entregam um fluxo funcional completo.

## Critérios

- **Parcial:** existe persistencia, API ou interface, mas falta integracao, operacao
  autoritativa ou validacao ponta a ponta.
- **Nao funcional:** a estrutura existe, mas nao ha fluxo utilizavel ou esta limitada
  a dados locais/demonstração.
- **Nao integrado:** existem componentes independentes que ainda nao sao usados pelo
  sistema principal.
- **Nao validado:** o codigo implementa o fluxo, mas nao existe evidencia suficiente
  para considerar o recurso pronto para release.

## Equipamentos e atributos

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| Motor central de atributos | Parcial | backend/app/services/attribute_engine.py | Existe como serviço puro e isolado; nao participa das APIs reais nem do snapshot de combate. |
| Contrato H.19 | Não implementado | docs/H19-planejamento-sistema-atributos-equipamentos.md vazio | Nomes, operações, limites, precedência e arredondamento ainda nao possuem contrato aprovado. |
| Equipar/desequipar pelo jogador | Não funcional | CharacterItem possui is_equipped e slot em backend/app/models/entities.py | Não existe endpoint nem ação funcional de equipamento. |
| Slots oficiais | Não implementado | CharacterItem.slot existe como texto livre | Não existe lista oficial de slots nem compatibilidade categoria-slot. |
| Limites por slot | Não implementado | Nenhum contrato persistente ou validação encontrado | Não há exclusividade, ocupação, limite ou carga validada por slot. |
| Modificadores de item | Parcial | Item.attributes e Item.effects são JSON livres | A UI administrativa usa campos textuais; não existe contrato estruturado. |
| Bônus aditivos e percentuais | Parcial | Motor reconhece add_flat, add_percent e aliases | Não existe cadastro, persistência estruturada nem integração ponta a ponta. |
| Multiplicadores | Parcial | Motor reconhece multiply | Regras completas, limites e integração ainda nao estão definidos. |
| Modificadores especiais | Não implementado | Nenhuma entidade de efeito especial estruturada encontrada | Roubo de vida, regeneração, resistência especial e efeitos similares não existem como contrato funcional. |
| Remoção ao desequipar | Não funcional | Combate recalcula uma lista de equipamentos equipados | Não há operação autoritativa nem motor integrado; o comportamento nao pode ser considerado garantido para todos os atributos. |
| Persistência dos atributos finais | Não implementado | Character.attributes continua sendo a ficha base JSON | Valores derivados nao possuem API, persistência calculada ou atualização consistente. |
| Integração de atributos no combate | Parcial | backend/app/api/combat.py lê ataque, defesa e alcance | O motor central nao é chamado; magias, velocidade, crítico, esquiva, precisão, resistência e outros atributos nao são derivados pelo motor. |

## Buffs e debuffs

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| Dano contínuo por turno | Parcial | damage_over_time em Combatant.conditions e remaining_turns | Funciona apenas para o tipo dano contínuo. |
| Buff/debuff genérico de atributos | Não implementado | O motor aceita active_effects, mas não existe modelo persistente encontrado | Não há aplicação real de força, defesa, velocidade ou outros atributos. |
| Duração por tempo real | Não implementado | Não existe expires_at para efeitos de combate | Todo sistema atual de duração conhecido é por turnos. |
| Acumulação e substituição | Não implementado | Não existe política persistida nem contrato | Cada efeito precisa de regra de stacking ou replacement. |
| Efeitos exclusivos | Não implementado | Nenhum identificador de exclusividade encontrado | Não há bloqueio de acumulação incompatível. |
| Expiração automática | Parcial | remaining_turns e tick do dano por turno | Não existe sistema universal de expiração para efeitos, origem ou tempo real. |
| Persistência pós-reconexão | Não integrado | Efeitos ficam no JSON conditions do combatente | Falta demonstrar recuperação completa em rotas de reconexão e reconciliação. |
| Remoção pela origem | Não implementado | Não existe vínculo de efeito com equipamento ou habilidade | Desequipar ou perder uma origem não remove efeitos derivados automaticamente. |

## Player administrativo

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| CRUD administrativo | Funcional/depende da API | src/components/admin/ManagementPages.tsx | Os recursos dependem da API oficial; há componentes locais misturados. |
| Cadastro administrativo de modificadores | Não funcional | Campos bonuses e effects textuais | Não existem campos estruturados para slot, operação, prioridade ou duração. |
| CRUD de personagens com inventário | Parcial | inventoryInput e equipamentos do personagem | O inventário é aceito por cadastro; equipar em slots nao possui ação completa. |
| Configuração de slots por item | Não implementado | O item administrativo não possui slot permitido estruturado | Apenas categorias existem. |

## Dados locais e demonstração

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| Banco local de demonstração | Não funcional como backend oficial | src/services/dataService.ts usa LocalDemoService | Dados sao armazenados em localStorage e nao são autoritativos. |
| Dados mockados | Não funcional em produção | src/data/mock.ts | Existem IDs Discord e registros fictícios; nao representam integração real. |
| Preferências administrativas locais | Local | src/components/admin/AdminApp.tsx usa localStorage | Nome do projeto, densidade e limites de campanha ficam apenas no navegador. |

## Economia

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| Configuração de economia | Parcial | GET/PUT /api/admin/economy/config | Persiste configuração, mas não existe transação comercial completa. |
| Registro administrativo de transação | Parcial | POST /api/admin/transactions | Apenas cria o registro; nao atualiza saldo, estoque ou inventário de forma atomica. |
| Compra para o jogador | Não implementado | Não existe endpoint de compra encontrado | Não há validação de ouro, estoque, item e rollback integrado. |
| Venda para o jogador | Não implementado | Não existe endpoint de venda encontrado | Não há atualização segura de ouro e inventário. |
| Check de saldo | Não funcional no fluxo comercial | WalletTransaction apenas registra valores positivos | Não existe entidade ou regra confirmada para débito/crédito de saldo. |
| Compra/venda com idempotência | Não implementado | Sem chave de idempotência específica de comércio | Repetições podem produzir registros inconsistentes. |

## Multiplayer, tempo real e reconexao

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| WebSockets/tempo real | Não implementado | src usa polling e create-non-overlapping-poll | Atualizações de lobby e combate usam HTTP periódico. |
| Presenca em tempo real | Não implementado | Lobby atualiza presença por polling | Não há canal persistente nem evento instantaneo. |
| Desconexão/reconexão visual | Não validado | Modelo possui status/sessões, mas UI nao possui evidência completa | Falta teste visual e funcional com processos reais simultaneos. |
| Persistência pós-reinicialização | Não validado | Documentação indica que nao foi validada | Faltam testes em ambiente de release. |
| Histórico compartilhado narrativo | Não validado | API/eventos existem | Fluxo completo e recuperação por reload ainda nao possuem evidencia suficiente. |
| Cena compartilhada | Não validado | APIs de campanha/narrativa existem | Não houve publicação e validação visual completa com vários participantes. |

## Discord

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| Vínculo Discord | Parcial | ID externo e modelos Discord persistem estruturas | É metadado estrutural, nao OAuth funcional. |
| OAuth Discord | Não implementado | Nenhuma rota OAuth encontrada | Nao há troca ou armazenamento seguro de token. |
| Bot Discord | Não implementado | Não existe processo/bot servidor | Canais e guildas não possuem operação real. |
| Eventos Discord para campanha | Não implementado | Modelos Discord existem apenas como estrutura | Falta publicação, recepção e sincronização funcional. |

## Modo solo

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| Modo solo | Não implementado | Campanhas e início exigem membros multiplayer | Não existem rota, modelo, UI ou IA de campanha solo. |

## Release e infraestrutura

| Funcionalidade | Estado | Evidencia no codigo | Lacuna principal |
|---|---|---|---|
| PostgreSQL de produção validado | Não validado | Conexao e migrations existem | Não houve aplicação e validação completas em ambiente homologado. |
| Bootstrap administrativo de produção | Não implementado | CLI possui bootstrap somente para ambiente local autorizado | O release nao possui procedimento seguro documentado e validado. |
| Evidência visual boss MÉDIO | Não validado | Combate cobre o boss por testes | Falta captura visual integral aprovada. |
| Evidência visual boss DIFÍCIL | Não validado | Combate cobre o boss por testes | Falta captura visual integral aprovada. |
| Backup/restauração | Não validado | Configuração PostgreSQL/Alembic existe | Nao existe resultado de teste documentado nesta auditoria. |
| Exclusão lógica/auditoria completa | Parcial | Existem eventos, recompensas e logs | Alguns fluxos criticos nao possuem auditoria/retencao comprovada ponta a ponta. |

## Resumo por prioridade

### Bloqueia sistemas oficiais

1. Contrato H.19 e cadastro estruturado de modificadores.
2. Endpoint e transações de equipar/desequipar.
3. Slots oficiais e validação de compatibilidade.
4. Integração do motor central com personagem e combate.
5. Modelo persistente de buffs/debuffs.

### Bloqueia lançamento multiplayer

1. WebSockets ou sincronização mais adequada para estado compartilhado.
2. Reconexão visual e persistência pós-reinicialização.
3. Cena compartilhada, voto, consequência e histórico.
4. PostgreSQL/migrations/backup validados.
5. Evidência visual dos bosses pendentes.

### Fora da primeira versão, salvo decisão contrária

1. Modo solo.
2. Discord funcional.
3. Compra/venda comercial.
4. Dados locais/demonstração como fonte oficial.

## Lacunas específicas de batalhas

| Funcionalidade | Estado no código | O que ainda falta |
|---|---|---|
| Criação de encontro multiplayer | Implementado parcialmente | Requer 3 a 5 participantes ativos, personagens válidos e HP disponíveis; ainda não existe fluxo reutilizável completo para todos os cenários. |
| Combate por turnos | Implementado | Continuar validando jogo morto, abandono, reconexão, reload e empate em ambiente de release. |
| Ações simultâneas e duplo clique | Implementado parcialmente | Existem idempotência e pendência de ação; falta validar concorrência real com os clientes do cenário publicado. |
| Desempate por velocidade | Parcial | Velocidade é usada em partes do snapshot, mas o motor central não é integrado aos atributos finais. |
| Critério de iniciativa | Parcial | Existe atributo no motor, mas não está conectado à ordem completa das regras multiplayer. |
| Dano físico | Implementado | Base, defesa e equipamentos básicos estão conectados. |
| Dano mágico | Parcial | Existe atributo e custo, mas a integração universal com resistências, defesa mágica e modificadores ainda não está fechada. |
| Defesa física | Implementado parcialmente | Equipamentos e personagens podem alterar ataque e defesa. |
| Defesa mágica | Parcial | Atributo existe, mas não há integração completa com todos os danos mágicos. |
| Crítico | Não integrado | Chance e dano crítico não possuem contrato completo nem cálculo automático centralizado. |
| Precisão e esquiva | Não integrado | Não há resolução universal ponta a ponta. |
| Resistências e fraquezas elementais | Parcial/mostrado como estrutura | Listas existem em snapshots, mas não há contrato completo para dano, buff/debuff, itens e combate. |
| Alcance | Parcial | Equipamentos podem produzir alcance; a integração não usa o motor central. |
| Bosses comuns, médios, difíceis e hard | Parcialmente implementado | MÉDIO e DIFÍCIL possuem cobertura de estado/API, mas não evidência visual integral aprovada. |
| Boss com ataques consecutivos | Implementado em parte | HARD possui estratégia baseada em teste, mas precisa ser validado no fluxo visual completo e com reconciliação de ação. |
| Inteligência artificial por estratégia | Implementado parcialmente | Estratégias `balanced`, `aggressive`, `defensive` e similares existem em análise, mas nem todos os comportamentos estão integrados a uma validação end-to-end pública. |
| Dano por tempo | Parcial | Funciona por turnos para `damage_over_time`, mas não constitui sistema genérico de efeitos. |
| Cura contínua, escudos, veneno, silêncio e stun | Não implementado como sistema genérico | Alguns tipos podem existir em JSON ou código específico, mas não há contrato persistente único. |
| Interruptar ação visual sem alterar resultado | Implementado | O frontend recebe resultado autoritativo; a interrupção visual continua usando fallback/timers. |
| Animações ausentes ou incompatíveis | Parcial | Há fallback visual em combate, mas não substitui validação de todos os GIFs e perfis publicados. |
| Abandono/desconexão de combate | Não validado | Falta política autoritativa completa para timeout, reconexão e substituição/continuação de turno. |
| Combate após reload | Parcial | Estado é persistido, mas o fluxo precisa de validação simultânea de ações e resolução repetida. |
| Auditoria de dano | Parcial | Eventos de combate existem, mas não há relatório unificado do histórico completo de bônus, efeitos e equipamentos por turno. |
| Escala e carga do motor | Não validado | Não existem evidências de capacidade e concorrência para partidas extensas. |

## Lacunas específicas de campanhas

| Funcionalidade | Estado no código | O que ainda falta |
|---|---|---|
| Criar campanha | Implementado | Falta criar via painel administrativo amplo com os mesmos controles do fluxo jogador. |
| Entrar por código | Implementado | Validar concorrência com códigos duplicados, divisão de rede e reload do lobby. |
| Mínimo e máximo de jogadores | Implementado | Regras estão presentes, mas falta validação de release com todas as combinações de saída/reentrada. |
| Saída da campanha | Implementado parcialmente | Falta política completa de proprietário, expulsão, transferência de propriedade e personagem órfão. |
| Pronto para iniciar | Implementado | Validar todos os participantes em estado `ready`, personagens únicos e presença simultânea. |
| Presença | Parcial | Usa heartbeat HTTP e polling; presença não é tempo real nem confiável em split network. |
| Timeout de participante | Não implementado de forma comprovada | Não existe política operada pelo servidor para ausente prolongado ou desconexão. |
| Transferência de propriedade | Não implementado | Não existe rota/papel validado nem interface. |
| Expulsão de jogador | Não implementado | Não há operação administrativa/jogador do lobby com histórico auditável. |
| Papel de mestre narrativo | Não implementado | Não existe autoridade separada do proprietário; o painel do mestre narrativo é opção de interface, não papel server-side completo. |
| Personagem único por participante | Implementado | Continuar validando troca simultânea, personagens antigos e campanha ativa. |
| Início da campanha | Implementado | Falta testar ausência de conteúdo narrativo e recuperação após conflito no servidor. |
| Capítulos | Implementado | Criar, publicar, bloquear e ordenar precisam ser validados com dependências de cenas, NPCs e missões. |
| Cenas | Implementado parcialmente | Falta evidência visual completa de cena compartilhada e reencontro posterior ao reload. |
| Diálogos | Implementado parcialmente | Depende de publicação oficial e fluxo narrativo completo. |
| Escolhas | Implementado parcialmente | Condições de escolha e próximas cenas precisam ser validadas com estado real da campanha. |
| Votação | Implementado parcialmente | Maioria, empates, votos duplicados, alteração de voto e deadline precisam validação ponta a ponta. |
| Prazo de votação | Parcial | Existe interface conceitual, mas falta mecanismo robusto de conclusão automática persistente. |
| Consequência de voto | Não validado | Não existe evidência completa de transição para cenário seguinte com todos os participantes. |
| Histórico compartilhado | Não validado | Eventos existem, mas a apresentação completa após reload ainda não está comprovada. |
| Estado mundial persistido | Implementado parcialmente | World state existe; falta auditoria de quais escolhas alteram quais dados. |
| NPCs e relações | Implementado | Validação completa depende da campanha, dependências e conteúdo publicado. |
| Missões de campanha | Implementado parcialmente | Atribuição e progresso existem; falta cobertura integral com conclusão, recompensas e conteúdo simultâneo. |
| Conflito de eventos após reload | Não validado | Falta validar idempotência narrativa, sequência, duplicação e eventos atrasados. |
| Reconexão de jogador | Não validado | Presença e sessao podem persistir, mas o estado visual completo deve ser testado. |
| Escala do lobby | Não validado | Não há teste de carga para códigos, polling, 5 participantes e campanhas concorrentes. |

## Lacunas específicas do painel administrativo

| Funcionalidade | Estado no código | O que ainda falta |
|---|---|---|
| Autenticação administrativa | Implementado parcialmente | Login seguro existe, mas bootstrap e revalidação de produção precisam de procedimento autorizado. |
| Proteção backend das rotas administrativas | Implementado | Continuar validando todas as ações com usuário comum, sessão expirada e origem inválida. |
| CRUD de jogadores | Parcial | Lista, ficha e inventário existem; suspensão, recuperação e histórico completo não estão fechados. |
| CRUD de personagens | Parcial | CRUD/inventário/atributos existem, mas equipar, slots, efeitos derivados e edição segura não estão completos. |
| CRUD de NPCs | Implementado | Dependências, soft-delete, assets, diálogos e relações precisam validação operacional. |
| CRUD de criaturas/monstros | Implementado | Estatísticas, resistências, fraquezas, drops e dependências estão presentes. |
| Configuração visual de boss | Implementado | Ainda precisa ser validada com todos os modos visual e comportamental. |
| CRUD de itens/equipamentos | Parcial | Preço, peso, atributos JSON, versão e dependências existem, mas modificadores estruturados não. |
| Slots permitidos no admin | Não implementado | Não existe campo de slot ou categoria compatível. |
| Modificadores estruturados de item | Não implementado | Bônus e efeitos são texto/JSON livre na UI. |
| Prévia do atributo final | Não implementado | O admin não consegue calcular ou visualizar o impacto final de um modificador no personagem. |
| CRUD de habilidades | Parcial | Mana, alvo, efeito e cooldown existem, mas efeitos especiais e contrato universal não estão completos. |
| Editor de efeitos de habilidade | Não implementado | JSON livre não garante tipos de alvo, duração, stacking, elementos ou exclusividade. |
| Biblioteca de assets | Implementado | Falta validar concorrência, armazenamento de produção e limpeza de órfãos. |
| Upload de arquivos e GIFs | Implementado parcialmente | Persistência local existe; CDN/storage de produção e política de retenção não foram validadas. |
| Editor de animações | Implementado | Falta validar todas as combinações de entidade, ataque, impacto, frames e duração. |
| Perfis de entidades | Implementado | Items de perfil, NPCs e personagens estão presentes, mas combinação visual precisa de cobertura completa. |
| Missões | Implementado | Objetivos, atribuição, progresso, conclusão e recompensa possuem backend e UI. |
| Recompensas | Parcial | Persistência/autorização existem; contrato econômico completo ainda não está fechado. |
| Criar/editar/excluir campanhas administrativas | Parcial | Há visualização e conteúdo narrativo, mas não CRUD amplo consistente com campanhas de jogador. |
| Publicação de capítulo/cena | Parcial | APIs existem, mas o fluxo visual completo exige capítulo ativo, cena inicial e participantes. |
| Economia administrativa | Parcial | Configuração e registro existem, mas compra/venda, saldo, estoque e rollback não. |
| Configurações gerais | Parcial | World settings por chave existem, mas falta contrato e validação por tipo em todas as seções. |
| Dados demonstrativos no admin | Local/não oficial | Alguns eventos, preferências e listas devem ser removidos ou claramente segregados antes do release. |
| Auditoria administrativa | Não completo | Existem eventos específicos, mas não há histórico uniforme antes/depois de todas as alterações críticas. |
| Paginação e filtros extensos | Parcial | Backend e UI não aplicam paginação consistente em todas as coleções grandes. |
| Exclusão lógica uniforme | Parcial | Algumas entidades protegem dependências ou soft-delete; faltam retenção e políticas completas por tipo. |
| Publicação/despublicação em lote | Não implementado | Não há operação segura de lote para itens, NPCs, capítulos ou criaturas. |
| Ações críticas com confirmação | Parcial | Algumas exclusões dependem da UI; falta confirmação segura e auditoria de todas as operações sensíveis. |
| Testes E2E administrativos | Não completo | Existem testes unitários/integrados, mas não um fluxo visual completo de todas as seções críticas. |
| Logout e expiração administrativa | Parcial | Sessão existe, mas expiração, renovação e recuperação precisam de validação de release. |
