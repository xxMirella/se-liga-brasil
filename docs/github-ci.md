# Validação contínua e entrega

O workflow `.github/workflows/quality.yml` executa em pushes, pull requests e acionamento manual. Não recebe credenciais de produção. As Actions e as imagens do PostgreSQL e Gitleaks são fixadas por hash; Dependabot propõe atualizações.

## Validações obrigatórias

- Ruff verifica sintaxe, imports, erros comuns e complexidade ciclomática.
- `python scripts/check_quality.py` bloqueia funções acima de 60 linhas, escore cognitivo estrutural acima de 15, profundidade acima de 3 e violações de separação entre domínio e infraestrutura. Esses limites são heurísticas; revisão humana de semântica e custo algorítmico continua necessária.
- O contrato de configuração exige todos os nomes em `.env.example`, sem nenhum valor preenchido. Não lê `.env`, `.env.storage` ou chaves reais. A forma dos endpoints, caminhos e opções é validada por testes dos adaptadores; validade ou permissão de uma chave real não é testada em CI.
- A verificação de caminhos rastreados bloqueia `data/`, arquivos `.env` preenchíveis e chaves SSH privadas antes da entrega. O exemplo vazio `.env.example` é permitido.
- Gitleaks varre todo o histórico Git com saída redigida. Uma detecção bloqueia o workflow; uma chave comprometida deve ser revogada, e remover apenas a linha atual não limpa o histórico.
- Pytest executa testes unitários e integração contra PostgreSQL 17 descartável. Cada teste SQL usa schema aleatório e rollback. Nunca configure `TEST_DATABASE_URL` com produção.
- Coverage mede todo `src`, incluindo branches, e exige **95%**. Não há exclusões de módulos para inflar o número. XML, HTML e JUnit são preservados mesmo quando o limite falha.

Cobertura não comprova TDD: a ordem teste falhando → implementação → refatoração deve ser seguida no desenvolvimento e demonstrada na revisão. Os testes adicionais priorizam conflitos, limites, erros, repetição e integridade dos dados.

## Reprodução local

Em Python 3.12 ou superior:

```sh
python -m pip install -r requirements.lock
python -m pip install --no-build-isolation --no-deps -e .
ruff check src tests scripts
python scripts/check_quality.py
TEST_DATABASE_URL=postgresql://usuario:senha@127.0.0.1:5432/banco_descartavel python -m coverage run -m pytest -q --junitxml=reports/tests.xml
python -m coverage xml --fail-under=0
python -m coverage html --fail-under=0
python -m coverage report
se-liga-brasil build-static-site --output-directory dist/public
```

A variável do exemplo aponta exclusivamente para um banco de testes. Sem ela, os testes SQL são pulados e a cobertura não representa o pipeline completo.

## Entrega e ativação no GitHub

Após os checks aprovarem, o workflow gera o artefato `public-static-site` com a página educativa estática. O pacote não inclui arquivos originais, dados privados, credenciais ou cache de perfis. O relatório de qualidade fica em outro artefato com retenção de sete dias.

O diretório atual ainda não é um checkout Git e não tem remoto configurado. Portanto, o workflow está preparado localmente e não foi executado no GitHub. Para ativá-lo, é necessário disponibilizar o projeto em um repositório GitHub e enviar estes arquivos. Depois, configure `quality` e `secrets` como checks obrigatórios na proteção da branch.

Publicação automática em hospedagem depende do destino escolhido e sua configuração de deploy. Não há deploy remoto configurado. O artefato estático não substitui a hospedagem da API, da busca e dos perfis dinâmicos.

## Estado da cobertura

O limite de 95% é obrigatório e não foi relaxado. Em 19/10/2026, a medição completa
com PostgreSQL 17 descartável alcançou **95,90%**, com **1.521 testes aprovados**.
A medição inclui linhas e ramificações de todo `src`, sem excluir módulos para
elevar a porcentagem. O ponto inicial da suíte offline era aproximadamente 70%.
Os relatórios XML, HTML e JUnit ficam em `reports/` e são regenerados pelo workflow.
Uma execução posterior abaixo de 95% bloqueará a entrega.

O ambiente exato Python 3.12 também foi validado em container durante o trabalho;
a última medição consolidada acima foi executada no Python 3.13 local. Isso não
substitui uma execução do workflow no GitHub, ainda pendente de repositório remoto.
