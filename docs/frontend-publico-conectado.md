# Frontend público renderizado no servidor

O módulo `src/service/public_profile_web` produz HTML/CSS a partir das projeções
públicas dos serviços de busca, perfil e votos. Não consulta banco, Storage ou
fontes oficiais; o transporte Python fornece os dados. A prévia fictícia em
`docs/prototipo-linha-do-tempo` permanece separada.

## Interface de integração

- `render_search_page(query, results)`: recebe filtros GET (ou texto da busca) e página com
  `items` (`person_id`, `display_name`) e `next_cursor` opcional.
- `render_person_profile(profile, votes, filters)`: recebe o contrato público
  de perfil e a página do serviço de votos; retorna um documento HTML completo.
- `render_error_page(status, message)`: página de erro com texto escapado.
- `public_stylesheet()`: conteúdo do CSS local para `/assets/public-profile.css`.
  Este acesso é ao recurso da aplicação, não aos arquivos de dados.

Rotas HTML esperadas: `/pessoas?q=...` e `/pessoas/{person_id}`. A aba usa
`tab=profile` ou `tab=activity`. Na atuação, formulários GET submetem
`start_date`, `end_date`, `office_kind` e `exercise_id`; o transporte valida o
intervalo máximo de 31 dias. A paginação preserva o recorte e troca o cursor;
a troca de aba remove o cursor da página anterior. Sem intervalo informado,
o transporte pode selecionar os últimos 30 dias. Não existe crawler durante
uma requisição de consulta.

O transporte deve devolver `Content-Type: text/html; charset=utf-8` e servir o
CSS como `text/css`. Recomenda-se CSP sem scripts, `nosniff`, proteção contra
embedding, `Referrer-Policy: no-referrer` e erros genéricos sem SQL ou caminhos.
O HTML não contém JavaScript nem requer conexão do navegador ao Supabase.

## Semântica de apresentação

O perfil mostra foto oficial ou alternativa neutra, idade calculada pelo
serviço, partido com escopo temporal, todos os exercícios atuais disponíveis
e remunerações individualizadas por órgão/competência. Não soma pagamentos
para produzir um suposto salário único. Campo ausente permanece indisponível;
não recebe zero. Partido declarado em eleição não aparece como filiação atual.

A atuação agrupa os votos pelo mês comprovado da votação. Data apenas anual,
desconhecida ou inválida fica em grupo próprio. A entrada deve preservar a
ordenação determinística fornecida pela API. Cada cartão separa matéria,
resumo curto, objeto, turno, participação, voto individual e resultado coletivo.
Um voto sobre parecer, emenda ou turno não é anunciado como aprovação final de
uma lei. Ausência, presidência e voto não registrado não viram voto contrário.
Links externos são HTTPS em domínios governamentais/legislativos oficiais.

Escolaridade é exibida quando disponível na projeção. Bens, trajetória
completa e catálogo de atribuições ainda não estão conectados a esta versão;
a interface explicita esses limites. Não há
nota automática de desempenho nem inferência de inatividade pela falta de
registros. A cobertura exibida vem do contrato do serviço e não certifica toda
a carreira política.

## Segurança, limites e validação

A apresentação usa projeção explícita de campos públicos: não serializa o
objeto de dados inteiro. CPF, nascimento, chaves, hashes e campos privados
adicionais são ignorados. Conteúdo textual e atributos são escapados; URLs com
credenciais, esquema executável ou domínio externo são recusadas.

A renderização limita cada página a 100 votos/resultados, 100 opções de
exercício e 20 vínculos/pagamentos do cabeçalho. A leitura e agrupamento dos
`k` registros da página custam O(k) em tempo e memória; não há chamada remota
ou consulta por registro. O CSS usa os mesmos tons e linguagem visual da
prévia, com layout responsivo, labels de formulários, navegação de teclado,
link para saltar ao conteúdo e indicação da aba corrente.

Testes em `tests/test_public_profile_web.py` cobrem escape de HTML, URLs,
projeção sem campos privados, estados ausentes, escolha versus participação,
agrupamento temporal, filtros/cursor, limite de consumo e separação de
pagamentos. Dados de teste nunca são gravados no banco.
