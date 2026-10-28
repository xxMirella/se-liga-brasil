"""Parse the official Goiás succession table, retaining collective and temporary service."""

from collections import defaultdict
from datetime import date, timedelta

from crawlers.state_government.parsing import evidence, source_exercise, visible_text
from normalization.executive_intervals import remove_documented_temporary_overlap
from parsing.html import HtmlTableParser, decode_html


def parse_goias_republican_gallery(artifact):
    parser = HtmlTableParser(None)
    parser.feed(decode_html(artifact.path.read_bytes()))
    text = visible_text(artifact.path.read_bytes())
    if "10 de julho de 2026" not in text:
        raise ValueError('GOIAS_GALLERY_OBSERVATION_DATE_CHANGED')
    records, reviews = [], []
    for cells in parser.rows:
        if len(cells) != 4 or cells[0] == 'Nome':
            continue
        try:
            record = goias_gallery_exercise(cells, artifact)
            if record['starts_on'] >= '1889-11-15':
                records.append(record)
        except ValueError as error:
            reviews.append({'source_row': cells, 'error': str(error)})
    if len(records) < 50:
        raise ValueError('GOIAS_GALLERY_TOO_FEW_VALID_RECORDS')
    records = combine_documented_juntas(records)
    return remove_documented_temporary_overlap(records), reviews


def goias_gallery_exercise(cells, artifact):
    name, role, start, end = cells
    start = date.fromisoformat('-'.join(start.split('/')[::-1]))
    end = date.fromisoformat('-'.join(end.split('/')[::-1])) if end else None
    if end and (end.month, end.day) == (12, 31):
        end += timedelta(days=1)
    if end and end <= start:
        raise ValueError('GOIAS_GALLERY_INVALID_INTERVAL')
    record = source_exercise(name, 'GO', name)
    record.update(starts_on=str(start), ends_before=str(end) if end else None,
                  observed_through='2026-07-10' if not end else None,
                  date_precision='day', source_office_code=role,
                  exercise_id=record['person_id'] + ':' + str(start),
                  exercise_kind='temporary' if 'vice' in role.lower() else 'holder',
                  source_url=artifact.resource.url,
                  evidence=[evidence(artifact, ' | '.join(cells))],
                  territory_identity_basis='historical_state_of_goias_jurisdiction',
                  territorial_boundaries_reconstructed=False)
    return record


def combine_documented_juntas(records):
    groups, result = defaultdict(list), []
    for record in records:
        if record['source_office_code'] == 'Junta Governativa':
            groups[(record['starts_on'], record['ends_before'])].append(record)
        else:
            result.append(record)
    for members in groups.values():
        names = sorted(row['name'] for row in members)
        collective = dict(members[0], name='Junta Governativa (' + '; '.join(names) + ')',
                          exercise_capacity='collective_junta', collective_members=names)
        collective['person_id'] = 'state-executive:GO:junta:' + collective['starts_on']
        collective['exercise_id'] = collective['person_id']
        collective['evidence'] = [item for row in members for item in row['evidence']]
        result.append(collective)
    return result
