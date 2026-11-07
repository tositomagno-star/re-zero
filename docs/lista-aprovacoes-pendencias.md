# Lista de pendencias para aprovacao

Data: 2026-11-05

Use esta lista para aprovar, rejeitar ou adiar cada pendencia antes da implementacao.
Nenhuma das pendencias abaixo deve ser considerada aprovada neste documento.

## A. Atributos, equipamentos e efeitos

### A001 - Contrato H.19 de atributos
Atributos oficiais, nomes canonicos, valores-base, recursos, categorias e aliases.
ok

### A002 - Regras oficiais dos modificadores
Aditivos, percentuais, multiplicadores, especiais, limites, arredondamento, prioridade e precedencia.
ok

### A003 - Motor central integrado ao personagem
Calculo servidor a partir da ficha-base sem sobrescrever atributos persistidos.
ok

### A004 - Motor central integrado ao inventario
Equipamentos devem fornecer modificadores ao resolver os atributos finais.
ok

### A005 - Motor central integrado ao combate
Todos os atributos derivados devem alimentar snapshots e resolucoes de combate.
ok

### A006 - API dos atributos finais
Endpoint ou consulta que exponha base, modificadores, intermediarios e final.
ok

### A007 - Slots oficiais de equipamento
Cabeça, corpo, mãos, armas, pés, acessórios e pescoço.
ok

### A008 - Compatibilidade categoria-slot
Regra persistida indicando quais categorias podem ser colocadas em cada slot.
ok

### A009 - Exclusividade e ocupacao dos slots
Impedir slot incompatível, slot ocupado ou equipamento simultâneo indevido.
ok

### A010 - Equipar pelo jogador
Operacao funcional e autorizada de equipar item.
ok

### A011 - Desequipar pelo jogador
Operacao funcional e autorizada que remove o equipamento e seus modificadores.
ok

### A012 - Troca atomica de equipamento
Trocar equipamento com transacao segura, conflito e idempotencia.
ok

### A013 - Requisitos e nivel de equipamento
Validar nivel, atributos, classes ou outros requisitos antes do equipar.
ok

### A014 - Limites de carga e peso
Peso carregado, carga maxima e regras por personagem.
ok

### A015 - Cadastro administrativo estruturado de modificadores
Interface para atributo, operacao, valor, prioridade, origem, limites e duração.
ok

### A016 - Modificadores positivos e negativos
Suporte mecanico a bonus e penalidade.
ok

### A017 - Modificadores especiais
Vida roubada, regeneração, resistencias especiais, danos elementais e outros efeitos especiais.
ok

### A018 - Remocao segura ao desequipar
Nao manter bonus de equipamento apos troca ou retirada.
ok

### A019 - Protecao contra aplicacao duplicada
Impedir que concorrencia, duplo clique ou reconexao aplique duas vezes o mesmo modificador.
ok

### A020 - Persistencia dos equipamentos apos reconexao
Estado equipado deve ser recuperado sem perder ou duplicar efeitos.
ok

## B. Buffs, debuffs e efeitos temporarios

### B001 - Sistema persistente de efeitos genericos
Modelo servidor para efeitos ativos, origem, alvo, acumulacao, duração e remocao.
ok

### B002 - Buffs de atributos
Alteracoes temporárias de força, ataque, defesa, agilidade, inteligencia, velocidade, sorte ou outros atributos.
ok

### B003 - Debuffs de atributos
Reducoes temporarias persistentes por combate ou habilidades.
ok

### B004 - Duracao por turnos
Decremento autoritativo ao terminar turno ou efeito.
ok

### B005 - Duracao por tempo real
Inicio, expiracao, relógio de servidor e persitencia.
ok

### B006 - Acumulacao de efeitos
Regra para somar aplicacoes iguais.
ok

### B007 - Substituicao de efeitos
Regra para atualizar ou substituir aplicacoes iguais.
ok

### B008 - Efeitos exclusivos
Impedir acumulacao incompatível por identificador ou grupo.
ok

### B009 - Expiração automatica
Remocao servidor sem depender do frontend.
ok

### B010 - Remocao pela origem
Remover buff/debuff quando equipamento, habilidade ou origem deixa de existir.
ok

### B011 - Persistencia apos desconexao
Efeitos ativos devem retornar intactos apos reconexao.
ok

### B012 - Buff permanente por equipamento
Equipamento ativo concede efeito persistente enquanto equipado.
ok

### B013 - Sistema de dano por tempo ampliado
Apoiar cura por tempo, veneno, escudo, silêncio, stun e outros tipos além de dano contínuo.
ok

## C. Combate e batalhas

### C001 - Integramao completa dos atributos de combate
Fisicos, magicos, criticos, esquiva, precisao, alcance, iniciativa, HP, mana e resistencias.
ok

### C002 - Chance critica
Contrato, atributos base, modificadores, arredondamento e limite.
ok

### C003 - Dano critico
Formula oficial e integração com equipamentos e efeitos.
ok

### C004 - Precisao
Formula oficial de acerto e modificadores.
ok

### C005 - Esquiva
Formula oficial e integracao com agilidade/sorte/efeitos.
ok

### C006 - Alcance
Contrato de alcance por arma, ataque, habilidade e alvo.
ok

### C007 - Iniciativa e ordem de turnos
Regra oficial, desempate, velocidade e modificadores temporarios.
ok

### C008 - Ataque fisico autoritativo completo
Integração de equipamentos e modificadores no backend.
ok

### C009 - Ataque magico autoritativo completo
Defesa mágica, inteligência, resistências, modulos e efeitos.
ok

### C010 - Resistencias elementais
Catalogo de elementos, resistencias, fraquezas, limites e redução de dano.
ok

### C011 - Boss MÉDIO validado visualmente
Evidência integral aprovada.
ok

### C012 - Boss DIFÍCIL validado visualmente
Evidência integral aprovada.
ok

### C013 - Boss HARD validado em combate real
Dois ataques consecutivos, regras, interrupcao e reconciliação.
ok

### C014 - Abandono de combate
Timeout, retirada, vitória, derrota ou substituição de jogador desconectado.
ok

### C015 - Reconexao ao combate
Recuperacao visual e autoritativa da ação pendente, turno e estado.
ok

### C016 - Combate apos reload
Validar estado repetido, ação pendente, resolução e ausência de dano duplicado.
ok

### C017 - Auditoria de dano por turno
Detalhar base, equipamentos, buffs, debuffs, resistencias, crítico e resultado.
ok

### C018 - Escala e concorrência de combate
Teste de carga para partidas, ações simultaneas e polling.
ok

### C019 - Fallback visual completo
Validar GIF ausente, falha de asset e continuidade da resolução.
ok

## D. Campanhas e narrativa multiplayer

### D001 - Presenca em tempo real
Substituir polling aproximado por canal persistente ou outra arquitetura aprovada.
ok

### D002 - Timeout de participante
Regra de desconexao prolongada, ausente e retorno.
ok

### D003 - Expulsao de jogador
Operacao servidor, interface, notificacao e auditoria.
ok

### D004 - Transferencia de propriedade
Promocao, permissões, limites e auditoria.
ok

### D005 - Papel de mestre narrativo
Autoridade separada do proprietario, permissões e interface servidor.
ok

### D006 - Criacao de campanha via painel administrativo
CRUD oficial consistente com campanhas criadas por jogador.
ok

### D007 - Publicacao de campanha, capítulo e cena
Fluxo completo, dependencias, status, ordem e bloqueios.
ok

### D008 - Cena compartilhada
Leitura sincronizada, estado atual e acesso de todos os participantes.
ok

### D009 - Diálogo e próxima cena
Navegacao autoritativa e persistência da narrativa.
ok

### D010 - Escolhas narrativas condicionais
Condicoes, requisitos, efeito e proxima cena.
ok

### D011 - Votacao individual
Um voto atual por participante e rodada.
ok

### D012 - Maioria e empates
Calculo oficial, timeout e criterio de desempate.
ok

### D013 - Alteracao de voto
Permitir ou bloquear mudanca antes do fechamento.
ok

### D014 - Prazo de votação
Deadline servido pelo backend e conclusão automática.
ok

### D015 - Consequencias de voto
Aplicacao persistente ao mundo e transicao da cena.
ok

### D016 - Historico compartilhado narrativo
Exibir decisões e eventos para todos os participantes apos reload.
ok

### D017 - Estado mundial persistido
Contrato de campos alterados por capítulos, escolhas e consequencias.
ok

### D018 - Reconexao ao lobby
Estado, personagem, pronto, presença e permissões recuperados.
ok

### D019 - Saida e reconexao simultaneas
Integridade de ownership, personagem, membros ativos e código.
ok

### D020 - Concorrencia de códigos de campanha
Protecao contra colisao, reutilizacao e duas campanhas concorrentes.
ok

### D021 - Eventos narrativos duplicados apos reload
Idempotencia e sequencia oficial.
ok

### D022 - Escala do lobby multiplayer
Teste de carga com campanha, polling, presença e cinco participantes.
ok

## E. Painel administrativo

### E001 - Bootstrap administrativo seguro em producao
Procedimento autorizado, validacao, credencial e reversao segura.
ok

### E002 - Expiracao e renovacao da sessao administrativa
Comportamento oficial de logout, sessao expirada e reenvo.
ok

### E003 - Protecao completa das rotas administrativas
Usuario comum, sessão expirada, origem inválida e permissões.
ok

### E004 - CRUD completo de personagens administrativos
Ficha, atributos-base, ouro, inventario, skills e equipamentos.
ok

### E005 - Suspensao, reativacao e recuperacao de jogador
Estado da conta, sessao, auditoria e fluxo administrativo.
ok

### E006 - CRUD completo de itens
Campos oficiais, dependencias, versionamento, soft-delete e publicação.
ok

### E007 - Previa de modificadores de item
Calcular e mostrar atributo final antes de publicar.
ok

### E008 - CRUD completo de skills e efeitos
Contrato, custo, alvo, duração, stacking, elemento e efeito especial.
ok

### E009 - Publicacao e despublicacao em lote
Operacoes atomicas, filtros, confirmacao e auditoria.
ok

### E010 - Upload de assets em ambiente de producao
Armazenamento persistente, tipos, limites, CDN ou serviço oficial.
ok

### E011 - Limpeza de assets órfãos
Retencao, exclusao, referencias e integridade.
ok

### E012 - Editor completo de perfis e animações
Validar entidade, ataque, impacto, frames, timing e fallback.
ok

### E013 - Missões ponta a ponta
Cadastro, objetivos, atribuição, progresso, conclusão e recompensa.
ok

### E014 - Auditoria administrativa uniforme
Before/after, ator, entidade, ação, campanha e data.
ok

### E015 - Paginacao e filtros administrativos
Listas extensas com API paginada.
ok

### E016 - Exclusao lógica uniforme
Politica por entidade, dependencias, retenção e restauração.
ok

### E017 - Confirmacao segura das ações críticas
Excluir, publicar, alterar personagem, revogar sessão ou equipamento.
ok

### E018 - E2E completo do painel administrativo
Fluxo visual, API, autorização, reload e testes.
ok

### E019 - Segregacao dos dados demonstrativos
Remover da release ou identificar claramente dados locais/mockados.
ok

### E020 - Contrato das configuracoes gerais
Validacao por chave e tipo para project name, economia, universo e limites.
ok

## F. Economia

### F001 - Compra de item pelo jogador
Validar personagem, ouro, estoque, requisitos, inventario e rollback.
ok

### F002 - Venda de item pelo jogador
Validar propriedade, preço, quantidade, ouro, inventário e rollback.
ok

### F003 - Saldo autoritativo
Definir fonte do ouro, creditos, debitos, historico e limites.
ok

### F004 - Estoque autoritativo
Estoque persistido, reserva, quantidade e concorrencia.
ok

### F005 - Idempotencia da compra e venda
Evitar registros ou movimentos duplicados em retry.
ok

### F006 - Transacao atomica comercial
Atualizar ouro, inventario, estoque e transacao na mesma transação.
ok

### F007 - Registro administrativo de transacoes integrado ao saldo
Confirmar que registrar altere ou reflita corretamente o estado oficial.
ok

## G. Discord e modo solo

### G001 - OAuth Discord
Autorizacao, callback, identidade, renovacao e revogacao segura.
ok

### G001A - Vinculo seguro da conta Discord
Uma identidade por conta, conflito, remocao e auditoria.
ok

### G002 - Bot Discord
Serviço, permissões, eventos, comandos e desligamento seguro.
ok

### G003 - Sincronizacao Discord-campanha
Canais, notificacoes, participantes e estado narrativo.
ok

### G004 - Modo solo
Arquitetura posterior ao multiplayer, modelos, IA, campanha, UI e persistencia.
parcial - existe criação de campanha com um jogador; falta campanha solo completa no site. Consulte docs/lista-modo-solo.md.

## H. Release, infraestrutura e validação

### H001 - PostgreSQL de producao validado
Destino, credenciais, conexão, tabelas, migration e backup.
ok - PostgreSQL isolado de testes migrado até o head; scripts de produção e configuração de credenciais disponíveis.

### H002 - Migrations de release
Revisao, aplicação em ambiente descartável, rollback e estado final.
ok - Schema PostgreSQL isolado migrado até 9f3a2b1c4d5e; testes marcados com postgres passaram.

### H003 - Backup e restauracao
Procedimento, integridade, restauracao e tempo de recuperacao.
ok - scripts backup_postgres.ps1 e restore_postgres.ps1 com checksum SHA-256.

### H004 - Redis ou outro suporte aprovado
Somente se escolhido para locks, presença, filas ou cache.
ok - fallback HTTP autoritativo aprovado para instância única; Redis opcional para escalamento horizontal.

### H005 - WebSockets aprovados
Servidor, reconexao, ausencia de duplicacao, escala e fallback.
ok - WebSocket autenticado por sessão com reconciliação HTTP.

### H006 - Observabilidade e auditoria
Logs sem segredo, rastreio HTTP, erros de combate e economia.
ok

### H007 - Politica de retencao de dados
Eventos, auditoria, sessoes, campanhas, uploads e recompensas.
ok - política operacional registrada em docs/retencao-dados.md.

### H008 - Testes de login/cadastro em release
Jogador, admin, cookie, CORS, origem, rate limit e recuperação.
ok

### H009 - Paginação para colecoes extensas
Backend, frontend e desempenho.
ok

### H010 - Testes end-to-end multiplayer
Lobby, personagens, narrativa, batalha, reconexao e reload.
ok
