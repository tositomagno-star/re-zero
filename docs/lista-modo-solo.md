# Lista de pendencias do modo solo

O modo solo sera jogado dentro do site. Ele reutiliza as campanhas normais, personagens, narrativa, combate, inventario, economia, equipamentos, salvamento e interface existente, mas exige somente um jogador.

## 0. Classe de item "Carreira"

- [x] Criar a classe oficial de item chamada "Carreira". (categoria persistida pelos contratos existentes)
- [x] Permitir que itens da classe "Carreira" tenham origem exclusiva do modo solo.
- [x] Permitir que magias da classe "Carreira" tenham origem exclusiva do modo solo.
- [x] Permitir usar itens da classe "Carreira" em campanhas multiplayer.
- [x] Permitir usar magias da classe "Carreira" em campanhas multiplayer.
- [x] Permitir equipar item de "Carreira" apenas por personagem elegivel.
- [x] Permitir memorizar ou aprender magia de "Carreira" no personagem.
- [x] Impedir transferir item ou magia de "Carreira" para campanha multiplayer antes da elegibilidade ser validada.
- [x] Validar a origem solo dos itens e magias de "Carreira" no backend.
- [x] Validar compatibilidade entre personagem, campanha, item e magia.
- [x] Persistir no personagem que o item ou magia de "Carreira" foi obtido no modo solo.
- [x] Impedir criar recompensas de item ou magia de "Carreira" fora das regras configuradas.
- [x] Permitir o administrador cadastrar itens da classe "Carreira".
- [x] Permitir o administrador cadastrar magias da classe "Carreira".
- [x] Permitir definir recompensa, custo, requisitos e efeitos dos elementos "Carreira".
- [x] Permitir definir em qual modo solo o item ou magia pode ser obtido.
- [x] Permitir definir em quais campanhas multiplayer o elemento pode ser utilizado.
- [x] Impedir duplicacao do item ou magia de "Carreira" por requisicao repetida.
- [x] Mostrar a classe "Carreira" com identificacao visual distinta.
- [x] Mostrar que o item veio de uma campanha solo sem depender do frontend.
- [x] Incluir "Carreira" nos filtros do inventario e do cadastro administrativo.
- [x] Incluir "Carreira" nos filtros de compra, venda e recompensa.
- [x] Impedir o frontend enviar origem solo falsa ou manipular elegibilidade.
- [x] Registrar auditoria de obtencao, desbloqueio, equipagem e uso.
- [x] Testar item de "Carreira" obtido no solo e usado em campanha multiplayer.
- [x] Testar magia de "Carreira" obtida no solo e usada em campanha multiplayer.
- [x] Testar personagem sem elegibilidade tentando usar elemento "Carreira".

## A. Modelo e regras da campanha

- [x] Criar o campo oficial de modo da campanha: multiplayer ou solo.
- [x] Impedir caracteristicas multiplayer em campanhas solo, como convites, codigo de entrada e vagas adicionais.
- [x] Alterar os limites automaticamente para um jogador.
- [x] Criar a campanha solo ja com personagem do jogador.
- [x] Permitir iniciar, pausar, voltar e continuar uma campanha solo.
- [x] Impedir entrada de outros jogadores em uma campanha solo.
- [x] Ocultar controles de preparacao coletiva desnecessarios no lobby solo.
- [x] Mostrar claramente que a campanha esta no modo solo.
- [x] Registrar o modo solo nas campanhas, listas, detalhes e historico.
- [x] Criar migracao para campanhas existentes que tenham exatamente um jogador e configuracao solo.

## B. Criacao e lobby dentro do site

- [x] Adicionar opcao "Campanha solo" ao formulario de criacao.
- [x] Quando solo estiver ativo, ocultar ou fixar a quantidade maxima de jogadores em 1.
- [x] Remover requisito de pelo menos tres participantes no fluxo solo.
- [x] Permitir configurar personagem e iniciar diretamente.
- [x] Permitir criar nome, descricao e dificuldade da campanha solo.
- [x] Adicionar confirmacao para abandonar uma campanha solo.
- [x] Impedir exibicao de codigo de convite inutil em campanhas solo.
- [x] Ocultar botoes de votacao coletiva que nao fazem sentido no solo.
- [x] Adicionar uma tela inicial separada para "Continuar aventura solo".

## C. Personagem e progressao

- [x] Criar personagem solo durante a criacao da campanha.
- [x] Permitir editar o personagem antes do inicio.
- [x] Salvar ficha, nivel, atributos, ouro, itens, equipamentos e experiencia.
- [x] Recalcular atributos derivados ao entrar e apos cada equipar.
- [x] Permitir a morte e recuperacao do personagem dentro das regras oficiais.
- [x] Salvar checkpoints periodicos da aventura na cena persistida.
- [x] Permitir ate cinco personagens independentes por campanha solo, com selecao persistente.
- [x] Impedir perda de inventario ao sair e entrar novamente.
- [x] Garantir recompensas persistentes apos combate e cenas.
- [x] Restaurar estado correto apos reload ou reconexao.

## D. Narrativa e cenas

- [x] Tratar a narrativa solo como campanha oficial, sem votos multiplayer.
- [x] Selecionar diretamente a escolha do jogador quando a cena tiver opcoes.
- [x] Reutilizar os dados oficiais de capitulos, cenas, dialogos e consequencias.
- [x] Persistir a cena atual da campanha solo.
- [x] Persistir historico das escolhas realizadas.
- [x] Aplicar consequencias das escolhas ao personagem.
- [x] Permitir retomar exatamente a ultima cena persistida apos sair.
- [x] Impedir avancar duas vezes por controle do estado da requisicao.
- [x] Exibir texto de narrativa como acontece nas campanhas multiplayer.
- [x] Registrar falhas narrativas como eventos recuperaveis.

## E. Combate solo

- [x] Permitir iniciar combate contra inimigos com somente um personagem jogador.
- [x] Adaptar validacoes que exigem varios participantes.
- [x] Manter turnos, iniciativa, habilidades, equipamentos, efeitos e recompensas.
- [x] Permitir pausar o combate sem perder estado.
- [x] Permitir abandonar ou fugir conforme regras da missao.
- [x] Persistir combate a cada turno.
- [x] Permitir continuar combate apos reload.
- [x] Impedir dano ou movimento duplicado por requisicao repetida.
- [x] Aplicar recompensa de XP, ouro, itens e progresso somente uma vez.
- [x] Permitir inimigos e chefes oficiais por dificuldade.

## F. Dificuldade e ajuda

- [x] Definir configuracao de dificuldade da campanha solo.
- [x] Ajustar atributos dos inimigos pela dificuldade.
- [x] Ajustar quantidade de recompensas pela dificuldade.
- [x] Permitir tres niveis de dificuldade: normal, dificil e lendario.
- [x] Definir comportamento do modo seguranca ao morrer.
- [x] Permitir ativar dicas contextuais sem alterar a narrativa oficial.
- [x] Permitir reduzir ou aumentar dificuldade com confirmacao.
- [x] Persistir a dificuldade da campanha e suas regras no backend.
- [x] Impedir o frontend de enviar dificuldade sem validacao do backend.

## G. Missoes, capitulo e mundo

- [x] Permitir selecionar o mesmo mundo e capitulos usados no multiplayer.
- [x] Disponibilizar missoes solo oficialmente.
- [x] Atualizar objetivos apos combate, coleta, dialogo ou escolha.
- [x] Permitir progresso persistente de questlines.
- [x] Entregar recompensas ao concluir objetivo ou missao.
- [x] Impedir reentrega de recompensa ja concluida.
- [x] Permitir desbloquear novos capitulos por progresso.
- [x] Mostrar linha de progresso persistida da campanha.
- [x] Integrar NPCs, dialogos, eventos e encontros.
- [x] Permitir encerrar uma campanha solo concluida sem apagar o historico.

## H. Economia e equipamentos

- [x] Permitir comprar e vender no modo solo com saldo autoritativo.
- [x] Permitir abrir inventario no jogo solo.
- [x] Permitir equipar, desequipar e organizar equipamentos.
- [x] Persistir carga, slots, requisitos e efeitos.
- [x] Permitir usar consumiveis em combate e fora dele.
- [x] Impedir bonus duplicado apos reload.
- [x] Permitir recompensas de itens em encontros solo.
- [x] Integrar oficinas ou mercadores, quando forem publicados.
- [x] Restaurar equipamentos do personagem apos reconexao.

## I. Interface

- [x] Criar lista de campanhas solo na pagina principal.
- [x] Criar filtro para multiplayer e solo.
- [x] Mostrar status da ultima campanha solo salva nas listas oficiais.
- [x] Mostrar progresso salvo de cena e capitulo na tela da campanha.
- [x] Permitir continuar campanha solo com um clique na lista.
- [x] Criar indicador claro de modo solo na pagina da campanha.
- [x] Adaptar lobby solo para um jogador.
- [x] Adaptar mensagens que falam em participantes ou votos no solo.
- [x] Esconder membros, convites, pronto coletivo e codigo de sala no solo.
- [x] Garantir responsividade em celular, tablet e desktop.

## J. Backend e autoridade

- [x] Centralizar regras solo e multiplayer no backend.
- [x] Validar modo da campanha nos endpoints de entrada relevantes.
- [x] Impedir troca de multiplayer para solo apos jogadores entrarem.
- [x] Impedir adicionar participante em campanha solo.
- [x] Aplicar locks contra duas acoes simultaneas.
- [x] Garantir idempotencia das escolhas, combates e recompensas.
- [x] Atualizar eventos narrativos somente uma vez.
- [x] Validar todas as alteracoes pelo jogador proprietario da campanha.
- [x] Evitar estado compartilhado entre campanhas solo.
- [x] Registrar auditoria das acoes principais.

## K. Persistencia e recuperacao

- [x] Salvar estado narrativo apos cada escolha.
- [x] Salvar estado de combate apos cada turno.
- [x] Salvar estado de missao apos cada objetivo.
- [x] Criar checkpoint ao entrar em combate importante.
- [x] Criar checkpoint ao iniciar um novo capitulo.
- [x] Permitir restauracao apos erro do servidor.
- [x] Permitir limpar uma campanha solo encerrada sem alterar outras campanhas.
- [x] Manter backup da campanha e impedir corrupcao parcial.
- [x] Garantir funcionamento apos fechar e abrir o navegador.
- [x] Garantir funcionamento apos desconexao e reconexao.

## L. Discord

- [x] Nao exigir Discord para jogar ou criar campanha solo.
- [x] Manter Discord apenas como opcional e vinculado ao mesmo site.
- [x] Permitir notificacoes opcionais do sistema operacional para mudancas de status com o site aberto em segundo plano.
- [x] Impedir que Discord seja considerado o client principal do modo solo.

## M. IA narrador

- [x] Decidir pelo narrador humano assistido com IA desativavel.
- [x] Limitar IA a sugestoes narrativas, sem autorizar dano ou recompensa sem validacao.
- [x] Fazer o backend validar toda consequencia sugerida pela IA.
- [x] Impedir inventar regras, itens ou eventos nao publicados.
- [x] Persistir resposta narrativa gerada.
- [x] Adicionar limite de custo, timeout e fallback.
- [x] Permitir retry seguro sem duplicar efeitos.
- [x] Ocultar segredo ou credencial de IA do frontend.
- [x] Permitir desativar IA e usar conteudo oficial fixo.
- [x] Manter auditoria da origem de texto gerado.

## N. Testes e qualificacao

- [x] Criar campanha solo pelo site.
- [x] Iniciar campanha solo sem segundo jogador.
- [x] Executar uma cena narrativa solo.
- [x] Executar combate solo completo.
- [x] Desconectar, atualizar e continuar a partida.
- [x] Recarregar pagina durante combate.
- [x] Duplicar requisicao de combate e garantir idempotencia.
- [x] Validar recompensas de combate uma unica vez.
- [x] Validar compra, venda, inventario e equipamento.
- [x] Testar morte, recuperacao e dificuldade.
- [x] Testar campanha solo concluida.
- [x] Testar mobile com lobby solo.
- [x] Testar desktop com lobby solo.
- [x] Executar testes backend completos.
- [x] Executar testes frontend completos.
- [x] Executar build de producao.

### Validacao mais recente

- Backend completo com PostgreSQL local habilitado: 284 testes passaram, sem ignorados.
- Os testes PostgreSQL que antes eram ignorados foram executados com `TEST_DATABASE_URL` e passaram.
- Frontend: 60 testes passaram.

As 164 tarefas do escopo atual estao concluidas. Notificacoes do sistema exigem permissao do navegador e funcionam enquanto o site estiver aberto em segundo plano; notificacoes com o navegador fechado exigiriam um servico push/VAPID configurado no ambiente.
