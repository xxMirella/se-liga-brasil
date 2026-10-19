# Ingestão de votações do Senado

O comando `collect-votes --source senado --start-date YYYY-MM-DD --end-date YYYY-MM-DD` consulta `votacao.json` da API oficial, versão 2, por intervalos mensais. O padrão permite uma partição e 25 votações; `--max-partitions` e `--limit` aumentam explicitamente os limites. O intervalo final é inclusivo. A aquisição reutiliza cache, bloqueio por fonte e política de espera após indisponibilidade.

Os arquivos originais são preservados. Perfis oficiais já baixados identificam pessoas por nome completo normalizado e data de nascimento, com correspondência única na tabela `person`. O código pessoal do provedor existe apenas durante a execução. Homônimos ou perfis sem comprovação ficam sem vínculo automático; a aquisição padrão não faz requisições adicionais por votante.

A migração 0017 prepara `voting`, `person_vote` e `person_vote_revision`. A projeção também preenche `institution`, `proposition` e a proveniência em `source_record`. A data é armazenada com precisão de dia, sem horário inventado. Turnos são eventos separados. Correções de votos encerram a revisão anterior e criam outra; repetição do mesmo fato não cria revisão adicional. Uma correção explícita para votação secreta remove o voto individual vigente, preservando o histórico privado.

Favor, contra, abstenção e obstrução são escolhas. Ausência, presidência, licença e voto não registrado são estados de participação distintos. O resultado coletivo não é inferido a partir dos votos individuais. O partido observado na votação não altera automaticamente a filiação atual.

Limites atuais: apenas o canal do plenário; não comprova comissões nem toda a vida pública. Registros sem processo associado são rejeitados para análise, sem criar uma proposição fictícia. A vinculação depende de perfis oficiais previamente disponíveis e da identificação segura na base. A implementação não publica automaticamente dados no frontend.

## Aquisição limitada de perfis

`--max-identity-profiles 10` autoriza até dez aquisições de perfis oficiais ausentes por execução. O padrão é zero e o teto é 100. Perfis e solicitações são deduplicados entre turnos e partições, reutilizando cache. Cada perfil único pode exigir uma requisição; não há repetição por voto ou turno. Identidades novas são consultadas em lote no banco. Perfis incompletos e homônimos continuam sem vínculo. HTTP 429 interrompe a coleta e respeita a espera da fonte. Baixar perfis não comprova cobertura histórica nem garante correspondência com as pessoas cadastradas.
