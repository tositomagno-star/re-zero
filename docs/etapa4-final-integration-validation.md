# Etapa 4 — validação integrada final

## PostgreSQL MCP e isolamento

- O provider oficial `pgsql-tools-mcp-server-provider` listou os perfis
  `Crônicas — Desenvolvimento` e `Crônicas — Testes`. A conexão foi tentada
  somente pelo identificador informado para Testes
  (`4B9AA492-62F3-421B-BF75-9B32E8D8F9C7`), mas o provider respondeu
  `profile not found`.
- Não foi possível confirmar endpoint, conexão ativa ou ferramentas SQL
  utilizáveis pelo Agent Host. Nenhuma consulta PostgreSQL, inclusive de
  leitura, foi executada.
- A identidade previamente observada para Testes (`cronicas_dev_agent`,
  schema `public`, `search_path` `"$user", public`) não comprova o isolamento
  exigido. O código do projeto oferece uma configuração explícita de testes
  por `TEST_DATABASE_URL` e `TEST_ASSET_SCHEMA`, valida o banco e restringe o
  `search_path` ao schema indicado. A fixture PostgreSQL também verifica role,
  revisão e catálogo antes de limpar tabelas, mas depois executa `TRUNCATE`.
  Como o perfil MCP não foi encontrado e a identidade isolada não foi
  comprovada, esse caminho não foi usado contra PostgreSQL e os testes
  marcados `postgres` foram excluídos.

## Validação integrada em ambiente descartável

A aplicação foi iniciada localmente com `DATABASE_URL=sqlite+aiosqlite://`,
sem usar perfis ou dados PostgreSQL. Foram criadas contas sintéticas e uma
campanha temporária na base SQLite em memória.

- Duas sessões em páginas de origens de API distintas entraram na mesma
  campanha e viram os dois participantes. Isso validou sessões e cookies
  separados por origem no navegador integrado; não foram criados contextos
  independentes do motor do navegador.
- A prontidão de um participante apareceu na outra sessão pelo polling. Após
  recarregar a página, a lista e o estado de prontidão foram recuperados.
- Com apenas dois participantes, a tentativa de início foi rejeitada pelo
  backend com HTTP `409` e a mensagem “São necessários pelo menos 3
  participantes ativos para iniciar.” A campanha permaneceu aguardando.
- A saída de um participante foi refletida em uma consulta nova da outra
  sessão (`1/5`); o retorno restaurou a lista para `2/5` e reiniciou a
  prontidão do participante que retornou.
- Em 390, 768 e 1440 px, a largura do documento foi respectivamente 375, 753
  e 1425 px. Não houve overflow horizontal; a diferença de 15 px corresponde
  à barra vertical. Capturas do lobby foram produzidas na sessão, sem arquivos
  de imagem versionados.
- O navegador integrado inicialmente reportava a página como oculta. Para
  permitir que o polling fosse executado, a visibilidade foi simulada no
  harness de teste. Portanto, as capturas e medições refletem a UI real, mas
  não substituem uma validação de foco/visibilidade em navegadores
  convencionais com contextos independentes.

## Verificações automatizadas

| Verificação | Resultado |
| --- | --- |
| `npm.cmd test` | 46 testes aprovados em 6 arquivos. |
| `npx.cmd tsc --noEmit` | Aprovado. |
| `npm.cmd run lint` | 0 erros; 7 avisos preexistentes de Fast Refresh. |
| `npm.cmd run build` | Aprovado; Vite emitiu o aviso informativo sobre `vite-tsconfig-paths`. |
| `python -m pytest -m 'not postgres' -q` | 122 aprovados; 12 testes PostgreSQL excluídos. |
| `python -m compileall -q app tests` | Aprovado. |

Os testes backend foram executados a partir de `backend`, com o Python do
ambiente virtual do projeto, `APP_ENVIRONMENT=development`,
`DATABASE_URL=sqlite+aiosqlite://` e `TEST_DATABASE_URL` removida do processo.
Nenhum teste PostgreSQL com `TRUNCATE` foi executado.

## Pendências e garantias

- O provider ainda precisa disponibilizar o perfil real de Testes e provar a
  identidade esperada (`cronicas_local`, banco `cronicas_do_reino_test`,
  schema `test_asset_h_7e4c91a2d603` e `search_path` restrito) antes de qualquer
  consulta PostgreSQL.
- Conteúdo narrativo publicado e fluxo administrativo em navegador não foram
  validados: não havia conteúdo de teste autorizado nem conta administrativa
  de teste disponível. Os testes automatizados seguros cobriram esses fluxos
  em SQLite.
- Permanecem pendentes a validação com três ou mais contextos independentes de
  navegador e a observação de presença/reconexão em browsers convencionais.
- Não foram alterados credenciais, perfis, roles, grants, permissões ou dados
  PostgreSQL. Não houve acesso a `cronicas_do_reino_dev`; nenhuma migration,
  DDL, limpeza ou escrita PostgreSQL foi executada.
