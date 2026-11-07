# Biblioteca de Assets

## Escopo

A Biblioteca de Assets do Painel do Mestre guarda imagens PNG, JPG, JPEG, WebP e GIF sem converter os bytes originais. Ela oferece pesquisa, filtro por categoria, prévia, cadastro e edição de metadados, vínculos com entidades do jogo, substituição de arquivo e exclusão protegida.

As categorias disponíveis incluem personagens, NPCs, aliados, hostis, monstros, minibosses, bosses, armas, equipamentos, magias, poderes e efeitos visuais. Cada registro também aceita subcategoria e tipo específico em texto livre (por exemplo, `chefes de fase` / `idle`), sem exigir enum ou alteração de código por variante. Os vínculos referenciais aceitos nesta versão são personagens, NPCs, monstros, itens e habilidades existentes.

## API

Todas as rotas administrativas exigem a sessão de administrador existente e validam a origem nas operações de escrita.

| Método | Rota | Operação |
| --- | --- | --- |
| `GET` | `/api/admin/assets` | Lista assets; aceita os filtros `category` e `search`. |
| `POST` | `/api/admin/assets` | Cria asset via multipart, com metadados e associações opcionais. |
| `PUT` | `/api/admin/assets/{asset_id}` | Atualiza nome, descrição, categoria e associações sem reenviar o arquivo. |
| `PUT` | `/api/admin/assets/{asset_id}/file` | Substitui o arquivo, preservando o identificador e as associações. |
| `GET` | `/api/admin/assets/{asset_id}/file` | Prévia privada autenticada para administradores. |
| `DELETE` | `/api/admin/assets/{asset_id}?confirm=true` | Exclui somente após confirmação e quando não houver referências. |
| `GET` | `/api/content/assets/{asset_id}/file` | Serve somente assets explicitamente publicados; assets privados retornam 404. |

O limite padrão é 5 MiB por arquivo, com limite adicional no corpo total multipart. `ASSET_MAX_UPLOAD_BYTES` permite reduzi-lo entre 1 byte e 5 MiB; aumentar o teto exige atualizar a constraint e a migration. Extensão e MIME precisam corresponder ao formato decodificado. O backend usa Pillow para decodificar os quadros e validar dimensões, quantidade de quadros e conteúdo; o GIF original e os canais alpha são preservados. A análise registra proporção, transparência, quadros, durações por quadro, duração total e loop; durações/loop indisponíveis são `null`.

## Dados e integridade

A revisão Alembic `c2f6d8a41b90_asset_library` adiciona as tabelas `assets` e `asset_entity_associations`; `d7b13c9a5e42_asset_analysis_metadata` adiciona subcategoria, tipo específico, JSON de análise e publicação explícita. As associações possuem chaves estrangeiras para as tabelas atuais de personagens, NPCs, monstros, itens e habilidades, e impedem a exclusão de entidades ainda vinculadas. Referências em `image_url` de NPCs, monstros e itens também bloqueiam a exclusão do arquivo. O cadastro de uma associação valida se a entidade existe. Ainda não existe entidade de efeito visual no domínio; a categoria/tipo visual permite organizar esses arquivos, mas associação relacional a efeitos aguarda um modelo oficial.

As migrations foram criadas, mas **não foram executadas** nesta etapa. Antes de usar as rotas numa instalação cujo banco ainda não tenha essas tabelas/colunas, aplique-as de forma controlada após conferir o banco e obter autorização operacional. Nenhuma migração é executada pela aplicação automaticamente.

## Armazenamento

O adaptador `LocalAssetStorage` guarda os arquivos no caminho de `ASSET_STORAGE_PATH` (padrão: `backend/uploads/assets` quando o backend é iniciado pelo procedimento do projeto), usando uma chave aleatória exclusiva e sem usar o nome fornecido pelo cliente como caminho. O diretório é ignorado pelo Git. A camada `AssetStorage` abstrai gravação, leitura em fluxo e exclusão, permitindo substituir o armazenamento local por um volume persistente ou outro adaptador no futuro.

O armazenamento local é adequado para desenvolvimento, mas **não é assumido como persistente em produção**. Configure `ASSET_STORAGE_PATH` para um volume durável montado, com permissões restritas de leitura/escrita, backup e restauração testados. Em múltiplas réplicas, todas devem compartilhar o armazenamento ou usar outro adaptador durável. A rota legada de imagens PNG de monstros permanece disponível e não foi alterada por esta biblioteca.

## Teste local

1. Instale as dependências do backend declaradas em `backend/pyproject.toml`.
2. Confira a revisão existente e aplique, somente no banco autorizado, a cadeia que inclui `c2f6d8a41b90_asset_library` e `d7b13c9a5e42_asset_analysis_metadata`.
3. Inicie/recarregue o backend e o frontend pelos procedimentos normais do projeto.
4. Entre no Painel do Mestre como administrador e abra **Biblioteca de Assets** no menu lateral.
5. Cadastre uma imagem de teste, filtre/pesquise, abra a prévia, edite metadados, teste uma substituição e confirme que uma entidade vinculada bloqueia a exclusão.

Os testes automatizados usam SQLite isolado por padrão. Testes PostgreSQL existentes são opt-in e exigem `TEST_DATABASE_URL` para o banco local de teste; esta implementação não exige nem executa esses testes.
