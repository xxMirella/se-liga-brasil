-- Official parliamentary registration; valid_until is exclusive.
-- S/Partido is a status in the Senate source, never an invented political_party row.
WITH identified_person AS (
 SELECT se_liga_brasil.canonical_person_id(i.person_id) AS person_id
 FROM se_liga_brasil.person_identifier i
 JOIN se_liga_brasil.source s ON s.id=i.source_id
 WHERE s.code='senado' AND i.namespace='senator' AND i.external_id='5894'
), latest_history_source AS (
 SELECT r.id
 FROM se_liga_brasil.source_record r
 JOIN se_liga_brasil.source s ON s.id=r.source_id
 WHERE s.code='senado' AND r.external_key='senator:5894:historical_affiliations'
 ORDER BY r.fetched_at DESC,r.id DESC LIMIT 1
), dated_history AS (
 SELECT a.person_id,a.political_party_id,p.abbreviation AS political_party,
        a.valid_from,a.valid_until,a.source_record_id,
        'senate_parliamentary_affiliation' AS evidence_meaning
 FROM se_liga_brasil.political_party_affiliation a
 JOIN identified_person i ON i.person_id=a.person_id
 JOIN latest_history_source latest ON latest.id=a.source_record_id
 JOIN se_liga_brasil.political_party p ON p.id=a.political_party_id
 WHERE a.information_scope='institution:senado:historical_affiliations'
 UNION ALL
 SELECT f.person_id,NULL::bigint,'S/Partido',
        (interval->>'valid_from')::date,(interval->>'valid_until')::date,
        f.source_record_id,'no_party_registered_in_senate_not_civil_membership_certificate'
 FROM se_liga_brasil.person_fact f
 JOIN identified_person i ON i.person_id=f.person_id
 JOIN latest_history_source latest ON latest.id=f.source_record_id
 CROSS JOIN LATERAL jsonb_array_elements(f.normalized_value) interval
 WHERE f.field_name='senate_no_affiliation_intervals'
)
SELECT h.*,r.source_url,r.content_sha256
FROM dated_history h
JOIN se_liga_brasil.source_record r ON r.id=h.source_record_id
WHERE h.valid_from<'2022-01-01' AND coalesce(h.valid_until,'infinity'::date)>'2019-01-01'
ORDER BY h.valid_from,h.source_record_id;
