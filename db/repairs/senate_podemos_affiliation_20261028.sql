-- Repair only the three observed October2026 omissions, using official source identifiers.
-- TSE approved Podemos' number20 on05/03/2024; retain historical number19 records.
WITH verified_observations AS (
 SELECT i.person_id,f.source_record_id,sr.effective_at,
        (sr.payload->>'observedOn')::date AS observed_on,p.id political_party_id
 FROM se_liga_brasil.person_identifier i
 JOIN se_liga_brasil.source s ON s.id=i.source_id AND s.code='senado'
 JOIN se_liga_brasil.person_fact f ON f.person_id=i.person_id
  AND f.field_name='current_public_office_observation'
 JOIN se_liga_brasil.source_record sr ON sr.id=f.source_record_id
  AND sr.source_id=i.source_id
  AND sr.source_url='https://legis.senado.leg.br/dadosabertos/senador/'||i.external_id||'.json'
 JOIN se_liga_brasil.political_party p ON p.abbreviation='PODE' AND p.code='20'
 WHERE i.namespace='senator' AND i.external_id IN ('3806','5959','6008')
  AND sr.payload->>'politicalPartyAbbreviation'='PODE'
  AND sr.payload->>'observedOn'='2026-10-23'
  AND sr.effective_at IS NOT NULL
)
INSERT INTO se_liga_brasil.political_party_affiliation(
 person_id,political_party_id,observed_on,source_record_id,information_valid_from,
 information_scope,evidence_kind)
SELECT person_id,political_party_id,observed_on,source_record_id,effective_at,
       'institution:senado','administrative'
FROM verified_observations
ON CONFLICT(person_id,political_party_id,source_record_id) DO NOTHING
RETURNING id,person_id,political_party_id,observed_on,source_record_id;
