"""Reviewed locators in the official Paraíba newspaper of 2 January 2023."""

NEWSPAPER_URL = (
    "https://auniao.pb.gov.br/servicos/copy_of_jornal-a-uniao/2023/janeiro/"
    "a-uniao-02-01.2023/@@download/file/Jornal%20em%20PDF%2002-01-23%20CDEPC.pdf"
)
SENATE_URL = (
    "https://www12.senado.leg.br/radio/1/noticia/2023/01/02/"
    "dia-de-posse-27-governadores-assumiram-o-cargo-no-ultimo-domingo"
)

# Page, UF, display name, party explicitly reported at inauguration, mandatory locators.
NEWSPAPER_OBSERVATIONS = (
    (12, "AP", "Clécio Luís", "SOLIDARIEDADE", (
        "Clécio Luís, do Solidariedade", "Ele foi empossado na madrugada de 1º de janeiro")),
    (12, "TO", "Wanderlei Barbosa", "REPUBLICANOS", (
        "de Wanderlei Barbosa, do Republicanos, no Tocantins", "Às8h30damanhãfoiavez")),
    (12, "PA", "Helder Barbalho", "MDB", (
        "No Pará, Helder Barbalho, do MDB, também foi empossado pela manhã",)),
    (12, "RO", "Marcos Rocha", "UNIÃO", (
        "Às15h30,tomouposseem Rondônia o governador também reeleito Marcos Rocha, "
        "do União Brasil",)),
    (12, "AC", "Gladson Cameli", "PP", (
        "No Acre, assumiu o governador reeleito Gladson Cameli, do PP",)),
    (12, "AM", "Wilson Lima", "UNIÃO", (
        "Os demais governadores da Região Norte foram empossados às 17h",
        "No Amazonas, mais uma reeleição. Wilson Lima, do União Brasil",)),
    (12, "RR", "Antonio Denarium", "PP", (
        "Em Roraima, quem assumiu foi Antonio Oliverio Garcia De Almeida",
        "conhecido como Antonio Denarium, do PP",)),
    (12, "RS", "Eduardo Leite", "PSDB", (
        "Eduardo Leite (PSDB) tomou posse como governador "
        "do Rio Grande do Sul neste domingo, 1º",)),
    (11, "BA", "Jerônimo Rodrigues", "PT", (
        "Jerônimo Rodrigues (PT), novo governador da Bahia", "Durante a posse, ontem",)),
    (5, "PB", "João Azevêdo", "PSB", (
        "João Azevêdo (PSB), empossado",)),
    (11, "PE", "Raquel Lyra", None, (
        "A governadora Raquel Lyra foi empossada ontem "
        "pela Assembleia Legislativa de Pernambuco",)),
    (12, "MG", "Romeu Zema", None, (
        "O governador de Minas Gerais, Romeu Zema, foi reconduzido ontem ao cargo",)),
    (11, "SP", "Tarcísio de Freitas", None, (
        "No 2° discurso como governador, Tarcísio de Freitas",)),
    (11, "RJ", "Cláudio Castro", None, (
        "O governador do Rio de Janeiro, Cláudio Castro", "tomou posse na manhã de ontem",)),
)
