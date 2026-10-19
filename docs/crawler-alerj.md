# Crawler ALERJ

Implementação em `src/crawlers/alerj/`; contrato `collect_alerj_enrichment(connection, storage: Path, people: list[dict], fields: set[str] | None = None)`. Cada pessoa fornece `person_id`, `civil_name`, `display_name`, e opcionalmente `civil_names`/`public_names` já associados à pessoa. Nenhuma nova pessoa é criada pelo conector.

## Fontes verificadas em 17/10/2026

- Lista oficial: https://www.alerj.rj.gov.br/Deputados/QuemSao
- Perfis, exemplo técnico: https://www.alerj.rj.gov.br/Deputados/PerfilDeputado/{codigo}?Legislatura={legislatura}
- Índice mensal: https://transparencia.alerj.rj.gov.br/section/report/73
- PDF setembro/2026: https://www2.alerj.rj.gov.br/leideacesso/verArquivo.asp?idArquivo=2962

Amostras originais preservadas em `data/alerj/research/` (HTML de lista/perfil/índice e PDF de 9.365.334 bytes). Nenhuma ingestão real em massa foi executada. O perfil publica nome parlamentar, nascimento completo, partido e eventos históricos com datas explícitas. Não publica CPF. A folha traz nome civil completo e cargo, sem nascimento ou CPF. O PDF setembro/2026 contém 70 linhas de deputado estadual, todas conciliadas aritmeticamente pelo parser.

## Identidade e ingestão

O nome parlamentar serve exclusivamente para selecionar uma única pessoa candidata a verificação. A folha deve conter exatamente um dos nomes civis já conhecidos dessa pessoa. Nome civil da folha + nascimento do perfil são confirmados no banco pela resolução pessoal existente; deve haver exatamente uma pessoa e o `person_id` esperado. Alias público ambíguo, ausência de nome civil, nascimento divergente ou identidade insuficiente impedem a ingestão. O ID da URL oficial somente navega a fonte; não é salvo como identificador pessoal.

Projeções: pagamento mensal verificado, observação administrativa de partido e fatos de perfil com histórico publicado. O histórico estruturado permanece nos fatos auditáveis; o conector não converte ainda todos esses eventos em períodos jurídicos canônicos. A projeção partidária atual preserva vigência de informação SCD2. Observação não é data jurídica de entrada.

O PDF contém 14 componentes financeiros: base, comissão, representação, incorporado, triênio, abono, férias, redutor, IPALERJ, pensão alimentícia, previdência, imposto de renda, indenização e líquido. O parser exige layout de deputado, soma remunerações e descontos com Decimal e valida bruto − descontos = líquido. Indenizações permanecem separadas do líquido. O campo legado `tax_amount` recebe o agregado de descontos, com composição e escopo explícitos no payload; não significa exclusivamente imposto. Pensão alimentícia descontada não significa beneficiário pensionista.

## Limites explícitos

O formulário de situação usa POST; o GET com parâmetro `situacaoDeputado=1` não confirmou seleção explícita no retorno. Lista na legislatura e pagamento mensal não comprovam exercício na data atual. Por isso o perfil normalizado mantém `inExercise=null`, não produz fato positivo ou negativo de cargo e não altera desconhecido para falso. A flag da pessoa depende de outra observação administrativa comprovada. `current_public_office` permanece não atendido por este conector.

Atividade legislativa usa a plataforma institucional Lotus Notes, cuja chave, paginação e contrato de autoria ainda precisam de validação. O coletor retorna `political_activity` como capacidade não atendida; biografia e alegações de impacto não viram proposituras ou leis aprovadas.

## Custo e segurança operacional

`SUPPORTED_FIELDS` contém apenas `current_salary` e `current_political_party`. Solicitações exclusivamente de campos não suportados retornam sem HTTP nem banco. `deferred_person_ids` informa os alvos excedentes ao limite.

Uma execução baixa/cacheia uma lista, um índice e a folha mais recente para atender todas as pessoas solicitadas; perfis são limitados a 25 pessoas por execução. Aquisição compartilha allowlist HTTPS, cache, orçamento de bytes, pacing, cooldown e retries existentes. PDFs requerem `pdftotext` instalado (Poppler); ausência gera erro explícito, sem ingestão parcial de números. Originais nunca são reescritos; bundles registram os hashes das três evidências usadas na identidade. Staging inclui escopo de pessoas e checksum, e o repositório compartilhado mantém idempotência.

Índice de aliases e seleção são O(p+a+r), sendo p pessoas, a aliases e r parlamentares; lookup em dicionário é O(1) médio. Leitura do PDF é O(n) nas linhas. A confirmação pessoal executa até 25 consultas pontuais por lote; não é uma promessa de O(1) global. Nenhuma busca é feita candidato por candidato nos milhares de nomes que não constam da lista institucional.
