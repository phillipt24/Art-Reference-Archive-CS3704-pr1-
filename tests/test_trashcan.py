# AI-generated tests (opencode build/tester agent, DeepSeek-V4.1-Flash), to be reviewed by the team.
# Prompt: "Write tests for US-004 (docs/requirements/US-004-trashcan-soft-delete.md),
# one or more per acceptance criterion AC 1–20, tagged # AC-US-004-<n>.
# Use docs/design/us-004-trashcan-sequence-diagram.md for the routes,
# status codes and error messages. Put them in a new file tests/test_trashcan.py
# using the same temp data.json/uploads fixtures as tests/test_zip_import.py.
# Add a comment at the top of the file saying the tests are AI-generated,
# with this prompt. Don't modify existing tests."

import json
import os
import re
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


def make_record(picture_id, tags, trashed=False):
    record = {'id': picture_id, 'filename': f'{picture_id}.png', 'tags': list(tags)}
    if trashed:
        record['trashed'] = True
    return record


def function_body(html, name):
    """Return the body of `async function <name>(...) { ... }` in the page."""
    match = re.search(
        r'async function ' + re.escape(name) + r'\([^)]*\)\s*\{(.*?)\n    \}',
        html,
        re.DOTALL,
    )
    assert match is not None, f'could not find async function {name} in the page'
    return match.group(1)


# ---------- US-004 acceptance criteria (AC 1-20) ----------

def test_ac1_soft_delete_moves_one_picture_to_trash_and_keeps_the_rest(client, store):
    # AC-US-004-01
    records = [make_record(i, [f'tag{i}']) for i in range(1, 6)]
    write_records(store, records)
    tags_before = {r['id']: list(r['tags']) for r in records}
    files_before = {
        r['id']: (store / 'uploads' / r['filename']).read_bytes() for r in records
    }

    response = client.delete('/api/pictures/3')
    assert response.status_code == 200

    gallery = client.get('/api/pictures').get_json()
    assert [p['id'] for p in gallery] == [1, 2, 4, 5]
    assert 3 not in [p['id'] for p in gallery]

    trash = client.get('/api/trash').get_json()
    assert [p['id'] for p in trash] == [3]

    stored = read_records(store)
    assert len(stored) == 5
    assert sum(1 for r in stored if r.get('trashed')) == 1
    for record in stored:
        if record['id'] == 3:
            continue
        assert record['tags'] == tags_before[record['id']]
        assert (store / 'uploads' / record['filename']).read_bytes() == files_before[record['id']]
        assert client.get(f"/uploads/{record['filename']}").status_code == 200


def test_ac2_trashed_picture_absent_from_every_active_view(client, store):
    # AC-US-004-02
    write_records(store, [
        make_record(1, ['nature', 'tree']),
        make_record(2, ['nature']),
        make_record(3, ['other']),
    ])
    assert client.delete('/api/pictures/1').status_code == 200

    # Gallery with no filter and gallery filtered by "nature".
    assert {p['id'] for p in client.get('/api/pictures').get_json()} == {2, 3}
    assert {p['id'] for p in client.get('/api/pictures?tags=nature').get_json()} == {2}

    # Random viewer filtered by "nature".
    assert client.get('/api/pictures/random?tags=nature').get_json()['id'] == 2

    # Slideshow filtered by "nature" (same endpoint, with its history excluded).
    assert client.get('/api/pictures/random?tags=nature&exclude_ids=2').get_json()['id'] == 2


def test_ac3_only_matching_picture_trashed_reports_no_match(client, store):
    # AC-US-004-03
    write_records(store, [make_record(1, ['sky']), make_record(2, ['tree'])])
    assert client.delete('/api/pictures/1').status_code == 200

    for url in (
        '/api/pictures/random?tags=sky',
        '/api/pictures/random?tags=sky&exclude_ids=2',
        '/api/pictures/random?tags=sky&exclude_ids=1',
    ):
        response = client.get(url)
        assert response.status_code == 404
        assert 'No pictures match' in response.get_json()['error']


def test_ac4_trash_entry_keeps_image_and_tags(client, store):
    # AC-US-004-04
    write_records(store, [make_record(1, ['nature', 'tree'])])
    assert client.delete('/api/pictures/1').status_code == 200

    entry = client.get('/api/trash').get_json()[0]
    assert entry['id'] == 1
    assert entry['filename'] == '1.png'
    assert entry['tags'] == ['nature', 'tree']
    assert entry['image_available'] is True
    assert client.get(f"/uploads/{entry['filename']}").status_code == 200

    # The trash view renders the stored image at a viewable size plus the tags.
    trash_body = function_body(client.get('/').get_data(as_text=True), 'loadTrash')
    assert '/uploads/${picture.filename}' in trash_body
    assert 'max-height: 300px' in trash_body
    assert 'picture.tags.join' in trash_body


def test_ac5_trash_survives_restart(client, store):
    # AC-US-004-05
    write_records(store, [
        make_record(1, ['nature', 'tree']),
        make_record(2, ['sky']),
    ])
    assert client.delete('/api/pictures/1').status_code == 200

    # Simulate a restart: forget the cached id counter and build a fresh client.
    app_module.last_allocated_id = None
    restarted = app_module.app.test_client()

    trash = restarted.get('/api/trash').get_json()
    assert [p['id'] for p in trash] == [1]
    assert trash[0]['tags'] == ['nature', 'tree']
    assert trash[0]['image_available'] is True
    assert [p['id'] for p in restarted.get('/api/pictures').get_json()] == [2]
    assert next(r for r in read_records(store) if r['id'] == 2)['tags'] == ['sky']


def test_ac6_restore_returns_picture_to_active_views(client, store):
    # AC-US-004-06
    write_records(store, [
        make_record(1, ['nature', 'tree'], trashed=True),
        make_record(2, ['other']),
    ])
    response = client.post('/api/trash/1/restore')
    assert response.status_code == 200

    gallery = client.get('/api/pictures').get_json()
    assert [p['id'] for p in gallery].count(1) == 1
    assert next(p for p in gallery if p['id'] == 1)['tags'] == ['nature', 'tree']
    assert [p['id'] for p in client.get('/api/pictures?tags=nature').get_json()] == [1]
    assert client.get('/api/pictures/random?tags=nature').get_json()['id'] == 1
    assert client.get('/api/pictures/random?tags=nature&exclude_ids=2').get_json()['id'] == 1
    assert client.get('/api/trash').get_json() == []
    assert 'trashed' not in next(r for r in read_records(store) if r['id'] == 1)


def test_ac7_restore_survives_restart(client, store):
    # AC-US-004-07
    write_records(store, [make_record(1, ['nature', 'tree'], trashed=True)])
    assert client.post('/api/trash/1/restore').status_code == 200

    app_module.last_allocated_id = None
    restarted = app_module.app.test_client()

    gallery = restarted.get('/api/pictures').get_json()
    assert [p['id'] for p in gallery] == [1]
    assert gallery[0]['tags'] == ['nature', 'tree']
    assert restarted.get('/api/trash').get_json() == []
    assert 'trashed' not in read_records(store)[0]


def test_ac8_permanent_delete_removes_record_and_file_for_good(client, store):
    # AC-US-004-08
    write_records(store, [
        make_record(1, ['nature'], trashed=True),
        make_record(2, ['tree']),
    ])
    response = client.delete('/api/trash/1')
    assert response.status_code == 200

    assert client.get('/api/trash').get_json() == []
    assert [p['id'] for p in client.get('/api/pictures').get_json()] == [2]
    assert not (store / 'uploads' / '1.png').exists()
    assert client.get('/uploads/1.png').status_code == 404
    assert [r['id'] for r in read_records(store)] == [2]

    # No action can bring it back.
    assert client.post('/api/trash/1/restore').status_code == 404
    assert client.delete('/api/trash/1').status_code == 404


def test_ac9_permanent_delete_confirmation_names_picture_and_changes_nothing(client, store):
    # AC-US-004-09
    write_records(store, [make_record(1, ['nature'], trashed=True)])
    before = read_records(store)

    body = function_body(client.get('/').get_data(as_text=True), 'deletePermanently')
    assert 'Permanently delete ${picture.filename}?' in body
    assert 'cannot be undone' in body

    # Merely viewing the trash sends no delete request, so nothing changes yet.
    client.get('/api/trash')
    assert read_records(store) == before
    assert (store / 'uploads' / '1.png').exists()


def test_ac10_cancelling_permanent_delete_leaves_picture_restorable(client, store):
    # AC-US-004-10
    write_records(store, [make_record(1, ['nature', 'tree'], trashed=True)])
    before = read_records(store)

    # Dismissing the confirmation returns before any request is sent.
    body = function_body(client.get('/').get_data(as_text=True), 'deletePermanently')
    assert 'if (!ok) return;' in body

    trash = client.get('/api/trash').get_json()
    assert [p['id'] for p in trash] == [1]
    assert trash[0]['tags'] == ['nature', 'tree']
    assert (store / 'uploads' / '1.png').exists()
    assert read_records(store) == before

    # It is still restorable.
    assert client.post('/api/trash/1/restore').status_code == 200
    assert [p['id'] for p in client.get('/api/pictures').get_json()] == [1]


def test_ac11_trash_and_active_views_are_mutually_exclusive(client, store):
    # AC-US-004-11
    write_records(store, [
        make_record(1, ['shared'], trashed=True),
        make_record(2, ['shared']),
        make_record(3, []),
    ])
    assert [p['id'] for p in client.get('/api/trash').get_json()] == [1]

    gallery = client.get('/api/pictures').get_json()
    assert {p['id'] for p in gallery} == {2, 3}
    assert {p['id'] for p in client.get('/api/pictures?tags=shared').get_json()} == {2}
    for _ in range(5):
        assert client.get('/api/pictures/random?tags=shared').get_json()['id'] == 2
    # Slideshow fallback can hand back an excluded active picture, never the trashed one.
    assert client.get('/api/pictures/random?tags=shared&exclude_ids=2').get_json()['id'] == 2


def test_ac12_repeat_delete_of_trashed_picture_is_rejected_without_duplicating(client, store):
    # AC-US-004-12
    write_records(store, [make_record(1, ['nature', 'tree'])])
    assert client.delete('/api/pictures/1').status_code == 200
    before = read_records(store)
    uploads_before = sorted(os.listdir(store / 'uploads'))

    response = client.delete('/api/pictures/1')
    assert response.status_code == 409
    assert 'already in the trash' in response.get_json()['error']

    assert read_records(store) == before
    assert len(client.get('/api/trash').get_json()) == 1
    assert client.get('/api/pictures').get_json() == []
    assert sorted(os.listdir(store / 'uploads')) == uploads_before
    assert next(r for r in read_records(store) if r['id'] == 1)['tags'] == ['nature', 'tree']


def test_ac13_restore_of_active_picture_is_rejected(client, store):
    # AC-US-004-13
    write_records(store, [
        make_record(1, ['nature']),
        make_record(2, ['other'], trashed=True),
    ])
    before = read_records(store)

    response = client.post('/api/trash/1/restore')
    assert response.status_code == 409
    assert 'not in the trash' in response.get_json()['error']

    assert read_records(store) == before
    assert [p['id'] for p in client.get('/api/pictures').get_json()] == [1]
    assert [p['id'] for p in client.get('/api/trash').get_json()] == [2]


def test_ac14_missing_image_is_marked_and_blocks_restore(client, store):
    # AC-US-004-14
    write_records(store, [
        make_record(1, ['nature'], trashed=True),
        make_record(2, ['tree'], trashed=True),
    ])
    (store / 'uploads' / '1.png').unlink()
    before = read_records(store)

    response = client.get('/api/trash')
    assert response.status_code == 200
    entries = {p['id']: p for p in response.get_json()}
    assert set(entries) == {1, 2}
    assert entries[1]['image_available'] is False
    assert entries[2]['image_available'] is True

    restore = client.post('/api/trash/1/restore')
    assert restore.status_code == 409
    error = restore.get_json()['error']
    assert 'image' in error and 'unavailable' in error

    assert read_records(store) == before
    assert [p['id'] for p in client.get('/api/trash').get_json()] == [1, 2]


def test_ac15_missing_image_can_still_be_permanently_deleted(client, store):
    # AC-US-004-15
    write_records(store, [
        make_record(1, ['nature'], trashed=True),
        make_record(2, ['tree'], trashed=True),
    ])
    (store / 'uploads' / '1.png').unlink()
    other_before = next(r for r in read_records(store) if r['id'] == 2)

    response = client.delete('/api/trash/1')
    assert response.status_code == 200
    assert client.get('/api/trash').status_code == 200
    assert [p['id'] for p in client.get('/api/trash').get_json()] == [2]
    assert next(r for r in read_records(store) if r['id'] == 2) == other_before


def test_ac16_stale_trash_action_after_deletion_elsewhere_is_rejected(client, store):
    # AC-US-004-16
    write_records(store, [
        make_record(1, ['nature'], trashed=True),
        make_record(2, ['tree'], trashed=True),
    ])
    # Another tab permanently deletes picture 1.
    assert client.delete('/api/trash/1').status_code == 200
    before = read_records(store)

    restore = client.post('/api/trash/1/restore')
    assert restore.status_code == 404
    assert 'no longer exists' in restore.get_json()['error']

    purge = client.delete('/api/trash/1')
    assert purge.status_code == 404
    assert 'no longer exists' in purge.get_json()['error']

    assert read_records(store) == before
    # The refreshed trash list shows only the pictures actually in the trash.
    assert [p['id'] for p in client.get('/api/trash').get_json()] == [2]
    assert client.get('/api/pictures').get_json() == []


def test_ac17_restart_with_active_trash_and_deleted_picture(client, store):
    # AC-US-004-17
    write_records(store, [make_record(i, [f't{i}']) for i in range(1, 7)])
    assert client.delete('/api/pictures/2').status_code == 200   # trashed
    assert client.delete('/api/pictures/5').status_code == 200   # trashed
    assert client.delete('/api/pictures/3').status_code == 200   # trashed
    assert client.delete('/api/trash/3').status_code == 200      # permanently deleted

    app_module.last_allocated_id = None
    restarted = app_module.app.test_client()

    assert [p['id'] for p in restarted.get('/api/pictures').get_json()] == [1, 4, 6]
    assert [p['id'] for p in restarted.get('/api/trash').get_json()] == [2, 5]
    assert restarted.get('/uploads/3.png').status_code == 404
    assert not (store / 'uploads' / '3.png').exists()


def test_ac18_other_pictures_keep_tags_and_images_after_trash_and_purge(client, store):
    # AC-US-004-18
    records = [make_record(i, [f'tag{i}']) for i in range(1, 7)]
    write_records(store, records)
    originals = {
        r['id']: (list(r['tags']), (store / 'uploads' / r['filename']).read_bytes())
        for r in records
    }

    assert client.delete('/api/pictures/1').status_code == 200   # moved to trash
    assert client.delete('/api/pictures/2').status_code == 200   # trashed then purged
    assert client.delete('/api/trash/2').status_code == 200

    remaining = {3, 4, 5, 6}
    gallery = client.get('/api/pictures').get_json()
    assert {p['id'] for p in gallery} == remaining
    for picture_id in remaining:
        record = next(p for p in gallery if p['id'] == picture_id)
        tags, content = originals[picture_id]
        assert record['tags'] == tags
        assert (store / 'uploads' / record['filename']).read_bytes() == content
        assert client.get(f"/uploads/{record['filename']}").status_code == 200
        assert [p['id'] for p in client.get(f"/api/pictures?tags={tags[0]}").get_json()] == [picture_id]


def test_ac19_tag_only_on_deleted_picture_matches_nothing_but_shared_tag_still_works(client, store):
    # AC-US-004-19
    write_records(store, [
        make_record(1, ['sky', 'nature']),
        make_record(2, ['nature']),
        make_record(3, ['other']),
    ])
    assert client.delete('/api/pictures/1').status_code == 200
    assert client.delete('/api/trash/1').status_code == 200

    assert client.get('/api/pictures?tags=sky').get_json() == []
    for url in (
        '/api/pictures/random?tags=sky',
        '/api/pictures/random?tags=sky&exclude_ids=2',
        '/api/pictures/random?tags=sky&exclude_ids=1',
    ):
        response = client.get(url)
        assert response.status_code == 404
        assert 'No pictures match' in response.get_json()['error']

    # "nature" was on both the deleted picture and a surviving one.
    assert [p['id'] for p in client.get('/api/pictures?tags=nature').get_json()] == [2]
    assert client.get('/api/pictures/random?tags=nature').get_json()['id'] == 2


def test_ac20_picture_trashed_from_random_or_slideshow_disappears(client, store):
    # AC-US-004-20
    write_records(store, [make_record(1, ['solo']), make_record(2, ['other'])])
    # Picture 1 is what the random viewer / slideshow currently displays.
    assert client.get('/api/pictures/random?tags=solo').get_json()['id'] == 1
    assert client.delete('/api/pictures/1').status_code == 200

    # The server can no longer return it, even through the slideshow fallback.
    assert client.get('/api/pictures/random?tags=solo').status_code == 404
    assert client.get('/api/pictures/random?tags=solo&exclude_ids=2').status_code == 404
    assert client.get('/api/pictures/random?tags=').get_json()['id'] == 2

    # Both views stop showing it on response: they hide/clear the image and move on.
    html = client.get('/').get_data(as_text=True)
    random_body = function_body(html, 'deleteRandomPicture')
    assert 'moveToTrash' in random_body
    assert 'randomImage").style.display = "none"' in random_body
    timer_body = function_body(html, 'deleteTimerPicture')
    assert 'moveToTrash' in timer_body
    assert 'loadTimerPicture()' in timer_body
