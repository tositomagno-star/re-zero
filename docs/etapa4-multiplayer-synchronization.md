# Etapa 4 — multiplayer e sincronização

## Alterações implementadas

- O lobby interrompe consultas e heartbeats enquanto a aba está oculta e
  retoma ambos imediatamente quando volta a ficar visível.
- Polling de lobby e presença continuam sem sobreposição. Respostas GET que
  ficaram obsoletas por uma ação local ou por um snapshot mais novo são
  descartadas, evitando que respostas fora de ordem revertam prontidão ou
  estado narrativo já atualizado.
- As consultas em voo são abortadas ao desmontar o componente ou trocar a
  campanha. Erros temporários permanecem visíveis e uma resposta posterior bem
  sucedida limpa o aviso de conexão.
- A UI impede ações de lobby duplicadas enquanto outra ação está em andamento.
  A prontidão exibida permanece baseada no estado retornado pela API.
- O backend permanece como autoridade: cada endpoint altera o estado do membro
  autenticado; presença é considerada conectada por até 45 segundos após o
  último heartbeat; membros que saem deixam de contar como ativos e reentrada
  restaura o membro sem prontidão marcada.
- As regras atuais de início da campanha não exigem que todos estejam prontos.
  Elas continuam sendo aplicadas no backend (proprietário, número mínimo de
  membros ativos, personagens válidos e conteúdo narrativo inicial). Nenhuma
  nova regra de prontidão foi introduzida.

## Cobertura e verificações

- Frontend inclui testes de lobbies independentes, propagação de prontidão,
  reload da sessão, resposta GET fora de ordem, polling sem sobreposição,
  pausa/retomada por visibilidade, retry após falha transitória, cancelamento
  ao desmontar e renderização da presença desconectada retornada pelo servidor.
- Backend inclui teste SQLite com três participantes: duas atualizações
  simultâneas de prontidão, repetição idempotente, heartbeat, saída, acesso
  negado após saída, reentrada, reset de prontidão e consistência da lista de
  membros.
- `npm test`: 46 testes aprovados em 6 arquivos.
- Backend: 122 aprovados; 12 testes marcados `postgres` excluídos. Execução
  feita com `DATABASE_URL=sqlite+aiosqlite://`, `APP_ENVIRONMENT=development` e
  `TEST_DATABASE_URL` removida do processo.
- `tsc --noEmit`: aprovado.
- `compileall` para `backend/app` e `backend/tests`: aprovado.
- ESLint: zero erros e sete avisos preexistentes sobre Fast Refresh.
- Build frontend: aprovado.

## Limites de validação

- Nenhum teste PostgreSQL, consulta MCP, migration, DDL, limpeza ou operação de
  escrita em PostgreSQL foi executado nesta etapa. A identidade/search path do
  perfil de testes continua sem isolamento comprovado; portanto, os testes
  PostgreSQL com limpeza permanecem bloqueados.
- Uma validação integrada posterior executou a aplicação com SQLite em memória
  e duas contas sintéticas em páginas servidas por origens de API distintas.
  Foram exercitados entrada na campanha, sincronização de prontidão, reload,
  bloqueio de início com menos de três participantes, saída e retorno. O
  relatório com evidências e resultados está em
  [`etapa4-final-integration-validation.md`](./etapa4-final-integration-validation.md).
- O lobby foi medido em 390, 768 e 1440 px sem overflow horizontal; capturas
  foram produzidas na sessão do navegador, mas não foram adicionadas ao
  repositório. O navegador integrado reportava a página como oculta, então a
  visibilidade foi simulada para permitir o polling. Isso não substitui a
  validação em contextos independentes de navegador nem comprova o
  comportamento de abas foreground/background em um browser convencional.
- Permanecem pendentes: sessão simultânea com três ou mais navegadores reais,
  narrativa com conteúdo publicado, painel administrativo com conta autorizada
  e validação PostgreSQL depois de provar o isolamento.

`cronicas_do_reino_dev`, suas credenciais, perfis, roles e permissões não foram
acessados nem alterados. Os testes de backend usaram somente o banco SQLite
efêmero criado pela fixture local.
