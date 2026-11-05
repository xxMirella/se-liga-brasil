"""Verify archived official text supporting explicitly reviewed year-end cases."""

import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urlparse


class OfficialTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments = []

    def handle_data(self, data):
        self.fragments.append(data)


def load_reviewed_year_end_cases(review_file, storage):
    if not review_file.is_file():
        return []
    cases = json.loads(review_file.read_text())
    verified = {}
    for case in cases:
        for assertion in case["evidence_assertions"]:
            key = (assertion["archive"], json.dumps(assertion["source"], sort_keys=True))
            if key not in verified:
                verified[key] = verified_official_text(storage, assertion)
            if assertion["contains"] not in verified[key]:
                raise ValueError("CHAMBER_REVIEWED_SOURCE_ASSERTION_MISMATCH")
    return cases


def verified_official_text(storage, assertion):
    evidence = assertion["source"]
    url = urlparse(evidence["url"])
    if url.scheme != "https" or url.hostname != "www.camara.leg.br":
        raise ValueError("CHAMBER_REVIEWED_SOURCE_NOT_OFFICIAL")
    path = (storage / assertion["archive"]).resolve()
    if not path.is_relative_to(storage.resolve()):
        raise ValueError("CHAMBER_REVIEWED_ARCHIVE_OUTSIDE_STORAGE")
    raw = path.read_bytes()
    if evidence["http_status"] != 200 or hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
        raise ValueError("CHAMBER_REVIEWED_SOURCE_HASH_MISMATCH")
    parser = OfficialTextParser()
    parser.feed(raw.decode("utf-8"))
    return " ".join(" ".join(parser.fragments).split())
