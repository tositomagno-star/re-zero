# Etapa H.4 — Motor de combate e integração visual

## Mapa de integrações

- **Personagens e campanhas:** reutiliza `CampaignMember`, `Character`, `CharacterItem` e `CharacterSkill`. O personagem participante continua sendo a ficha vinculada à campanha; não há ficha de combate paralela.
- **Inimigos e conteúdo H.3:** os perfis `EntityContentProfile`, suas associações de habilidades, recompensas e regras de drop definem quais inimigos podem entrar em batalha e os dados copiados para os snapshots.
- **Equipamentos e progressão:** o snapshot considera itens equipados do inventário existente. A vitória entrega XP, moeda, itens e habilidades através de `apply_character_reward`.
- **Assets H.1 e animações H.2:** os snapshots guardam as referências a assets e configurações persistentes de animação. O painel de combate reutiliza `AnimationPreviewArena`; GIFs e callbacks visuais não calculam nem aplicam resultados de jogo.
- **Persistência do combate:** utiliza `Encounter` e `Combatant` existentes, marcando os encontros H.4 com `configuration.combat_engine = "h4"`. Eventos de combate ficam em `CombatActionEvent`, separados dos eventos narrativos para não alterar a recuperação das campanhas existentes.

## Modelos e relacionamentos

- `Encounter` representa a batalha, sua campanha, estado, configuração, ordem de turnos, resultado e versão otimista.
- `Combatant` relaciona um encontro a um personagem **ou** a um inimigo. Persiste HP/mana atuais, condições, iniciativa, índice da instância e snapshot dos valores necessários durante aquela batalha.
- `CombatActionEvent` guarda eventos ordenados, resultado autoritativo e chave única de idempotência por encontro.
- Um mesmo perfil de inimigo pode aparecer mais de uma vez no encontro; cada instância recebe índice distinto.
- A migration `b74c2d91e5a0` prepara as colunas, restrições e tabela necessárias. **Ela não foi aplicada.** A atualização de ambiente deve seguir o fluxo de migrations já aprovado pelo projeto.

## Endpoints

Todos os endpoints exigem jogador autenticado e membro ativo da campanha:

| Método | Caminho | Uso |
|---|---|---|
| `GET` | `/api/campaigns/{campaign_id}/combat` | Recupera a batalha H.4 mais recente para polling e reload. |
| `GET` | `/api/campaigns/{campaign_id}/combat/enemies` | Lista inimigos ativos com perfil disponível. |
| `POST` | `/api/campaigns/{campaign_id}/combat` | Inicia batalha; somente o proprietário da campanha pode iniciar. |
| `GET` | `/api/campaigns/{campaign_id}/combat/{encounter_id}` | Recupera estado e eventos, aceitando `after_sequence`. |
| `POST` | `/api/campaigns/{campaign_id}/combat/{encounter_id}/actions` | Envia `attack`, `skill` ou `end_turn`, com `action_id` único. |
| `GET` | `/api/campaigns/{campaign_id}/combat/assets/{asset_id}` | Serve asset privado somente quando referenciado por snapshot da batalha. |

O início requer campanha em andamento, personagens ativos vinculados a todos os membros ativos e inimigos existentes e disponíveis. O limite do pedido é de 1 a 12 entradas de inimigo.

## Turnos, ações e dano

- A iniciativa usa os aliases `speed`, `agility`, `dexterity` ou `agilidade`, em ordem decrescente; empates são resolvidos por UUID estável. A ficha de personagem também reconhece os campos administrativos em português.
- Apenas o membro que controla o personagem ativo pode agir. Personagens derrotados, alvos inválidos, ações fora de turno e batalhas finalizadas são recusados.
- `action_id` impede repetição; repetir a mesma ação retorna o estado já persistido, e reutilizar o ID para outra ação gera conflito. A versão do encontro e locks de linha protegem atualizações concorrentes.
- Habilidades devem estar aprendidas pelo personagem ou associadas ao perfil do inimigo, ativas e publicadas. O backend valida mana, cooldown, tipo de alvo, lado e alcance.
- Valores baseados nos modelos existentes são copiados para snapshots quando a batalha começa; alterações posteriores no perfil não recalculam uma batalha em andamento.
- Regra inicial explícita: `dano = max(1, poder_de_ataque + dano_base_da_habilidade - defesa_correspondente)`. Em ataques sem habilidade, `dano_base_da_habilidade` é zero. Habilidades mágicas usam poder/defesa mágicos; ataques físicos usam ataque/defesa físicos. Resistência reduz o dano pela metade, com mínimo de 1; fraqueza duplica, limitado ao teto numérico seguro configurado no serviço.
- Armas equipadas contribuem com ataque, defesa e alcance usando os atributos/configurações existentes do item. Não foram adicionados atributos novos à ficha.
- Mana e HP são limitados pelos máximos da ficha. Alterações dos recursos do personagem são sincronizadas pelo backend.

## Inimigos, efeitos e recompensas

- A IA é determinística: entre ataques e habilidades válidos contra alvos vivos ao alcance, prioriza eliminação, dano efetivamente aplicado, menor custo de mana e dano calculado; empates favorecem IDs lexicograficamente menores. Considera mana, alcance, cooldown, tipo de dano, defesa e resistência; se não houver ação ao alcance, encerra o turno.
- Efeitos implementados nesta etapa: cura e dano contínuo com duração limitada, resistência/fraqueza e proteção contra reaplicação da mesma habilidade enquanto o efeito permanece ativo.
- Buffs/debuffs genéricos, imunidades e alvos múltiplos não foram implementados.
- Na vitória, XP e moeda são distribuídos igualmente, com restos atribuídos de forma determinística; itens são distribuídos em rodízio pelos personagens ordenados, e habilidades são concedidas ao primeiro personagem ordenado. Drops usam hash determinístico do encontro, instância e regra.
- A concessão chama o serviço central `apply_character_reward`, com chave idempotente por encontro/personagem, na mesma transação da finalização. Derrotas não concedem recompensas de vitória.
- A distribuição de itens/habilidades é uma regra inicial desta etapa, não uma regra de loot configurável por grupo. Regras mais avançadas precisam de decisão de produto.

## Eventos visuais e interface

O backend persiste a ação, consome recursos, resolve o resultado e registra HP/dano antes de retornar o evento visual. A interface em `CombatPanel` mostra participantes, recursos, ordem, alvos, habilidades, histórico e resultado; consulta novamente o estado para recuperação após reload/rede.

O evento visual inclui animação de ataque/habilidade, impacto, animação do alvo, referências aos assets e velocidade configurada. Na associação inimigo-habilidade, a velocidade individual sobrescreve a velocidade padrão do perfil. A interface reproduz as animações com `AnimationPreviewArena` e apresenta o dano já confirmado. Terminar, falhar ou interromper uma animação não altera o resultado e não envia uma segunda ação.

Os assets são servidos por endpoint autenticado, com cache privado desabilitado, e apenas se estiverem referenciados por um snapshot de combate acessível ao membro da campanha.

## Testes e validações

- `backend/tests/test_combat.py` cobre SQLite isolado para snapshots/iniciativa, instâncias repetidas, ataque e recompensa idempotentes, custo de mana, resistência, efeitos, habilidades múltiplas de inimigo, sobrescrita de velocidade, recompensa de item, autorização e isolamento entre campanhas.
- `src/test/combat-panel.test.tsx` verifica o envio de uma única ação e que concluir a sequência visual não aplica dano nem envia outra ação.
- `src/test/animation-editor.test.tsx` verifica a compatibilidade do executor visual reutilizado.
- Testes automatizados não equivalem a smoke test contra infraestrutura real nem a validação visual manual no navegador. PostgreSQL não é necessário para esses testes SQLite.

## Limitações e próximas integrações

- Ainda não há combate automático em tempo real, WebSockets, estratégia avançada, raids, alvo múltiplo, buffs/debuffs genéricos, imunidades, nem interface de configuração de loot por grupo.
- Velocidade de ataque é usada como dado de apresentação visual; não altera duração de turno nem balanceamento.
- A migration precisa ser aplicada em uma implantação futura autorizada antes de executar esta versão contra banco persistente que ainda não possua o schema H.4.
- Smoke tests com PostgreSQL e inspeção visual real não foram executados nesta etapa; nenhuma migration foi aplicada durante o desenvolvimento.
