# Hospedagem sem cartão ou teste de 30 dias

Pesquisa em fontes oficiais em 18/10/2026. Planos podem mudar; confirmar o plano
Free no momento do cadastro. Nenhuma conta foi criada ou serviço publicado.

## Opções que atendem documentalmente ao requisito

**Netlify Free para o guia estático:** plano contínuo, sem cartão e com uso
comercial permitido. O anúncio de 2024 confirma essas condições, mas seus
limites antigos não devem ser usados: o plano atual usa 300 créditos mensais
compartilhados entre deploys, tráfego e requisições. Ao esgotar a quota,
o serviço pode ficar suspenso até renovar o período. Não hospeda nosso servidor
Python persistente. Publicar somente `dist/public`, com o backend configurado.

- https://www.netlify.com/blog/introducing-netlify-free-plan/
- https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/
- https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/how-credits-work/

**Render Free para uma futura API Python de demonstração:** admite operação
sem método de pagamento; o web service não tem a expiração de 30 dias do banco
Postgres Free. Podemos manter o Supabase existente. O serviço dorme após 15
minutos sem tráfego e pode levar cerca de um minuto para voltar. Disco efêmero,
quota mensal e suspensão por consumo. Não escolher para prometer navegação
sempre rápida ou milhões de acessos. A própria documentação desaconselha Free
para produção. Nosso servidor atual é restrito a loopback: é necessário o
servidor de produção antes de publicar API. Crawlers ficam separados.

- https://render.com/docs/free
- https://render.com/docs/faq
- https://render.com/docs/compute-plans

## Alternativa com requisito de cartão ainda não confirmado

**Cloudflare Pages:** plano estático gratuito contínuo; 500 builds/mês,
20 mil arquivos, 25 MiB por arquivo e tráfego estático gratuito. Na pesquisa
não encontramos declaração oficial explícita sobre cartão para Pages;
portanto não tratar esse requisito como confirmado. Pages é diferente de R2,
que não atende à exigência atual relatada pela usuária. Não executa diretamente
nosso servidor Python convencional.

- https://developers.cloudflare.com/pages/platform/limits/
- https://developers.cloudflare.com/pages/functions/pricing/

## Descartados para esta exigência

Koyeb exige cartão/pré-autorização. PythonAnywhere tem expiração mensal do web
app gratuito sob as regras atuais. Vercel Hobby restringe uso a pessoal não
comercial. GitHub Pages restringe hospedagem de negócios/SaaS comercial.

- https://www.koyeb.com/docs/faqs/pricing
- https://help.pythonanywhere.com/pages/FreeAccountsFeatures/
- https://vercel.com/docs/plans/hobby
- https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits

Para começar sem cartão com confirmação documental, a opção estática é Netlify.
A publicação e escolha do backend são etapas separadas; gratuidade não equivale
a disponibilidade garantida, quota ilimitada ou suporte comprovado à escala.
