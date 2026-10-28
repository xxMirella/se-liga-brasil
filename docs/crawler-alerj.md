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

## Diagnóstico de evidência incompleta

O parser v3 distingue nascimento não publicado (`ALERJ_BIRTH_DATE_MISSING`), nascimento inválido ou duplicado (`ALERJ_BIRTH_DATE_INVALID`, `ALERJ_BIRTH_DATE_AMBIGUOUS`), legislatura atual ausente (`ALERJ_CURRENT_LEGISLATURE_MISSING`) e eventos de filiação com data inválida (`ALERJ_AFFILIATION_DATE_INVALID`). Cada código chega individualmente a `identity_unresolved`, sem transformar uma falha em atualização concluída. Um histórico partidário não publicado é representado por eventos vazios e `affiliationHistoryStatus=not_published`; isso não impede a confirmação do pagamento quando nome civil e nascimento comprovam a identidade. Nenhuma data de filiação é inferida.

Nascimento só é extraído da seção explicitamente identificada, em data por extenso ou `dia/mês/ano`. Datas da biografia, posse e troca partidária não comprovam nascimento. A ausência dessa informação impede a confirmação independente necessária ao pagamento, mesmo quando a base já conhece uma data eleitoral. É preciso obter outra evidência oficial suficiente para desbloquear esse caso.

`ALERJ_PAYROLL_IDENTITY_REVIEW_REQUIRED` também cobre nomes civis conhecidos sem correspondência na folha atual e múltiplas correspondências possíveis. O nome parlamentar da lista não substitui o nome civil na folha. Nenhum desses casos permite vincular remuneração por semelhança ou partido político.

## Vínculos de nomes revisados

`normalization.name_variants.classify_name_variant` distingue equivalência após normalização,
iniciais compatíveis, sufixos como `JR/JUNIOR` e partículas como `DE`. A classificação
descreve uma variação textual; não confirma identidade nem une homônimos automaticamente.
O custo é linear no tamanho dos nomes, com comparação dos tokens por posição.

Quando existe aprovação humana explícita, `service.identity_resolution.reviewed_names`
valida pessoa canônica, nomes registrados e publicados, fonte, competência e hash do arquivo.
Recipientes ou pessoas repetidos na mesma revisão são rejeitados. A decisão fica no registro
de origem do pagamento com sua referência de revisão; o nome original da folha é preservado.
`crawlers.alerj.reviewed_payroll.collect_reviewed_payroll` usa o mesmo parser, armazenamento
imutável e projeção idempotente dos demais pagamentos. Uma aprovação não é reutilizada para
outra competência ou outro arquivo. A confirmação manual do pagamento não declara cargo em
exercício nem preenche automaticamente filiação ou data de nascimento.

## Sinopses históricas da atividade parlamentar

O comando `scripts/collect_alerj_history.py` ingere narrativas datadas das sinopses oficiais,
sem converter discursos, encaminhamentos ou resultados coletivos em votos nominais.
A primeira fonte validada é
[Sinopse de Flávio Bolsonaro, 2018](https://www2.alerj.rj.gov.br/leideacesso/spic/arquivo/Flavio_Bolsonaro_2018.pdf).
O [perfil histórico ALERJ](https://www.alerj.rj.gov.br/Deputados/PerfilDeputado/275)
informa nome parlamentar e nascimento. A ponte independente é o JSON oficial do Senado,
que contém nome parlamentar, nome civil e nascimento, já arquivado com hash validado.
O nome civil e nascimento precisam corresponder univocamente à pessoa canônica; o nome
isolado do PDF nunca autoriza a associação. Esse caminho atende também outros ex-deputados
identificados no Senado; pessoas sem essa ponte ficam pendentes de evidência independente.

Exemplo (substituir o caminho do arquivo de ambiente local, sem publicar credenciais):

```bash
.venv/bin/python scripts/collect_alerj_history.py \
  --env-file /caminho/privado/.env \
  --person-id 4c30de36-97ec-4f4c-af89-dd16ff3d99a9 \
  --profile-url https://www.alerj.rj.gov.br/Deputados/PerfilDeputado/275 \
  --senator-code 5894 \
  --synopsis-url https://www2.alerj.rj.gov.br/leideacesso/spic/arquivo/Flavio_Bolsonaro_2018.pdf
```

`--synopsis-url` aceita até dez documentos oficiais explicitamente localizados, sem gerar
centenas de URLs por tentativa. `--offline` reaplica somente arquivos íntegros do cache,
sem requests e sem contornar cooldown. O documento mantém bytes originais, SHA-256,
observação, página PDF, referência da identidade e staging de rejeições. O checkpoint
registra documentos reconciliados, inclusive quando um documento seguinte falha. O
repositório genérico impede duplicação no replay e preserva versões observadas.

O parser usa a data da **sessão**, e não a data posterior do Diário Oficial. Cada narrativa
é `vote_declaration`, `speech`, `voting_procedure` ou `legislative_comment`. Declaração de
voto é evidência de manifestação individual descrita na sinopse, não lista nominal com
placar certificado. Nenhuma dessas entradas cria `person_vote` ou falsa autoria em
`proposition_person`. Ações ficam em `person_fact` com prefixo `alerj_historical_activity:`
e chegam ao histórico mensal do perfil com o link exato `PDF#page=N`. A sinopse não é o
texto integral da proposta; não reutilizar esse link como se fosse a lei votada.

O primeiro lote de 2018 contém 54 narrativas datadas, incluindo quatro declarações de voto,
sem rejeições. É **cobertura parcial**: as tabelas iniciais de autoria do PDF ainda não têm
contrato validado neste parser; tampouco foi comprovada uma enumeração completa de sinopses
para 2000–2017. O perfil de Flávio registra legislaturas a partir de 2003; não se infere
atuação parlamentar em 2000 nem posse pessoal a partir de limites gerais da legislatura.
O portal não deve declarar sua carreira ALERJ completa enquanto essas lacunas existirem.

A aquisição especifica `Accept` compatível com PDF/HTML: a preferência genérica anterior
por JSON provocava HTTP 406 nessa fonte. São preservados allowlist, orçamento, pacing,
locks e política de cooldown compartilhados. Parsing e staging são O(n) no tamanho do
arquivo; o banco reconcilia em lotes e a consulta pública limita mil eventos por perfil,
com indicação explícita de truncamento no contrato.
