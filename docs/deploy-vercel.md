# Portal público na Vercel

O entrypoint de produção é `app:app`, declarado em `pyproject.toml`. `app.py`
exporta o adaptador WSGI de `application.vercel`; não inicia o servidor HTTP local
e não importa testes. O preset Python encaminha as rotas ao mesmo portal usado
localmente, incluindo HTML, JSON, CSS e o script da busca.

Na Vercel, configurar as variáveis de ambiente do servidor:

- `DATABASE_URL`: conexão PostgreSQL utilizada pelas projeções públicas.
- `SUPABASE_STORAGE_URL` e `SUPABASE_STORAGE_KEY`: endpoint HTTPS e chave para
  leitura dos datasets privados de votação. As alternativas já suportadas pelo
  projeto são `SUPABASE_PROJECT_ID` e `SUPABASE_SERVICE_ROLE_KEY`.

Não preencher esses valores em arquivos versionados. A configuração local
`.env.storage`, datasets, ambientes virtuais e relatórios são excluídos do upload
pela `.vercelignore` e do bundle por `vercel.json`. Os diretórios `db/`, `config/`
e os assets em `src/` continuam disponíveis ao código.

A inicialização não conecta ao banco nem lê o Storage. A página inicial e os
assets funcionam sem credenciais. As consultas de perfil precisam do banco;
votações inicializam o Storage na primeira consulta. Falhas retornam 503 sem
expor credenciais. O runtime inclui DuckDB para consultar os Parquets.

O cache de datasets usa `/tmp/se-liga-brasil-public-cache`, com o orçamento já
existente de 256 MiB. Esse disco é temporário e separado por instância: um cursor
de histórico pode expirar com 410 se a próxima requisição chegar a outra
instância ou após reinício. A interface permite reiniciar a consulta. Para
garantir paginação estável entre instâncias será necessário persistir snapshots
em armazenamento compartilhado; esta adaptação mantém o contrato atual.

Validar localmente com `.venv/bin/python -m pytest tests/test_vercel_entrypoint.py`.
O build remoto da Vercel ainda deve ser executado após publicar essas alterações;
os testes WSGI não substituem a verificação do bundle e das variáveis no ambiente
remoto.

Referências: [Python Runtime](https://vercel.com/docs/functions/runtimes/python)
e [vercel.json](https://vercel.com/docs/project-configuration/vercel-json).
