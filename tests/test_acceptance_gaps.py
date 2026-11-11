# AI-generated tests (opencode tester agent, DeepSeek-V4.1-Flash), reviewed by the team.
# Prompt: "Add automated coverage for acceptance criteria in docs/requirements/US-001
# and US-002 that the existing suites do not exercise, using a temporary data.json and
# uploads folder so real data is never touched."

import io
import json
import os
import re
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 32
GIF = b'GIF89a' + b'\x00' * 32
WEBP = b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 32


def make_zip(entries):
    """entries: list of (archive_path, bytes). Returns the ZIP as bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


def post_zip(client, zip_bytes, name='refs.zip'):
    return client.post(
        '/api/import-zip',
        data={'archive': (io.BytesIO(zip_bytes), name)},
        content_type='multipart/form-data'
    )


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


# ---------- US-001 acceptance criteria not covered by test_zip_import.py ----------

@pytest.mark.parametrize('escaping_path', ['/abs.png', 'C:/win.png', 'a\\..\\b.png'])
def test_ac5_escaping_entry_paths_rejected_valid_entry_imports(client, store, escaping_path):
    # AC-US-001-05
    response = post_zip(client, make_zip([(escaping_path, PNG), ('ok.png', PNG)]))
    report = response.get_json()

    assert response.status_code == 200
    assert report['imported_count'] == 1
    assert report['failed_count'] == 1
    assert len(report['failures']) == 1

    failure = report['failures'][0]
    # zipfile stores backslashes as forward slashes, so compare the normalized path.
    assert failure['archive_path'] == escaping_path.replace('\\', '/')
    assert failure['reason']

    # The valid entry still imported, and no file landed outside uploads/.
    assert os.listdir(store / 'uploads') == [read_records(store)[0]['filename']]
    assert sorted(os.listdir(store)) == ['data.json', 'uploads']
    for outside in ('abs.png', 'win.png', 'b.png'):
        assert not (store / outside).exists()
        assert not (store.parent / outside).exists()


def test_ac11_oversize_archive_refused_whole(client, store, monkeypatch):
    # AC-US-001-11
    # The real limit is 100 MB; shrink it so the test stays small and fast.
    monkeypatch.setattr(app_module, 'MAX_ZIP_BYTES', 100)
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['keep']}])
    before_data = (store / 'data.json').read_text()
    before_uploads = sorted(os.listdir(store / 'uploads'))

    response = post_zip(client, make_zip([('big.png', PNG * 10)]))

    assert response.status_code == 400
    message = response.get_json()['message']
    assert '100 MB' in message and 'limit' in message
    assert (store / 'data.json').read_text() == before_data
    assert sorted(os.listdir(store / 'uploads')) == before_uploads


def test_ac14_excess_extracted_size_refused_whole(client, store, monkeypatch):
    # AC-US-001-14
    # The real extracted-size cap is 500 MB; shrink it for a fast test.
    monkeypatch.setattr(app_module, 'MAX_EXTRACTED_BYTES', 50)
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['keep']}])
    before_data = (store / 'data.json').read_text()
    before_uploads = sorted(os.listdir(store / 'uploads'))

    # Each PNG is 40 bytes, so two of them exceed the 50-byte extracted-size cap.
    response = post_zip(client, make_zip([('a.png', PNG), ('b.png', PNG)]))

    assert response.status_code == 400
    message = response.get_json()['message']
    assert 'extracted-size limit' in message and '500 MB' in message
    assert (store / 'data.json').read_text() == before_data
    assert sorted(os.listdir(store / 'uploads')) == before_uploads
    assert read_records(store) == [{'id': 1, 'filename': '1.png', 'tags': ['keep']}]


def test_ac15_import_survives_restart(client, store):
    # AC-US-001-15
    entries = [('a.png', PNG), ('b.jpg', JPG), ('c.gif', GIF)]
    report = post_zip(client, make_zip(entries)).get_json()
    assert report['imported_count'] == 3

    imported = read_records(store)
    # Simulate a restart: forget the cached id counter and build a fresh client.
    app_module.last_allocated_id = None
    restarted = app_module.app.test_client()

    pictures = restarted.get('/api/pictures').get_json()
    assert [(p['id'], p['filename'], p['tags']) for p in pictures] == [
        (p['id'], p['filename'], []) for p in imported
    ]
    for picture in imported:
        assert restarted.get(f"/uploads/{picture['filename']}").status_code == 200


# ---------- US-002 acceptance criteria not covered by test_tag_editing.py ----------

def test_ac1_gallery_exposes_per_picture_tag_editor(client):
    # AC-US-002-01
    response = client.get('/')
    assert response.status_code == 200
    assert 'text/html' in response.content_type
    html = response.get_data(as_text=True)

    # Stable ids/handlers, not styling: the editor container, the current-tags
    # container, the add-tags input/control, and the Save and Cancel controls.
    for marker in ('id="tagEditor"', 'id="tagEditorTags"', 'id="tagEditorInput"',
                   'addEditorTags', 'saveTagEdit', 'closeTagEditor'):
        assert marker in html


def test_ac12_cancel_leaves_stored_tags_untouched(client, store):
    # AC-US-002-12
    original = [{'id': 1, 'filename': '1.png', 'tags': ['nature', 'tree']}]
    write_records(store, original)

    # What the UI does when the gallery loads; a cancelled edit never sends a PUT.
    assert client.get('/api/pictures').status_code == 200
    assert read_records(store) == original

    html = client.get('/').get_data(as_text=True)
    assert 'onclick="closeTagEditor()"' in html and 'Cancel' in html

    # Partial, server-side verification of a client-side criterion: the Cancel
    # handler itself must not issue a fetch/PUT, otherwise "cancel" would persist.
    match = re.search(r'function closeTagEditor\(\)\s*\{(.*?)\n\s*\}', html, re.DOTALL)
    assert match is not None
    cancel_body = match.group(1)
    assert 'fetch' not in cancel_body
    assert 'PUT' not in cancel_body


def test_ac5_duplicate_tag_reports_already_present(client, store):
    # AC-US-002-05
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['forest']}])

    # The duplicate stays collapsed server-side...
    response = client.put('/api/pictures/1/tags',
                          json={'tags': ['forest', 'Forest', ' forest ']})
    assert response.status_code == 200
    assert read_records(store)[0]['tags'] == ['forest']

    # ...and the "already present" notice is produced by the editor in the page
    # the user actually sees (the PUT response itself carries no notice).
    html = client.get('/').get_data(as_text=True)
    match = re.search(r'function addEditorTags\(\)\s*\{(.*?)\n    \}', html, re.DOTALL)
    assert match is not None
    add_body = match.group(1)
    assert 'alreadyPresent' in add_body
    assert 'Already present: ' in add_body
