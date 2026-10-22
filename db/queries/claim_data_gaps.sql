WITH due AS (
              SELECT g.id, CASE WHEN p.has_current_public_office IS TRUE THEN 0
                WHEN EXISTS(SELECT 1 FROM se_liga_brasil.electoral_candidacy c
                  WHERE c.person_id=p.id AND upper(c.election_result) LIKE 'ELEITO%%'
                    AND c.office_code IN ('5','6','7')
                    AND make_date(c.election_year+1,2,1)<=current_date
                    AND make_date(c.election_year+CASE WHEN c.office_code='5'
                      THEN 9 ELSE 5 END,2,1)>current_date) THEN 1 ELSE 2 END AS person_priority,
                CASE WHEN g.field_name IN ('photo_url','current_public_office',
                  'current_salary','current_office_started_on')
                  THEN 0 ELSE 1 END AS field_priority,g.next_attempt_at
              FROM se_liga_brasil.person_data_gap g
              JOIN se_liga_brasil.person p ON p.id=g.person_id
              LEFT JOIN se_liga_brasil.source_request_policy policy
                ON policy.source_code=g.assigned_source
              WHERE (policy.cooldown_until IS NULL OR policy.cooldown_until<=now()
                OR (g.assigned_source='alesp' AND g.field_name IN
                  ('current_public_office','current_political_party','political_activity')))
                AND (status='queued' OR (status='running' AND lease_until<now()))
                AND assigned_source IS NOT NULL AND next_attempt_at<=now()
                AND (%s::uuid IS NULL OR g.person_id=%s::uuid)
                AND (%s::text[] IS NULL OR field_name=ANY(%s::text[]))
                AND (%s::text[] IS NULL OR assigned_source=ANY(%s::text[]))
              ORDER BY person_priority,field_priority,g.next_attempt_at,g.id
              FOR UPDATE OF g SKIP LOCKED LIMIT %s
            ), claimed AS (
            UPDATE se_liga_brasil.person_data_gap g SET status='running',claimed_by=%s::uuid,
              lease_until=now()+interval '30 minutes',attempts=attempts+1
            FROM due WHERE due.id=g.id
            RETURNING g.id,g.person_id::text,g.field_name,g.assigned_source
            )
            SELECT claimed.* FROM claimed JOIN due ON due.id=claimed.id
            ORDER BY due.person_priority,due.field_priority,due.next_attempt_at,due.id;
