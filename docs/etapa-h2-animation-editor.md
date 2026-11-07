# Etapa H.2 — Editor de Animações e Arena de Pré-visualização

## Arquitetura implementada

O editor administrativo reutiliza os assets persistidos pela H.1. A listagem busca os assets existentes e oferece apenas GIFs; a prévia baixa os bytes pelo endpoint administrativo protegido, sem expor chaves físicas de armazenamento. A configuração e as associações são persistidas pelo backend, não pelo estado React.

O componente exportado `AnimationPreviewArena` recebe a configuração validada, o asset e seus bytes, e executa somente a apresentação visual. A arena é isolada das campanhas: não chama endpoints de combate, não aplica dano e não altera estado de jogo.

## Modelo de configuração

A migration preparada cria:

- `animation_configurations`: nome, descrição, IDs do GIF principal e do impacto opcional, JSON de configuração e timestamps.
- `animation_configuration_associations`: associação polimórfica, com exatamente um vínculo entre personagem, NPC, inimigo, item ou habilidade.

O JSON persiste `animation_type`, `trajectory`, `movement`, `origin`, `target`, `scale`, `rotation`, `gif_playback_rate`, `travel_duration_ms`, `travel_speed`, `impact_time_ms`, `render_layer`, `direction` e `extra`.

Os quatro tempos/velocidades têm campos independentes:

- `gif_playback_rate`: multiplicador da duração individual dos frames do GIF.
- `travel_duration_ms`: duração total do deslocamento; zero significa deslocamento instantâneo.
- `travel_speed`: multiplicador visual de ritmo do deslocamento, independente da velocidade dos frames.
- `impact_time_ms`: duração visual da fase de impacto.

A prévia usa o progresso normalizado do tempo do deslocamento. O movimento `linear`, `ease_in`, `ease_out` ou `arc` define a curva base; o multiplicador de deslocamento ajusta o ritmo visual e a curva `arc` acrescenta elevação visual. Essas regras são somente de apresentação e não são fórmulas de combate.

Para a prévia, o ritmo é calculado como `min(1, curvaBase(t) ** (1 / travel_speed))`, onde `t` é o progresso do tempo de deslocamento. Assim, a duração determina o término temporal e a velocidade altera a evolução visual ao longo do percurso, sem substituir a taxa dos frames GIF. `travel_duration_ms = 0` posiciona o efeito instantaneamente.

As coordenadas de origem e destino são números finitos entre 0 e 1, relativos à arena. A seleção de cada trajetória preenche pontos iniciais convenientes, que podem ser ajustados:

| Trajetória | Origem inicial | Destino inicial |
|---|---:|---:|
| `right_to_center` | (0.95, 0.50) | (0.50, 0.50) |
| `left_to_center` | (0.05, 0.50) | (0.50, 0.50) |
| `right_to_left` | (0.95, 0.50) | (0.05, 0.50) |
| `left_to_right` | (0.05, 0.50) | (0.95, 0.50) |
| `bottom_to_top` | (0.50, 0.95) | (0.50, 0.05) |
| `top_to_bottom` | (0.50, 0.05) | (0.50, 0.95) |
| `origin_to_target` | (0.95, 0.50) | (0.50, 0.50) |
| `direct_impact` | (0.95, 0.50) | (0.50, 0.50) |
| `area_effect` | (0.95, 0.50) | (0.50, 0.50) |

Trajetórias adicionais podem ser introduzidas no contrato sem alterar a estrutura persistida. A API valida o nome da trajetória, os limites numéricos e os intervalos específicos de cada campo.

## Contratos de API

Todas as rotas abaixo exigem sessão administrativa. Escritas também passam pela validação de origem:

- `GET /api/admin/animations`: lista configurações e associações.
- `POST /api/admin/animations`: cria configuração.
- `PUT /api/admin/animations/{id}`: substitui configuração e associações.
- `DELETE /api/admin/animations/{id}`: exclui configuração sem referências; responde `409` enquanto houver associação.

O backend verifica a existência e disponibilidade dos GIFs principal e opcional de impacto, exige `image/gif` e extensão `.gif`, valida as entidades associadas e rejeita identificadores ausentes ou duplicados. O frontend usa `GET /api/admin/assets` e baixa previews privados pelo `GET /api/admin/assets/{id}/file`, mantendo a autorização H.1.

O GIF do impacto é opcional. A configuração visual pode ser associada a personagens, NPCs, inimigos, itens e habilidades. Bosses usam o modelo de inimigo existente. Magias e efeitos sem entidade própria podem ser representados pela associação à habilidade; ainda não há integração oficial com a resolução de combate. Os endpoints H.1 de listagem/exclusão/renovação do asset consultam essas referências; por isso, a migration H.2 precisa preceder a implantação do backend H.2.

## Executor visual e arena

O executor está exportado como `AnimationPreviewArena` em `src/components/admin/AnimationEditorPage.tsx` e aceita configuração, metadados do asset e blobs carregados pela sessão administrativa. Ele:

- decodifica frames com `gifuct-js`, preserva proporção/transparência e aplica o multiplicador de reprodução aos delays dos frames;
- utiliza coordenadas normalizadas para redimensionamento responsivo;
- executa a movimentação e exibe impacto/indicador de alvo na arena;
- oferece repetir e interromper, cancela `requestAnimationFrame`/timers ao concluir ou desmontar e revoga URLs de blob;
- acompanha `prefers-reduced-motion`, exibindo a posição final sem alterar a configuração salva;
- limita a prévia a 500 frames, 16 milhões de pixels no canvas e 32 milhões de pixels acumulados nos frames para evitar decodificação excessiva.

O canvas compõe frames incrementais e trata descarte de frame limpando a área do frame anterior quando indicado. Casos incomuns de disposição de GIF podem diferir de um decodificador completo de navegador. A imagem original nunca é alterada. O impacto visual não representa dano ou resultado de habilidade.

## Armazenamento e migration

Os GIFs permanecem no adaptador persistente da H.1 (`AssetStorage`/`LocalAssetStorage`) e respeitam a configuração `ASSET_STORAGE_PATH`; esta etapa não cria armazenamento paralelo. Em produção, esse caminho precisa apontar para volume durável, com backup e permissões de leitura/gravação para o serviço.

A migration `ea42d7b190c3_animation_configurations.py`, encadeada após `d7b13c9a5e42`, está preparada, mas **não foi aplicada**. PostgreSQL não foi acessado. A migration precisa ser aplicada em uma janela operacional autorizada antes de usar os endpoints em um banco que ainda não possua essas tabelas.

## Acesso administrativo

No painel, abra **Editor de Animações**. Selecione **Nova configuração**, informe nome e descrição, escolha GIFs da Biblioteca, trajetória e pontos, ajuste separadamente reprodução do GIF, duração/velocidade do deslocamento e tempo de impacto, e teste na arena. Salvar persiste no backend. Configurações salvas podem ser recarregadas, editadas, duplicadas ou excluídas; associações precisam ser removidas antes de excluir.

## Testes, limitações e próxima etapa

Os testes H.2 usam SQLite em memória e armazenamento temporário. Incluem CRUD e recuperação, validação de coordenadas/asset, autorização, associação, proteção contra exclusão referenciada e contra substituição de GIF em uso. Os testes frontend exercitam seleção, trajetória, tempos independentes, cenário, replay, interrupção e liberação do URL de preview.

Resultados da validação:

- Backend: `156 passed, 12 deselected` com `pytest -m "not postgres"`; os 12 testes que exigem PostgreSQL foram deliberadamente excluídos.
- Frontend: `9` arquivos e `55` testes passaram.
- TypeScript (`tsc --noEmit`): passou.
- Build frontend: passou.
- ESLint: `0` erros e `7` avisos preexistentes em componentes compartilhados/UI fora das alterações H.2.
- `compileall`: passou.
- `pip check`: `No broken requirements found`.
- `npm ls --depth=0`: passou, sem dependências ausentes.
- `alembic history`: confirmou `ea42d7b190c3` como head após `d7b13c9a5e42`.
- Smoke visual: o Vite respondeu `HTTP 200`; a rota `/admin` não completou a verificação de sessão porque a API não estava em execução em `127.0.0.1:8000`. Portanto, o acesso autenticado pelo navegador não foi validado neste ambiente; os testes de componente e API foram executados separadamente.

Pendências para combate real:

- aplicar a migration somente após autorização e backup operacional;
- definir o contrato de combate e conectar entidades de magia/efeito que ainda não têm modelo;
- integrar o executor a uma arena real sem conceder autoridade de regras ao frontend;
- revisar recursos de animação GIF com disposições incomuns e limites de performance conforme a biblioteca de assets crescer.

Nenhuma migration foi aplicada a PostgreSQL; nenhum banco PostgreSQL foi acessado e nenhum dado, credencial ou permissão PostgreSQL foi alterado. As tabelas SQLite dos testes foram criadas apenas no banco isolado em memória.
