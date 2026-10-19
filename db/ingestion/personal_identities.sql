-- Personal evidence determines identity; election identifiers only group source rows.
SELECT pg_advisory_xact_lock(hashtext('se_liga_brasil:identity_resolution'));
CREATE TEMP TABLE personal_resolution ON COMMIT DROP AS
SELECT b.entity_id,b.source_record_id,b.normalized_data,b.identity_evidence,
 document.person_id AS document_person_id,
 matched.person_id AS name_person_id,matched.matches,
 coalesce(document.person_id,matched.person_id,gen_random_uuid()) AS person_id,
 CASE WHEN document.person_id IS NULL AND matched.matches>1 THEN 'PERSON_IDENTITY_AMBIGUOUS'
 WHEN document.person_id IS NULL AND b.identity_evidence->>'documentFingerprint' IS NULL
 AND (b.normalized_data->>'birthDate' IS NULL OR b.identity_evidence->>'normalizedName' IS NULL)
 THEN 'PERSON_IDENTITY_INSUFFICIENT' END AS rejection_code
FROM ingestion_batch b
LEFT JOIN se_liga_brasil.person_document_identity document ON document.document_kind='cpf'
 AND document.document_fingerprint=b.identity_evidence->>'documentFingerprint'
LEFT JOIN LATERAL (
 SELECT count(*) AS matches,(array_agg(p.id ORDER BY p.id))[1] AS person_id
 FROM se_liga_brasil.person p
 WHERE p.normalized_name=b.identity_evidence->>'normalizedName'
 AND p.birth_date=(b.normalized_data->>'birthDate')::date
 AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a WHERE a.alias_person_id=p.id)
 AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_document_identity d
 WHERE d.person_id=p.id AND b.identity_evidence->>'documentFingerprint' IS NOT NULL
 AND d.document_fingerprint<>b.identity_evidence->>'documentFingerprint')
) matched ON document.person_id IS NULL
WHERE b.classification NOT IN ('conflicting','stale');
-- Equal personal evidence within one batch receives the same internal UUID.
UPDATE personal_resolution r SET person_id=grouped.person_id
FROM (SELECT entity_id,first_value(person_id) OVER (
 PARTITION BY coalesce(identity_evidence->>'documentFingerprint',
 (identity_evidence->>'normalizedName')||':'||(normalized_data->>'birthDate'))
 ORDER BY (document_person_id IS NOT NULL) DESC,(name_person_id IS NOT NULL) DESC,source_record_id)
 AS person_id FROM personal_resolution WHERE rejection_code IS NULL) grouped
WHERE grouped.entity_id=r.entity_id;
UPDATE personal_resolution r SET rejection_code='BIRTH_DATE_IDENTITY_CONFLICT'
FROM (SELECT person_id FROM personal_resolution WHERE rejection_code IS NULL
 GROUP BY person_id HAVING count(DISTINCT normalized_data->>'birthDate')>1) conflicts
WHERE r.person_id=conflicts.person_id AND r.document_person_id IS NULL;
-- A document-bearing row can identify its exact name/birth peers in the same batch.
UPDATE personal_resolution r SET person_id=grouped.person_id,
 rejection_code=CASE WHEN grouped.documents>1 THEN 'PERSON_IDENTITY_AMBIGUOUS' END
FROM (
 SELECT identity_evidence->>'normalizedName' AS name,normalized_data->>'birthDate' AS birth,
 count(DISTINCT identity_evidence->>'documentFingerprint') AS documents,
 (array_agg(person_id ORDER BY (identity_evidence->>'documentFingerprint' IS NOT NULL) DESC,
 source_record_id))[1] AS person_id
 FROM personal_resolution WHERE rejection_code IS NULL
 GROUP BY identity_evidence->>'normalizedName',normalized_data->>'birthDate'
) grouped
WHERE r.rejection_code IS NULL AND r.identity_evidence->>'documentFingerprint' IS NULL
 AND r.identity_evidence->>'normalizedName'=grouped.name
 AND r.normalized_data->>'birthDate'=grouped.birth AND grouped.documents>0;
-- Existing event ownership is a conflict guard, never evidence for choosing a person.
UPDATE personal_resolution r SET rejection_code='PERSON_IDENTITY_CHANGED_REQUIRES_REVIEW'
FROM se_liga_brasil.electoral_candidacy c
WHERE c.source_id=%(source_id)s AND c.election_year=(r.normalized_data->>'electionYear')::int
 AND c.election_id=r.normalized_data->>'electionId'
 AND c.candidate_sequence=r.normalized_data->>'candidateSequence'
 AND c.election_round=(r.normalized_data->>'electionRound')::int
 AND c.person_id<>r.person_id AND r.rejection_code IS NULL;
INSERT INTO se_liga_brasil.person_identity_review(source_record_id,suggested_person_id,reason_code)
SELECT source_record_id,NULL,rejection_code FROM personal_resolution WHERE rejection_code IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_rejection(run_id,artifact_id,resource_id,entry_name,row_number,reason_code,payload_sha256,details)
SELECT %(run_id)s,%(artifact_id)s,%(resource_id)s,b.entry_name,b.row_number,r.rejection_code,
 b.content_sha256,b.diagnostic_context FROM ingestion_batch b JOIN personal_resolution r USING(entity_id)
WHERE r.rejection_code IS NOT NULL;
DELETE FROM ingestion_batch b USING personal_resolution r
WHERE b.entity_id=r.entity_id AND r.rejection_code IS NOT NULL;
DELETE FROM personal_resolution WHERE rejection_code IS NOT NULL;
INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,birth_date,education_level,
 primary_record_id,normalized_name)
SELECT DISTINCT ON(person_id) person_id,'person-'||person_id::text,
 normalized_data->>'civilName',normalized_data->>'displayName',(normalized_data->>'birthDate')::date,
 normalized_data->>'educationLevel',source_record_id,identity_evidence->>'normalizedName'
FROM personal_resolution ORDER BY person_id,source_record_id DESC ON CONFLICT(id) DO NOTHING;
INSERT INTO se_liga_brasil.person_document_identity(document_kind,document_fingerprint,person_id,source_record_id)
SELECT DISTINCT ON(identity_evidence->>'documentFingerprint') 'cpf',
 identity_evidence->>'documentFingerprint',person_id,source_record_id FROM personal_resolution
WHERE identity_evidence->>'documentFingerprint' IS NOT NULL
ORDER BY identity_evidence->>'documentFingerprint',source_record_id ON CONFLICT DO NOTHING;
INSERT INTO se_liga_brasil.person_identity_review(source_record_id,suggested_person_id,reason_code)
SELECT r.source_record_id,p.id,'BIRTH_DATE_DISAGREEMENT_SAME_DOCUMENT'
FROM personal_resolution r JOIN se_liga_brasil.person p ON p.id=r.person_id
WHERE r.document_person_id IS NOT NULL AND p.birth_date IS NOT NULL
 AND r.normalized_data->>'birthDate' IS NOT NULL
 AND p.birth_date<>(r.normalized_data->>'birthDate')::date ON CONFLICT DO NOTHING;
INSERT INTO se_liga_brasil.person_identity_review(source_record_id,suggested_person_id,reason_code)
SELECT source_record_id,person_id,'INVALID_CPF' FROM personal_resolution
WHERE identity_evidence->>'documentStatus'='invalid' ON CONFLICT DO NOTHING;
