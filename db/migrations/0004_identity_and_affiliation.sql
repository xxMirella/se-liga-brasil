-- Stable private document identity and dated observations, not inferred legal membership dates.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
ALTER TABLE se_liga_brasil.person ADD COLUMN normalized_name text;
CREATE INDEX person_name_birth_lookup_idx ON se_liga_brasil.person(normalized_name,birth_date);
CREATE TABLE se_liga_brasil.person_document_identity (
 document_kind text NOT NULL CHECK(document_kind='cpf'),
 document_fingerprint text NOT NULL CHECK(document_fingerprint ~ '^[a-f0-9]{64}$'),
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(document_kind,document_fingerprint),
 UNIQUE(person_id,document_kind)
);
CREATE TABLE se_liga_brasil.person_identity_alias (
 alias_person_id uuid PRIMARY KEY REFERENCES se_liga_brasil.person,
 canonical_person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 resolution_reason text NOT NULL CHECK(resolution_reason IN ('validated_document','official_history')),
 resolved_at timestamptz NOT NULL DEFAULT now(),
 CHECK(alias_person_id<>canonical_person_id)
);
CREATE INDEX person_identity_alias_canonical_idx ON se_liga_brasil.person_identity_alias(canonical_person_id);
CREATE TABLE se_liga_brasil.person_identity_review (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 suggested_person_id uuid REFERENCES se_liga_brasil.person,
 reason_code text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE NULLS NOT DISTINCT(source_record_id,suggested_person_id,reason_code)
);
CREATE INDEX person_identity_review_source_idx ON se_liga_brasil.person_identity_review(source_record_id);
ALTER TABLE se_liga_brasil.political_party ADD COLUMN last_election_context_year integer;
ALTER TABLE se_liga_brasil.political_party ADD COLUMN last_observed_at timestamptz;
CREATE TABLE se_liga_brasil.political_party_observation (
 source_record_id bigint PRIMARY KEY REFERENCES se_liga_brasil.source_record,
 political_party_id bigint NOT NULL REFERENCES se_liga_brasil.political_party,
 name text NOT NULL,
 abbreviation text NOT NULL,
 election_context_year integer NOT NULL,
 observed_at timestamptz NOT NULL
);
ALTER TABLE se_liga_brasil.political_party_affiliation
 ADD COLUMN information_valid_from timestamptz,
 ADD COLUMN information_valid_until timestamptz,
 ADD COLUMN information_scope text,
 ADD COLUMN election_context_year integer,
 ADD COLUMN evidence_kind text NOT NULL DEFAULT 'administrative',
 ADD COLUMN recorded_at timestamptz NOT NULL DEFAULT now(),
 ADD CONSTRAINT affiliation_information_period_check CHECK(
 information_valid_until IS NULL OR information_valid_until>information_valid_from),
 ADD CONSTRAINT affiliation_evidence_kind_check CHECK(evidence_kind IN
 ('administrative','electoral_declaration','official_membership'));
CREATE INDEX affiliation_context_lookup_idx ON se_liga_brasil.political_party_affiliation
 (person_id,election_context_year,information_valid_from DESC);
ALTER TABLE se_liga_brasil.electoral_candidacy
 ADD COLUMN political_party_id bigint REFERENCES se_liga_brasil.political_party,
 ADD COLUMN political_party_affiliation_id bigint REFERENCES se_liga_brasil.political_party_affiliation;
CREATE TABLE se_liga_brasil.person_activity_context (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 activity_kind text NOT NULL,
 external_key text NOT NULL,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 role text NOT NULL DEFAULT 'subject',
 political_party_id bigint REFERENCES se_liga_brasil.political_party,
 political_party_affiliation_id bigint REFERENCES se_liga_brasil.political_party_affiliation,
 electoral_candidacy_id bigint REFERENCES se_liga_brasil.electoral_candidacy,
 office_term_id bigint REFERENCES se_liga_brasil.office_term,
 claimed_office_code text,
 context_kind text NOT NULL CHECK(context_kind IN ('electoral_declaration','administrative')),
 occurred_at timestamptz,
 observed_at timestamptz NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(source_id,activity_kind,external_key,person_id,role,source_record_id)
);
CREATE INDEX person_activity_context_feed_idx ON se_liga_brasil.person_activity_context(person_id,observed_at DESC);
CREATE INDEX electoral_candidacy_political_party_idx ON se_liga_brasil.electoral_candidacy(political_party_id);
CREATE OR REPLACE FUNCTION se_liga_brasil.canonical_person_id(person_uuid uuid)
RETURNS uuid LANGUAGE sql STABLE AS $$
 SELECT coalesce((SELECT canonical_person_id FROM se_liga_brasil.person_identity_alias
 WHERE alias_person_id=person_uuid),person_uuid)
$$;
CREATE OR REPLACE FUNCTION se_liga_brasil.merge_person_identity(
 old_person uuid,new_person uuid,evidence_record bigint,reason text)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE old_id uuid; new_id uuid; relation record; old_birth date; new_birth date;
BEGIN
 old_id:=se_liga_brasil.canonical_person_id(old_person);
 new_id:=se_liga_brasil.canonical_person_id(new_person);
 IF old_id=new_id THEN RETURN 'resolved'; END IF;
 PERFORM id FROM se_liga_brasil.person WHERE id IN (old_id,new_id) ORDER BY id FOR UPDATE;
 IF EXISTS(SELECT 1 FROM se_liga_brasil.person_document_identity old_doc
 JOIN se_liga_brasil.person_document_identity new_doc ON old_doc.document_kind=new_doc.document_kind
 WHERE old_doc.person_id=old_id AND new_doc.person_id=new_id
 AND old_doc.document_fingerprint<>new_doc.document_fingerprint)
 THEN RETURN 'DOCUMENT_IDENTITY_CONFLICT'; END IF;
 SELECT birth_date INTO old_birth FROM se_liga_brasil.person WHERE id=old_id;
 SELECT birth_date INTO new_birth FROM se_liga_brasil.person WHERE id=new_id;
 IF old_birth IS NOT NULL AND new_birth IS NOT NULL AND old_birth<>new_birth
 THEN RETURN 'BIRTH_DATE_IDENTITY_CONFLICT'; END IF;
 FOR relation IN
 SELECT table_class.relname,column_attribute.attname FROM pg_constraint constraint_row
 JOIN pg_class table_class ON table_class.oid=constraint_row.conrelid
 JOIN pg_namespace table_namespace ON table_namespace.oid=table_class.relnamespace
 JOIN pg_attribute column_attribute ON column_attribute.attrelid=constraint_row.conrelid
 AND column_attribute.attnum=constraint_row.conkey[1]
 WHERE constraint_row.contype='f' AND table_namespace.nspname='se_liga_brasil'
 AND constraint_row.confrelid='se_liga_brasil.person'::regclass
 AND table_class.relname<>'person_identity_alias'
 LOOP
 EXECUTE format('UPDATE se_liga_brasil.%I SET %I=$1 WHERE %I=$2',
 relation.relname,relation.attname,relation.attname) USING new_id,old_id;
 END LOOP;
 UPDATE se_liga_brasil.person_identity_alias SET canonical_person_id=new_id
 WHERE canonical_person_id=old_id;
 INSERT INTO se_liga_brasil.person_identity_alias(alias_person_id,canonical_person_id,
 source_record_id,resolution_reason) VALUES(old_id,new_id,evidence_record,reason)
 ON CONFLICT(alias_person_id) DO UPDATE SET canonical_person_id=excluded.canonical_person_id;
 RETURN 'resolved';
EXCEPTION WHEN unique_violation THEN RETURN 'IDENTITY_RELATION_CONFLICT';
END $$;
DO $$ DECLARE relation record; BEGIN
 FOR relation IN SELECT tablename FROM pg_tables WHERE schemaname='se_liga_brasil' LOOP
 EXECUTE format('ALTER TABLE se_liga_brasil.%I ENABLE ROW LEVEL SECURITY',relation.tablename);
 EXECUTE format('REVOKE ALL ON TABLE se_liga_brasil.%I FROM PUBLIC',relation.tablename);
 END LOOP;
END $$;
REVOKE ALL ON FUNCTION se_liga_brasil.canonical_person_id(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION se_liga_brasil.merge_person_identity(uuid,uuid,bigint,text) FROM PUBLIC;

DROP MATERIALIZED VIEW se_liga_brasil.person_profile;
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
 WHERE (a.evidence_kind<>'electoral_declaration' OR a.election_context_year=(SELECT max(other.election_context_year) FROM se_liga_brasil.political_party_affiliation other WHERE other.person_id=a.person_id AND other.evidence_kind='electoral_declaration')) AND a.observed_on<=current_date AND (a.valid_from IS NULL OR a.valid_from<=current_date) AND (a.valid_until IS NULL OR a.valid_until>current_date)
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
FROM (SELECT person.* FROM se_liga_brasil.person person WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias alias WHERE alias.alias_person_id=person.id)) p
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


COMMIT;
