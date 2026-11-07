# Etapa 4 — validação de narrativa e painel administrativo

## Concluído nesta etapa

- Corrigida a tela **História e capítulos**: enquanto a lista oficial ainda
  carrega, ou falha sem dados em cache, ela não apresenta incorretamente o
  estado “Cadastre um capítulo”. O estado vazio só aparece depois de uma
  resposta bem-sucedida sem capítulos. A criação de cena continua desabilitada
  sem capítulo selecionado.
- A cobertura backend existente valida, em SQLite isolado, conteúdo publicado,
  cena inicial e escolhas, snapshot imutável, votos e avanço de cena/capítulo,
  recuperação da sessão, isolamento entre campanhas, ausência de conteúdo e
  bloqueios de acesso administrativo.
- A cobertura administrativa existente valida autenticação, CRUD de capítulo,
  ordenação e escolhas, validações de origem e operações bloqueadas quando há
  progresso narrativo. Os testes usam fixtures de teste; nenhuma conta real foi
  promovida ou alterada.
- Adicionados testes de interface para os estados de carregamento, vazio e erro
  da página de história. Corrigido também um matcher de teste incompatível com
  a verificação de tipos TypeScript.

## Verificações executadas

| Verificação | Resultado |
| --- | --- |
| Frontend (`npm test`) | 38 testes aprovados em 6 arquivos. |
| Backend (`pytest -m "not postgres"`, com `DATABASE_URL` SQLite somente no processo) | 121 aprovados; 12 testes PostgreSQL explicitamente excluídos. |
| TypeScript (`tsc --noEmit`) | Aprovado. |
| Python (`compileall` em `backend/app` e `backend/tests`) | Aprovado. |
| ESLint | 0 erros; 7 avisos preexistentes de Fast Refresh em componentes/exportações compartilhados. |
| Build frontend | Aprovado. O Vite avisou que `vite-tsconfig-paths` pode ser substituído pelo suporte nativo; a configuração não foi alterada por ser independente desta correção. |

Os testes backend foram executados a partir de `backend`, com
`APP_ENVIRONMENT=development`, `DATABASE_URL=sqlite+aiosqlite://` e
`TEST_DATABASE_URL` removida do processo. O marcador `postgres` foi excluído;
portanto, não houve conexão PostgreSQL nem execução da limpeza `TRUNCATE`.

## Validações que permanecem pendentes

- **Conteúdo publicado real e renderização narrativa em navegador:** não
  validados nesta etapa. A última identidade MCP conhecida para Testes era
  `cronicas_dev_agent`, com schema `public` e `search_path` `"$user", public`,
  divergente do isolamento esperado (`cronicas_local` e
  `test_asset_h_7e4c91a2d603`). Nenhuma consulta foi executada nesta etapa e
  nenhuma alteração de perfil ou credencial foi feita. É necessário resolver
  essa divergência de forma autorizada antes da validação PostgreSQL.
- **Fluxo administrativo em navegador com uma conta autorizada:** não validado
  porque não há conta administrativa de teste autorizada disponível nesta
  execução. Autenticação, proteção e CRUD foram exercitados apenas pelos testes
  automatizados com banco SQLite temporário.
- **Multiplayer e sincronização:** a validação integrada posterior exercitou
  duas sessões sintéticas em páginas com origens de API distintas, prontidão,
  recarga, saída e retorno, além de layout em 390, 768 e 1440 px. O uso de
  contextos independentes de navegador, conteúdo narrativo publicado e acesso
  PostgreSQL isolado continuam pendentes; consulte
  [`etapa4-final-integration-validation.md`](./etapa4-final-integration-validation.md).

Nenhuma migration ou operação PostgreSQL foi executada. Nenhum dado, perfil,
credencial, role, grant ou permissão foi alterado. O banco
`cronicas_do_reino_dev` não foi acessado.
