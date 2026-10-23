# Ingestão de votações do Senado

O comando `collect-votes --source senado --start-date YYYY-MM-DD --end-date YYYY-MM-DD` consulta `votacao.json` da API oficial, versão 2, por intervalos mensais. O padrão permite uma partição e 25 votações; `--max-partitions` e `--limit` aumentam explicitamente os limites. O intervalo final é inclusivo. A aquisição reutiliza cache, bloqueio por fonte e política de espera após indisponibilidade.

No dataset público, o link de detalhes aponta para a lista nominal em `https://www25.senado.leg.br/web/atividade/materias/-/materia/{codigoMateria}/votacoes`. O identificador é o `codigoMateria` publicado no registro da votação, nunca o `idProcesso`; quando não há código válido, o link permanece ausente. O endpoint técnico do processo fornece dados da proposta, mas não substitui a evidência do voto individual.

Os arquivos originais são preservados. Perfis oficiais já baixados identificam pessoas por nome completo normalizado e data de nascimento, com correspondência única na tabela `person`. O código pessoal do provedor existe apenas durante a execução. Homônimos ou perfis sem comprovação ficam sem vínculo automático; a aquisição padrão não faz requisições adicionais por votante.

A migração 0017 prepara `voting`, `person_vote` e `person_vote_revision`. A projeção também preenche `institution`, `proposition` e a proveniência em `source_record`. A data é armazenada com precisão de dia, sem horário inventado. Turnos são eventos separados. Correções de votos encerram a revisão anterior e criam outra; repetição do mesmo fato não cria revisão adicional. Uma correção explícita para votação secreta remove o voto individual vigente, preservando o histórico privado.

Favor, contra, abstenção e obstrução são escolhas. Ausência, presidência, licença e voto não registrado são estados de participação distintos. O resultado coletivo não é inferido a partir dos votos individuais. O partido observado na votação não altera automaticamente a filiação atual.

Limites atuais: apenas o canal do plenário; não comprova comissões nem toda a vida pública. Registros sem processo associado são rejeitados para análise, sem criar uma proposição fictícia. A vinculação depende de perfis oficiais previamente disponíveis e da identificação segura na base. A implementação não publica automaticamente dados no frontend.

## Aquisição limitada de perfis

`--max-identity-profiles 10` autoriza até dez aquisições de perfis oficiais ausentes por execução. O padrão é zero e o teto é 100. Perfis e solicitações são deduplicados entre turnos e partições, reutilizando cache. Cada perfil único pode exigir uma requisição; não há repetição por voto ou turno. Identidades novas são consultadas em lote no banco. Perfis incompletos e homônimos continuam sem vínculo. HTTP 429 interrompe a coleta e respeita a espera da fonte. Baixar perfis não comprova cobertura histórica nem garante correspondência com as pessoas cadastradas.

## Reprocessamento sem rede

`collect-votes --source senado --start-date 2026-10-14 --end-date 2026-10-14 --local-only`
reprocessa exclusivamente o arquivo oficial já arquivado para esse intervalo exato.
O modo verifica URL e checksum, mantém as datas de observação e falha se o arquivo
não existir ou tiver sido alterado. Não abre cliente HTTP, não baixa novos perfis
e não modifica o cooldown. `--max-identity-profiles` deve permanecer zero.

Esse comando atualiza a projeção SQL. Para atualizar o dataset usado pelos perfis,
usar `run-voting-pipeline --source senado --start-date 2026-10-14 --end-date 2026-10-14 --cached-only`.
Nesse segundo comando, `--local-only` significa não publicar no Storage, conforme a
documentação do pipeline. `--cached-only` evita aquisição remota no Senado, mas
permite publicar o resultado no bucket privado. Não busca novos detalhes de matérias;
descrições sem evidência continuam desconhecidas.

Execução em 22/10/2026: a reaplicação do original de 14/10/2026 ampliou o vínculo de
uma para cinco pessoas, com dez registros de participação em duas votações e oito
novos vínculos. Foram publicados dez registros no dataset diário. A leitura pública
de Flávio Bolsonaro e Marcos Pontes retornou dois registros para cada um. A cobertura
continua parcial: outros 152 registros nominais do arquivo ainda não têm vínculo
pessoal confirmado. Participação em votação não é frequência diária ou mensal.
