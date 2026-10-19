-- Run ONLY in an isolated test database after schema.sql; fixtures roll back.
BEGIN;
INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method)
VALUES('test','Synthetic fixture','https://example.invalid','api');
INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,content_sha256,payload)
SELECT id,'test-record','https://example.invalid',repeat('a',64),'{}' FROM se_liga_brasil.source WHERE code='test';
INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id)
SELECT '00000000-0000-0000-0000-000000000001','test-person','Pessoa Fictícia','Teste',id FROM se_liga_brasil.source_record WHERE external_key='test-record';
INSERT INTO se_liga_brasil.political_party(code,name,abbreviation,source_record_id)
SELECT 'TEST','Partido fictício','TEST',id FROM se_liga_brasil.source_record WHERE external_key='test-record';
INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,observed_on,source_record_id)
SELECT p.id,pp.id,current_date,pp.source_record_id FROM se_liga_brasil.person p CROSS JOIN se_liga_brasil.political_party pp WHERE p.slug='test-person' AND pp.code='TEST';
INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url)
VALUES('TEST','Casa fictícia','state','PA','https://example.invalid');
INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,represented_uf,legislature_key,official_term_key,source_record_id)
SELECT p.id,i.id,'state_deputy','PA','test','term',r.id FROM se_liga_brasil.person p CROSS JOIN se_liga_brasil.institution i CROSS JOIN se_liga_brasil.source_record r
WHERE p.slug='test-person' AND i.code='TEST' AND r.external_key='test-record';
INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,ends_before,capacity,source_record_id)
SELECT id,current_date-10,current_date-5,'holder',source_record_id FROM se_liga_brasil.office_term WHERE official_term_key='term';
-- Five earlier days + two current days; deliberately overlapping record must not double-count.
INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,capacity,source_record_id)
SELECT id,current_date-1,'substitute',source_record_id FROM se_liga_brasil.office_term WHERE official_term_key='term';
INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,capacity,source_record_id)
SELECT id,current_date,'substitute',source_record_id FROM se_liga_brasil.office_term WHERE official_term_key='term';
INSERT INTO se_liga_brasil.proposition(institution_id,official_key,kind,number,year,title,current_status,status_as_of,source_record_id)
SELECT i.id,k,'PL',k,2026,'Projeto fictício',CASE WHEN k='P1' THEN 'approved_in_house' ELSE 'rejected_in_house' END,now(),r.id
FROM se_liga_brasil.institution i CROSS JOIN se_liga_brasil.source_record r CROSS JOIN (VALUES('P1'),('P2')) x(k)
WHERE i.code='TEST' AND r.external_key='test-record';
INSERT INTO se_liga_brasil.proposition_person(proposition_id,person_id,role,source_record_id)
SELECT q.id,p.id,role,q.source_record_id FROM se_liga_brasil.proposition q CROSS JOIN se_liga_brasil.person p CROSS JOIN (VALUES('author'),('coauthor')) x(role)
WHERE p.slug='test-person';
INSERT INTO se_liga_brasil.law(jurisdiction_key,official_key,number,year,title,published_on,source_record_id)
SELECT 'state:PA','L1','1',2026,'Lei fictícia',current_date,id FROM se_liga_brasil.source_record WHERE external_key='test-record';
INSERT INTO se_liga_brasil.proposition_law(proposition_id,law_id,source_record_id)
SELECT q.id,l.id,q.source_record_id FROM se_liga_brasil.proposition q CROSS JOIN se_liga_brasil.law l;
INSERT INTO se_liga_brasil.voting(proposition_id,institution_id,official_key,held_at,subject,method,result,source_record_id)
SELECT id,institution_id,'V1',now(),'Texto base','roll_call','approved',source_record_id FROM se_liga_brasil.proposition WHERE official_key='P1';
INSERT INTO se_liga_brasil.person_vote(voting_id,person_id,choice,participation_status,source_record_id)
SELECT v.id,p.id,'no','voted',v.source_record_id FROM se_liga_brasil.voting v CROSS JOIN se_liga_brasil.person p WHERE p.slug='test-person';
INSERT INTO se_liga_brasil.budget_amendment(jurisdiction_key,official_key,budget_year,amendment_type,source_record_id)
SELECT 'state:PA',k,2026,'individual',r.id FROM se_liga_brasil.source_record r CROSS JOIN (VALUES('A1'),('A2')) x(k) WHERE r.external_key='test-record';
INSERT INTO se_liga_brasil.amendment_person(amendment_id,person_id,role,source_record_id)
SELECT a.id,p.id,'formal_author',a.source_record_id FROM se_liga_brasil.budget_amendment a CROSS JOIN se_liga_brasil.person p WHERE p.slug='test-person';
INSERT INTO se_liga_brasil.amendment_execution_snapshot(amendment_id,slice_key,as_of,execution_year,paid,source_record_id)
SELECT id,'beneficiary:1',current_date-1,2026,100,source_record_id FROM se_liga_brasil.budget_amendment WHERE official_key='A1';
INSERT INTO se_liga_brasil.amendment_execution_snapshot(amendment_id,slice_key,as_of,execution_year,paid,source_record_id)
SELECT id,'beneficiary:1',current_date,2026,150,source_record_id FROM se_liga_brasil.budget_amendment WHERE official_key='A1';
REFRESH MATERIALIZED VIEW se_liga_brasil.person_profile;
DO $$
DECLARE card record; days integer; latest_paid numeric;
BEGIN
 SELECT * INTO STRICT card FROM se_liga_brasil.person_profile WHERE slug='test-person';
 IF card.last_observed_political_party IS DISTINCT FROM 'TEST' THEN RAISE EXCEPTION 'Political party projection failed'; END IF;
 IF card.authored_count<>2 OR card.authored_approved_in_house_count<>1 OR card.authored_rejected_in_house_count<>1 THEN
  RAISE EXCEPTION 'Coauthorship/join deduplication failed';
 END IF;
 IF card.authored_law_count<>1 OR card.formal_amendment_count<>2 THEN RAISE EXCEPTION 'Law/amendment counts failed'; END IF;
 IF card.yes_vote_count<>0 OR card.no_vote_count<>1 THEN RAISE EXCEPTION 'Individual vote conflated with collective result'; END IF;
 IF jsonb_array_length(card.current_offices)<>1 THEN RAISE EXCEPTION 'Current office was duplicated'; END IF;
 IF card.data_coverage<>'[]'::jsonb THEN RAISE EXCEPTION 'Coverage was invented'; END IF;
 SELECT sum(upper(r)-lower(r)) INTO days FROM (
 SELECT range_agg(daterange(e.starts_on,least(coalesce(e.ends_before,current_date+1),current_date+1),'[)')) periods
 FROM se_liga_brasil.office_exercise e JOIN se_liga_brasil.office_term t ON t.id=e.term_id
 WHERE t.person_id=card.person_id AND e.starts_on<=current_date) x CROSS JOIN LATERAL unnest(periods) r;
 IF days<>7 THEN RAISE EXCEPTION 'Exercise duration: expected 7, got %',days; END IF;
 SELECT paid INTO latest_paid FROM se_liga_brasil.amendment_execution_snapshot ORDER BY as_of DESC LIMIT 1;
 IF latest_paid<>150 THEN RAISE EXCEPTION 'Latest snapshot retrieval failed'; END IF;
 BEGIN
  INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,ends_before,capacity,source_record_id)
  SELECT id,current_date+10,current_date,'holder',source_record_id FROM se_liga_brasil.office_term LIMIT 1;
  RAISE EXCEPTION 'Invalid interval accepted';
 EXCEPTION WHEN check_violation THEN NULL;
 END;
 BEGIN
  UPDATE se_liga_brasil.person_vote SET choice='invalid';
  RAISE EXCEPTION 'Invalid vote accepted';
 EXCEPTION WHEN check_violation THEN NULL;
 END;
 IF EXISTS(SELECT 1 FROM pg_tables WHERE schemaname='se_liga_brasil' AND NOT rowsecurity) THEN RAISE EXCEPTION 'RLS missing'; END IF;
END $$;
ROLLBACK;
