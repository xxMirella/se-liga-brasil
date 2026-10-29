# Orientação do governo Itamar Franco (1992–1994)

Revisão: 28/10/2026. Sem deploy, mudança de CSS, de painel ou de classificação de partidos.

## Resultado

**O governo Itamar Franco não é classificado como direita, nem como centro-direita.** As fontes consultadas descrevem uma coalizão heterogênea, que se deslocou ao centro desde meados de 1993, e leituras divergentes da agenda (continuidade liberalizante nas privatizações contra elementos desenvolvimentistas e sociais). Nenhuma fonte consultada atribui ao governo, em bloco, o rótulo centro-direita. O catálogo registra **Classificação controversa**, categoria já usada para o início do governo Sarney, e não presume centro.

- Exercício: 02/10/1992 (interino, após o afastamento de Collor) até 01/01/1995, fim exclusivo, conforme o [Arquivo Nacional](https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/assuntos/biografias/203-itamar-augusto-cautiero-franco) e o registro `arquivo-nacional-president:203:1992-10-02`. A posse como presidente em 29/12/1992 não reinicia o exercício; o mandato formal termina em 31/12/1994.
- Linha do tempo: 1992 mostra Collor (Direita, até 02/10/1992, fim exclusivo) e Itamar (controversa, desde 02/10/1992), com o rótulo "Classificação controversa / Direita" e subperíodos preservados; 1993 e 1994 mostram Classificação controversa; 1995 pertence a FHC (Direita), sem Itamar.
- A filiação (PRN em 1989; PMDB desde 1992, segundo o Arquivo Nacional) e a de FHC como ministro da Fazenda não participam da classificação.

## Coalizão

Brasilio Sallum Jr., [O governo Itamar e a democracia de 1988](https://www.scielo.br/j/sant/a/6myNQV64TbN7cqwNtYkPBwH/?lang=pt), *Sociologia & Antropologia*, 2021 (DOI 10.1590/2238-38752021v11111): o governo reuniu PMDB, PSDB, PFL, PSB, PTB, PDT e PDS, além de ministros sem partido "de orientações políticas heterogêneas, ainda que predominantemente de esquerda"; o campo majoritário ia "da esquerda moderada à direita"; "de meados de 1993 em diante ela se deslocou em direção ao centro político, perdendo os seus componentes de esquerda". O PT recusou o ministério e se definiu como "oposição ativa propositiva".

Marcus Ianoni, [Políticas Públicas e Estado: o Plano Real](https://www.scielo.br/j/ln/a/zJXFW8TvZp35jQjQD7psypt/?lang=pt), *Lua Nova*, n. 78, 2009: "Era uma coalizão ampla, mas sem um programa consistente"; atores do velho desenvolvimentismo, inclusive Itamar, ainda estavam em cena, sobretudo até meados de 1993; FHC foi o quarto ministro da Fazenda em sete meses.

## Agenda

- **Plano Real**: conduzido pela equipe de FHC na Fazenda desde 1993 (URV em 1994, moeda em julho de 1994). Estabilização monetária, sozinha, não decide orientação (mesma cautela adotada para FHC).
- **Privatizações**: continuaram as herdadas de Collor (CSN em 02/04/1993, Açominas, Cosipa). Sallum Jr. as vê como moderação do impulso liberal: "maior controle da Presidência" e ritmo mais lento. Carlos Henrique Lopes Rodrigues e Vanessa Follmann Jurgenfeld, [O neoliberalismo no governo Itamar Franco](https://www.revistasep.org.br/index.php/SEP/article/view/698/334), *Revista da SEP*, n. 60, 2021, leem as privatizações de 1993–1994 (siderurgia, petroquímica, fertilizantes, Embraer, 100% de capital estrangeiro) como agenda neoliberal e contestam a imagem nacionalista.
- **Política social**: Consea (abril de 1993), Plano de Combate à Fome e à Miséria e LOAS (dezembro de 1993), segundo Sallum Jr. Também figuram no registro do Arquivo Nacional IPMF, plebiscito de 1993 e Comissão de Mortos e Desaparecidos.
- Contexto: [Agência Senado, 2011](https://www12.senado.leg.br/noticias/materias/2011/07/02/ex-presidente-itamar-franco-lancou-plano-real-participou-das-diretas-ja-e-da-constituinte) (texto jornalístico, apenas fatos).

## Contrapontos e limites da inferência

- As leituras divergem: coalizão da esquerda moderada à direita e depois ao centro (Sallum Jr.), ausência de programa consistente (Ianoni) e agenda neoliberal (Rodrigues e Jurgenfeld). Reduzi-las a "direita" apagaria as duas primeiras; reduzi-las a "centro" seria presunção sem fonte que use o termo para o governo.
- Rodrigues e Jurgenfeld focam privatizações; Ianoni, o Plano Real; Sallum Jr. cobre sobretudo o período anterior à revisão constitucional de outubro de 1993 e ao Plano Real. Nenhuma fonte mede o governo ano a ano; o recorte anual do catálogo é operacional e não afirma mudança em 01/01/1993 ou 01/01/1994.
- A pesquisa não localizou verbete do CPDOC/FGV sobre Itamar acessível; ele não foi usado. Os artigos acadêmicos foram lidos por extração de texto, não por arquivamento dos bytes originais: o SHA256 do registro identifica as notas revisadas locais (`data/executive-orientation/br-presidency-itamar-franco-1992-1994-reviewed-notes.txt`).
- Nada aqui classifica o PMDB, PSDB, PFL, aliados ou o Congresso, nem mede resultados econômicos.

## Implementação e validação

Um registro `br-presidency-itamar-franco-1992-1994` foi acrescentado a `src/service/political_dashboard/executive_orientation_evidence.json` (versão 2026-10-28.4), com `valid_years` 1992–1994, `period_start` 1992-10-02, `period_end_exclusive` 1995-01-01 e `formal_mandate_end` 1994-12-31. Nenhum código foi alterado: `classify_executive_orientation` recorta o ano pelo exercício e `executive_orientation_cell` já preserva subperíodos. A página de fontes renderiza o registro automaticamente (13 registros).

`tests/test_itamar_franco_orientation.py` cobre 1992, 1993 e 1994 (cobertura recortada), 1991/1995/1996 sem vazamento, a transição Collor→Itamar em 1992, a transição Itamar→FHC em 1995, a rejeição de direita forçada e a unicidade do exercício. Teste de hash existente cobre a nota arquivada.
