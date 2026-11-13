"""Committee attendance must resolve SPL IDs through the official roster."""

from crawlers.alesp.attendance import attendance_identity_index, committee_attendance_rows


def test_committee_uses_spl_id_instead_of_colliding_profile_id(tmp_path):
    roster = tmp_path / "deputados.xml"
    roster.write_text(
        "<Deputados><Deputado><IdDeputado>123</IdDeputado>"
        "<IdSPL>456</IdSPL></Deputado></Deputados>"
    )
    resolutions = [
        {"status": "unresolved"},
        {"status": "matched", "person_id": "person-a",
         "official_subjects": [{"source_subject_id": "123"}]},
    ]
    index = attendance_identity_index(resolutions, {"person-a"}, roster)
    assert index == {"456": "person-a"}
    export = tmp_path / "presencas.xml"
    export.write_text(
        "<Presencas>"
        "<ReuniaoComissaoPresenca><IdDeputado>456</IdDeputado>"
        "<IdReuniao>7</IdReuniao><IdComissao>8</IdComissao>"
        "<DataReuniao>2023-04-19T00:00:00-03:00</DataReuniao>"
        "</ReuniaoComissaoPresenca>"
        "<ReuniaoComissaoPresenca><IdDeputado>123</IdDeputado>"
        "<IdReuniao>9</IdReuniao><IdComissao>8</IdComissao>"
        "<DataReuniao>2023-04-20T00:00:00-03:00</DataReuniao>"
        "</ReuniaoComissaoPresenca></Presencas>"
    )
    rows = committee_attendance_rows([export], index)
    assert len(rows) == 1
    assert rows[0]["present"] == 1
    assert rows[0]["meetings"][0]["date"] == "2023-04-19"
    assert rows[0]["identityMethod"] == "official_profile_to_roster_IdSPL"
