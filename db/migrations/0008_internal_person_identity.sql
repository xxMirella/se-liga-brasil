-- Preserve person UUIDs and every dependent fact; remove electoral person identifiers.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
DELETE FROM se_liga_brasil.person_identifier i USING se_liga_brasil.source s
WHERE s.id=i.source_id AND s.code='tse' AND i.namespace LIKE 'candidate:%';
DELETE FROM se_liga_brasil.person_identifier WHERE namespace='public_office_member';
UPDATE se_liga_brasil.person SET slug='person-'||id::text
WHERE slug LIKE 'tse-%';
ALTER TABLE se_liga_brasil.person_identifier ADD CONSTRAINT person_identifier_no_electoral_identity
CHECK(namespace NOT LIKE 'candidate:%' AND namespace<>'public_office_member');
COMMIT;
