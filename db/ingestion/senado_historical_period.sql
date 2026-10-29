-- Named statements for the 1992-1994 Senate load. Every write is set-based, idempotent and
-- returns the rows it really inserted, so dry-run counts equal apply counts.
-- Parsed by database/historical_senate_load.py; "-- statement: <name>" opens each block.

-- statement: ensure_source
INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method)
VALUES(%(source_code)s,%(publisher)s,%(official_url)s,'api')
ON CONFLICT(code) DO NOTHING RETURNING id;

-- statement: ensure_institution
INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url)
VALUES('senado','Senado Federal','federal','BR','https://www.senado.leg.br')
ON CONFLICT(code) DO NOTHING RETURNING id;

-- statement: insert_source_records
INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,content_sha256,
 fetched_at,effective_at,payload,storage_reference)
SELECT %(source_id)s,r.external_key,r.source_url,r.content_sha256,r.fetched_at,r.fetched_at,
 r.payload,r.storage_reference
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(external_key text,source_url text,
 content_sha256 text,fetched_at timestamptz,payload jsonb,storage_reference text)
ON CONFLICT(source_id,external_key,content_sha256) DO NOTHING RETURNING id;

-- statement: select_source_record_ids
SELECT s.id,s.external_key,s.content_sha256
FROM se_liga_brasil.source_record s
JOIN jsonb_to_recordset(%(rows)s::jsonb) AS k(external_key text,content_sha256 text)
 ON s.external_key=k.external_key AND s.content_sha256=k.content_sha256
WHERE s.source_id=%(source_id)s;

-- statement: select_existing_identities
SELECT i.external_id,i.person_id::text AS person_id,
 EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
  WHERE a.alias_person_id=i.person_id) AS is_alias
FROM se_liga_brasil.person_identifier i
WHERE i.source_id=%(source_id)s AND i.namespace='senator' AND i.external_id=ANY(%(senator_ids)s);

-- statement: select_name_and_birth_matches
SELECT c.senator_id,p.id::text AS person_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS c(senator_id text,normalized_name text,birth_date date)
JOIN se_liga_brasil.person p ON p.normalized_name=c.normalized_name AND p.birth_date=c.birth_date
WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a WHERE a.alias_person_id=p.id);

-- statement: insert_people
INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,birth_date,primary_record_id,
 normalized_name)
SELECT r.person_id,'person-'||r.person_id::text,r.civil_name,r.display_name,r.birth_date,
 r.primary_record_id,r.normalized_name
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(person_id uuid,civil_name text,display_name text,
 birth_date date,primary_record_id bigint,normalized_name text)
ON CONFLICT(id) DO NOTHING RETURNING id;

-- statement: insert_person_identifiers
INSERT INTO se_liga_brasil.person_identifier(source_id,namespace,external_id,person_id,
 source_record_id)
SELECT %(source_id)s,'senator',r.senator_id,r.person_id,r.source_record_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(senator_id text,person_id uuid,source_record_id bigint)
ON CONFLICT(source_id,namespace,external_id) DO NOTHING RETURNING external_id;

-- statement: select_existing_abbreviations
SELECT lower(abbreviation) AS abbreviation FROM se_liga_brasil.political_party
WHERE lower(abbreviation)=ANY(%(abbreviations)s) AND NOT code=ANY(%(own_codes)s);

-- statement: insert_political_parties
INSERT INTO se_liga_brasil.political_party(code,name,abbreviation,source_record_id)
SELECT r.code,r.name,r.abbreviation,r.source_record_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(code text,name text,abbreviation text,
 source_record_id bigint)
ON CONFLICT(code) DO NOTHING RETURNING id;

-- statement: insert_office_terms
INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,represented_uf,
 legislature_key,official_term_key,term_start,term_end,source_record_id)
SELECT r.person_id,%(institution_id)s,'senator',r.represented_uf,r.legislature_key,
 r.official_term_key,r.term_start,r.term_end,r.source_record_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(person_id uuid,represented_uf text,
 legislature_key text,official_term_key text,term_start date,term_end date,source_record_id bigint)
ON CONFLICT(institution_id,official_term_key) DO NOTHING RETURNING id;

-- statement: select_conflicting_terms
SELECT t.official_term_key
FROM se_liga_brasil.office_term t
JOIN jsonb_to_recordset(%(rows)s::jsonb) AS r(person_id uuid,represented_uf text,
 official_term_key text,term_start date,term_end date)
 ON t.institution_id=%(institution_id)s AND t.official_term_key=r.official_term_key
WHERE t.person_id<>r.person_id OR t.represented_uf<>r.represented_uf
 OR t.term_start IS DISTINCT FROM r.term_start OR t.term_end IS DISTINCT FROM r.term_end;

-- statement: insert_office_exercises
INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,ends_before,capacity,
 source_record_id)
SELECT t.id,r.starts_on,r.ends_before,r.capacity,r.source_record_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(official_term_key text,starts_on date,
 ends_before date,capacity text,source_record_id bigint)
JOIN se_liga_brasil.office_term t
 ON t.institution_id=%(institution_id)s AND t.official_term_key=r.official_term_key
ON CONFLICT(term_id,starts_on) DO NOTHING RETURNING id;

-- statement: select_conflicting_exercises
SELECT r.official_term_key,r.starts_on::text AS starts_on
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(official_term_key text,starts_on date,
 ends_before date,capacity text)
JOIN se_liga_brasil.office_term t
 ON t.institution_id=%(institution_id)s AND t.official_term_key=r.official_term_key
JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id AND e.starts_on=r.starts_on
WHERE e.ends_before IS DISTINCT FROM r.ends_before OR e.capacity<>r.capacity;

-- statement: insert_affiliations
INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,valid_from,
 valid_until,observed_on,source_record_id,information_valid_from,information_scope,
 evidence_kind)
SELECT r.person_id,p.id,r.valid_from,r.valid_until,r.observed_on,r.source_record_id,
 r.information_valid_from,%(scope)s,'administrative'
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(person_id uuid,party_code text,valid_from date,
 valid_until date,observed_on date,source_record_id bigint,information_valid_from timestamptz)
JOIN se_liga_brasil.political_party p ON p.code=r.party_code
ON CONFLICT(person_id,political_party_id,source_record_id) DO NOTHING RETURNING id;

-- statement: select_conflicting_affiliations
SELECT r.person_id::text AS person_id,r.party_code,r.valid_from::text AS valid_from
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(person_id uuid,party_code text,valid_from date,
 valid_until date,source_record_id bigint)
JOIN se_liga_brasil.political_party p ON p.code=r.party_code
JOIN se_liga_brasil.political_party_affiliation a ON a.person_id=r.person_id
 AND a.political_party_id=p.id AND a.source_record_id=r.source_record_id
WHERE a.valid_from IS DISTINCT FROM r.valid_from OR a.valid_until IS DISTINCT FROM r.valid_until;

-- statement: insert_person_facts
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT r.person_id,r.field_name,r.value,r.value,'administrative',r.review_status,
 r.source_record_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(person_id uuid,field_name text,value jsonb,
 review_status text,source_record_id bigint)
ON CONFLICT(person_id,field_name,source_record_id) DO NOTHING RETURNING id;
