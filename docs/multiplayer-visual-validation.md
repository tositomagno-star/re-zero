# Etapa G — validação visual multiplayer

## Continuação narrativa de 2026-10-31

### Resultado atual

- A API visual respondeu `200 {"status":"ok"}` em `/health`.
- O frontend visual respondeu HTTP 200 na porta 8080.
- PostgreSQL, API visual e frontend permaneceram ativos; nenhum processo foi
  reiniciado ou encerrado.
- A conta `vg1` foi confirmada novamente como autenticável com o credencial
  sintético já existente, por clientes HTTP em
  `cronicas_do_reino_test`.
- O login administrativo exige uma senha administrativa com pelo menos 12
  caracteres. Não existe uma credencial administrativa sintética conhecida
  nesta execução, e nenhum `User` já existente nas contas conhecidas possui
  `is_admin=true`.
- A conta `vg1` não foi promovida, nenhuma senha foi alterada e nenhuma
  credencial real foi consultada ou alterada.

### Preparação narrativa

- Os contratos existentes continuam sendo respeitados:
  - capítulo via `ChapterWrite`;
  - cena via `SceneWrite`;
  - escolhas via `ChoiceWrite`.
- O endpoint `POST /api/admin/content/chapters` exige sessão administrativa.
- O conteúdo sintético não foi criado porque não há sessão administrativa
  sintética autenticável. A chamada não foi substituída por gravação direta em
  banco ou alteração de privilégios.
- O novo inventário confirmou que o schema visual continua sem capítulo,
  cena, escolha ou sessão narrativa criada nesta camada.
- Nenhum conteúdo narrativo real foi alterado.

### Fluxos visuais desta continuação

| Categoria | Resultado |
| --- | --- |
| Testes automatizados | Não executados novamente nesta continuação; os resultados aprovados anteriores permanecem registrados. |
| Testes de API | API visual saudável; login sintético de `vg1` confirmado. A criação de conteúdo permanece bloqueada pela ausência de uma sessão administrativa sintética. |
| Testes visuais reais | Não houve alteração do estado visual nesta continuação. O lobby de cinco da execução anterior permanece válido, mas não foi possível iniciar partida sem conteúdo publicado. |
| Partida com cinco jogadores | Pendente: nenhum capítulo ativo publicado ou cena inicial existe. |
| Votação, consequência e histórico | Pendente: dependem da partida iniciada. |
| Sexto jogador | `vg6` continua pendente após HTTP 429 anterior; não houve nova tentativa automática para contornar o rate limit. |
| Persistência após reinicialização real | Não validada. |

### Erros observados nesta continuação

- `POST /api/auth/admin/login` com a conta de jogador `vg1` e sua senha de seis
  dígitos foi rejeitado por HTTP 422 porque senhas administrativas exigem pelo
  menos 12 caracteres. Esse erro não indica um problema do fluxo administrativo
  nem foi tratado alterando credenciais.
- Nenhum novo erro de console ou HTTP foi observado na UI durante esta
  continuação, pois não foi possível avançar a partida sem autorização
  administrativa sintética.

### Dados sintéticos confirmados

- Campanha: `Validação Visual G`;
- ID da campanha: `e5961c42-585d-4a05-bfb2-7c316510e9b5`;
- código: `RZ-33191`;
- jogadores conhecidos: `vg1` a `vg5`;
- proprietário: `vg1`;
- personagens: `Personagem de vg1` a `Personagem de vg5`;
- conteúdo criado nesta continuação: nenhum.

### Autorizações necessárias

1. Disponibilizar uma conta administrativa sintética já existente ou autorizar
   separadamente a criação/promocão de uma conta exclusivamente de teste,
   sem alterar credenciais existentes.
2. Após a autorização administrativa, permitir a criação do capítulo publicado,
   da cena inicial e das escolhas sintéticas pelo endpoint administrativo.
3. Autorizar aguardar ou resolver controladamente o rate limit antes da nova
   tentativa de `vg6`.
4. Autorizar a interrupção e reinicialização específicas do processo Uvicorn da
   API visual para validar persistência.

## Continuação da execução de 2026-10-31

### Resultado da retomada

- A API visual, o frontend visual e PostgreSQL estavam ativos nas portas 8000,
  8080 e 5432, respectivamente. Nenhum processo foi reiniciado ou interrompido.
- `backend/app/visual_test_server.py` foi revisado novamente. A confirmação de
  banco local, schema visual, contagem de tabelas e ausência de operações
  destrutivas permaneceu válida.
- Foram utilizados exclusivamente o banco `cronicas_do_reino_test` e o schema
  `test_visual_g_eb8c40da20ae`.
- A campanha sintética `Validação Visual G`
  (`e5961c42-585d-4a05-bfb2-7c316510e9b5`, código `RZ-33191`) foi acessada
  novamente.
- A entrada das contas sintéticas `vg3`, `vg4` e `vg5` pela API retornou HTTP
  201 para cada jogador.
- Em contexto independente autenticado visualmente como `vg3`, o lobby exibiu
  corretamente:
  - contador `5 / 5`;
  - `0 vagas`;
  - mínimo de início de 3 jogadores;
  - `vg1` como proprietário, com personagem `Personagem de vg1`;
  - `vg2` e personagem `Personagem de vg2`;
  - `vg3` e personagem editável `Personagem de vg3`;
  - `vg4` e personagem `Personagem de vg4`;
  - `vg5` e personagem `Personagem de vg5`;
  - presença inicial `Conectado` para os participantes.

Em captura posterior da mesma página, a presença refletiu corretamente o estado
de heartbeat dos clientes: `vg1` e `vg3` apareciam como `Conectado`, enquanto
`vg2`, `vg4` e `vg5` apareciam como `Desconectado` por terem sido associados via
clientes HTTP sem páginas/browser heartbeats abertas naquele momento. Isso
valida a atualização visual de presença, mas não substitui o fluxo completo de
desconexão/reconexão com múltiplos navegadores reais.

### Cobertura efetiva desta retomada

| Item | Resultado nesta execução |
| --- | --- |
| Contextos independentes | Dois contextos independentes já confirmados na retomada anterior; um contexto adicional foi autenticado visualmente para `vg3`, chegando a pelo menos três contextos independentes nesta etapa. |
| Lobby com cinco jogadores | Passou visualmente, com 5/5 participantes e personagens individuais. |
| Personagens individuais | Passou: todos os personagens padrão apareciam associados aos respectivos usuários. |
| Presença conectada | Passou visualmente: os cinco participantes apareciam como conectados. |
| Atualização de presença | Não validada além da presença inicial; a sessão não permaneceu aberta pelo período necessário para observar os ciclos completos de desconexão/reconexão. |
| Desconexão/reconexão | Não concluída nesta retomada. |
| Votação e resultados | Não concluída; a partida não iniciou. |
| Consistência visual de partida | Não concluída; não há partida ativa. |
| Limite de seis jogadores | A tentativa ficou bloqueada por rate limit ao registrar `vg6`; não foi possível concluir uma tentativa válida de entrada do sexto usuário sem esperar ou obter outra conta sintética autorizada. |
| Partida com cinco jogadores | Bloqueada pela ausência de um capítulo ativo publicado com uma cena. A API de início respondeu HTTP 409 com essa condição. |
| Console e HTTP detalhados | Não foi possível confirmar console e códigos HTTP novos de todos os contextos; o ambiente integrado não expôs captura contínua de rede para esses fluxos nesta sessão. |
| Persistência após reinicialização real | Não validada; não houve autorização nem reinicialização do backend. |

### Erros conhecidos e limitações

- O início da campanha via proprietário respondeu HTTP 409:
  `Publique um capítulo ativo com ao menos uma cena antes de iniciar a campanha.`
- O frontend não iniciou porque essa dependência de conteúdo ainda não foi
  publicada.
- A tentativa de criação de `vg6` recebeu HTTP 429 por rate limit no cadastro.
  Nenhuma exclusão, reinicialização ou alteração de dados foi usada para
  contornar o limite.
- Não foram testados desconexão/reconexão, votação nem persistência após
  reinicialização real.

### Próxima autorização necessária

A Etapa G permanece não concluída. Ainda exigem decisão/autorização:

1. Publicar ou disponibilizar um capítulo ativo com cena no schema visual,
   permitindo iniciar uma partida de cinco.
2. Autorizar o intervalo necessário para contornar o rate limit ou registrar
   uma sexta conta sintética autorizada para validar o limite da sala.
3. Autorizar a realização de desconexão/reconexão por fechamento e abertura de
   contextos, sem parar serviços.
4. Autorizar a interrupção específica do processo Uvicorn da API visual, seu
   reinício pelo mesmo helper e a validação visual da persistência.

## Execução visual de 2026-10-31

### Resultado operacional

- O PostgreSQL permaneceu ativo e não foi reiniciado.
- O serviço visual em `127.0.0.1:8000` não estava ouvindo.
- O frontend em `127.0.0.1:8080` não estava ouvindo.
- Não houve autorização para iniciar novos processos; nenhum processo foi iniciado,
  encerrado ou reiniciado nesta execução.
- O navegador mantinha duas páginas já abertas da execução anterior. Não foi
  possível confirmar que elas utilizavam contextos/perfis independentes.
- Não foram criadas contas, campanhas, personagens ou votos nesta execução.

### Helper visual revisado

`backend/app/visual_test_server.py` foi confirmado como não destrutivo:

- rejeita bancos que não sejam `cronicas_do_reino_test`;
- exige um schema local no formato `test_visual_g_[0-9a-f]{12}`;
- verifica a presença das 38 tabelas esperadas no schema visual;
- não executa migrations, `DROP`, `TRUNCATE` ou `DELETE`;
- substitui apenas os objetos de conexão do processo da API e inicia Uvicorn na
  porta fixa 8000.

### Evidências visuais capturadas

- Foi aberta uma captura da página compartilhada do lobby com um participante,
  personagem próprio, presença conectada, código sintético `RZ-64892` e controle
  de iniciar campanha desabilitado.
- A tela permaneceu legível e coerente com o estado registrado da sala.
- Nenhum segundo contexto independente foi confirmado visualmente.

### Console e HTTP

- Foram observados vários erros esperados do fluxo anterior com HTTP 409 ao
  tentar iniciar uma campanha com menos de três jogadores.
- Após a indisponibilidade dos serviços, o console registrou repetidamente
  `net::ERR_CONNECTION_REFUSED` nas consultas da interface.
- A interface exibiu `Falha ao carregar dados`/`Failed to fetch` e informou que
  tentaria atualizar novamente.
- Não foi possível atribuir os erros aos endpoints exatos nem inspecionar
  requisições HTTP novas porque os serviços backend e frontend estavam
  indisponíveis durante esta execução.

### Cobertura efetiva

| Item | Resultado |
| --- | --- |
| Dois navegadores/contextos independentes | Não confirmado |
| Lobby com dois jogadores | Não testado |
| Partida com cinco jogadores | Não testado |
| Personagens individuais | Observação estática de um personagem; não testado multijogador |
| Presença e atualização | Não testado |
| Desconexão/reconexão | Não testado |
| Votação e resultados | Não testado |
| Consistência visual entre participantes | Não testado |
| Console e HTTP | Bloqueado pela conexão recusada |
| Persistência após reinicialização real | Pendente de autorização |

### Limitações e autorização pendente

Os critérios visuais multiplayer não podem ser validados com os serviços
indisponíveis. A Etapa G permanece não concluída até que seja autorizada a
execução adicional dos serviços já preparados, com pelo menos dois contextos
independentes, seguida da validação de lobby de dois, partida de cinco,
desconexão/reconexão, votação, console/requisições e consistência visual.

Também continua pendente autorização explícita para interromper somente o
processo Uvicorn iniciado para o teste, reiniciá-lo pelo mesmo helper e validar
a persistência visualmente. Isso não autoriza reiniciar PostgreSQL ou encerrar
processos por nome.

## Estado desta auditoria

Auditoria e preparação realizadas em 2026-10-30. O serviço PostgreSQL não foi
iniciado, parado ou reiniciado. Após autorização explícita, a API e o frontend
foram iniciados em processos novos para preparar a validação visual. Testes e
preparação gravaram apenas em schemas novos e isolados de
`cronicas_do_reino_test`:

- O serviço `postgresql-x64-18` está ativo e a porta 5432 aceita conexões.
- A configuração efetiva `DATABASE_URL` do projeto aponta para
  `cronicas_do_reino_dev`; a URL PostgreSQL local `TEST_DATABASE_URL` foi
  validada sem exibir credenciais e aponta para `cronicas_do_reino_test`.
  Os testes receberam somente `TEST_DATABASE_URL`; o banco de desenvolvimento
  não foi usado para gravações.
- Antes da suíte, havia 54 schemas `test_*`. Depois dela, havia 64. Os dez
  testes marcados `postgres` passaram e criaram schemas isolados preservados.
- O schema `public` do banco de teste não tem tabelas nem `alembic_version`.
  Nenhuma migração foi executada. Para permitir um teste visual sem reutilizar
  schemas antigos nem gravar no banco de desenvolvimento, foi criado o schema
  isolado `test_visual_g_eb8c40da20ae`, com 38 tabelas via
  `Base.metadata.create_all`. Depois disso, uma sessão de navegador já
  autenticada mostrou nesse schema um lobby com um participante; essa sessão
  não foi usada nem modificada nos testes a seguir.
- O teste de integração independente criou schemas novos e preservados:
  `test_visual_g_acca817f9b47` para uma primeira execução parcial e
  `test_visual_g_953442dd2b82` para a execução completa. A primeira falhou em
  uma asserção do próprio harness, que comparava o ID do proprietário com o
  objeto cliente; o harness também produziu erro ao tentar verificar um
  atributo privado do engine no encerramento. Os dados parciais (seis contas
  sintéticas, duas campanhas e sete participações) foram preservados, sem
  limpeza. A execução corrigida passou os cenários e preservou seis contas,
  duas campanhas, sete participações e uma sessão narrativa.
- A última conferência encontrou 67 schemas de teste. Os 54 schemas
  preexistentes foram preservados; nenhum schema foi apagado.
- Após a autorização para iniciar as aplicações, a API respondeu
  `200 {"status":"ok"}` em `/health`, e o frontend respondeu HTTP 200 em
  `/register`. A tela de cadastro foi aberta em uma página nova e vazia; nenhum
  formulário foi preenchido ou submetido. Os processos iniciados usam as
  portas 8000 e 8080.
- O frontend usa `http://127.0.0.1:8000` por padrão, envia credenciais com
  `credentials: "include"` e chama a API diretamente; não há proxy de API
  configurado no `vite.config.ts`.
- O CORS do backend permite `http://localhost:8080` e
  `http://127.0.0.1:8080`. Em desenvolvimento, os cookies são `HttpOnly`,
  `SameSite=Lax`, `Path=/` e `Secure=false`. A troca de cookies foi exercitada
  por clientes HTTP independentes contra a aplicação ASGI, mas não em dois
  navegadores reais. Para evitar diferenças de site entre `localhost` e
  `127.0.0.1`, use `127.0.0.1` nos dois endereços.
- O lobby atualiza a sala a cada 5 segundos e envia heartbeat a cada 15
  segundos; o backend considera a presença desconectada após 45 segundos. Os
  timers são limpos ao sair da página. Uma resposta que demore mais que o
  intervalo pode se sobrepor à próxima consulta; isso foi observado no código,
  não reproduzido em execução.
- Testes automatizados executados: backend 38/38 (inclui 10 testes PostgreSQL),
  frontend 10/10, TypeScript sem erros, build concluído, ESLint com 0 erros e
  7 avisos.
- Testes adicionais contra um schema PostgreSQL novo usando seis clientes HTTP
  com cookies independentes: lobby de dois jogadores, lobby de cinco,
  rejeição do sexto, isolamento de campanhas, autorização do proprietário,
  atualização individual de personagem, reentrada sem personagem duplicado,
  presença após mais de 45 segundos sem heartbeat, reconexão, votação 3–2 e
  resultado/histórico igual para os cinco participantes. Todos esses cenários
  passaram na execução completa. Não foram testes visuais em navegador.
- A página compartilhada do navegador já mostrava um lobby autenticado com
  um único participante. Ela não foi alterada. O uso de um segundo contexto
  Playwright foi bloqueado pelo isolamento de sessão de armazenamento da
  ferramenta; por isso, as sessões de teste com cookies independentes foram
  clientes HTTP ASGI, não navegadores. A captura existente também mostrou
  respostas 409 ao tentar iniciar com menos de três jogadores, comportamento
  esperado pelo servidor; não houve fluxo visual de duas contas.
- A persistência foi conferida após fechar os clientes HTTP e recriar o pool
  de conexões, com novo login e recuperação da mesma sessão narrativa,
  resultado e histórico. O processo do backend não foi reiniciado; persistência
  após reinicialização continua pendente.
- O helper `app.visual_test_server` passou na verificação de sintaxe e sua
  validação de banco/schema foi exercitada somente com consultas de leitura.
  Na primeira inicialização, foi detectado e corrigido um encerramento de
  conexão asyncpg entre event loops; somente o processo de backend iniciado
  nesta sessão foi substituído. Depois da correção, API e frontend responderam
  HTTP 200. A API e o frontend permanecem ativos; nenhum cadastro foi
  submetido pelos navegadores.
- No primeiro harness de integração, ocorreu ainda um aviso de encerramento
  asyncpg ao fechar o pool de teste fora do event loop original. A execução
  completa de cenários passou (exit code 0); esse aviso foi do cleanup do
  harness, não de uma requisição da aplicação. Nenhum banco, schema, tabela
  ou registro foi apagado.

## Pré-condições de segurança

1. Para execuções futuras, obtenha autorização antes de criar contas,
   campanhas, personagens, votos ou outros registros.
2. Use somente uma base isolada, previamente autorizada e preparada para a
   aplicação. **Não use `cronicas_do_reino_dev`** para esta validação.
3. `TEST_DATABASE_URL` é consumida pela fixture de testes; ela não troca
   automaticamente o banco usado pelo servidor FastAPI. O schema público da
   base de teste está vazio. Use somente o helper `app.visual_test_server`,
   que exige o banco local de teste e o schema `test_visual_g_eb8c40da20ae`,
   seleciona esse schema no `search_path` e verifica as 38 tabelas antes de
   iniciar a API. Não use `uvicorn app.main:app` diretamente para este teste.
4. O serviço PostgreSQL já está ativo. Não o reinicie. Se estiver parado em
   uma execução futura, solicite autorização antes de iniciar ou reiniciar
   serviços do Windows.
5. Os testes PostgreSQL automatizados criam schemas `test_<uuid>` e os
   preservam. Não remova nem reutilize os 54 schemas já preservados; cada
   execução pode acrescentar outro schema.
6. Use contas e conteúdo sintéticos, exclusivos do teste. Não registre nem
   compartilhe senhas, cookies ou tokens.

## Preparar os servidores

A autorização para testes sintéticos na base de teste foi concedida. O helper
visual só inicia a API se `DATABASE_URL` apontar para
`cronicas_do_reino_test` local e `VISUAL_TEST_SCHEMA` identificar o schema
visual. O helper não executa migrações.

1. Confirme o PostgreSQL sem reiniciá-lo:

   ```powershell
   Get-Service -Name postgresql-x64-18
   Test-NetConnection 127.0.0.1 -Port 5432
   ```

2. O backend desta sessão já foi iniciado com autorização explícita. Para uma
   execução futura, confirme que não há usuários ou partidas reais dependendo
   do processo. Em um terminal PowerShell, carregue a URL de teste já
   configurada sem imprimi-la e execute o helper:

   ```powershell
   Set-Location C:\Users\Pichau\Downloads\site-rpg\backend
   $testLine = Get-Content .env | Where-Object { $_ -match '^TEST_DATABASE_URL=' } | Select-Object -First 1
   if (-not $testLine) { throw 'TEST_DATABASE_URL não encontrada.' }
   $env:DATABASE_URL = $testLine.Substring('TEST_DATABASE_URL='.Length).Trim().Trim('"').Trim("'")
   $env:VISUAL_TEST_SCHEMA = 'test_visual_g_eb8c40da20ae'
   .\.venv\Scripts\python.exe -m app.visual_test_server
   ```

   Esse comando inicia somente a API na porta 8000 e seleciona o schema
   visual; não inicia nem reinicia PostgreSQL. Não copie nem mostre a URL
   completa. Confirme `http://127.0.0.1:8000/health` e espere
   `{"status":"ok"}`. Se não responder, não cadastre contas.

3. O frontend desta sessão já foi iniciado com autorização explícita. Para
   uma execução futura, em outro terminal PowerShell:

   ```powershell
   Set-Location C:\Users\Pichau\Downloads\site-rpg
   $env:VITE_API_URL = 'http://127.0.0.1:8000'
   npm.cmd run dev -- --host 127.0.0.1 --port 8080 --strictPort
   ```

   Esse comando inicia somente o servidor de desenvolvimento frontend na
   porta 8080; não encerra processos existentes.

4. Use `http://127.0.0.1:8080`. Não misture `localhost` e `127.0.0.1` durante
   a sessão. Abra as ferramentas do navegador e observe erros de rede/console,
   sem copiar cookies, tokens ou conteúdo sensível.

## Teste visual com dois jogadores

Use dois perfis de navegador independentes, por exemplo, um perfil normal e
uma janela privada. Não use duas abas do mesmo perfil: elas compartilham o
cookie.

1. No perfil A, crie uma conta sintética e entre. No perfil B, crie uma conta
   sintética diferente e entre.
2. No A, crie uma campanha com limite de cinco participantes e anote o código
   `RZ-#####` somente para compartilhar com o B.
3. No B, entre pelo código. Confirme em ambos os navegadores que o título,
   código, proprietário, participantes e limite correspondem à mesma sala.
4. Altere o nome do personagem em cada sessão. Confirme que cada pessoa vê o
   nome próprio e o nome atualizado do outro, sem poder editar o personagem
   alheio.
5. Marque preparação e confirme que a atualização aparece na outra sessão.
6. Com dois participantes, confirme que a tentativa de iniciar é bloqueada
   pela regra atual: o mínimo é três jogadores. Adicione um terceiro jogador
   sintético para testar início, cena narrativa e votação.
7. Com pelo menos três participantes e personagens associados, inicie como
   proprietário. Confirme que apenas o proprietário pode iniciar e que os
   participantes veem a mesma cena, escolhas, contagem/resultado da votação e
   histórico.
8. Registre o resultado em cada navegador, sem incluir credenciais no
   relatório. Se o servidor ou a rede falhar, registre a mensagem apresentada
   e confirme se o lobby tenta atualizar novamente.

## Teste com cinco participantes e limite

1. Use cinco perfis independentes: um proprietário e quatro jogadores
   sintéticos. Mantenha todos na mesma origem e backend.
2. Faça os quatro jogadores entrarem pelo mesmo código. Confirme cinco
   participantes, cinco personagens distintos e o mesmo proprietário em cada
   sessão.
3. Consulte o lobby em cada sessão e confirme os mesmos participantes e
   personagens.
4. Use uma sexta conta sintética para tentar entrar. A API deve recusar a
   entrada por sala cheia; confirme que os cinco participantes e a propriedade
   não mudaram.
5. Como cada conta, tente alterar somente o próprio personagem. Confirme que
   não é possível alterar o personagem de outro participante.
6. Como não proprietário, confirme que iniciar não é permitido. Não contorne
   a interface nem envie requisições manuais para forçar uma operação.

## Desconexão e reconexão

1. Mantenha pelo menos dois jogadores conectados e o lobby aberto.
2. Feche completamente a janela/perfil de um jogador, sem usar o botão de
   sair da campanha. Isso interrompe o heartbeat sem marcar a participação
   como saída.
3. Aguarde pelo menos 60 segundos. O outro jogador deve ver a presença como
   desconectada após o timeout de 45 segundos e a atualização seguinte do
   lobby.
4. Reabra o perfil e entre com a mesma conta. A campanha deve continuar em
   `/play`; abra-a novamente e confirme que o mesmo personagem e participação
   foram recuperados sem duplicação.
5. Se a campanha já estiver ativa, confirme que cena, votação, resultado e
   histórico permanecem os mesmos para todos.
6. Registre tempos observados e mensagens de erro. Não altere o timeout do
   heartbeat durante o teste.

## Persistência após reiniciar o backend

Este procedimento ainda **não foi executado** e exige autorização explícita.
Não reinicie o serviço PostgreSQL.

1. Confirme que a API está conectada à base isolada autorizada e que a
   campanha usa exclusivamente dados sintéticos.
2. Verifique com os jogadores que não há sessões reais ou partidas em uso.
   Se houver qualquer dúvida, pare e aguarde autorização.
3. Registre identificadores não sensíveis da campanha e o estado esperado:
   participantes, nomes dos personagens, capítulo/cena, votos e histórico.
4. Com autorização, interrompa somente o processo Uvicorn iniciado para o
   teste (`Ctrl+C` no terminal dele). Não encerre processos por nome nem
   reinicie serviços do Windows.
5. Inicie novamente o mesmo comando do backend, sem migrations, e aguarde o
   health check.
6. Faça login nas mesmas contas de teste e abra a campanha. Compare todos os
   itens registrados no passo 3. Não declare persistência confirmada sem essa
   comparação visual.

## Erros comuns

- **Health check indisponível:** confirme que o backend está ouvindo na porta
  8000 e que a base isolada configurada está acessível.
- **Erro de rede/CORS ou sessão retorna 401:** use o mesmo host
  `127.0.0.1` nas URLs do frontend e da API; confirme `VITE_API_URL`, `FRONTEND_ORIGINS`
  e que a API foi iniciada com a configuração esperada. Não copie cookies.
- **Porta ocupada:** não encerre processos desconhecidos. Escolha uma porta
  após identificar o processo e atualize `VITE_API_URL` e `FRONTEND_ORIGINS`
  de forma consistente, com autorização.
- **Campanha não inicia:** a regra exige no mínimo três participantes ativos,
  personagens associados e uma cena inicial publicada com escolhas.
- **Sala cheia:** a campanha admite no máximo cinco participantes; conte o
  proprietário nesse limite.
- **Presença não muda:** mantenha outro lobby aberto e aguarde mais que o
  timeout de 45 segundos mais um ciclo de polling. A presença não foi validada
  visualmente nesta auditoria.
- **Mensagem de conexão no lobby:** a interface mostra erro e informa que
  tentará atualizar novamente; confirme a recuperação após a API voltar.

## Verificações automatizadas e pendentes

Automatizados nesta etapa: `python -m pytest` com os dez testes PostgreSQL
marcados habilitados (38 passaram), `npm.cmd test` (10 passaram),
`tsc --noEmit` (passou), `npm.cmd run build` (passou) e `npm.cmd run lint`
(0 erros, 7 avisos). O primeiro `npm test` foi bloqueado pela política de
execução do PowerShell; o mesmo teste passou pelo `npm.cmd`.

Também passou um cenário de integração ASGI contra PostgreSQL com cinco
participantes e clientes de cookie independentes, incluindo limite, acesso,
personagens, reentrada, heartbeat, reconexão, votação e isolamento entre
campanhas. A validação foi de API, não de interface visual em navegadores.

`alembic check` foi executado com `DATABASE_URL` apontando explicitamente para
`cronicas_do_reino_test` e terminou com erro `Target database is not up to
date`: o schema público desse banco não tem revisão Alembic. O comando não
aplicou migrations. O schema visual usa o metadata ORM diretamente, sem
revisão Alembic. Não execute migrations ou downgrades para esta etapa.

Continuam pendentes a validação em dois ou mais navegadores reais, o console
durante um fluxo visual completo e a persistência após reiniciar o processo do
backend. A presença e a reconexão passaram apenas no cenário de integração
ASGI. Os servidores permanecem iniciados para permitir a validação manual;
nenhum comando de encerramento foi executado. Não declare a Etapa G concluída
até realizar essas verificações visuais e obter um schema de teste com revisão
Alembic existente para que `alembic check` possa ser avaliado sem executar
migrations nesta etapa.

## Retomada de 31 de outubro de 2026

### Verificações realizadas

- A API visual respondeu `200 {"status":"ok"}` em `/health` na porta 8000.
- O frontend visual respondeu HTTP 200 na porta 8080.
- PostgreSQL permaneceu ativo na porta 5432.
- Nenhum processo foi reiniciado, encerrado ou interrompido nesta retomada.
- Foram revisados novamente `visual_test_server.py`, `ChapterWrite`,
  `SceneWrite`, `ChoiceWrite` e os vínculos exigidos pelo conteúdo narrativo.
- Nenhuma operação destrutiva, migration, alteração de credencial ou alteração
  de conteúdo real foi realizada.
- Nenhum dado narrativo sintético foi criado nesta retomada.

### Bloqueio administrativo

- O fluxo administrativo exige sessão com usuário `is_admin=true`.
- A conta de jogador `vg1` usa senha de seis dígitos e foi rejeitada no login
  administrativo por HTTP 422, pois a senha administrativa exige pelo menos 12
  caracteres.
- Não existe credencial administrativa sintética conhecida nesta execução.
- Não foi criada nem promovida uma conta e nenhuma senha existente foi
  alterada.
- Consequentemente, não foi possível chamar
  `POST /api/admin/content/chapters` nem criar capítulo, cena ou escolhas.

### Cobertura visual e de API desta retomada

| Categoria | Resultado |
| --- | --- |
| Contextos independentes ativos e saudáveis | API e frontend validados; nenhum novo contexto visual foi iniciado nesta retomada. |
| Lobby com cinco participantes | Resultado aprovado em retomadas anteriores. |
| Personagens individuais | Resultado aprovado em retomadas anteriores. |
| Partida com cinco jogadores | Bloqueada pela ausência de capítulo ativo publicado com cena. |
| Cena compartilhada | Pendente. |
| Votação individual e maioria | Pendente. |
| Consequência e novo cenário | Pendente. |
| Histórico para todos | Pendente. |
| Desconexão/reconexão visual | Pendente de validação em páginas reais simultâneas. |
| Sexto jogador | Pendente após HTTP 429 de cadastro da retomada anterior. |
| Console e requisições HTTP | Nenhum novo fluxo visual foi iniciado nesta retomada, portanto não houve novas evidências de console/rede. |
| Persistência pós-reinicialização | Não validada. |

### Erros conhecidos

- Login administrativo com a senha de jogador de `vg1`: HTTP 422 por tamanho
  mínimo de senha administrativa.
- Início da partida em execução anterior: HTTP 409 porque não havia capítulo
  ativo publicado com cena.
- Cadastro de `vg6` em execução anterior: HTTP 429 por rate limit, sem novas
  tentativas nesta retomada.

### Dados sintéticos desta retomada

- Nenhum novo dado foi criado.
- Dados sintéticos anteriores preservados:
  campanha `Validação Visual G`;
  ID `e5961c42-585d-4a05-bfb2-7c316510e9b5`;
  código `RZ-33191`;
  proprietário `vg1`;
  participantes `vg1` a `vg5`.

### Autorizações pendentes

1. Autorizar o início separado da API visual na porta 8000, já configurada para
   o schema visual autorizado, para validar o login administrativo, preparar o
   conteúdo sintético e executar os testes HTTP.
2. Autorizar o início separado do frontend visual na porta 8080 e a abertura
   dos contextos de navegador necessários.
3. Autorizar o tratamento controlado de rate limit ou fornecer uma conta
   sintética independente para testar o limite do sexto participante.
4. Autorizar a reinicialização específica somente da API visual para validar
   persistência real.

### Estado administrativo da retomada atual

- O procedimento oficial `python -m app.cli create-admin` foi confirmado.
- A conta sintética `vg_admin_g` foi criada exclusivamente pelo mecanismo
  oficial do CLI, com suporte seguro ao schema visual autorizado.
- `cronicas_do_reino_test`, `test_visual_g_eb8c40da20ae`, status ativo,
  privilégio administrativo e hash de senha válido foram confirmados por
  leitura isolada do schema visual.
- Nenhuma conta existente foi promovida ou teve credenciais alteradas.
- A porta 5432 continuou ativa; 8000 e 8080 não estavam ouvindo nesta
  conferência.
- A senha administrativa não foi registrada neste documento nem no repositório.
- Login HTTP administrativo, criação do conteúdo narrativo e testes visuais
  permanecem bloqueados enquanto os serviços visualmente solicitados estiverem
  desligados, sem autorização separada para iniciá-los.

A Etapa G permanece não concluída. Esta retomada não validou conteúdo narrativo
sintético, partida multiplayer completa, votos, consequência narrativa,
histórico consistente, reconexão visual em todos os participantes, limite do
sexto jogador ou persistência após reinicialização real.

## Conferência atual de 2026-10-31

- Foram confirmados novamente os ouvintes do ambiente visual: PostgreSQL na
  porta 5432 (processo 4952) e frontend na porta 8080 (processo 4328).
- Nenhum serviço estava ouvindo na porta 8000 antes da nova tentativa.
- A tentativa autorizada nesta retomada de executar
  `backend/app/visual_test_server.py` com `DATABASE_URL` apontando somente para
  `cronicas_do_reino_test` falhou antes de abrir a porta 8000.
- O ambiente ativo continuou usando o Python 3.14 do `.venv`. A falha foi
  `asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the
  middle of operation`, com `WinError 64`, na conexão com PostgreSQL.
- Isso reproduz o bloqueio técnico anterior da API visual; não foi possível
  concluir login HTTP, criar conteúdo narrativo ou executar partida visual
  nesta retomada.
- O procedimento oficial de administrador continua confirmado pelo comando
  protegido `python -m app.cli create-admin`. `vg_admin_g` permanece registrada
  como conta sintética ativa e administrativa exclusivamente no schema visual
  autorizado, sem promoção de contas existentes.
- Nenhum processo foi iniciado, reiniciado, encerrado ou substituído. Nenhuma
  credencial foi alterada. Nenhum conteúdo narrativo foi criado ou alterado.
- Nenhuma operação de banco além das leituras de conferência foi executada
  nesta retomada. Não houve DROP, TRUNCATE, DELETE em massa, migration ou
  limpeza automática.

### Resultado desta conferência

| Categoria | Resultado |
| --- | --- |
| Banco e schema exigidos | Configurados; PostgreSQL 5432 ativo. |
| Administrador sintético oficial | Existente: `vg_admin_g`; login HTTP não executado. |
| API visual | Não disponível na porta 8000; bloqueada por desconexão asyncpg. |
| Frontend visual | Ativo na porta 8080. |
| Conteúdo narrativo sintético | Não criado; dependente da API/admin autenticável. |
| Partida com cinco jogadores | Não executada nesta retomada. |
| Votação, consequência e histórico | Pendentes. |
| Sexto jogador | Pendente; 429 anterior não foi contornado. |
| Persistência pós-reinicialização | Não autorizada e não executada. |

### Validação visual real desta conferência

- Contextos independentes utilizados: 1 contexto real do navegador integrado,
  destinado à conferência da interface.
- O frontend em `http://127.0.0.1:8080` respondeu HTTP 200 e a página inicial
  carregou normalmente.
- A rota `/admin/login` carregou o formulário administrativo no navegador, sem
  enviar credenciais nem realizar login.
- Não houve autenticação ou partida visual nesta retomada.
- Captura persistida:
  `docs/evidencias/etapa-g-admin-login.png`.
- `http://127.0.0.1:8000/health` permaneceu indisponível. Não foi possível
  verificar console de erros da aplicação nem respostas HTTP do backend.

### Autorizações necessárias antes da próxima retomada

1. Autorizar separadamente o diagnóstico ou uso de um runtime Python compatível
   com esta conexão PostgreSQL/asyncpg, caso a troca esteja fora do ambiente
   já configurado.
2. Autorizar o início da API visual por
   `python -m app.visual_test_server`, mantendo somente
   `cronicas_do_reino_test` e `VISUAL_TEST_SCHEMA=test_visual_g_eb8c40da20ae`.
3. Autorizar o uso da senha já configurada para `vg_admin_g` no fluxo oficial de
   login administrativo, sem registrar a credencial neste documento.
4. Autorizar a criação do capítulo, cena e escolhas sintéticas pelos endpoints
   oficiais do Painel do Mestre.
5. Autorizar um novo contexto controlado para diferenciar limite de
   participantes de rate limit de cadastro.
6. Autorizar especificamente a reinicialização da API visual para verificar
   persistência real.

## Diagnóstico controlado de 2026-10-31 — API visual

### Resultado do diagnóstico

- A API visual não estava disponível na porta 8000.
- PostgreSQL estava disponível na porta 5432 pelo processo PostgreSQL
  identificado nesta conferência.
- O frontend deixou de estar disponível na porta 8080 nesta conferência.
- Nenhum processo foi iniciado ou encerrado durante o diagnóstico.
- Nenhuma alteração de banco, aplicação, dependência ou credencial foi feita.
- Nenhuma operação de escrita foi executada no banco.

### Ambiente e dependências observados

- Interpretador efetivo do ambiente `backend/.venv`: Python 3.14.7.
- FastAPI efetivo observado anteriormente: 0.162.0.
- SQLAlchemy efetivo observado anteriormente: 2.1.6.
- asyncpg efetivo observado anteriormente: 0.32.0.
- Uvicorn efetivo observado anteriormente: 0.54.0.
- O projeto declara suporte mínimo de Python 3.11 e não apresentou evidência
  reproducível de incompatibilidade específica com Python 3.14 nesta etapa.

### Conexão comprovada

O helper visual foi reproduzido em isolamento com o mesmo interpretador do
backend e o mesmo esquema configurado. A conexão de leitura confirmou:

| Propriedade | Resultado |
| --- | --- |
| Driver | `postgresql+asyncpg` |
| Banco atual | `cronicas_do_reino_test` |
| Schema efetivo | `test_visual_g_eb8c40da20ae` |
| Tabelas no schema visual | 38 |
| Tabelas esperadas por `Base.metadata` | 38 |
| Verificação de pré-inicialização do servidor visual | Aprovada |
| Descarte dos engines recreados | Concluído sem desconexão |

O banco atual, schema atual, configuração de `search_path` e quantidade de
tabelas foram validados por consultas somente leitura. Não foi comprovada
qualquer conexão ao banco de desenvolvimento nesta execução.

### Falha anterior

A última falha registrada foi uma desconexão `asyncpg` durante a tentativa de
inicialização, mas não foi acompanhado um log local completo da API atual. A
mesma conexão foi novamente bem-sucedida neste diagnóstico com o mesmo
interpretador e com o engine configurado pelo helper visual. Portanto:

- A causa não foi comprovada como incompatibilidade Python 3.14.
- Não foi comprovado que asyncpg, SQLAlchemy ou FastAPI sejam incompatíveis.
- Não há evidência de que a URL efetiva aponto para outro banco.
- Não há evidência, nesta execução, de problema persistente de schema ou de
  tabela esperada.
- A falha anterior deve ser tratada como indisponibilidade não reproduzida
  nesta conferência até que um novo log completo da inicialização esteja
  disponível.

### O que não foi executado

Nesta execução, deliberadamente não foram:

- iniciados serviços ou processos adicionais;
- executadas login administrativo, criação narrativa ou testes multiplayer;
- enviados dados ao frontend;
- reiniciados PostgreSQL ou frontend;
- realizadas reinicializações de backend;
- alteradas dependências ou configurações sensíveis;
- executadas migrações, DROP, TRUNCATE ou limpeza de dados.

### Estado final de portas

- `5432`: ativo, PostgreSQL (PID 2728 nesta conferência).
- `8000`: livre.
- `8080`: livre.

### Próxima autorização necessária

É necessária autorização separada para iniciar somente a API visual isolada,
confirmar `/health`, banco e schema efetivos e aguardar nova autorização antes
de login, conteúdo narrativo ou testes multiplayer. Login, criação de conteúdo
e testes visuais não foram executados nesta etapa conforme determinação.

## Inicialização autorizada da API visual — 2026-10-31

### Execução realizada

- A porta `8000` foi confirmada livre antes da inicialização.
- O servidor visual foi iniciado com o ambiente `backend/.venv` por:
  `backend/.venv/Scripts/python.exe -m app.visual_test_server`
- Foram exportados ao processo somente:
  - `DATABASE_URL` derivada da URL de teste;
  - `VISUAL_TEST_SCHEMA=test_visual_g_eb8c40da20ae`.
- Nenhuma credencial, URL completa ou token foi registrada no relatório.
- PostgreSQL e frontend não foram reiniciados, interrompidos ou modificados.

### Processo e saúde

- Processo ativo da API visual: PID `14160`.
- Processo Python responsável: executável registrado em
  `backend/.venv`/launcher Python 3.14 no Windows.
- Porta: `127.0.0.1:8000`.
- Estado de inicialização: Uvicorn iniciou e alcançou a aplicação.
- `GET http://127.0.0.1:8000/health`: HTTP `200`;
  corpo `{"status":"ok"}`.
- A API permaneceu ativa após o health check.

### Banco e schema efetivos

- Inicialização confirmada pelo próprio `visual_test_server.py`: ele rejeitaria
  a execução se `DATABASE_URL` não apontasse para o banco local
  `cronicas_do_reino_test`, se o schema não fosse selecionado corretamente ou
  se a contagem de tabelas não correspondesse aos metadados.
- Uma consulta separada de somente leitura, pelo mesmo ambiente Python e pela
  mesma URL de teste, confirmou:
  - banco: `cronicas_do_reino_test`;
  - schema: `test_visual_g_eb8c40da20ae`.
- Nenhum acesso ao banco de desenvolvimento foi confirmado em nenhuma consulta
  desta inicialização.

### Erros

- Nenhum erro ocorreu durante esta inicialização ou durante o health check.
- Uma inspeção inicial separada carregou acidentalmente
  `cronicas_do_reino_dev/public`, por não ter exportado `DATABASE_URL` nesse
  processo de verificação. Essa conexão foi rejeitada pelo teste local, não
  modificou dados e não é representativa da API visual. A verificação seguinte
  foi repetida com a URL de teste explícita e confirmou o destino autorizado.

### Limites desta execução

Não foram realizados nesta execução:

- login administrativo ou de jogadores;
- criação ou alteração de capítulos, cenas ou escolhas;
- testes multiplayer, votação ou presença;
- criação ou alteração de dados;
- reinicialização ou parada de PostgreSQL, frontend ou backend;
- migrações Alembic;
- testes de persistência após reinicialização;
- alteração de dependências ou do Python global.

### Próxima autorização necessária

É necessária uma autorização separada para autenticação administrativa,
preparação narrativa, acesso dos cinco jogadores, votação, reconexão e demais
testes visuais. A Etapa G permanece aberta; o backend visual foi inicializado,
mas persistência após reinicialização real continua pendente de autorização
específica.

## Inicialização autorizada do frontend — 2026-10-31

### Execução realizada

- Antes da inicialização, a porta `8080` foi confirmada livre.
- O projeto declara em `package.json`:
  `npm run dev`, que executa `vite dev`.
- O frontend foi iniciado com as dependências já instaladas por:
  `npm.cmd run dev -- --host 127.0.0.1 --port 8080 --strictPort`
- A configuração do frontend continua apontando para
  `http://127.0.0.1:8000`.

### Processo e saúde

- Processo ativo do frontend: PID `9112`.
- Porta: `127.0.0.1:8080`.
- Vite informou que estava pronto e disponível em
  `http://127.0.0.1:8080/`.
- `GET http://127.0.0.1:8080/`: HTTP `200`.
- `GET http://127.0.0.1:8000/health`: HTTP `200`;
  corpo `{"status":"ok"}`.
- A API visual permaneceu ativa no processo PID `14160`.

### Limites desta execução

Não foram realizados nesta execução:

- login, preenchimento de formulários ou envio de ações pela interface;
- criação ou alteração de dados;
- testes multiplayer ou visuais de jogadores;
- alterações de configuração ou instalação de dependências;
- reinicialização ou parada da API, PostgreSQL ou frontend.

As próximas fases continuam pendentes de autorizações separadas. A Etapa G
permanece aberta, inclusive para persistência após reinicialização real do
backend visual.

## Encerramento da Etapa G e preparação da Etapa H — 2026-10-31

Este registro consolida as validações feitas ao longo da Etapa G e diferencia
essas evidências das verificações finais realizadas após a correção do polling.
O trabalho de encerramento foi somente documental: não houve acesso a banco,
alteração de conteúdo, migração ou implementação da Etapa H.

### Resultado consolidado da Etapa G

| Fluxo ou verificação | Quando | Resultado |
| --- | --- | --- |
| Login administrativo sintético, abertura do Painel do Mestre e leitura das rotas protegidas de capítulos | Validação visual anterior | Login e painel funcionaram; a leitura de capítulos foi confirmada. O capítulo e a cena inicial publicados estavam disponíveis. |
| Início de campanha com conteúdo publicado | Validação visual anterior | Iniciado com cena inicial válida; o antigo HTTP 409 por ausência de cena publicada não se reproduziu. |
| Votação com três participantes | Validação visual anterior | Resultado 2–1; uma decisão foi registrada e a narrativa avançou. |
| Votação com quatro participantes | Validação visual anterior | Empate 2–2; o estado permaneceu empatado, sem avanço da cena, com um evento de empate. |
| Votação com cinco participantes | Validação visual anterior | Resultado 3–2; uma decisão foi registrada e a narrativa avançou. |
| Persistência no banco de teste | Validação visual anterior | Votos, decisões, empate e cena resultante foram confirmados no schema de teste. |
| Recuperação após recarregar a sessão de cinco participantes | Validação visual após a correção final | A tela recuperou a campanha 5/5, a decisão anterior, a rodada seguinte e o histórico; não ficou em “Carregando sala...”. A presença respondeu HTTP 204. |
| Empate de quatro participantes após reload | Não validado novamente na execução final | O estado de empate foi confirmado por inspeção visual passiva, mas não houve novo reload conclusivo dessa sessão. |
| Captura dos outros alvos de navegador | Limitação da validação final | A automação de captura falhou em dois alvos; a falha da ferramenta não foi tratada como falha funcional do aplicativo. |

O conteúdo sintético publicado usado nas partidas permaneceu no banco de teste.
A publicação e a leitura administrativa ocorreram durante as validações visuais
anteriores; não houve nova publicação ou edição no encerramento.

### Correção do polling

Uma requisição de campanha atrasada em aproximadamente 7,2 segundos reproduziu
três atualizações simultâneas antes da proteção. A primeira proteção reduziu a
concorrência observada a uma requisição. A implementação final serializa as
atualizações de lobby e da lista de campanhas e guarda somente o tick pendente
mais recente, executando-o depois da atualização em curso. Também evita iniciar
uma atualização enfileirada após o componente do lobby ser desmontado.

A suíte final do frontend contém 11 testes aprovados, incluindo o teste
automatizado que verifica execução serial e coalescência do tick mais recente.
O teste unitário cobre a implementação final; a observação visual da redução
de três chamadas para uma ocorreu na validação após a primeira proteção.

### Testes e verificações

| Verificação | Momento e resultado |
| --- | --- |
| Backend | 38 testes aprovados na validação anterior à correção final de frontend. |
| Frontend | 11 testes aprovados após a correção final. |
| TypeScript | `tsc --noEmit` aprovado após a correção final. |
| Build | Build de produção aprovado após a correção final. |
| Lint | Sem erros; 7 avisos preexistentes de `react-refresh/only-export-components`. |
| Alembic/schema | Comparação read-only da metadata sem diferenças. O schema visual não contém `alembic_version`, portanto não há revisão registrada. Nenhuma migration foi aplicada. |
| Serviços | Frontend `/` e API `/health` responderam HTTP 200 na verificação final; nenhum serviço foi reiniciado. |

### Banco, segredos e checkpoint Git

- Os testes visuais da Etapa G usaram exclusivamente o banco
  `cronicas_do_reino_test`, schema `test_visual_g_eb8c40da20ae`.
- `cronicas_do_reino_dev` não foi acessado nem alterado. Nenhum banco foi
  acessado ou modificado durante o encerramento documental.
- Não foram alteradas contas ou permissões, nem executadas migrations.
- O workspace disponível não contém diretório ou arquivo `.git` na raiz do
  projeto nem nos diretórios pais examinados. Assim, `git status`, branch,
  histórico e verificação de arquivos no índice não estão disponíveis; nenhum
  commit ou hash pôde ser criado. Não foi inicializado um repositório novo para
  evitar tratar o conteúdo existente como arquivos novos sem histórico.
- As regras observadas em `.gitignore` e `backend/.gitignore` cobrem `.env`,
  dependências instaladas, caches Python, `.db`, saídas de build e arquivos
  temporários. O arquivo real `backend/.env` existe e não foi lido. Como não há
  metadados Git, não foi possível confirmar estado de indexação ou provar a
  exclusão de segredos do histórico; nenhum arquivo foi staged ou commitado.
- Neste encerramento, `.gitignore` também foi complementado para excluir
  ambientes virtuais, `.pytest_cache`, `__pycache__`, bytecode Python e arquivos
  `*.db` na raiz e em subdiretórios.
- Os arquivos da correção de polling são
  `src/components/player/CampaignPages.tsx`,
  `src/lib/create-non-overlapping-poll.ts` e
  `src/test/create-non-overlapping-poll.test.ts`. Os dois primeiros participam
  do comportamento; o último cobre a serialização. O relatório e esta seção
  documentam a validação, mas não substituem um checkpoint versionado.
- Este encerramento atualizou `.gitignore`, `README.md` e
  `docs/multiplayer-visual-validation.md`.
- Arquivos e diretórios locais de ambiente, dependências, saída de build,
  caches, evidências e dados privados não foram incluídos em checkpoint Git.

### Preparação da Etapa H — sem implementação

A Etapa H é a última etapa planejada. Os tópicos abaixo são escopo de
planejamento, não funcionalidades iniciadas neste encerramento:

1. Biblioteca visual de assets acessível pelo Painel do Mestre.
2. Upload e preview de imagens; metadados; edição, substituição e exclusão
   segura.
3. Entidades visuais e de jogo para personagens, NPCs, aliados, hostis,
   monstros, minibosses e bosses.
4. Armas, equipamentos, magias e poderes.
5. GIFs para os estados de idle, ataque, impacto, dano e derrota.
6. Análise técnica de cada GIF: dimensões, quantidade de frames, duração,
   delay por frame, transparência e proporção.
7. Sistema de combate completo, animações e integração com os atributos e as
   regras do jogo.

**Regra de animação:** não confundir a velocidade interna dos frames de um GIF
com a velocidade de deslocamento do objeto ou personagem. São propriedades
distintas e devem ser tratadas separadamente no planejamento e na implementação.

A Etapa H não foi iniciada. A implementação depende de planejamento e
autorização próprios.
