# Viabilidade do modo solo

## Conclusão executiva

O modo solo **não está implementado**. Parte do combate, do personagem, da narrativa e das entidades pode ser reutilizada, mas o modelo de campanha atual é obrigatório e multiplayer.

Não se recomenda criar um sistema solo paralelo. A evolução segura é adaptar a criação, entrada e início de campanhas para suportar uma sessão solo controlada, mantendo o backend como autoridade e reutilizando o executor de combate.

## Evidências técnicas

### Campanhas

- `Campaign.min_players` possui constraint de 3 a 5.
- `Campaign.max_players` é limitado entre o mínimo e 5.
- `CampaignCreateRequest.max_players` aceita apenas 3 a 5.
- O endpoint de início exige pelo menos `campaign.min_players` participantes ativos.
- Todo participante ativo precisa possuir personagem associado à campanha.

Essas regras tornam impossível iniciar uma campanha solo por meio do fluxo atual sem alterações coerentes de modelo, schemas e API.

### Backend de combate

O combate já é modelado por encontros, combatentes e ações persistidas. Isso permite reutilizar:

- submissão de ação;
- resolução autoritativa;
- idempotência;
- turnos;
- estratégias de IA;
- perfil visual dos ataques.

Seria necessário definir como criar o combatente controlado pelo sistema, instanciá-lo por campanha solo ou entidade temporária, e como persistir/retomar a batalha sem múltiplos participantes humanos.

### Narrativa

As campanhas carregam história, capítulos, cenas, escolhas e votos. O modelo de voto pressupõe participantes humanos. Um modo solo ainda pode reutilizar o snapshot narrativo, mas precisa definir substituição de votação, escolha direta do jogador, checkpoints e persistência.

### Personagens, inventário e progressão

O modelo `Character` já contém campanhas, owner, atributos, HP, mana, XP, ouro e inventário. Pode representar um personagem solo sem criar um modelo paralelo se a campanha puder ter um único participante ativo.

## O que pode ser reutilizado

1. Autenticação.
2. Criação de personagem.
3. Ficha, atributos, XP, ouro e progressão.
4. Inventário, itens, habilidades e equipamentos.
5. Missões, recompensas e catálogo de drops.
6. Perfis de entidades, assets e animações.
7. Motor de combate autoritativo.
8. Estratégias de IA de boss.
9. Snapshot de conteúdo narrativo.

## O que precisa ser definido

### Contrato de campanha

- Modos `multiplayer` e `solo`, explicitamente persistidos.
- Um mínimo de 1 jogador no modo solo.
- Propriedade e remoção segura da campanha.
- Limite de participantes apropriado ao modo.
- Preservação das campanhas multiplayer existentes.

### Progresso solo

- Save único autoritativo.
- Estado resumível após reload.
- Checkpoints narrativos.
- Tratamento de morte, derrota e game over.
- Política de retry/recarregar batalha.

### Combate solo

- Aliados controlados por jogador.
- Inimigos controlados por IA.
- Ordem de turnos simplificada.
- Tratamento de pausas e interrupções.
- Reutilização da resolução autoritativa sem exigir participantes humanos.

### Narrativa solo

- Escolha direta pelo jogador ou mecanismo adaptado de votação.
- Determinação de tempo limite, se houver.
- Histórico e consequências persistentes.
- Continuidade sem outros jogadores.

### Autorizações

- Jogador é proprietário da campanha solo.
- Nenhum participante de terceiros acessa a sessão.
- Admin continua separado.
- APIs existentes não devem aceitar bypass de membership.

## Avaliação de esforço

### Pequena alteração de apresentação, sem viabilidade real

Não seria suficiente apenas remover o aviso de mínimo ou ocultar participantes. Isso quebraria constraints, início, narrativa e autorização.

### Incremento seguro planejado

- Migration de modo de campanha.
- Ajustes em constraints e schemas.
- Separação clara das políticas multiplayer/solo.
- Criação e inicialização de campanha solo.
- UX de personagem principal, narrativa, combate e retomada.
- Testes SQLite isolados.
- Testes de autorização e idempotência.
- Validação visual com navegador.

O trabalho exigiria novas fases controladas. Não deve ser iniciado nesta consolidação.

## Riscos

1. DB constraints divergirem da API.
2. Turnos assumirem múltiplos atores humanos.
3. Narrativa depender de votação.
4. Interfaces reutilizarem componentes multiplayer incompatíveis.
5. Progressão duplicar saldo, XP ou recompensas.
6. Dados multiplayer serem migrados ou alterados acidentalmente.

## Critério de viabilidade

O modo solo será viável quando:

- o modo fizer parte do contrato persistido;
- 1 participante puder iniciar sem lógica especial no frontend;
- o combate reutilizar o executor autoritativo existente;
- a narrativa puder ser decidida pelo jogador ou por política definida;
- save, retry e reload forem idempotentes;
- os testes cobrirem SQLite isolado;
- campanhas multiplayer existentes forem preservadas.

