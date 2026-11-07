# Checklist de lançamento — Crônicas do Reino

## A. Produto e decisão de escopo

- [ ] Confirmar se modo solo faz parte da versão 1.
- [ ] Confirmar quais dificuldades de boss serão anunciadas como validadas visualmente.
- [ ] Confirmar se economia comercial será publicada nesta versão.
- [ ] Confirmar se Discord/WebSocket serão publicados nesta versão.
- [ ] Remover da UI funcionalidades que não fizerem parte da versão publicada.

## B. Segurança e autenticação

- [ ] Validar login/cadastro em ambiente de release.
- [ ] Validar expiração, renovação e logout de sessão jogador.
- [ ] Validar cookie, CORS e origem em ambiente de release.
- [ ] Validar sessão administrativa separada.
- [ ] Confirmar que todas as rotas administrativas exigem admin no backend.
- [ ] Validar rate limit e mensagens sem exposição de segredo.
- [ ] Validar recuperação de usuário inativo/suspenso.

## C. Banco, migrations e integridade

- [ ] Confirmar PostgreSQL de produção e `DATABASE_URL` de destino.
- [ ] Executar revisão de migrations em ambiente descartável autorizado.
- [ ] Aplicar migrations somente por procedimento autorizado.
- [ ] Confirmar backup/restauração antes do release.
- [ ] Confirmar constraints de campanha, personagem, inventário e eventos.
- [ ] Confirmar que não existem migrations pendentes inesperadas.
- [ ] Confirmar idempotência de progressão, recompensas, drops e combate.
- [ ] Confirmar os campos JSON suportados oficialmente antes de anunciar efeito completo.

## D. Campanhas multiplayer

- [ ] Criar campanha com usuário de teste.
- [ ] Entrar por código em segunda/terceira sessão.
- [ ] Confirmar mínimo de 3 participantes ativos.
- [ ] Confirmar máximo de 5 participantes.
- [ ] Confirmar personagens únicos de cada participante.
- [ ] Confirmar owner, saída, presença e reentrada.
- [ ] Confirmar início, bloqueio de início incompleto e navegação pós-início.
- [ ] Confirmar narrativa e recuperação após reload.

## E. Personagens, inventário e progressão

- [ ] Validar criação de personagem.
- [ ] Validar XP, níveis, atributos e ponto de atributo.
- [ ] Validar HP/mana e limites.
- [ ] Validar ouro e recompensas.
- [ ] Validar inventário, quantidade e empilhamento.
- [ ] Validar equipar/desequipar e slots.
- [ ] Validar peso/carga e limites por slot.
- [ ] Validar requisitos de itens.
- [ ] Validar efeitos JSON de itens/habilidades em uso real.
- [ ] Definir o contrato mecanicamente suportado para efeitos, atributos e requisitos.
- [ ] Validar cooldown, custo de mana e alvo.
- [ ] Validar compra/venda, estoque, ouro, inventário e rollback ponta a ponta antes de publicar economia comercial.

## F. Combate

- [ ] Validar ação única por jogador.
- [ ] Validar duplo clique.
- [ ] Validar reload e resolução repetida.
- [ ] Validar dano, HP, mana e turnos.
- [ ] Validar interrupção visual sem mudança autoritativa.
- [ ] Validar boss COMUM.
- [ ] Obter e aprovar evidência visual do boss MÉDIO.
- [ ] Obter e aprovar evidência visual do boss DIFÍCIL.
- [ ] Validar boss HARD com dois ataques sequenciais.
- [ ] Validar GIF de personagem, GIF de ataque, delay e duração.
- [ ] Validar configurações administrativas visíveis.
- [ ] Validar resolução autoritativa em ambiente alvo.

## G. Admin

- [ ] Validar login administrativo.
- [ ] Validar CRUD de entidades.
- [ ] Validar editor de perfis de entidades.
- [ ] Validar GIF/dano/delay/duração de ataque.
- [ ] Validar dificuldade, máximo de ataques e interrupção de boss.
- [ ] Validar assets, animações, missões, drops e recompensas.
- [ ] Confirmar que usuários comuns não acessam endpoints administrativos.

## H. Assets, uploads e performance

- [ ] Validar tipos, tamanhos e limites de upload.
- [ ] Validar persistência dos arquivos.
- [ ] Validar associações com entidades.
- [ ] Validar tratamento de arquivo inválido.
- [ ] Medir carregamento de catálogos extensos.
- [ ] Confirmar necessidade de paginação.
- [ ] Validar GIFs problemáticos ou sem fallback.

## I. Observabilidade

- [ ] Confirmar `/health`.
- [ ] Confirmar logs sem segredo ou credencial.
- [ ] Confirmar rastreamento de erro HTTP.
- [ ] Confirmar auditoria das ações administrativas críticas.
- [ ] Confirmar monitoramento de combate e recompensas.
- [ ] Confirmar política de retenção de eventos.

## J. Aprovação final

- [ ] 250 testes backend aprovados e 13 ignorados registrados nesta auditoria em SQLite isolado.
- [ ] 60 testes frontend aprovados registrados nesta auditoria.
- [ ] Aviso `act(...)` de `combat-panel.test.tsx` investigado e corrigido ou formalmente aceito como não bloqueador.
- [ ] Página de login confirmada por DOM; demais fluxos críticos confirmados separadamente por navegador.
- [ ] Nenhum banco real foi usado nesta auditoria.
- [ ] Nenhuma campanha real foi usada nesta auditoria.
- [ ] Nenhuma conta real foi usada nesta auditoria.
- [ ] Nenhuma migration foi aplicada nesta auditoria.
- [ ] Nenhum dado, role, grant ou permissão foi alterado nesta auditoria.
- [ ] Status visual MÉDIO/DIFÍCIL registrado separadamente.
- [ ] Pendências não resolvidas estão documentadas.
