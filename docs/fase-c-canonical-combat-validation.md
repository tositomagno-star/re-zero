# Fase C — Validação do balanceamento canônico

> **Status: bloqueada antes do acesso ao banco.** A configuração disponível identifica apenas um ambiente local de desenvolvimento; não há evidência suficiente para afirmar que ele contém o catálogo canônico. Nenhum banco foi conectado, consultado ou alterado.

## 1. Resumo executivo

| Item | Resultado |
|---|---|
| Ambiente configurado para a aplicação | `development`, com destino local `127.0.0.1:5432/cronicas_do_reino_dev` |
| Catálogo canônico identificado | **Não** |
| Banco acessado / consulta executada | **Não / nenhuma** |
| Acesso administrativo confirmado | **Não verificado** |
| Inventário canônico | **Não obtido** |
| Simulações com snapshots canônicos | **0** |
| Ajustes canônicos | **Nenhum** |
| Dados, permissões e `.env` alterados | **Não** |
| Site | Frontend e API iniciados; página pública aberta no navegador |

O nome e a finalidade de desenvolvimento do banco local não comprovam que ele seja a fonte canônica. Seguindo a instrução de interromper o acesso quando o destino não puder ser identificado inequivocamente, não foram feitas consultas de identidade, privilégios, backup, administrador ou catálogo.

## 2. Auditoria do ambiente

- A configuração da aplicação carregada a partir de `backend/.env` indica `APP_ENVIRONMENT=development` e um destino local para `cronicas_do_reino_dev`. Credenciais não foram incluídas neste relatório.
- A documentação do projeto descreve `cronicas_do_reino_dev` para desenvolvimento e `cronicas_do_reino_test` para testes. Ela não designa nenhum deles como fonte canônica para esta fase.
- O host, banco, schema e role do alvo canônico, os privilégios efetivos, a existência de backup recuperável e a revisão Alembic instalada no alvo permanecem **desconhecidos**.
- `alembic heads` foi executado sem conexão e identificou `d129a4c7e601` como head do código. Isso não informa a revisão instalada no banco nem quais migrations estão pendentes nele. O runbook H.10 registra que essa migration estava preparada, mas não aplicada à época daquela entrega; não foi inferido o estado atual.
- A configuração não define explicitamente `ASSET_STORAGE_PATH`; o caminho padrão é `backend/uploads/assets`. A pasta não existia durante a inspeção. Nenhum asset foi criado ou modificado.

### Bloqueio e procedimento necessário

O operador responsável deve identificar a fonte canônica por documentação/autorização do ambiente de deploy e fornecer o destino aprovado (host, database e schema), sem compartilhar credenciais. Antes de consultas persistentes, também devem ser confirmados identidade do alvo, privilégios mínimos e backup recuperável. Só então será possível fazer inventário somente de leitura e verificar a existência de administrador.

## 3. Autenticação administrativa

- A documentação H.8/H.9/H.10 e o código confirmam que o bootstrap não é um endpoint público e não promove contas de jogador.
- O procedimento H.10 é operacionalmente restrito a Linux/produção, exige confirmação explícita do alvo, configuração esperada de host/database/schema, flags de autorização e diretório seguro em `/run/admin-bootstrap`. A migration correspondente deve ser aprovada e aplicada em procedimento separado.
- O ambiente observado é Windows/`development`; portanto, não satisfaz as guardas do bootstrap de produção. O comando legado `create-admin` é destinado somente a bancos locais de teste e não foi executado.
- A existência de administrador não foi consultada porque o alvo canônico não foi identificado. Nenhuma conta, senha, role ou permissão foi criada ou alterada.

## 4. Inventário canônico

Contagens abaixo são **não obtidas**, e não zero. Não houve consulta às tabelas nem leitura de dados persistentes.

| Categoria | Contagem | Situação |
|---|---:|---|
| Personagens e arquétipos | — | Não obtido |
| Níveis, atributos, HP e mana | — | Não obtido |
| Inimigos comuns e bosses | — | Não obtido |
| Armas e equipamentos | — | Não obtido |
| Habilidades físicas, magias e especiais | — | Não obtido |
| Custos, dano, defesa, resistências, fraquezas e efeitos | — | Não obtido |
| Animações e associações visuais | — | Não obtido |
| Relacionamentos, duplicidades e registros incompletos | — | Não verificado |

## 5. Comparação H.11–H.16 e experimentos

Os artefatos H.11–H.16 foram mantidos como evidência **sintética**. Nenhum resultado sintético foi combinado com população canônica.

| Fonte | Uso possível nesta fase | Resultado canônico |
|---|---|---|
| [H.11 — Simulador automatizado](./etapa-h11-combat-simulator.md) | Reutilizar o simulador após validação do snapshot | Não executado |
| [H.12 — Análise comparativa](./etapa-h12-combat-balance-analysis.md) | Comparar cenários equivalentes sem duplicar fórmulas | Não comparado |
| [H.13 — Análise de habilidades](./etapa-h13-skill-balance-analysis.md) | Reavaliar habilidades com valores canônicos | Não reavaliado |
| [H.14 — Estratégias de IA](./etapa-h14-ai-strategy-comparison.md) | Preservar baseline e tratar políticas alternativas como experimentais | Não reavaliado |
| [H.15 — Relatório consolidado](./etapa-h15-combat-balance-report.md) | Usar recomendações como hipóteses, não como fatos canônicos | Não validado |
| [H.16 — Validação final](./etapa-h16-final-combat-balance-validation.md) | Reutilizar evidência de reprodutibilidade sintética | Não extrapolado |

- Batalhas canônicas executadas: **0**.
- Seeds, snapshots e resultados por personagem/inimigo: **não aplicáveis**.
- Classificação de equilíbrio, dominância ou fraqueza canônica: **dados insuficientes**.
- Nenhuma recomendação de alteração pode ser sustentada nesta fase bloqueada; nenhuma regra, atributo, habilidade, custo, IA oficial ou dado canônico foi alterado.

## 6. Validade das conclusões

### Fatos demonstrados por evidência local

- A configuração atualmente carregada é de desenvolvimento e referencia um banco local chamado `cronicas_do_reino_dev`.
- O código Alembic tem um único head: `d129a4c7e601`.
- O diretório padrão de assets não existia durante a inspeção.
- A API iniciou e respondeu `200` em `/health`; isso é um health check sem consulta ao banco.
- O frontend respondeu `200` e a página pública foi aberta no navegador.

### Hipóteses que precisam de novos experimentos

- As conclusões sintéticas H.11–H.16 podem ou não se manter com o catálogo real.
- Não há evidência sobre equilíbrio de personagens, inimigos, bosses, equipamentos ou habilidades canônicas.

### Conclusões dependentes do catálogo canônico

- Inventário, integridade relacional, métricas de combate, desempenho por cenário e recomendações quantitativas dependem de snapshot autorizado do destino correto e de simulações isoladas.

### Questões sem evidência suficiente

- Identidade do banco canônico, revisão Alembic instalada, privilégios efetivos, backup recuperável, presença de administrador, conteúdo e permissões de leitura do catálogo.

## 7. Site e serviços

- Backend FastAPI iniciado em `http://127.0.0.1:8000`; `/health` retornou `200 OK`.
- Frontend iniciado em `http://127.0.0.1:8080`; `/` retornou `200`.
- A página pública foi aberta no navegador integrado em `http://localhost:8080/`.
- O health check não testa conectividade PostgreSQL. O login administrativo e rotas que leem o catálogo não foram usados.
- Os servidores foram vinculados somente a loopback. Nenhum bootstrap foi executado.

## 8. Testes, integridade e pendências

- Suíte backend não PostgreSQL: **236 aprovados, 1 ignorado, 12 excluídos**. Foi executada com o diretório de trabalho temporário e sem `DATABASE_URL`/`TEST_DATABASE_URL`, para não carregar `backend/.env`; os 12 testes marcados para PostgreSQL foram excluídos.
- Frontend: **58 testes aprovados**; `tsc --noEmit` aprovado; build aprovado; ESLint sem erros e com **7 avisos** preexistentes.
- Python: `compileall` aprovado; `pip check` aprovado, sem dependências quebradas.
- Alembic: `heads` somente leitura; head do código `d129a4c7e601`. Estado do banco não consultado.
- Consultas PostgreSQL, testes PostgreSQL, migrations e simulações canônicas: **não executados**, pois o alvo não foi identificado e protegido.
- Não houve alteração de dados persistentes, permissões, credenciais ou `.env`.
- Os arquivos JSON/CSV acompanham este relatório e registram explicitamente dados não obtidos, em vez de contagens inventadas.

**Próximo passo:** obter confirmação autorizada do ambiente canônico e evidências de identidade, privilégios de leitura e backup recuperável. Repetir então a auditoria; se as guardas administrativas continuarem incompatíveis, manter o bootstrap pendente para o operador de deploy autorizado.
