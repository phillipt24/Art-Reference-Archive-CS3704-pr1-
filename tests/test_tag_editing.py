# AI-generated tests (Claude Code, claude-opus-5-5), to be reviewed by the team.
# Prompt: "Implement US-002 (add and remove tags on one picture) and write pytest
# tests for its acceptance criteria, using a temporary data.json and uploads folder."

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32


@pytest.fixture
def store(tmp_path, monkeypatch):
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    monkeypatch.setattr(app_module, 'DATA_FILE', str(tmp_path / 'data.json'))
    monkeypatch.setitem(app_module.app.config, 'UPLOAD_FOLDER', str(uploads))
    monkeypatch.setattr(app_module, 'last_allocated_id', None)
    return tmp_path


@pytest.fixture
def client(store):
    app_module.app.config['TESTING'] = True
    return app_module.app.test_client()


def write_records(store, records):
    (store / 'data.json').write_text(json.dumps(records))
    for record in records:
        (store / 'uploads' / record['filename']).write_bytes(PNG)


def read_records(store):
    return json.loads((store / 'data.json').read_text())


def put_tags(client, picture_id, tags):
    return client.put(f'/api/pictures/{picture_id}/tags', json={'tags': tags})


def tags_of(store, picture_id):
    return next(r['tags'] for r in read_records(store) if r['id'] == picture_id)


# ---------- normalize_tags ----------

def test_normalize_trims_lowercases_and_splits_commas():
    assert app_module.normalize_tags(['  Forest  ', 'sky, WATER']) == ['forest', 'sky', 'water']


def test_normalize_drops_empty_and_duplicates_keeping_first_position():
    assert app_module.normalize_tags(['sky', ' , ', 'tree', 'Sky']) == ['sky', 'tree']


def test_normalize_keeps_internal_spaces_and_underscores():
    assert app_module.normalize_tags(['line_art', 'oil  paint']) == ['line_art', 'oil  paint']


# ---------- US-002 acceptance criteria (AC 1-12) ----------

def test_ac2_ac3_added_tag_is_returned_and_persisted(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['nature', 'tree']}])
    response = put_tags(client, 1, ['nature', 'tree', 'Forest'])
    assert response.status_code == 200
    assert response.get_json()['picture']['tags'] == ['nature', 'tree', 'forest']
    assert tags_of(store, 1) == ['nature', 'tree', 'forest']


def test_ac4_tag_is_trimmed_and_lowercased(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': []}])
    put_tags(client, 1, ['  Forest  '])
    assert tags_of(store, 1) == ['forest']


def test_ac5_variant_of_existing_tag_is_not_duplicated(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['forest']}])
    put_tags(client, 1, ['forest', 'Forest', ' forest '])
    assert tags_of(store, 1) == ['forest']


@pytest.mark.parametrize('bad', ['', '   ', ' , '])
def test_ac6_empty_tag_is_rejected_and_tags_unchanged(client, store, bad):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['sky']}])
    response = put_tags(client, 1, ['sky', bad])
    assert response.status_code == 400
    assert 'cannot be empty' in response.get_json()['error']
    assert tags_of(store, 1) == ['sky']


def test_ac7_comma_separated_tags_are_both_added(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': []}])
    put_tags(client, 1, ['sky, water'])
    assert tags_of(store, 1) == ['sky', 'water']


def test_ac8_removing_tag_only_affects_that_picture(client, store):
    write_records(store, [
        {'id': 1, 'filename': '1.png', 'tags': ['sky']},
        {'id': 2, 'filename': '2.png', 'tags': ['sky']},
    ])
    put_tags(client, 1, [])
    assert tags_of(store, 2) == ['sky']
    results = client.get('/api/pictures?tags=sky').get_json()
    assert [r['id'] for r in results] == [2]


def test_ac9_removing_last_tag_keeps_picture_with_zero_tags(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['sky']}])
    put_tags(client, 1, [])
    assert read_records(store) == [{'id': 1, 'filename': '1.png', 'tags': []}]


def test_ac10_added_tag_is_immediately_filterable(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': []}])
    put_tags(client, 1, ['forest'])
    assert [r['id'] for r in client.get('/api/pictures?tags=forest').get_json()] == [1]
    assert client.get('/api/pictures/random?tags=forest').get_json()['id'] == 1


def test_ac11_removed_tag_is_immediately_unfilterable(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['forest']}])
    put_tags(client, 1, [])
    assert client.get('/api/pictures?tags=forest').get_json() == []
    assert client.get('/api/pictures/random?tags=forest').status_code == 404


# ---------- US-002 edge cases (listed under Assumptions) ----------

def test_edge_stored_duplicates_are_collapsed_on_edit(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['sky', 'sky']}])
    put_tags(client, 1, ['sky', 'sky', 'water'])
    assert tags_of(store, 1) == ['sky', 'water']


def test_edge_untouched_pictures_keep_their_records(client, store):
    write_records(store, [
        {'id': 1, 'filename': '1.png', 'tags': ['sky']},
        {'id': 2, 'filename': '2.png', 'tags': ['sky', 'sky']},
    ])
    put_tags(client, 1, ['sky', 'water'])
    assert tags_of(store, 2) == ['sky', 'sky']


def test_edge_editing_deleted_picture_returns_404_and_changes_nothing(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['sky']}])
    before = read_records(store)
    response = put_tags(client, 999, ['forest'])
    assert response.status_code == 404
    assert 'no longer exists' in response.get_json()['error']
    assert read_records(store) == before


# ---------- input validation and invariants ----------

@pytest.mark.parametrize('body', [{}, {'tags': 'sky'}, {'tags': [1, 2]}, {'tags': None}])
def test_malformed_body_is_rejected(client, store, body):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['sky']}])
    response = client.put('/api/pictures/1/tags', json=body)
    assert response.status_code == 400
    assert tags_of(store, 1) == ['sky']


def test_edit_never_changes_picture_count_or_filenames(client, store):
    records = [
        {'id': 1, 'filename': '1.png', 'tags': ['a']},
        {'id': 2, 'filename': '2.png', 'tags': ['b']},
    ]
    write_records(store, records)
    put_tags(client, 2, ['c'])
    after = read_records(store)
    assert [(r['id'], r['filename']) for r in after] == [(1, '1.png'), (2, '2.png')]
    assert after[0]['tags'] == ['a']
