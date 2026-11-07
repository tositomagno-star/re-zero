# Etapa H.8 — Autenticação administrativa e Biblioteca de Assets

## Status

**Auditoria de código e testes automatizados concluídos; validação visual da Biblioteca e fluxo integrado pela interface bloqueados.** Inicialmente o servidor compartilhado estava indisponível (`127.0.0.1:8080` retornou `ERR_CONNECTION_REFUSED`). Depois foi iniciado somente o frontend local e aberta `/admin/login`; não havia backend nem sessão administrativa legítima compartilhada. Não foram criadas contas, nem contornada a autenticação.

## Auditoria do acesso administrativo

### Fluxo existente

- A página pública `/admin/login` renderiza `AdminLoginPage`; o endpoint é `POST /api/auth/admin/login`. O identificador é o **nome de usuário**, não e-mail: `AdminLoginRequest.username` aceita 3–32 letras ASCII, números ou `_`. A senha administrativa precisa ter 12–128 caracteres.
- O cadastro público `/api/auth/register` exige os mesmos limites de usuário e senha e sempre cria `is_admin=false`. Não há endpoint público de promoção nem campo de role no cadastro.
- A verificação administrativa é separada da sessão de jogador. O backend usa cookie `rpg_admin_session`, `HttpOnly`, `SameSite=Lax`, path `/` e flag `Secure` configurada pelo ambiente. O token aleatório é persistido como hash, com validade determinada pela configuração de sessão. A senha é verificada por hash scrypt.
- Login incorreto, conta inativa e conta sem flag administrativa retornam a mesma resposta genérica de 401 (`Usuário ou senha inválidos.`), evitando confirmar se uma conta existe ou é administradora. Ao verificar sessão/rotas, uma sessão ausente ou expirada retorna 401; identidade autenticada sem autorização administrativa retorna 403. `current_admin` exige usuário ativo e `is_admin=true`.
- A tela protegida consulta `GET /api/auth/admin/session`, encaminha 401 para `/admin/login` e mostra erro com opção de nova tentativa para outras falhas. A UI do login apresenta o estado de envio, `aria-busy`, retorno acessível com `role=alert` e validação de campos.

### Respostas com evidência disponível

1. **Existe usuário administrador cadastrado?** Não foi verificado. Esta etapa não consulta banco algum. O código e os testes não permitem inferir os registros existentes em uma instalação específica.
2. **Há bootstrap legítimo?** Há um comando `python -m app.cli create-admin`, com senha solicitada em prompt oculto e hash scrypt, mas `resolve_admin_test_target` e `_create_admin` recusam destinos que não sejam `cronicas_do_reino_test`, locais e com schema de teste autorizado. Portanto, é um utilitário de teste, não um bootstrap de produção. Nenhum administrador foi criado.
3. **Qual identificador?** Nome de usuário; não e-mail.
4. **Campos exigidos?** `username` (3–32 caracteres, padrão `[A-Za-z0-9_]{3,32}`) e `password` (12–128 caracteres no login administrativo).
5. **A UI mostra os campos?** Sim. A auditoria encontrou que o campo de senha não declarava o mínimo de 12, apesar da validação do backend. Corrigido nesta etapa.
6. **Por que não há usuário/senha disponíveis?** Não há credenciais padrão; o cadastro aberto cria apenas jogadores e a senha só é armazenada como hash. A aplicação não tem mecanismo que revele credenciais existentes. Nenhum registro foi consultado para estabelecer se há admin cadastrado.
7. **Há documentação/configuração faltando?** Sim. `backend-requirements.md` dizia que o CLI criava o primeiro administrador após migrations sem explicitar que ele rejeita alvos reais; também descrevia incorretamente o cadastro como PIN de seis dígitos. A documentação foi corrigida.
8. **Funciona sem cadastro manual no banco?** Cadastro de jogador funciona via API, mas não confere privilégio administrativo. O provisionamento administrativo de produção não está implementado; não declarar que o sistema está pronto para criar seu primeiro admin sem operação autorizada.

## Correção da interface

`AdminLoginPage` agora:

- identifica explicitamente o campo como **Nome de usuário administrativo** e explica que e-mail não é aceito;
- informa o mínimo de 12 caracteres e aplica `minLength=12`, alinhado a `AdminLoginRequest`;
- preserva a mensagem genérica do backend para credenciais inválidas, sem revelar existência ou role de uma conta;
- mantém mensagens acessíveis, estados de carregamento e proteção da rota.

O caso correspondente em `src/test/player-onboarding.test.tsx` agora verifica a regra de comprimento real do backend, em vez de afirmar que senhas curtas são aceitas.

## Primeiro administrador: proposta segura

Não implementar bootstrap automático ou promoção self-service nesta etapa. Recomenda-se aprovar separadamente um procedimento operacional que:

1. Seja executado manualmente por operador autorizado, fora de rotas públicas e sem senha padrão ou senha em variável/arquivo.
2. Exija confirmação explícita do ambiente e do alvo antes de escrita; recuse ambientes não autorizados ou conexões inesperadas.
3. Só crie o primeiro usuário administrativo quando não existir nenhum; não transforme um cadastro comum em admin.
4. Solicite usuário e senha em prompt não ecoado, valide as regras vigentes, grave somente hash scrypt e nunca registre a senha.
5. Use uma operação transacional e idempotente, permita repetição segura sem criar/promover usuários adicionais e ofereça caminho auditável de revogação/rotação.
6. Registre a ação administrativa (operador, ambiente, horário e ID do novo usuário) sem registrar senha, token ou hash de credencial em logs de aplicação.
7. Tenha revisão/aprovação de implantação e testes contra SQLite isolado antes de qualquer proposta para ambiente persistente.

Até a aprovação e implementação desse fluxo, o comando existente só pode ser usado nos targets de teste que ele valida. Não executar esse comando nesta etapa.

## Biblioteca de Assets — auditoria e limite da evidência

O código H.1 oferece listagem por busca/categoria, cadastro, metadados, preview autenticado, substituição, confirmação de exclusão, associação de entidades e opção explícita `is_public` (desmarcada por padrão). O backend valida PNG/JPEG/WebP/GIF; testa bytes reais além do MIME/extensão, calcula dimensões/transparência e quadros/durações/loop do GIF. A UI mostra metadados, vínculos e feedback de operações. O preview usa rota autenticada; assets privados têm cache privado/no-store. A API de arquivo público exige publicação explícita.

A suíte usa imagens sintéticas e armazenamento temporário. Os testes cobrem PNG, WebP e GIF animado, metadados de frame, bytes originais, edição, substituição preservando ID/vínculos, exclusão confirmada/bloqueada por referência e acesso privado versus opt-in público. Os testes de animação exercitam contratos de associação à configuração H.2; isso não comprova criação e reload pela interface visual.

**Evidência visual real limitada a `/admin/login`:** a página abriu pelo navegador compartilhado após iniciar Vite; o snapshot de acessibilidade apresentou os rótulos “Nome de usuário administrativo”, “Senha administrativa (mínimo 12 caracteres)” e “Entrar no painel”. A tela não foi submetida. Isso confirma a interface pública de login, não a biblioteca.

**Não foi possível testar visualmente a Biblioteca:** sem backend disponível e sem sessão administrativa legítima, a página protegida não foi aberta. Não foi tentado criar sessão, inserir registros, nem fabricar sessão. Consequentemente, upload PNG/WebP/GIF pela interface, preview real, editar/substituir, reload, privacidade em navegador, responsividade da biblioteca a 390/768/1440 px e associação/reprodução H.2 permanecem pendentes. Não declarar esses cenários como validados visualmente.

## Ambiente e proteção

- Nenhuma conexão a PostgreSQL foi feita; `cronicas_do_reino_dev` não foi acessado.
- Nenhuma migration, DDL, alteração de `.env`, credencial, role, grant ou dado persistente foi feita.
- Não se executou `create-admin`, não se criou usuário e não se reutilizou credencial.
- Os testes automatizados de backend utilizam o fixture SQLite isolado e storage temporário.

## Validação automatizada

Resultados das execuções finais desta etapa:

| Verificação | Resultado |
|---|---|
| Backend auth/assets/animações focado em SQLite | **27 passed**, 0 falhas. |
| Backend SQLite completo: `pytest -m "not postgres" -q` | **188 passed**, **12 deselected** (PostgreSQL), 0 falhas. |
| Frontend login/biblioteca/animações focado | **34 passed**, 3 arquivos, 0 falhas. |
| Frontend completo: `npm.cmd run test` | **58 passed**, 11 arquivos, 0 falhas. |
| TypeScript: `npx.cmd tsc --noEmit` | Aprovado, sem diagnósticos. |
| Build: `npm.cmd run build` | Aprovado; aviso informativo existente sobre `vite-tsconfig-paths`. |
| Compileall: `python -m compileall -q app migrations tests` | Aprovado. |
| `python -m pip check` | Aprovado; nenhuma dependência quebrada. |
| `npm.cmd ls --depth=0` | Aprovado; sem dependências inválidas. |
| `npm.cmd run lint` | 0 erros, **7 warnings** existentes `react-refresh/only-export-components` em componentes compartilhados/UI. |

## Pendências

- Disponibilizar uma sessão administrativa legítima já existente no navegador de teste, ou aprovar e implementar o bootstrap operacional de produção sem credenciais padrão.
- Iniciar os serviços em ambiente isolado autorizado e executar visualmente a biblioteca em 390, 768 e 1440 px.
- Fazer upload dos três arquivos sintéticos, verificar metadados/preview, editar/substituir/recarregar, confirmar publicação opt-in e acesso privado, e associar/reproduzir uma animação H.2.
- Tratar eventual erro de conexão do frontend antes de alegar qualquer validação de navegador.

## Atualização posterior — H.10

A ausência de mecanismo de produção descrita nesta etapa é histórica. A etapa H.10 adicionou um fluxo de bootstrap por CLI, sem rota pública, com concessão única e migration `d129a4c7e601` preparada, mas não aplicada. Nenhuma conta foi criada; a Biblioteca de Assets continua sem validação visual real. Consulte [etapa-h10-admin-bootstrap-operations.md](./etapa-h10-admin-bootstrap-operations.md) para os limites e pré-requisitos.
