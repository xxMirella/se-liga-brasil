BEGIN;
SET LOCAL lock_timeout='10s';
ALTER TABLE se_liga_brasil.person_data_gap
 DROP CONSTRAINT person_data_gap_assigned_source_check,
 ADD CONSTRAINT person_data_gap_assigned_source_check
 CHECK(assigned_source IN ('tse','alesp','camara','alerj','senado','tse_filiation'));
INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method)
VALUES('alerj','Assembleia Legislativa do Rio de Janeiro','https://www.alerj.rj.gov.br','download'),
 ('senado','Senado Federal','https://www.senado.leg.br','api'),
 ('tse_filiation','Tribunal Superior Eleitoral — filiação','https://www.tse.jus.br','download')
ON CONFLICT(code) DO NOTHING;
COMMIT;
