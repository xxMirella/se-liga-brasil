WITH latest AS (
          SELECT DISTINCT ON(person_id) person_id,office_code,represented_uf
          FROM se_liga_brasil.electoral_candidacy ORDER BY person_id,election_year DESC,id DESC
        ), elected_hint AS (
          SELECT DISTINCT ON(person_id) person_id,office_code,represented_uf
          FROM se_liga_brasil.electoral_candidacy
          WHERE office_code IN ('5','6','7') AND upper(election_result) LIKE 'ELEITO%'
            AND make_date(election_year+1,2,1)<=current_date
            AND make_date(election_year+CASE WHEN office_code='5' THEN 9 ELSE 5 END,2,1)>current_date
          ORDER BY person_id,election_year DESC,id DESC
        ), routing_context AS (
          SELECT l.person_id,coalesce(e.office_code,l.office_code) AS office_code,
            coalesce(e.represented_uf,l.represented_uf) AS represented_uf
          FROM latest l LEFT JOIN elected_hint e ON e.person_id=l.person_id
        ), routes AS (
          SELECT g.id,CASE
            WHEN g.field_name IN ('full_name','birth_date','education_level',
              'declared_assets','declared_wealth') THEN 'tse'
            WHEN g.field_name='current_political_party' AND g.assigned_source='tse_filiation'
              AND p.has_current_public_office IS NOT TRUE THEN 'tse_filiation'
            WHEN i.code IN ('camara','alesp','alerj','senado') THEN i.code
            WHEN latest.office_code='6' THEN 'camara'
            WHEN latest.office_code='7' AND latest.represented_uf='SP' THEN 'alesp'
            WHEN latest.office_code='7' AND latest.represented_uf='RJ' THEN 'alerj'
            WHEN latest.office_code='5' THEN 'senado' END AS source
          FROM se_liga_brasil.person_data_gap g
          JOIN se_liga_brasil.person p ON p.id=g.person_id
          LEFT JOIN routing_context latest ON latest.person_id=g.person_id
          LEFT JOIN se_liga_brasil.institution i ON i.id=p.current_public_office_institution_id
          WHERE NOT g.is_processed AND g.status<>'running'
        )
        UPDATE se_liga_brasil.person_data_gap g SET assigned_source=r.source,
          status=CASE WHEN r.source IS NULL THEN 'blocked' ELSE 'queued' END,
          last_error_code=CASE WHEN r.source IS NULL THEN 'SOURCE_NOT_MAPPED'
            WHEN g.assigned_source IS DISTINCT FROM r.source THEN NULL ELSE g.last_error_code END,
          next_attempt_at=CASE WHEN g.assigned_source IS DISTINCT FROM r.source
            THEN now() ELSE g.next_attempt_at END
        FROM routes r WHERE g.id=r.id AND
          (g.assigned_source IS DISTINCT FROM r.source
            OR (g.status='blocked' AND r.source IS NOT NULL
                AND g.last_error_code='SOURCE_NOT_MAPPED'));


-- The Senate nominal administrative API now supports salary collection.
UPDATE se_liga_brasil.person_data_gap SET status='queued',last_error_code=NULL,
  next_attempt_at=now(),claimed_by=NULL,lease_until=NULL
WHERE assigned_source='senado' AND field_name='current_salary' AND status='blocked'
  AND last_error_code='SOURCE_FIELD_NOT_SUPPORTED' AND NOT is_processed;
