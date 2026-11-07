# Etapa H.1 — Fundação da Biblioteca de Assets

## Entrega

A Biblioteca de Assets foi integrada ao Painel do Mestre, reutilizando os
módulos de storage, validação, API e interface que já existiam no projeto.
Não foi criado um sistema paralelo. O administrador pode pesquisar/listar,
cadastrar, visualizar, organizar, editar, substituir e excluir assets, com
confirmação e proteção por referência.

## Modelo e classificação

As tabelas existentes `assets` e `asset_entity_associations` continuam sendo a
base. O asset registra nome, descrição, categoria principal, subcategoria,
tipo específico, nome original sanitizado, extensão, MIME type, chave opaca de
armazenamento, tamanho, dimensões, datas, análise JSON e publicação pública.
`is_in_use` é calculado pelas associações e referências em `image_url`; não é
um valor fornecido pelo cliente.

As categorias principais disponíveis incluem personagens, NPCs, aliados,
hostis, monstros, minibosses, bosses, armas, equipamentos, magias, poderes e
efeitos visuais. Subcategorias e tipos (por exemplo, `chefes de fase`,
`idle`, `ataque` ou `impacto`) são campos de texto opcionais e podem ser
cadastrados pelo formulário sem mudança de código ou enumeração de cada valor.
As associações relacionais usam as entidades existentes: personagens, NPCs,
inimigos, itens e habilidades. Ainda não há entidade de efeito visual no
domínio, então os arquivos podem ser organizados como efeitos, mas não
associados a uma entidade de efeito inexistente.

## Upload, armazenamento e segurança

- Formatos: PNG, JPG, JPEG, WebP e GIF. Extensão, MIME declarado e formato
  decodificado precisam corresponder. SVG, HTML, scripts e executáveis são
  rejeitados.
- O limite padrão é 5 MiB. `ASSET_MAX_UPLOAD_BYTES` configura um teto menor
  (1 byte a 5 MiB); um teto maior exigirá alterar a constraint de tamanho e
  preparar outra revisão de schema.
- Pillow valida e decodifica o conteúdo, com limites de dimensão 8192 px,
  40 milhões de pixels por imagem, 500 frames e 100 milhões de pixels totais
  dos frames. O nome original nunca define o caminho. A chave persistente é
  aleatória, exclusiva e validada contra path traversal.
- Os bytes originais e dimensões são preservados; não há conversão ou
  redimensionamento.
- A configuração `ASSET_STORAGE_PATH` aponta para o armazenamento local. O
  default continua em `backend/uploads/assets`; caminhos relativos são
  ancorados ao diretório do backend. `AssetStorage` é uma interface para
  implementação futura de storage externo.
- O storage local serve para desenvolvimento. Produção deve configurar um
  volume persistente, restringir permissões, preparar backups/restauração e,
  em implantação com várias réplicas, compartilhar o volume ou usar outro
  adaptador durável.
- Assets são privados por padrão. O endpoint público só entrega registros
  marcados explicitamente como públicos. Prévia privada usa endpoint
  autenticado de administrador, com `Cache-Control: private, no-store`.
  Nenhuma rota retorna o caminho físico; as prévias não ficam retidas no cache
  React Query após o unmount.
- Substituição grava o novo arquivo antes de atualizar o registro; se a
  transação falhar, remove a nova cópia e mantém o original. Associações e
  identificador do asset são preservados. Exclusão exige confirmação e falha
  se houver associação ou referência em conteúdo do jogo.

## Análise de imagens e GIF

O JSON `analysis_metadata` contém proporção e presença de transparência. Para
GIF, contém quantidade de frames, durações individuais, duração total e loop.
Duração total é `null` se algum frame não fornecer duração; duração individual
e loop indisponíveis também são representados por `null`, não por zero. O valor
de loop `0` significa repetição infinita. Os tempos são duração de reprodução
dos frames em milissegundos; não representam velocidade ou deslocamento de
projétil. A análise percorre os frames dentro dos limites, e o GIF original é
mantido.

## Interface e uso

1. Abra `/admin`, autentique-se como administrador e selecione
   **Biblioteca de Assets** no menu lateral.
2. Em **Novo asset**, escolha arquivo, nome e categoria; opcionalmente
   preencha subcategoria/tipo, descrição, associações e a opção de publicação.
   A prévia local aparece antes do envio.
3. Abra a prévia ampliada para consultar dimensões, MIME, proporção,
   transparência, quantidade/duração de frames, loop, tamanho e identificador.
4. Em **Editar**, altere metadados. Para trocar a imagem, selecione outro
   arquivo e use **Substituir arquivo**; a confirmação preserva ID e vínculos.
5. **Excluir** solicita confirmação; assets ainda utilizados são recusados
   pelo backend e a resposta identifica referências.

## Endpoints

Todas as rotas administrativas exigem a sessão admin; operações de escrita
também validam a origem da requisição.

| Método | Endpoint | Uso |
| --- | --- | --- |
| `GET` | `/api/admin/assets?category=&search=` | Lista e filtra assets. |
| `POST` | `/api/admin/assets` | Upload multipart com metadados. |
| `PUT` | `/api/admin/assets/{id}` | Edita metadados e associações. |
| `PUT` | `/api/admin/assets/{id}/file` | Substitui o arquivo. |
| `GET` | `/api/admin/assets/{id}/file` | Prévia privada autenticada. |
| `DELETE` | `/api/admin/assets/{id}?confirm=true` | Exclusão protegida. |
| `GET` | `/api/content/assets/{id}/file` | Download de asset explicitamente público. |

## Schema e alterações pendentes

A revisão inicial `c2f6d8a41b90_asset_library` cria as tabelas da biblioteca.
A revisão H.1 `d7b13c9a5e42_asset_analysis_metadata`, descendente da revisão
de progressão `a41b9e2d7c10`, adiciona subcategoria, tipo específico, JSON de
análise e publicação. Ambas estão preparadas no repositório, mas nenhuma
migration foi aplicada durante esta etapa. Antes de habilitar a biblioteca em
um banco, confirme a revisão instalada e aplique as migrations somente no
ambiente autorizado. Nenhuma operação PostgreSQL foi tentada.

## Validação

- Testes backend não-PostgreSQL: `153 passed, 12 deselected` (rodada completa
  segura com SQLite).
- Testes frontend: `53 passed` em 8 arquivos.
- TypeScript (`tsc --noEmit`): aprovado.
- Build frontend (`npm run build`): aprovado; o Vite exibiu aviso informativo
  sobre resolução nativa de aliases e a opção `resolve.tsconfigPaths`.
- ESLint (`npm run lint`): código de saída 0, 0 erros e 7 avisos
  `react-refresh/only-export-components` em arquivos existentes.
- Compilação Python (`compileall app migrations`): aprovada.
- Dependências: `pip check` sem dependências quebradas; `npm ls --depth=0`
  concluiu com código 0, embora liste 5 pacotes instalados como `extraneous`.
- A cabeça da cadeia Alembic foi inspecionada sem executar migration:
  `d7b13c9a5e42`.
- Validação visual manual em navegador/resoluções não foi realizada. Os testes
  frontend executam em ambiente JSDOM, não são evidência de validação visual.

## Pendências e limites

- A revisão de schema não foi aplicada; endpoints novos necessitam das tabelas
  e colunas correspondentes no banco autorizado.
- O storage durável de produção, backup/restauração e eventual adapter de
  objeto externo devem ser configurados antes de receber conteúdo de produção.
- A associação a efeitos visuais depende de existir primeiro uma entidade de
  efeito no domínio; combate visual e editor de animações não fazem parte da
  H.1.
- Nenhum teste PostgreSQL, banco `cronicas_do_reino_dev`, credencial, role,
  grant ou permissão foi acessado ou alterado. As exclusões de arquivos e
  gravações de teste ocorreram somente no SQLite e storage temporário isolados.

## Arquivos da entrega

- Backend: `backend/app/api/admin_assets.py`,
  `backend/app/core/config.py`, `backend/app/models/entities.py`,
  `backend/app/schemas/assets.py`,
  `backend/app/services/asset_storage.py`,
  `backend/app/services/asset_validation.py`.
- Migration preparada: `backend/migrations/versions/d7b13c9a5e42_asset_analysis_metadata.py`.
- Testes: `backend/tests/test_admin_assets.py`,
  `backend/tests/test_config.py`, `src/test/asset-library.test.tsx`.
- Frontend/configuração: `src/components/admin/AssetLibraryPage.tsx`,
  `src/lib/admin-content-api.ts`, `backend/.env.example`.
- Documentação: `README.md`, `docs/asset-library.md`,
  `docs/admin-content-api.md` e este relatório.
