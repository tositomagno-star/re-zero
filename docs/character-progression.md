# Progressão e evolução de personagens

## Regras iniciais

O backend mantém a regra em `backend/app/services/progression.py`:

- `Character.xp` é o XP acumulado **na faixa do nível atual**, preservando o
  significado dos valores existentes sem converter dados antigos.
- O custo para o próximo nível é `100 × nível atual`. O XP excedente é
  transportado para a faixa seguinte e pode subir vários níveis numa única
  recompensa.
- O nível máximo inicial é 10.000. No limite, o XP continua sendo acumulado e
  a ficha informa que não há próximo nível.
- Cada nível aumenta HP máximo em 5, mana máxima em 2 e concede 1 ponto de
  atributo não alocado. HP e mana atuais recebem o mesmo incremento, limitados
  aos novos máximos.
- Não há aumento automático de atributos-base: ainda não existe regra de classe
  ou de alocação definida. Os pontos ficam disponíveis na ficha até uma etapa
  definir essa alocação.

Esses valores são uma regra inicial explícita e centralizada, não uma regra de
balanceamento permanente. Recompensas e progressão são calculadas no backend;
nenhuma rota de jogador aceita valores de XP, ouro, nível ou pontos.

## Recompensas e consistência

`apply_character_reward` aplica uma especificação validada a um personagem
vinculado à campanha. O serviço aceita XP, ouro, itens e habilidades publicadas,
verifica limites e vínculo com a campanha, registra cada concessão e aplica
todas as alterações na transação do chamador. O chamador deve confirmar ou
reverter essa transação.

A chave idempotente é única por personagem. Repetir a mesma chave e conteúdo
retorna o resultado já registrado; reutilizá-la com outra recompensa retorna
conflito. Um bloqueio por personagem no processo permanece ativo até o commit
ou rollback da transação, impedindo atualizações perdidas no mesmo worker; o
bloqueio da linha e a restrição única do banco coordenam workers PostgreSQL
distintos. SQLite valida concorrência com requests simultâneos em um banco
file-backed, mas não substitui o teste PostgreSQL entre workers.

`apply_world_reward` converte uma definição ativa do catálogo `WorldReward`
para a mesma estrutura. A resolução autoritativa de uma escolha narrativa
chama o serviço dentro da transação do voto vencedor. Consequências publicadas
podem referenciar IDs de recompensas ativas e missões publicadas atribuídas ao
personagem; o cliente não envia quantidades nem pode acionar a concessão
diretamente. Missões só são concluídas se estiverem em andamento para o
personagem. Vitórias em combate e outros eventos ainda não implementados não
concedem recompensas.

O histórico guarda valores anteriores e posteriores, XP/ouro concedidos,
níveis ganhos e snapshot da especificação. Para concessões narrativas e de
missão, esse snapshot inclui o ID e o nome da origem; registros antigos sem
esses campos continuam legíveis. A ficha apresenta o progresso do nível atual,
pontos disponíveis e os dez eventos mais recentes, incluindo a origem e itens.

## Persistência e implantação

A migração `a41b9e2d7c10_character_progression` adiciona
`characters.attribute_points` e cria `character_reward_grants`, incluindo
chave idempotente, histórico, dados de auditoria e índices. Ela ainda precisa
ser aplicada nos ambientes autorizados antes de implantar o código. Nesta
etapa, a migração foi criada, mas **não foi executada**; não houve DDL em
PostgreSQL.

Testes locais usam SQLite isolado. Os testes marcados `postgres`, migrations e
qualquer escrita nos perfis PostgreSQL continuam bloqueados enquanto o
isolamento do banco de Testes não for comprovado.

## Próximos passos

- Definir balanceamento final, limites e eventual alocação de atributo por
  classe.
- Implementar UX de seleção das missões/objetivos na edição narrativa; a tela
  atual permite inserir UUIDs e identificadores de objetivo explicitamente.
- Implementar eventos de combate antes de permitir recompensas de combate.
- Definir tratamento de itens/habilidades já possuídos em recompensas futuras
  e UX para distribuição de pontos.
- Aplicar a migração somente em banco de teste comprovadamente isolado e
  executar os testes PostgreSQL apropriados com autorização específica.
