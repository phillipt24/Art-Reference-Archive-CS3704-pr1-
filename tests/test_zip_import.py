# AI-generated tests (Claude Code, claude-opus-5-5), reviewed by the team.
# Prompt: "Write pytest unit tests for each new function in app.py for ZIP import
# (US-001), plus integration tests for the US-001 acceptance criteria, using a
# temporary data.json and uploads folder so real data is never touched."

import io
import json
import os
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


# ---------- unit tests ----------

@pytest.mark.parametrize('name', ['../x.png', '/x.png', 'C:/x.png', 'a\\..\\b.png', 'a/../../b.png'])
def test_is_unsafe_path_rejects_escaping_paths(name):
    assert app_module.is_unsafe_path(name)


@pytest.mark.parametrize('name', ['cat.png', 'folder/cat.png', 'a/b/c.jpg'])
def test_is_unsafe_path_allows_normal_paths(name):
    assert not app_module.is_unsafe_path(name)


@pytest.mark.parametrize('name', ['__MACOSX/._cat.png', '__MACOSX/refs/._cat.png', 'refs/._cat.png', '.DS_Store', 'refs/Thumbs.db'])
def test_is_os_metadata_detects_hidden_files(name):
    assert app_module.is_os_metadata(name)


@pytest.mark.parametrize('name', ['cat.png', 'refs/cat.png', 'macosx/cat.png'])
def test_is_os_metadata_allows_real_files(name):
    assert not app_module.is_os_metadata(name)


@pytest.mark.parametrize('ext, content', [('.png', PNG), ('.jpg', JPG), ('.jpeg', JPG), ('.gif', GIF), ('.webp', WEBP)])
def test_looks_like_image_accepts_real_headers(ext, content):
    assert app_module.looks_like_image(ext, content[:12])


def test_looks_like_image_rejects_renamed_text_file():
    assert not app_module.looks_like_image('.png', b'hello, world')


def test_next_id_is_unique_and_increasing_for_a_batch(store):
    ids = [app_module.next_id([]) for _ in range(200)]
    assert len(set(ids)) == 200
    assert ids == sorted(ids)


def test_next_id_starts_above_existing_ids(store):
    huge_id = 10 ** 15
    assert app_module.next_id([{'id': huge_id}]) > huge_id


def test_load_data_missing_file_is_empty_archive(store):
    assert app_module.load_data() == []


def test_load_data_corrupt_file_raises(store):
    (store / 'data.json').write_text('{not json')
    with pytest.raises(app_module.StoreError):
        app_module.load_data()


def test_save_data_writes_json_and_leaves_no_temp_file(store):
    app_module.save_data([{'id': 1, 'filename': '1.png', 'tags': []}])
    assert read_records(store) == [{'id': 1, 'filename': '1.png', 'tags': []}]
    assert not (store / 'data.json.tmp').exists()


def test_save_data_failure_raises_store_error_and_keeps_old_file(store, monkeypatch):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['keep']}])

    def failing_replace(src, dst):
        raise OSError('disk full')

    monkeypatch.setattr(app_module.os, 'replace', failing_replace)
    with pytest.raises(app_module.StoreError):
        app_module.save_data([])
    assert read_records(store) == [{'id': 1, 'filename': '1.png', 'tags': ['keep']}]


def test_open_archive_rejects_non_zip():
    archive, error = app_module.open_archive(io.BytesIO(b'not a zip'))
    assert archive is None
    assert 'could not be read' in error


def test_open_archive_rejects_too_many_entries():
    zip_bytes = make_zip([(f'{i}.png', PNG) for i in range(201)])
    archive, error = app_module.open_archive(io.BytesIO(zip_bytes))
    assert archive is None
    assert '200' in error


def test_open_archive_accepts_exactly_200_entries():
    zip_bytes = make_zip([(f'{i}.png', PNG) for i in range(200)])
    archive, error = app_module.open_archive(io.BytesIO(zip_bytes))
    assert error is None


def test_open_archive_does_not_count_mac_metadata_toward_limit():
    entries = [(f'refs/{i}.png', PNG) for i in range(150)]
    entries += [(f'__MACOSX/refs/._{i}.png', b'\x00\x05\x16\x07') for i in range(150)]
    archive, error = app_module.open_archive(io.BytesIO(make_zip(entries)))
    assert error is None


def test_open_archive_rejects_oversize_upload(monkeypatch):
    monkeypatch.setattr(app_module, 'MAX_ZIP_BYTES', 100)
    archive, error = app_module.open_archive(io.BytesIO(make_zip([('a.png', PNG * 10)])))
    assert archive is None
    assert '100 MB' in error


def test_open_archive_rejects_oversize_extracted_content(monkeypatch):
    monkeypatch.setattr(app_module, 'MAX_EXTRACTED_BYTES', 50)
    archive, error = app_module.open_archive(io.BytesIO(make_zip([('a.png', PNG), ('b.png', PNG)])))
    assert archive is None
    assert '500 MB' in error


def read_single_entry(name, content):
    archive = zipfile.ZipFile(io.BytesIO(make_zip([(name, content)])))
    return app_module.read_entry(archive, archive.infolist()[0])


def test_read_entry_valid_image():
    ext, content, reason = read_single_entry('Folder/Cat.PNG', PNG)
    assert (ext, content, reason) == ('.png', PNG, None)


def test_read_entry_unsupported_type():
    assert 'not a supported image type' in read_single_entry('notes.txt', b'hello')[2]


def test_read_entry_empty_file():
    assert read_single_entry('empty.png', b'')[2] == 'file is empty'


def test_read_entry_not_really_an_image():
    assert 'not a valid image' in read_single_entry('fake.png', b'hello, world')[2]


def test_read_entry_oversize(monkeypatch):
    monkeypatch.setattr(app_module, 'MAX_IMAGE_BYTES', 10)
    assert '20 MB' in read_single_entry('big.png', PNG)[2]


def test_add_pictures_creates_untagged_records_with_files(store):
    added, failures = app_module.add_pictures([('a.png', '.png', PNG), ('b.jpg', '.jpg', JPG)])
    assert failures == []
    assert [record['tags'] for record in added] == [[], []]
    for record in added:
        assert (store / 'uploads' / record['filename']).exists()
    assert read_records(store) == added


def test_import_archive_report_matches_store(store):
    zip_bytes = make_zip([('a.png', PNG), ('notes.txt', b'hello')])
    report, status = app_module.import_archive(io.BytesIO(zip_bytes))
    assert status == 200
    assert report['imported_count'] == 1
    assert report['failed_count'] == len(report['failures']) == 1
    assert report['message'] == 'Imported 1 picture(s); 1 failed.'
    assert len(read_records(store)) == report['imported_count']


def test_import_archive_refused_archive_writes_nothing(store):
    report, status = app_module.import_archive(io.BytesIO(b'not a zip'))
    assert status == 400
    assert report['imported_count'] == 0
    assert not (store / 'data.json').exists()
    assert os.listdir(store / 'uploads') == []


# ---------- integration tests (US-001 acceptance criteria) ----------

def test_ac1_three_images_added_untagged(client, store):
    write_records(store, [{'id': i, 'filename': f'{i}.png', 'tags': ['old']} for i in range(1, 5)])
    response = post_zip(client, make_zip([('a.png', PNG), ('b.jpg', JPG), ('c.gif', GIF)]))
    assert response.status_code == 200
    records = read_records(store)
    assert len(records) == 7
    assert all(record['tags'] == [] for record in records[4:])


def test_ac2_untagged_imports_follow_filters(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['nature']}])
    post_zip(client, make_zip([('a.png', PNG)]))
    assert len(client.get('/api/pictures?tags=').get_json()) == 2
    assert [p['id'] for p in client.get('/api/pictures?tags=nature').get_json()] == [1]


def test_ac3_single_upload_unchanged(client, store):
    response = client.post(
        '/api/upload',
        data={'image': (io.BytesIO(PNG), 'tree.png'), 'tags': 'Nature, tree'},
        content_type='multipart/form-data'
    )
    assert response.status_code == 200
    assert read_records(store)[0]['tags'] == ['nature', 'tree']


def test_ac4_partial_success_report(client, store):
    zip_bytes = make_zip([
        ('a.png', PNG), ('b.png', PNG), ('c.jpg', JPG),
        ('notes.txt', b'hello'), ('fake.png', b'not an image')
    ])
    report = post_zip(client, zip_bytes).get_json()
    assert report['imported_count'] == 3
    assert report['failed_count'] == 2
    assert {f['archive_path'] for f in report['failures']} == {'notes.txt', 'fake.png'}
    assert all(f['reason'] for f in report['failures'])
    assert len(read_records(store)) == 3


def test_ac5_path_escape_rejected(client, store):
    report = post_zip(client, make_zip([('../../evil.png', PNG), ('ok.png', PNG)])).get_json()
    assert report['imported_count'] == 1
    assert report['failures'][0]['archive_path'] == '../../evil.png'
    assert not (store / 'evil.png').exists()
    assert not (store.parent / 'evil.png').exists()


def test_ac6_corrupt_zip_adds_nothing(client, store):
    response = post_zip(client, b'PK\x03\x04 this is not really a zip')
    assert response.status_code == 400
    assert 'could not be read' in response.get_json()['message']
    assert not (store / 'data.json').exists()


def test_ac7_empty_zip(client, store):
    report = post_zip(client, make_zip([])).get_json()
    assert report['imported_count'] == 0
    assert report['message'] == 'The archive contained no entries.'


def test_ac8_ac9_nested_folders_and_duplicate_names(client, store):
    report = post_zip(client, make_zip([('a/cat.png', PNG), ('b/cat.png', PNG)])).get_json()
    assert report['imported_count'] == 2
    records = read_records(store)
    assert len({record['id'] for record in records}) == 2
    assert len({record['filename'] for record in records}) == 2
    assert all('/' not in record['filename'] and '\\' not in record['filename'] for record in records)
    for record in records:
        assert client.get(f"/uploads/{record['filename']}").status_code == 200


def test_ac10_name_collision_keeps_existing_picture(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': ['keep']}])
    report = post_zip(client, make_zip([('1.png', PNG)])).get_json()
    assert report['imported_count'] == 1
    records = read_records(store)
    assert records[0] == {'id': 1, 'filename': '1.png', 'tags': ['keep']}
    assert records[1]['filename'] != '1.png'


def test_ac12_more_than_200_refused_whole(client, store):
    response = post_zip(client, make_zip([(f'{i}.png', PNG) for i in range(201)]))
    assert response.status_code == 400
    assert not (store / 'data.json').exists()


def test_ac13_oversize_image_fails_others_import(client, store, monkeypatch):
    monkeypatch.setattr(app_module, 'MAX_IMAGE_BYTES', 50)
    report = post_zip(client, make_zip([('big.png', PNG + b'\x00' * 100), ('ok.png', PNG)])).get_json()
    assert report['imported_count'] == 1
    assert report['failures'][0]['archive_path'] == 'big.png'


def test_ac16_all_valid_reports_zero_failed(client, store):
    report = post_zip(client, make_zip([('a.png', PNG), ('b.webp', WEBP)])).get_json()
    assert report['imported_count'] == 2
    assert report['failed_count'] == 0
    assert report['failures'] == []


def test_mac_zip_imports_without_metadata_failures(client, store):
    entries = [('refs/a.png', PNG), ('__MACOSX/refs/._a.png', b'\x00\x05\x16\x07'), ('refs/.DS_Store', b'\x00')]
    report = post_zip(client, make_zip(entries)).get_json()
    assert report['imported_count'] == 1
    assert report['failures'] == []


def test_corrupt_data_json_is_not_overwritten(client, store):
    (store / 'data.json').write_text('{not json')
    response = post_zip(client, make_zip([('a.png', PNG)]))
    assert response.status_code == 500
    assert 'error' in response.get_json()
    assert (store / 'data.json').read_text() == '{not json'


def test_delete_removes_record_and_file(client, store):
    write_records(store, [{'id': 1, 'filename': '1.png', 'tags': []}])
    assert client.delete('/api/pictures/1').status_code == 200
    assert read_records(store) == []
    assert not (store / 'uploads' / '1.png').exists()
