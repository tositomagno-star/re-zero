# Progressão narrativa persistente

## Estado desta etapa

A progressão reutiliza `Campaign`, `CampaignMember`, `Character`, `Chapter`, `StoryNode`, `StoryChoice`, `StoryVote`, `GameSession` e `GameEvent`. Não foi criada uma segunda hierarquia de sessões e não foi necessária migração: o snapshot e o estado atual ficam em `GameSession.state`, enquanto votos e histórico usam as tabelas já existentes.

O proprietário continua podendo iniciar a sala conforme a regra do lobby da Etapa B. Durante a partida, não há papel de mestre nem permissões narrativas especiais para proprietário ou participante; o backend valida e executa as decisões.

## Fluxo e persistência

1. `POST /api/campaigns/{id}/start` verifica participação ativa, proprietário iniciador, estado da sala, mínimo/máximo de jogadores e personagens.
2. O servidor seleciona o primeiro capítulo global publicado e ativo por posição, e a primeira cena ativa desse capítulo.
3. Antes de iniciar, valida se destinos explícitos das escolhas apontam para cenas ativas disponíveis no mesmo capítulo e exige escolhas na cena inicial.
4. A sessão guarda um snapshot de capítulos, cenas, escolhas, condições e consequências, além da configuração de votação e dos IDs atuais. Uma edição futura do Painel do Mestre não substitui esse snapshot.
5. `GET /api/campaigns/{id}/game` devolve capítulo, cena, participantes/personagens, escolhas, estado/apuração da votação e o histórico completo.
6. `POST /api/campaigns/{id}/game/vote` aceita a decisão de um participante elegível. O servidor valida sessão ativa, associação, rodada, cena e escolha a partir do snapshot; `StoryVote` mantém um voto atual por jogador/cena/rodada.
7. Ao completar a votação ou vencer o prazo, a apuração e a progressão acontecem na mesma transação que registra os eventos. O destino explícito avança para a cena indicada; sem destino explícito, segue a próxima cena ativa e, ao fim do capítulo, o próximo capítulo ativo publicado. Sem próximo conteúdo, a sessão termina.
8. Reentrada pelo código preserva personagem, sessão, votos e histórico. A elegibilidade é congelada no início; quem sair precisa reentrar para votar enquanto a votação ainda estiver aberta.

O snapshot da sessão também impede que o Painel do Mestre remova capítulos, cenas ou escolhas referenciados enquanto a sessão estiver em andamento. Os eventos de decisão guardam rótulo, apuração e consequência oficial usada naquele momento. A edição do catálogo não reescreve o histórico já registrado.

Sessões `in_progress` criadas pela versão anterior podem ter `GameSession.state` vazio. Elas são preservadas, mas a API retorna `409` em vez de reconstruir conteúdo retroativamente sem snapshot; a política para reconciliá-las precisa ser definida.

## Votação

`POST /api/campaigns` aceita `voting_settings`:

```json
{
  "allow_vote_change": true,
  "deadline_seconds": null,
  "tie_breaker": "unresolved"
}
```

- O padrão escolhido para campanhas novas permite alterar o voto aberto, não define prazo e não resolve empate automaticamente.
- Uma repetição idêntica do mesmo voto é idempotente. Alterações são registradas como eventos, sem criar um segundo voto ativo do mesmo participante naquela rodada.
- A votação fecha quando todos os participantes elegíveis votam ou quando `deadline_seconds` expira. Sem prazo, não há encerramento temporal.
- Se um prazo terminar sem nenhum voto, o resultado fica como `no_votes` e a sessão não avança; a política para reabrir essa votação ainda precisa ser definida.
- A apuração usa a escolha com maior contagem. Empate pode usar `choice_order` (menor posição cadastrada no Painel do Mestre) ou `unresolved`; no padrão `unresolved`, o empate fica registrado, não aplica consequência e não avança a cena.
- O polling da interface consulta o prazo e efetua o fechamento vencido; não existe worker de temporizadores nesta etapa. A UI do lobby atualiza snapshots a cada cinco segundos e heartbeat de presença a cada quinze segundos somente enquanto a aba está visível; ao voltar para a aba, dispara nova atualização imediatamente. Respostas de polling iniciadas antes de uma ação local não substituem o estado mais recente aplicado.
- `GameSession` é bloqueada com `SELECT FOR UPDATE` durante votação/apuração e eventos finais usam chaves idempotentes. O teste de concorrência real ignora SQLite, que não implementa esse bloqueio; deve ser executado no PostgreSQL.

## Consequências e limites intencionais

O texto editorial `description` da consequência vencedora é mantido no estado e no evento de decisão. Também é possível configurar `world_reward_ids`, `quest_objective_updates` e `complete_quest_ids` em uma escolha publicada. O backend avança objetivos somente após a resolução do voto vencedor; cada avanço é idempotente por decisão. A conclusão exige o conjunto de objetivos definido na missão (todos por padrão, ou ao menos um se configurado). XP, ouro, itens, habilidades autorizadas, evolução e conclusão são persistidos na transação do voto. Eventos `quest_progress_updated`/`rewards_granted` registram as alterações. Recompensas e condições são congeladas quando a missão é atribuída; o cliente não pode declarar progresso nem conclusão. Consulte [`character-progression.md`](./character-progression.md).

O editor aceita referências a recompensas e missões por UUID, além de avanço de objetivo no formato `questUUID:objectiveID:quantidade`; IDs inválidos, repetidos ou acima do limite rejeitam a decisão sem concessões parciais. Recompensas devem existir e estar ativas. Missões devem estar publicadas e pertencer à campanha; personagens sem missão atribuída/em andamento não recebem a recompensa da missão. A gestão administrativa de missões e atribuições está em `MissionManagementPage`. Combate não está implementado e não concede recompensas.

As expressões de `conditions` ainda não têm linguagem nem avaliador definido; nesta etapa, todas as escolhas da cena ativa são exibidas. Não há IA narrativa, WebSockets ou fallback para conteúdo demonstrativo. O polling do lobby respeita a visibilidade da aba conforme descrito acima.

Decisões para etapas futuras: definir a gramática geral de condições narrativas; decidir como reabrir uma votação encerrada sem votos; decidir novos desempates; e decidir se capítulos/sessões poderão ser reiniciados. Até essas definições, condições de escolhas não filtram opções e efeitos não narrativos além das consequências de recompensa e missão não são executados.

## PostgreSQL

PostgreSQL 18.6 foi validado em ambiente local. `cronicas_do_reino_dev` está migrado até `91d4a0b7c8e2` (head), e `alembic check` não identificou operações pendentes. Os testes de concorrência narrativa são executados contra `cronicas_do_reino_test`, em schemas isolados que permanecem no banco após a execução para evitar limpeza destrutiva automática.

Para configurar outro ambiente e executar os testes PostgreSQL, siga [`postgresql-development.md`](./postgresql-development.md). As decisões pendentes de votação, condições e efeitos mecânicos permanecem abertas; esta etapa não introduziu regras novas.
