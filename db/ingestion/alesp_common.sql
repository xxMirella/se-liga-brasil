DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url)
VALUES('alesp','Assembleia Legislativa de São Paulo','state','SP','https://www.al.sp.gov.br')
ON CONFLICT(code) DO NOTHING;
