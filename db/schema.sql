-- Initial schema, PostgreSQL 17+. Apply once with an administrative connection.
-- Intentionally private: no Data API exposure or public grants.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
CREATE SCHEMA se_liga_brasil;
REVOKE ALL ON SCHEMA se_liga_brasil FROM PUBLIC;

CREATE TABLE se_liga_brasil.source (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 code text NOT NULL UNIQUE,
 publisher text NOT NULL,
 official_url text NOT NULL CHECK (official_url ~ '^https?://'),
 acquisition_method text NOT NULL CHECK (acquisition_method IN ('api','download','html','document','sic'))
);
CREATE TABLE se_liga_brasil.source_record (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 external_key text NOT NULL,
 source_url text NOT NULL CHECK (source_url ~ '^https?://'),
 content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
 fetched_at timestamptz NOT NULL DEFAULT now(),
 effective_at timestamptz,
 payload jsonb,
 storage_reference text,
 UNIQUE(source_id, external_key, content_sha256),
 CHECK (payload IS NOT NULL OR storage_reference IS NOT NULL)
);
CREATE TABLE se_liga_brasil.person (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 slug text NOT NULL UNIQUE,
 civil_name text NOT NULL,
 display_name text NOT NULL,
 birth_date date,
 education_level text,
 photo_url text,
 primary_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE se_liga_brasil.person_identifier (
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 namespace text NOT NULL, -- e.g. deputy, senator, candidate:2022:general
 external_id text NOT NULL,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(source_id, namespace, external_id)
);
CREATE TABLE se_liga_brasil.person_fact (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 field_name text NOT NULL,
 original_value jsonb NOT NULL,
 normalized_value jsonb,
 evidence_kind text NOT NULL CHECK(evidence_kind IN ('administrative','declaration','biography','derived')),
 review_status text NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','verified','conflicting','incomplete')),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(person_id, field_name, source_record_id)
);
CREATE TABLE se_liga_brasil.person_data_coverage (
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 area text NOT NULL CHECK(area IN ('profile','offices','parties','propositions','votes','laws','amendments')),
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 covered_from date,
 covered_until date,
 status text NOT NULL CHECK(status IN ('complete_for_period','partial','unavailable')),
 checked_at timestamptz NOT NULL DEFAULT now(),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(person_id, area, source_id),
 CHECK(covered_from IS NULL OR covered_until IS NULL OR covered_until >= covered_from)
);
CREATE TABLE se_liga_brasil.education (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 course text NOT NULL,
 institution text,
 completion_year integer CHECK(completion_year BETWEEN 1800 AND 2200),
 completion_status text NOT NULL DEFAULT 'unknown' CHECK(completion_status IN ('completed','incomplete','in_progress','unknown')),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record
);
CREATE TABLE se_liga_brasil.public_career_event (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 event_kind text NOT NULL CHECK(event_kind IN ('candidacy','first_known_office','appointment','declared_public_life_start','other')),
 event_year integer NOT NULL CHECK(event_year BETWEEN 1800 AND 2200),
 event_date date,
 description text NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 CHECK(event_date IS NULL OR extract(year FROM event_date) = event_year)
);
CREATE TABLE se_liga_brasil.political_party (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 code text NOT NULL UNIQUE, -- durable code; keep renamed/merged parties distinct
 name text NOT NULL,
 abbreviation text NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record
);
CREATE TABLE se_liga_brasil.political_party_affiliation (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 political_party_id bigint NOT NULL REFERENCES se_liga_brasil.political_party,
 valid_from date, -- NULL when exact historical start is unknown
 valid_until date, -- exclusive
 observed_on date NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 CHECK(valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from),
 UNIQUE(person_id, political_party_id, source_record_id)
);
CREATE TABLE se_liga_brasil.institution (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 code text NOT NULL UNIQUE,
 name text NOT NULL,
 level text NOT NULL CHECK(level IN ('federal','state','district','municipal')),
 uf text NOT NULL CHECK(uf IN ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PE','PI','PR','RJ','RN','RS','RO','RR','SC','SP','SE','TO','BR')),
 official_url text NOT NULL
);
CREATE TABLE se_liga_brasil.office_term (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 institution_id bigint NOT NULL REFERENCES se_liga_brasil.institution,
 office_kind text NOT NULL CHECK(office_kind IN ('federal_deputy','state_deputy','district_deputy','senator','councillor','mayor','other')),
 represented_uf text NOT NULL CHECK(represented_uf IN ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PE','PI','PR','RJ','RN','RS','RO','RR','SC','SP','SE','TO')),
 legislature_key text NOT NULL,
 official_term_key text NOT NULL,
 term_start date,
 term_end date, -- exclusive; expected term, not effective exercise
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(institution_id, official_term_key),
 CHECK(term_start IS NULL OR term_end IS NULL OR term_end > term_start)
);
CREATE TABLE se_liga_brasil.office_exercise (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 term_id bigint NOT NULL REFERENCES se_liga_brasil.office_term,
 starts_on date NOT NULL,
 ends_before date,
 capacity text NOT NULL CHECK(capacity IN ('holder','substitute')),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(term_id, starts_on),
 CHECK(ends_before IS NULL OR ends_before > starts_on)
);
CREATE TABLE se_liga_brasil.proposition (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 institution_id bigint NOT NULL REFERENCES se_liga_brasil.institution,
 official_key text NOT NULL,
 kind text NOT NULL,
 number text NOT NULL,
 year integer NOT NULL CHECK(year BETWEEN 1800 AND 2200),
 title text NOT NULL,
 summary text,
 introduced_on date,
 current_status text NOT NULL CHECK(current_status IN ('unknown','in_progress','approved_in_house','rejected_in_house','archived','withdrawn','enacted')),
 status_as_of timestamptz NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(institution_id, official_key)
);
CREATE TABLE se_liga_brasil.proposition_person (
 proposition_id bigint NOT NULL REFERENCES se_liga_brasil.proposition,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 role text NOT NULL CHECK(role IN ('author','coauthor','rapporteur')),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(proposition_id, person_id, role)
);
CREATE TABLE se_liga_brasil.proposition_event (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 proposition_id bigint NOT NULL REFERENCES se_liga_brasil.proposition,
 official_event_key text NOT NULL,
 occurred_at timestamptz NOT NULL,
 event_type text NOT NULL,
 description text NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(proposition_id, official_event_key)
);
CREATE TABLE se_liga_brasil.voting (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 proposition_id bigint NOT NULL REFERENCES se_liga_brasil.proposition,
 institution_id bigint NOT NULL REFERENCES se_liga_brasil.institution,
 official_key text NOT NULL,
 held_at timestamptz NOT NULL,
 subject text NOT NULL, -- base text, amendment, procedural motion, etc.
 method text NOT NULL CHECK(method IN ('roll_call','symbolic','secret','unknown')),
 result text NOT NULL CHECK(result IN ('approved','rejected','withdrawn','no_quorum','unknown')),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(institution_id, official_key)
);
CREATE TABLE se_liga_brasil.person_vote (
 voting_id bigint NOT NULL REFERENCES se_liga_brasil.voting,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 choice text NOT NULL CHECK(choice IN ('yes','no','abstention','obstruction','absent','not_recorded')),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(voting_id, person_id)
);
CREATE TABLE se_liga_brasil.law (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 jurisdiction_key text NOT NULL, -- BR, state:PA, municipality:IBGE
 official_key text NOT NULL,
 number text NOT NULL,
 year integer NOT NULL,
 title text NOT NULL,
 published_on date NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(jurisdiction_key, official_key)
);
CREATE TABLE se_liga_brasil.proposition_law (
 proposition_id bigint NOT NULL REFERENCES se_liga_brasil.proposition,
 law_id bigint NOT NULL REFERENCES se_liga_brasil.law,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(proposition_id, law_id)
);
CREATE TABLE se_liga_brasil.budget_amendment (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 jurisdiction_key text NOT NULL,
 official_key text NOT NULL,
 budget_year integer NOT NULL,
 amendment_type text NOT NULL CHECK(amendment_type IN ('individual','bench','committee','rapporteur','unknown')),
 description text,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(jurisdiction_key, budget_year, official_key)
);
CREATE TABLE se_liga_brasil.amendment_person (
 amendment_id bigint NOT NULL REFERENCES se_liga_brasil.budget_amendment,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 role text NOT NULL CHECK(role IN ('formal_author','requester','supporter')),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(amendment_id, person_id, role)
);
CREATE TABLE se_liga_brasil.amendment_execution_snapshot (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 amendment_id bigint NOT NULL REFERENCES se_liga_brasil.budget_amendment,
 slice_key text NOT NULL, -- source-defined beneficiary/action/execution-year grain
 as_of date NOT NULL,
 beneficiary_name text,
 beneficiary_identifier text,
 municipality_ibge text,
 execution_year integer NOT NULL,
 committed numeric(20,2),
 liquidated numeric(20,2),
 paid numeric(20,2),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(amendment_id, slice_key, as_of)
);

-- Business lookup indexes. Foreign-key indexes are added below, once each.
CREATE INDEX proposition_status_idx ON se_liga_brasil.proposition(institution_id, current_status, id);
CREATE INDEX proposition_person_feed_idx ON se_liga_brasil.proposition_person(person_id, role, proposition_id);
CREATE INDEX vote_person_feed_idx ON se_liga_brasil.person_vote(person_id, voting_id);
CREATE INDEX voting_feed_idx ON se_liga_brasil.voting(held_at DESC, id DESC);
CREATE INDEX amendment_person_feed_idx ON se_liga_brasil.amendment_person(person_id, role, amendment_id);
CREATE INDEX amendment_latest_snapshot_idx ON se_liga_brasil.amendment_execution_snapshot(amendment_id, slice_key, as_of DESC);
CREATE INDEX proposition_event_feed_idx ON se_liga_brasil.proposition_event(proposition_id, occurred_at DESC, id DESC);
CREATE INDEX political_party_affiliation_latest_idx ON se_liga_brasil.political_party_affiliation(person_id, observed_on DESC, id DESC);
CREATE INDEX office_person_idx ON se_liga_brasil.office_term(person_id, id);
CREATE INDEX exercise_term_idx ON se_liga_brasil.office_exercise(term_id, starts_on, ends_before);

-- Ensure every FK has a leading-column B-tree index, without duplicating a PK/index.
DO $$
DECLARE fk record;
BEGIN
 FOR fk IN
  SELECT c.conrelid, t.relname, a.attname, a.attnum
  FROM pg_constraint c
  JOIN pg_class t ON t.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=t.relnamespace
  JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
  WHERE n.nspname='se_liga_brasil' AND c.contype='f'
 LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_index i WHERE i.indrelid=fk.conrelid AND i.indisvalid AND i.indkey[0]=fk.attnum) THEN
   EXECUTE format('CREATE INDEX %I ON se_liga_brasil.%I (%I)', fk.relname || '_' || fk.attname || '_idx', fk.relname, fk.attname);
  END IF;
 END LOOP;
END $$;

-- Derived, rebuildable read model: independent aggregations avoid cartesian inflation.
CREATE MATERIALIZED VIEW se_liga_brasil.person_profile AS
WITH current_offices AS (
 SELECT t.person_id,
  jsonb_agg(jsonb_build_object('term_id',t.id,'office',t.office_kind,'uf',t.represented_uf,'institution',i.name) ORDER BY t.id) AS offices,
  array_agg(DISTINCT t.represented_uf) AS represented_ufs
 FROM se_liga_brasil.office_term t JOIN se_liga_brasil.institution i ON i.id=t.institution_id
 WHERE EXISTS(SELECT 1 FROM se_liga_brasil.office_exercise e WHERE e.term_id=t.id AND e.starts_on<=current_date AND (e.ends_before IS NULL OR e.ends_before>current_date))
 GROUP BY t.person_id
), latest_political_party AS (
 SELECT DISTINCT ON (a.person_id) a.person_id, a.political_party_id, p.abbreviation, a.observed_on
 FROM se_liga_brasil.political_party_affiliation a JOIN se_liga_brasil.political_party p ON p.id=a.political_party_id
 WHERE a.observed_on<=current_date AND (a.valid_from IS NULL OR a.valid_from<=current_date) AND (a.valid_until IS NULL OR a.valid_until>current_date)
 ORDER BY a.person_id, a.observed_on DESC, a.id DESC
), authored AS (
 SELECT pp.person_id, count(DISTINCT pp.proposition_id) AS authored_count,
  count(DISTINCT pp.proposition_id) FILTER(WHERE p.current_status='approved_in_house') AS authored_approved_in_house_count,
  count(DISTINCT pp.proposition_id) FILTER(WHERE p.current_status='rejected_in_house') AS authored_rejected_in_house_count
 FROM se_liga_brasil.proposition_person pp JOIN se_liga_brasil.proposition p ON p.id=pp.proposition_id
 WHERE pp.role IN ('author','coauthor') GROUP BY pp.person_id
), laws AS (
 SELECT pp.person_id, count(DISTINCT pl.law_id) AS authored_law_count
 FROM se_liga_brasil.proposition_person pp JOIN se_liga_brasil.proposition_law pl ON pl.proposition_id=pp.proposition_id
 WHERE pp.role IN ('author','coauthor') GROUP BY pp.person_id
), amendments AS (
 SELECT person_id, count(DISTINCT amendment_id) AS formal_amendment_count
 FROM se_liga_brasil.amendment_person WHERE role='formal_author' GROUP BY person_id
), votes AS (
 SELECT person_id, count(*) FILTER(WHERE choice='yes') AS yes_vote_count,
 count(*) FILTER(WHERE choice='no') AS no_vote_count FROM se_liga_brasil.person_vote GROUP BY person_id
), coverage AS (
 SELECT person_id, jsonb_agg(jsonb_build_object('area',area,'source_id',source_id,'status',status,'from',covered_from,'until',covered_until,'checked_at',checked_at) ORDER BY area,source_id) AS areas
 FROM se_liga_brasil.person_data_coverage GROUP BY person_id
)
SELECT p.id AS person_id, p.slug, p.civil_name, p.display_name, p.birth_date, p.education_level, p.photo_url,
 coalesce(o.offices,'[]'::jsonb) AS current_offices, coalesce(o.represented_ufs,ARRAY[]::text[]) AS represented_ufs,
 lp.political_party_id AS last_observed_political_party_id, lp.abbreviation AS last_observed_political_party, lp.observed_on AS political_party_observed_on,
 coalesce(a.authored_count,0) AS authored_count,
 coalesce(a.authored_approved_in_house_count,0) AS authored_approved_in_house_count,
 coalesce(a.authored_rejected_in_house_count,0) AS authored_rejected_in_house_count,
 coalesce(l.authored_law_count,0) AS authored_law_count,
 coalesce(am.formal_amendment_count,0) AS formal_amendment_count,
 coalesce(v.yes_vote_count,0) AS yes_vote_count, coalesce(v.no_vote_count,0) AS no_vote_count,
 to_tsvector('portuguese',p.civil_name || ' ' || p.display_name) AS search_document,
 coalesce(c.areas,'[]'::jsonb) AS data_coverage, statement_timestamp() AS refreshed_at
FROM se_liga_brasil.person p
LEFT JOIN current_offices o ON o.person_id=p.id LEFT JOIN latest_political_party lp ON lp.person_id=p.id
LEFT JOIN authored a ON a.person_id=p.id LEFT JOIN laws l ON l.person_id=p.id
LEFT JOIN amendments am ON am.person_id=p.id LEFT JOIN votes v ON v.person_id=p.id
LEFT JOIN coverage c ON c.person_id=p.id
WITH DATA;
CREATE UNIQUE INDEX person_profile_id_idx ON se_liga_brasil.person_profile(person_id);
CREATE UNIQUE INDEX person_profile_slug_idx ON se_liga_brasil.person_profile(slug);
CREATE INDEX person_profile_political_party_idx ON se_liga_brasil.person_profile(last_observed_political_party_id, person_id);
CREATE INDEX person_profile_search_idx ON se_liga_brasil.person_profile USING gin(search_document);
CREATE INDEX person_profile_ufs_idx ON se_liga_brasil.person_profile USING gin(represented_ufs);

-- Defense in depth. No anon/authenticated policies; access goes through backend.
DO $$
DECLARE t record; r text;
BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='se_liga_brasil' LOOP
  EXECUTE format('ALTER TABLE se_liga_brasil.%I ENABLE ROW LEVEL SECURITY',t.tablename);
 END LOOP;
 FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE format('REVOKE ALL ON SCHEMA se_liga_brasil FROM %I',r);
   EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA se_liga_brasil FROM %I',r);
  END IF;
 END LOOP;
END $$;
COMMIT;
