# Auditoria geral do RPG e prontidão para lançamento

## 1. Escopo e método

Esta auditoria considera o estado atual do backend FastAPI, do frontend TanStack/React, dos modelos SQLAlchemy, dos testes existentes e da documentação histórica. Não houve acesso a PostgreSQL, execução de migrations ou alteração de dados persistentes. Os testes e a validação visual citados nesta etapa são evidências de sessões anteriores.

Os estados usados neste documento têm os seguintes significados:

- **Implementado:** existe persistência, API e interface ou regra no projeto.
- **Coberto por testes:** existe suíte automatizada que exerce o comportamento.
- **Validado por DOM/API:** o fluxo foi observado sem depender apenas de código.
- **Validado visualmente:** existe evidência de captura visual válida.
- **Pendente:** falta evidência ou existe uma lacuna funcional objetiva.
- **Não comprovado:** o código contém parte da estrutura, mas não há evidência suficiente para considerar o recurso completo.

## 2. Arquitetura auditada

### Backend

- FastAPI com routers separados para autenticação, campanhas, narrativa, combate, conteúdo administrativo, assets, animações e perfis de entidades.
- SQLAlchemy assíncrono com SQLite em testes comuns e PostgreSQL configurável para ambientes persistentes.
- Autenticação por cookie/sessão, com sessão administrativa separada.
- Alembic configurado para migrations.
- Backend autoritativo para combate; animações do frontend não participam da resolução.

### Frontend

- TanStack Start/Router, React, TypeScript, Tailwind e Radix/shadcn.
- Rotas públicas, autenticação, jogador, campanhas, lobby, administração.
- `dataService` integra coleções administrativas ao servidor quando há endpoints oficiais.
- A interface do lobby atualiza estado por polling.

### Persistência

Os modelos cobrem usuários, campanhas, membros, personagens, inventário, itens, habilidades, missões, monstros, drops, encontros, combatentes, eventos, recompensas, assets, animações, perfis de entidades e integrações Discord.

## 3. Inventário de funcionalidades

| Área | Estado | Evidência | Observações |
|---|---|---|---|
| Autenticação de jogador | Implementado/Coberto por testes | API e suíte backend | Cookie de sessão, login, cadastro, logout e proteção de rotas. |
| Autenticação administrativa | Implementado/Coberto por testes | API e suíte backend | Sessão administrativa separada e operação de bootstrap já existente. |
| Campanhas multiplayer | Implementado/Coberto por testes/DOM/API | Lobby, API e testes | Sala, convite por código, personagens, presença e início. |
| Mínimo de jogadores | Implementado | Modelos e API | 3 jogadores são mínimos por padrão e validados no início da campanha. |
| Narrativa e capítulos | Implementado/Coberto por testes | Snapshots, votação e testes | Conteúdo congelado ao iniciar; frontend consulta por polling. |
| Personagens e fichas | Implementado/Coberto por testes | API, modelos e frontend | Nível, XP, atributos, HP, mana, ouro, status e descrição persistidos. |
| Progressão | Implementado/Coberto por testes | Serviço de progressão | XP, ouro, atributos, itens e habilidades possuem aplicação autoritativa. |
| Missões | Implementado/Coberto por testes | APIs e painel administrativo | Cadastro, atribuição, progresso, conclusão e recompensas. |
| Inventário | Implementado/Coberto por testes | Modelo e API de personagens | Quantidade, equipar e associação por personagem/item. |
| Equipamentos | Implementado/Coberto por testes | Associação persistida e perfil de entidade | Equipar usa estado persistido; consumo de atributos/equipamentos deve ser conferido caso a caso no release. |
| Itens | Implementado/Coberto por testes | CRUD administrativo e testes | Campos de preço, peso, efeitos, requisitos, atributos, estoque, uso, imagem e versão. |
| Habilidades/magias | Implementado/Coberto por testes | CRUD, modelo, perfil e combate | Custo de mana, efeitos JSON, alvo, requisitos e recarga. |
| Criaturas e drops | Implementado/Coberto por testes | CRUD, regras de drop | Estatísticas, XP, recompensas, resistências/fraquezas e chances. |
| Biblioteca de assets | Implementado/Coberto por testes | API, frontend e testes | Upload, metadados, associações e conteúdo persistente. |
| Editor de animações | Implementado/Coberto por testes | API, frontend e testes | Configurações persistidas e associados a entidades, itens ou habilidades. |
| Perfis administrativos de entidades | Implementado/Coberto por testes/visual | Editor de entidades | Ataques, GIFs, delay, duração, dano e configuração de boss. |
| Combate por turnos | Implementado/Coberto por testes/DOM/API | Motor de combate e testes | Backend aplica ação, resolve estado, turnos, dano e efeitos. |
| Boss COMUM | Implementado/Validado visualmente | Evidência histórica | Máximo de um ataque por turno conforme estratégia existente. |
| Boss MÉDIO | Implementado/Coberto por testes/DOM/API | Evidência de estado/API | Evidência visual integral ainda pendente. |
| Boss DIFÍCIL | Implementado/Coberto por testes/DOM/API | Evidência de estado/API | Evidência visual integral ainda pendente. |
| Boss HARD | Implementado/Validado visualmente | Evidência histórica | Dois ataques podem ocorrer em sequência com resoluções separadas. |
| Economia e transações | Parcialmente implementado | API administrativa/modelos | Configuração e registros persistem; README registra que compra/venda comercial ainda não é executada. |
| Integração Discord | Estruturalmente preparado | Metadados de guild/canal | Não há OAuth, bot ou uso funcional real documentado. |
| WebSockets/tempo real | Não implementado | Arquitetura atual usa polling | Atualização e presença possuem latência aproximada. |
| Modo solo | Não implementado | Não existem rotas/modelos/UI/estratégia solo | Campanhas e início são obrigatoriamente multiplayer. |

## 4. Auditoria por área

### 4.1 Autenticação e autorização

Há divisão entre jogador e administrador, tokens/sessões armazenados por hash e proteção administrativa server-side. A API ainda trata origens e cookies explicitamente. Não foram encontrados defeitos reproduzíveis que justificassem alteração nesta consolidação.

### 4.2 Campanhas, lobby e narrativa

O modelo de campanha exige entre 3 e 5 jogadores; o padrão mínimo é 3 e o máximo default é 5. A validação de início impede campanhas com participantes ativos abaixo do mínimo ou acima do máximo. O frontend admite campanhas para múltiplos participantes, mas não apresenta fluxo solo. O proprietário não recebe papel de mestre narrativo.

### 4.3 Personagem, inventário, equipamentos e recompensas

Existem personagens associados a usuários e campanhas, com atributos JSON para extensibilidade. Inventário usa quantidade, equipar e slot; itens incluem efeitos, atributos e requisitos em JSON. Habilidades persistem custo, efeitos, alvo, requisitos e cooldown. Regras comerciais não estão completas, pois transações são registradas sem implementação comprovada de compra/venda.

Risco de lançamento: campos JSON são flexíveis, mas dependem de consumidores coerentes. Antes de ampliar conteúdo, é necessário validar a aplicação efetiva dos efeitos em cada rota de personagem, combate, inventário e recompensa.

### 4.4 Combate

O combat engine mantém estado, ações, resolução, idempotência, turnos e IA determinística. O frontend anima o resultado sem autorizar dano ou HP. Há evidências positivas de jogador, COMUM, HARD e interface administrativa de ataque/boss. MÉDIO e DIFÍCIL permanecem pendentes somente por evidência visual.

### 4.5 Administrações e editor de entidades

O painel contém campanhas, jogadores, personagens, criaturas, habilidades, itens, assets, animações, missões, economia e configuração visual. Os registros oficiais persistem no servidor. Alguns cartões ou preferências demonstrativas continuam explicitamente separados de dados oficiais.

### 4.6 Documentação e configuração

O README foi atualizado na H.18 para reconhecer combate, mas partes dele ainda apresentam contagens históricas de testes e instruções antigas de ambiente. A documentação não deve ser usada como fonte operacional isolada: os documentos de arquitetura podem conter requisitos futuros, não implementados.

## 5. Problemas concretos encontrados

1. **Modo solo inexistente.**
   - Evidência: mínimo de jogadores no banco, schema, API de criação e regra de início.
   - Impacto: não é seguro comercializar modo solo sem uma alteração arquitetural planejada.

2. **Economia incompleta.**
   - Evidência: README e documentação registram transações armazenadas, mas compra/venda ainda não executadas.
   - Impacto: saldo pode ser mostrado sem oferecer economia funcional ponta a ponta.

3. **Tempo real limitado a polling.**
   - Impacto: presença usa aproximação por heartbeat, e eventos podem chegar com atraso.
   - Não é defeito reproduzível, mas pode ser bloqueador dependendo dos requisitos de lançamento.

4. **WebSockets e Discord não implementados.**
   - Impacto: funcionalidades anunciadas como futuras continuam fora do produto.

5. **Evidência visual incompleta de dois bosses.**
   - MÉDIO e DIFÍCIL estão validados por estado/API/testes, mas não visualmente.
   - Isso não deve ser tratado como defeito da implementação.

6. **Integração de campos JSON não auditável apenas por presença de schema.**
   - Itens, habilidades e requisitos usam JSON extensível.
   - É necessário fechar um contrato canonical antes de ampliar mecânicas ou afirmar compatibilidade completa.

Nenhum bloqueador foi atribuído a ausência de capturas visuais como se fosse erro de combate.

## 6. Priorização para lançamento

### P0 — Bloqueadores

- Decidir se o lançamento exige modo solo. O produto atual não possui suporte.
- Definir o banco de produção e executar somente a preparação/versionamento necessária com autorização.
- Confirmar autenticação, cookies, CORS, expiração e recuperação de sessão em ambiente alvo.
- Fechar ou despublicizar economia que não execute compra/venda.
- Corrigir integrações externas ou removê-las da experiência publicada até ficarem implementadas.

### P1 — Alta prioridade

- Validar migrações e integridade PostgreSQL em ambiente descartável autorizado.
- Obter evidência visual de MÉDIO e DIFÍCIL se o lançamento anunciar esses bosses como comprovados.
- Padronizar contratos JSON de efeitos, requisitos, atributos, inventário e recompensas.
- Testar concorrência e recuperação de actions de combate em ambiente alvo.
- Garantir observabilidade de saúde, erros e eventos críticos.

### P2 — Evolução

- Avaliar WebSockets após confirmar que polling não atende à experiência desejada.
- Implementar Discord/OAuth somente com gestão segura de credenciais.
- Melhorar paginação e filtros para catálogos extensos.
- Automatizar auditoria de dados administrativos e estados demonstrativos.

## 7. Checklist resumido de lançamento

- [ ] Banco de produção definido e backup/restauração testados.
- [ ] Migrations aplicadas somente pelo procedimento autorizado.
- [ ] Playwright ou teste navegador cobre login de jogador/admin e recuperação de sessão.
- [ ] Campanhas criadas, entradas por código e início validados com participantes reais de teste.
- [ ] Narrativa, progressão e recompensas validadas ponta a ponta.
- [ ] Inventário, equipamentos e habilidades validados com efeitos autorizativos.
- [ ] Combate validado visualmente conforme cada dificuldade publicada.
- [ ] Admin protegido por sessão e validação server-side.
- [ ] Assets e uploads validados com limites e persistência.
- [ ] Economia implementada ou retirada da superfície pública.
- [ ] Integrações não implementadas removidas ou claramente marcadas como futuras.
- [ ] Logs, segredo, CORS, cookies, origens e rate limit revisados em ambiente de lançamento.
- [ ] PostgreSQL real não foi alterado nesta auditoria.

## 8. Situação do banco

Nenhum PostgreSQL foi acessado, nenhuma migration aplicada, nenhum DDL/DML destrutivo executado e nenhuma role, grant, campanha ou conta real modificada. Esta auditoria manteve SQLite isolado e arquivos somente de documentação.

## 9. Auditoria detalhada de inventário e atributos

### 9.1 Modelo e persistência

O catálogo de itens persiste `category`, `rarity`, `price`, `weight`, `effects`, `requirements`, `attributes`, `stock`, `usage`, `is_stackable`, `is_active` e imagem. O vínculo personagem-item persiste quantidade, equipar/desequipar, slot e data de aquisição.

| Campo | Persistido | CRUD/Admin | Consumidor comprovado |
|---|---|---|---|
| Nome, descrição, categoria, raridade | Sim | Sim | Catálogos, fichas e filtros |
| Preço e estoque | Sim | Sim | Configuração/catálogo; compra-venda não comprovada ponta a ponta |
| Peso | Sim | Sim | Persistência e formulário; sem validação de carga de personagem comprovada |
| Empilhável | Sim | Sim | Persistência; sem política única de limite de quantidade comprovada |
| Uso | Sim | Sim | Persistência; sem executor universal de consumo comprovado |
| Imagem | Sim | Upload/campo | Asset/preview; validação visual depende de catálogo real |
| `effects` JSON | Sim | Sim | `attack`/`defense` podem alimentar combate |
| `attributes` JSON | Sim | Sim | `attack`/`defense` podem alimentar combate |
| `requirements` JSON | Sim | Sim | Estrutura persistida; aplicação de requisitos não comprovada fora do contrato de combate |
| Equipado/slot | Sim | Gestão parcial | O combate soma `attack` e `defense` somente de itens equipados |

### 9.2 Efeitos reais de equipamentos

Itens equipados pelo personagem entram no snapshot do combate. A fonte de bônus usa, nesta ordem, o perfil administrativo `settings.attack/defense`, depois `item.attributes`, depois `item.effects`.

- **Ataque de equipamento:** comprovado no backend de combate.
- **Defesa de equipamento:** comprovado no backend de combate.
- **Alcance de arma:** comprovado como leitura do perfil `settings.reach`.
- **Animação visual do equipamento:** associável ao perfil e consumida pelo snapshot visual.
- **Outros atributos JSON:** não têm contrato autoritativo único, logo não devem ser considerados efetivos.
- **Buff permanente ou temporário derivado de um item:** não foi comprovado.
- **Limite de carga:** não comprovado.
- **Limites por tipo/slot:** a persistência aceita slot, mas não há política completa por slot comprovada nas rotas públicas.
- **Requisitos de classe, nível ou atributo:** persistidos, mas não comprovada aplicação geral ponta a ponta.

### 9.3 Inventário e operações

Existe vínculo único personagem-item com quantidade positiva. Isso permite representar empilhamento em uma única linha. O modelo permite quantidade maior que zero, mas não existe um limite maximo de inventário comprovado em serviço público ou API.

Confirmado estruturalmente:

- adicionar recompensas ao inventário;
- consolidar quantidades para item já existente;
- ler inventário na ficha da campanha;
- marcar item como equipado e informar slot;
- aplicar bônus de ataque e defesa de itens equipados.

Não comprovado ou ausente:

- compra/venda de personagem completa com atualização de ouro, estoque, inventário e transação de forma atomicamente validada ponta a ponta;
- consumo de poções/itens de cura fora dos caminhos de combate apresentados;
- remoção de item por interface jogável;
- limite de peso e capacidade;
- autoempilhamento condicionado por `is_stackable`;
- restrição por requisito antes de equipar;
- validação única entre slots oficiais;
- expiração de buffs de itens e efeitos temporários persistentes.

## 10. Auditoria detalhada de habilidades e mana

Habilidades persistem custo de mana, efeitos JSON, alvo, requisitos, categoria, cooldown e status.

### 10.1 Efeitos consumidos pelo combate

O backend:

- bloqueia uso sem mana suficiente;
- desconta mana na resolução da ação;
- registra cooldown absoluto;
- calcula dano físico ou mágico conforme categoria/tipo;
- aplica cura;
- aplica dano por turno limitado quando o efeito adicional declara `damage_over_time`, dano por turno e duração;
- valida alcance, mesmo lado, alvo e tipo de alvo compatível.

| Mecânica | Estado real |
|---|---|
| Custo de mana | Implementado |
| Bloqueio por mana insuficiente | Implementado |
| Desconto de mana | Implementado |
| Recarga por cooldown | Implementado |
| Dano direto | Implementado |
| Cura | Implementado |
| Resistência/fraqueza elementar | Implementado |
| Dano por turno | Implementado com escopo limitado em `additional_effects` |
| Buff/debuff genérico | PARCIAL/NÃO COMPROVADO além dos efeitos especiais existentes |
| Requisitos JSON | Estrutura existente, aplicação geral não comprovada |
| Alvo em área | Aceito pelo schema de Admin apenas em parte; o executor atual rejeita novos tipos de alvo fora de aliados/inimigos/próprio |
| Efeito elementar declarado apenas em `effects` | Não é um contrato universal comprovado |

O backend também chama `_sync_character_resources`, portanto o desconto deve persistir junto à resolução autoritativa da ação. A operação é incorporada ao fluxo de combate e não confiada ao frontend.

### 10.2 Limitações e riscos

- `effects` não possui um schema semântico completo e uniforme.
- `mana_cost`, dano base, cura, efeitos adicionais e elementos podem ser representados em múltiplos campos.
- Cooldown é armazenado em estado da combate antes da resolução visual, em vez de existir uma entidade calendário independente de habilidade.
- O frontend não é responsável por autorizar mana; ele apenas apresenta estado.
- Requisitos de classe/nível/atributos não possuem consumidor oficial único demonstrado em aprendizado e utilização.

## 11. Auditoria de campanhas, multiplayer, reconexão e narrativa

### 11.1 Campanhas

O fluxo atual exige:

- usuário autenticado;
- proprietário reservando o assento de partida;
- mínimo padrão de três participantes ativos e máximo padrão de cinco;
- personagem associado de todo participante ativo;
- campanha ativa antes da inicialização.

A API valida o intervalo mínimo/máximo antes de iniciar. Os schemas também limitam `min_players/max_players` ao intervalo 3–5.

### 11.2 Multiplayer observável

Funcionalidades presentes:

- criação de campanha;
- convite por código;
- entrada e saída de participantes;
- personagem por participante;
- lobby e presença;
- narrativa por capítulos;
- snapshots de conteúdo congelados ao iniciar;
- votação e resolução narrativa.

Limitações:

- atualização por polling, não WebSocket;
- reconexão/reload devem ser testados contra sessão real e conflitos de participantes;
- presença é aproximada por heartbeat;
- escalabilidade e ordenação de eventos não foram comprovadas por carga;
- não há documentação operacional suficiente sobre expulsão, transferência de propriedade ou presença prolongada.
- o papel de mestre narrativo não existe como autoridade separada do proprietário do cliente.

### 11.3 Integridade

Os documentos anteriores registraram testes de start com participantes, personagens, ownership, narrative reload e idempotência. Ainda devem ser considerados pendentes de release:

- saída e reconexão simultâneas;
- timeout de participante ativo;
- divisão de rede em sessão criada/iniciada;
- duas campanhas reutilizando códigos concorrentes;
- progressão simultânea de recompensas;
- eventos duplicados após reload.

## 12. Painel administrativo auditado por seção

| Seção | Cadastro/edição | Exclusão | Configuração real | Estado |
|---|---|---|---|---|
| Personagens/Jogadores | CRUD parcial de fichas | Regras defensivas | Ficha, atributos, ouro, histórico, inventário e habilidades mostrados na gestão | PARCIAL |
| NPCs/Aliados | CRUD administrativo | Sim por entidade quando sem dependências | Perfis, dados, assets, animações | IMPLEMENTADO |
| Criaturas/Monstros | CRUD | Sim com proteção de dependência | HP, ataque, defesa, velocidade, XP, resistências, fraquezas, drops | IMPLEMENTADO |
| Bosses | Perfil administrativo e campos visualis do combate | Conforme entidade/perfil | Dificuldade, ataques, máximo por turno, interrupção, GIFs | IMPLEMENTADO e evidência visual de Admin positiva |
| Itens | CRUD/versionamento | Soft-delete quando utilizado | Preço, peso, raridade, estoque, efeitos, atributos, requisitos, uso, empilhamento, imagem | PARCIAL na mecânica de efeitos |
| Equipamentos | Associação a perfil e campos do item | Proteção de dependência | Ataque, defesa e alcance podem produzir efeito | PARCIAL; outros atributos não auditados ponta a ponta |
| Armas | Tipo/categoria de item + perfil | Proteção de dependência | Ataque, alcance, animações/GIFs | PARCIAL |
| Magias/Habilidades | CRUD | Proteção de dependência | Mana, dano, alvo, efeito, cooldown e requisito | PARCIAL além das mecânicas comprovadas |
| Assets | Upload e metadados | Conforme uso | Categoria, associação, status | IMPLEMENTADO |
| Animações | Editor e bindings | Conforme uso | Frames, duração, associação visual | IMPLEMENTADO |
| Missões | CRUD | Proteção de dependência | Objetivos, atribuição, recompensas | IMPLEMENTADO/TESTADO |
| Recompensas | CRUD | Proteção de dependência | Ouro, XP, itens | BACKEND integrado, contrato econômico incompleto em alguns fluxos |
| Campanhas | Visualização e controles administrativos limitados | Não equivalente a CRUD completo público | Participantes, capítulos e estado; criação administrativa ampla não comprovada | PARCIAL |
| Combate | Configuração por perfil | Não se aplica | GIF personagem/ataque, delay, duração, dano, boss IA | IMPLEMENTADO/EVIDÊNCIA VISUAL POSITIVA |
| Economia | Configuração oficial e transações | Conforme integridade | Moedas, markup, taxa de venda, regras | PARCIAL/NÃO COMPROVADO ponta a ponta |
| Configurações gerais | Settings por chave | Proteção | Valores JSON | PARCIAL; exige contrato por chave |

## 13. Matriz geral de funcionalidades

| Sistema | Existe | Admin configura | Backend funcional | Testado | Estado consolidado |
|---|---|---|---|---|---|
| Combate | Sim | Sim | Sim | Sim | COMPLETO no backend; MÉDIO/DIFÍCIL com pendência visual |
| Campanhas multiplayer | Sim | Parcial | Sim | Sim | COMPLETO para escopo atual |
| Solo | Não | Não | Não | Não | AUSENTE |
| Inventário | Sim | Sim, parcialmente | Parcial | Sim | PARCIAL |
| Equipamentos | Sim | Sim, parcialmente | Ataque/defesa/alcance | Sim | PARCIAL |
| Buffs | Estrutura limitada | Parcial | Alguns efeitos especiais | Parcial | PARCIAL |
| Magias | Sim | Sim | Cura/dano/efeitos limitados | Sim | PARCIAL |
| Mana | Sim | Sim | Consumo/custo/cooldown | Sim | COMPLETO para caminhos de combate auditados |
| Missões | Sim | Sim | Sim | Sim | COMPLETO, sujeito a conteúdo real |
| Progressão | Sim | Parcial | Sim | Sim | COMPLETO |
| Bosses | Sim | Sim | Sim | Sim | COMPLETO funcional; evidência visual MÉDIO/DIFÍCIL pendente |
| Biblioteca de Assets | Sim | Sim | Sim | Sim | COMPLETO |

## 14. Prontidão para lançamento por prioridade detalhada

### P0

1. **Autorizar/revisar banco de lançamento e backups**
   - Importância: integridade de campanha, personagens, inventário e eventos.
   - Sistemas: PostgreSQL, Alembic, sessão SQLAlchemy.
   - Dependência: ambiente autorizado e plano de restore.
   - Validação: checklist de backup/restore e migrations em banco descartável.
   - Complexidade: média.

2. **Fechar ou despublicizar economia incompleta**
   - Importância: ouro e estoque podem divergir do catálogo.
   - Sistemas: items, character_items, wallet/transactions, Admin economia.
   - Dependência: decisão de escopo e contrato transacional.
   - Validação: compra, venda e rollback em SQLite isolado.
   - Complexidade: média.

3. **Fechar autenticação de release**
   - Importância: prevenção de acesso indevido a campanhas e administração.
   - Sistemas: auth, cookies, CORS, dependências administrativas, rate limit.
   - Dependência: domínio/origens de produção.
   - Validação: login, expiração, logout e autorização negativa.
   - Complexidade: média.

### P1

- Padronizar contratos JSON de item/habilidade/requisitos.
- Obter evidência visual MÉDIO/DIFÍCIL apenas se forem anunciados como validados visualmente.
- Validar reconexão, reload, expiracao de presença e início simultâneo.
- Validar efeitos de item por equipamento real em SQLite.
- Fechar a superfície de compra/venda ou removê-la da interface.
- Definir observabilidade e alerta de falha de combate/recompensa.
- Revisar páginas demonstrativas ou campos de dados não persistentes na UI.

Complexidade geral: média; os contratos JSON podem exigir migração incremental de dados se forem formalizados fora da retrocompatibilidade atual.

### P2

- Adotar WebSockets/SSE se polling não atender multiplayer.
- Melhorar filtros, paginação e desempenho de Admin.
- Decidir integração Discord real ou remover preparação não funcional da interface.
- Automatizar auditoria de dependências de assets, profiles e conteúdo.

### P3

- Modo solo completo.
- Narrativa assistida por IA.
- Economia avançada e mercados.
- Conteúdo procedural expandido.

## 15. Modo solo: viabilidade, implementação recomendada e complexidade

O modo solo é viável sem duplicar campanhas, personagens ou combate. É necessário estender o modelo de campanha com tipo/modalidade e manter multiplayer como política alternativa.

Recomendação:

1. Persistir `game_mode = multiplayer|solo`.
2. Alterar constraints/schema para exigir mínimo/máximo coerentes por modalidade.
3. Manter o mesmo motor de campanha/narrativa/combate, substituindo participantes humanos por atores controlados por sistema apenas na execução.
4. Implementar snapshot/save e retomada para o personagem solo.
5. Adaptar votação narrativa para escolha direta do jogador solo.
6. Adicionar UX de criação solo e continuar salvo.
7. Cobrir autorização, integridade, reload e recompensas em SQLite isolado.

Não existe necessidade de recriar inventário, progressão, habilidades ou combate. Estimativa: grande alteração incremental de várias áreas, pois campanha, narrativa, UI, constraints e testes são afetados. Não é recomendável iniciar sem concluir o contrato JSON e preservar integralidade do multiplayer.

## 16. Ordem recomendada de desenvolvimento

1. Fechar contratos de itens, requisitos e habilidades.
2. Fechar economia ou remover da superfície pública.
3. Completar e revisar autenticação/autorização de lançamento.
4. Validar PostgreSQL e restauração em ambiente autorizado.
5. Completar reconexão, reload e integridade de combate.
6. Obter evidência visual dos itens de lançamento obrigatórios.
7. Implementar modo solo sobre o motor atual.
8. Adotar realtime ou Discord apenas como evolução posterior.

## 17. Conclusão da auditoria detalhada

O projeto possui núcleo multiplayer, personagem, inventário parcial, progressão, combate autoritativo, bosses, simulação, assets, animações, Admin, narrativa e missões. O backend é a fonte de dano, mana, turnos, progressão e recompensas para os caminhos auditados.

As afirmações de prontidão devem distinguir:

- implementado;
- coberto por testes;
- confirmado por DOM/API;
- confirmado visualmente;
- pendente ou não comprovado.

Não há evidência nesta auditoria para declarar economia, todos os efeitos JSON de item/habilidade ou modo solo completos. Tampouco há prova visual integral de MÉDIO e DIFÍCIL. Essas limitações não invalidam o código já coberto por testes, mas impedem aprovação visual integral.

## 18. Fechamento da consolidação geral

### Estado operacional consolidado

- O núcleo multiplayer está implementado e coberto por testes.
- Autenticação, personagens, narrativa, progressão, missões, assets, perfis e combate possuem implementação no backend.
- O combate autoritativo foi validado por testes e DOM/API; jogador, COMUM, HARD, frames e Admin possuem evidência visual positiva.
- MÉDIO, DIFÍCIL e qualquer item visual adicional não coberto por captura continuam pendentes sem alteração de classificação funcional.
- O modo solo não existe no contrato atual de campanha e não deve ser anunciado como disponível.

### Riscos concretos de conteúdo

1. Campos JSON de `requirements`, `effects` e `attributes` não têm um validador semântico único em todas as rotas.
2. Os requisitos de item/habilidade só podem ser considerados efetivos quando o caminho de uso real os aplicar.
3. Itens equipados comprovam apenas ataque, defesa e alcance nos fluxos auditados.
4. Economia admite configuração e registros administrativos, mas a compra/venda pelo jogador não foi fechada ponta a ponta.
5. Polling e heartbeat são adequados ao escopo atual, mas não constituem WebSocket ou evento em tempo real.

### Decisões para próxima etapa

- Não iniciar modo solo até uma decisão explícita sobre modelo, narrativa, save, combate e autorização.
- Não publicar como completo qualquer efeito JSON sem consumidor backend comprovado.
- Não anunciar economia comercial completa até compra, venda, estoque, ouro, inventário e rollback serem validados.
- Obter evidência visual dos itens pendentes apenas em ambiente isolado, sem alterar código.
- Tratar PostgreSQL como operação separada e autorizada; esta consolidação não exige migration nem acesso ao banco.

### Evidências de integridade

A consolidação final foi feita somente com leitura de código, documentação, modelos e relatórios existentes. Nenhuma API, modelo, migration, regra de combate, `.env`, credencial, role, grant ou campanha persistente foi alterada neste fechamento.

## 19. Validação executada nesta auditoria (2026-11-05)

### Suítes automatizadas

- Backend: `backend/.venv/Scripts/python.exe -m pytest -q`
  - Resultado: **250 testes aprovados, 13 ignorados**.
  - Os testes foram executados no ambiente de teste do backend, em SQLite isolado.
- Frontend: `npm.cmd test -- --reporter=dot`
  - Resultado: **11 arquivos aprovados, 60 testes aprovados**.
- O frontend apresentou um aviso de `act(...)` no teste `combat-panel.test.tsx`; não houve falha na suíte, mas o aviso deve ser tratado antes do lançamento para evitar mascarar regressões assíncronas.

### Verificação visual já disponível nesta sessão

- Foi confirmada a página de login em `http://127.0.0.1:8080/login` por DOM: títulos, campos de usuário/senha, botão de entrar e links de cadastro/acesso administrativo estão presentes.
- Esta captura não representa autenticação concluída, combate, lobby ou fluxo administrativo e não deve ser usada para declarar esses fluxos visualmente aprovados.
- Não foi realizada nesta sessão uma verificação visual integral de campanhas, inventário, equipamentos, combate, bosses MÉDIO/DIFÍCIL ou modo solo.

### Limite da evidência atual

A execução atual aumenta a confiança em regressões cobertas pelas suítes, mas não altera a classificação de recursos que dependem de validação ponta a ponta ou visual:

- compra/venda comercial;
- efeito de atributos JSON além de ataque/defesa;
- buffs/debuffs temporários além do dano por turno já coberto;
- requisitos de item/habilidade durante todas as ações possíveis;
- médio/difícil em evidência visual;
- reconexão, reload e recuperação do multiplayer em ambiente de produção;
- modo solo.
