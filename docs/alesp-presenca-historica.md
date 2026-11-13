# Evidências históricas de participação na ALESP

A coleta ALESP acionada para `attendance` ou `political_activity` inclui o coletor de participação. A completude de presença aceita evidências históricas verificadas, com data do evento, sem exigir que sejam recentes.

Fontes consultadas:

- Exportação oficial de presença em comissões, com matrícula e nome parlamentar conferidos contra a identidade já verificada.
- API de presença em plenário, aceitando somente a situação `Presente`.
- Listas `parlamentaresPresentes` de reuniões realizadas, incluindo audiências quando publicadas nesse catálogo.
- Atas e transcrições descobertas pelos documentos das reuniões e pelas íntegras das sessões, incluindo sessões solenes. Leitura de HTML e PDFs com texto, usando `pdftotext`.

Nas atas, o parser reconhece listas explícitas de presentes, inclusive membros efetivos e substitutos. Nas transcrições, reconhece falas atribuídas nominalmente. Menções livres, listas de convidados, eventos futuros, ausências, licenças e chamadas seguidas de `(Pausa.)` não comprovam presença. Nomes com mais de uma identidade verificada são excluídos da resolução por nome. PDFs sem texto são reportados como `ALESP_PARTICIPATION_OCR_REQUIRED`.

Os arquivos e hashes ficam em `data/alesp/participation/manifest.json`. A fila em `queue.json` permite retomar documentos e páginas históricos. Cada execução faz até 40 requisições, respeitando o limite total de bytes da configuração ALESP. URLs já arquivadas são reaproveitadas. A pesquisa mensal do plenário começa pelos últimos 12 meses completos; o histórico anterior também é percorrido nas páginas de sessões e transcrições.

A projeção `alesp_participation` registra fatos com pessoa, data, evento, canal, nome identificado, trecho comprobatório, URL e hash do arquivo. Evidências de canais diferentes podem documentar o mesmo evento. A contagem de evidências não representa quantidade de dias presentes nem frequência percentual. Presença histórica não completa automaticamente a cobertura de proposições, votos ou leis.

O diagnóstico local da validação de 05/11/2026 está em `data/enrichment/audits/alesp-participation-validation-20261105.json`. Essa validação baixou e analisou fontes reais, sem gravar os novos fatos no banco.
