# Recuperação de fotos oficiais já disponíveis

O serviço `service.profile_media` verifica perfis Câmara/Senado já ingeridos com vínculo pessoal verificado. Não pesquisa pessoas por nome isolado nem cria vínculos com sequenciais externos. A projeção utiliza o `person_id` já atribuído e a referência `source_record_id` do perfil validado.

Execute a partir da raiz do projeto:

```bash
PYTHONPATH=src .venv/bin/python -m service.profile_media --env-file /caminho/ambiente.env
```

O comando é somente diagnóstico por padrão. Para aplicar propostas de atualização, acrescente `--apply`. `--data-directory` aponta para o diretório de enriquecimento com subpastas `manifests` e `archives`; o padrão é `data/enrichment`. `--limit` limita perfis examinados, com máximo de 10.000, e a resposta sinaliza eventual truncamento. A saída contém apenas contagens e cobertura, sem nomes, documentos ou credenciais.

## Pipeline

1. Consultar em lote os fatos de perfil verificados da Câmara e Senado, escolhendo a observação mais recente por pessoa/fonte. Excluir aliases. Exigir que o UUID do payload corresponda ao vínculo do fato.
2. Aproveitar `photoUrl` do perfil normalizado. No Senado, se o parser antigo descartou a foto, recuperar o campo `IdentificacaoParlamentar.UrlFotoParlamentar` do download local: manifesto/fonte devem corresponder ao perfil ligado, arquivo deve ficar no diretório permitido e o hash deve coincidir. Conferir nome completo e nascimento contra os dados do perfil previamente identificado.
3. Aceitar apenas hosts oficiais explicitamente permitidos. Converter HTTP para HTTPS somente nesses hosts; rejeitar credenciais, portas inesperadas e fragmentos. Não substituir uma foto HTTPS já válida de outra instituição permitida.
4. Deduplicar propostas por UUID interno e gravar em lote o fato `official_photo`, mantendo `source_record_id`. Atualizar `person.photo_url` somente se o valor anterior ainda coincidir, evitando sobrescrever uma alteração concorrente. As duas operações são uma transação.

O módulo do Senado também foi corrigido para levar a foto na coleta normal: parser `senado-personal-python-v3` e projeção `senado_profile.sql`. Assim o preenchimento não depende exclusivamente da manutenção pontual. A projeção Câmara já traz `photoUrl`.

## Cobertura observada

Na execução de 18/10/2026 havia 15.448 pessoas canônicas e somente quatro perfis institucionais pessoais ligados com os campos necessários: três da Câmara e um do Senado. Todos os quatro tinham foto HTTPS oficial após o preenchimento pontual anterior. A varredura completa não propôs novas atualizações e a repetição manteve as contagens, demonstrando idempotência nesse conjunto.

As outras 15.444 pessoas estavam sem `photo_url` e sem perfil Câmara/Senado pessoal ligado disponível para este serviço. Isso é uma lacuna de coleta/identidade; não significa inexistência de foto na fonte oficial. O serviço não inventa URL a partir de sequencial de candidatura nem associa imagens por nome isolado.

Duas imagens da validação inicial responderam HTTPS 200 com `Content-Type: image/*`. A varredura em lote não requisita cada imagem: ela valida a estrutura/domínio das URLs, reduzindo tráfego. Portanto contagem de URL válida não certifica disponibilidade HTTP de todas as imagens. ALESP/TSE ainda não estão incluídos nesse mecanismo.

## Custo e validação

A consulta é em lote e as escritas usam `jsonb_to_recordset`, sem uma requisição SQL por pessoa. Em Python há leitura dos m manifestos locais e processamento dos p perfis: O(m + p) tempo e O(p) memória de índices e propostas, limitados por execução; cada arquivo elegível tem máximo de 20 MiB. Não há requisições às APIs oficiais nesse comando. A consulta de cobertura total é uma operação administrativa e não é executada nas requisições do frontend.

Testes fictícios cobrem hash imutável, conflito de nascimento, recuperação HTTPS, diagnóstico sem escrita e replay idempotente. A revisão estrutural e Ruff fazem parte da validação do serviço.
