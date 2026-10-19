INSERT INTO se_liga_brasil.person_activity_context(source_id,activity_kind,external_key,
 person_id,political_party_id,political_party_affiliation_id,electoral_candidacy_id,
 claimed_office_code,context_kind,observed_at,source_record_id)
SELECT %(source_id)s,b.kind,b.external_key,identity.person_id,
 candidacy.political_party_id,candidacy.political_party_affiliation_id,candidacy.id,
 candidacy.office_code,'electoral_declaration',b.source_generated_at,b.source_record_id
FROM ingestion_batch b JOIN resolved_batch_identity identity ON identity.entity_id=b.entity_id
LEFT JOIN LATERAL (
 SELECT candidacy.* FROM se_liga_brasil.electoral_candidacy candidacy
 WHERE candidacy.source_id=%(source_id)s AND candidacy.person_id=identity.person_id
 AND candidacy.election_year=(b.normalized_data->>'electionYear')::int
 AND candidacy.candidate_sequence=b.normalized_data->>'candidateSequence'
 ORDER BY (candidacy.source_record_id=b.source_record_id) DESC,
 candidacy.source_generated_at DESC,candidacy.id LIMIT 1
) candidacy ON true
ON CONFLICT DO NOTHING;
