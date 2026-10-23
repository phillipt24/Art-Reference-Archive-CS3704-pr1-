import os
import io
import json
import random
import threading
import time
import zipfile
import zlib
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MB = 1024 * 1024  # open question in the design doc: MB vs MiB
MAX_ZIP_BYTES = 100 * MB
MAX_ZIP_ENTRIES = 200
MAX_IMAGE_BYTES = 20 * MB
MAX_EXTRACTED_BYTES = 500 * MB
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

# Every read and write of data.json happens while holding this lock
data_lock = threading.Lock()
last_allocated_id = None

class StoreError(Exception):
    pass

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise StoreError('data.json could not be read; nothing was changed') from e

def save_data(data):
    # Write to a temp file, then swap it in, so data.json is never half-written
    tmp_path = DATA_FILE + '.tmp'
    try:
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, DATA_FILE)
    except OSError as e:
        raise StoreError('data.json could not be saved; nothing was changed') from e

def next_id(data):
    # Must be called while holding data_lock
    global last_allocated_id
    if last_allocated_id is None:
        last_allocated_id = max((img['id'] for img in data), default=0)
    last_allocated_id = max(last_allocated_id + 1, int(time.time() * 1000))
    return last_allocated_id

@app.errorhandler(StoreError)
def handle_store_error(e):
    return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/upload', methods=['POST'])
def upload_picture():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    raw_tags = request.form.get('tags', '')
    tags = [t.strip().lower() for t in raw_tags.split(',') if t.strip()]

    ext = os.path.splitext(file.filename)[1]

    with data_lock:
        data = load_data()
        picture_id = next_id(data)
        filename = f"{picture_id}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        picture_record = {
            'id': picture_id,
            'filename': filename,
            'tags': tags
        }
        data.append(picture_record)
        save_data(data)

    return jsonify({'success': True, 'picture': picture_record})

def is_os_metadata(name):
    # Hidden files that macOS and Windows add when zipping a folder
    parts = name.replace('\\', '/').split('/')
    return parts[0] == '__MACOSX' or parts[-1].startswith('._') or parts[-1] in ('.DS_Store', 'Thumbs.db')

def is_unsafe_path(name):
    normalized = name.replace('\\', '/')
    return normalized.startswith('/') or ':' in normalized or '..' in normalized.split('/')

def looks_like_image(ext, header):
    if ext in ('.jpg', '.jpeg'):
        return header.startswith(b'\xff\xd8\xff')
    if ext == '.png':
        return header.startswith(b'\x89PNG\r\n\x1a\n')
    if ext == '.gif':
        return header[:6] in (b'GIF87a', b'GIF89a')
    if ext == '.webp':
        return header[:4] == b'RIFF' and header[8:12] == b'WEBP'
    return False

def archive_entries(archive):
    return [info for info in archive.infolist() if not info.is_dir() and not is_os_metadata(info.filename)]

def open_archive(upload):
    raw = upload.read(MAX_ZIP_BYTES + 1)
    if len(raw) > MAX_ZIP_BYTES:
        return None, 'The archive is larger than the 100 MB limit.'
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return None, 'The archive could not be read.'
    supported = [
        info for info in archive_entries(archive)
        if os.path.splitext(info.filename)[1].lower() in SUPPORTED_EXTENSIONS
    ]
    if len(supported) > MAX_ZIP_ENTRIES:
        return None, 'The archive contains more than 200 images, the entry limit.'
    if sum(info.file_size for info in supported) > MAX_EXTRACTED_BYTES:
        return None, 'The archive would extract to more than 500 MB, the extracted-size limit.'
    return archive, None

def read_entry(archive, info):
    """Return (ext, content, None) for a valid image, or (None, None, reason)."""
    if is_unsafe_path(info.filename):
        return None, None, 'path would place the file outside the uploads folder'
    ext = os.path.splitext(info.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return None, None, 'not a supported image type (jpg, jpeg, png, gif, webp)'
    if info.file_size > MAX_IMAGE_BYTES:
        return None, None, 'larger than the 20 MB per-image limit'
    try:
        with archive.open(info) as f:
            content = f.read(MAX_IMAGE_BYTES + 1)
    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, EOFError):
        return None, None, 'could not be extracted'
    if len(content) > MAX_IMAGE_BYTES:
        return None, None, 'larger than the 20 MB per-image limit'
    if not content:
        return None, None, 'file is empty'
    if not looks_like_image(ext, content[:12]):
        return None, None, 'file contents are not a valid image'
    return ext, content, None

def add_pictures(entries):
    added, failures = [], []
    with data_lock:
        data = load_data()
        for archive_path, ext, content in entries:
            picture_id = next_id(data)
            filename = f"{picture_id}{ext}"
            try:
                with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as f:
                    f.write(content)
            except OSError:
                failures.append({'archive_path': archive_path, 'reason': 'could not be saved'})
                continue
            record = {'id': picture_id, 'filename': filename, 'tags': []}
            data.append(record)
            added.append(record)
        save_data(data)
    return added, failures

def import_archive(upload):
    archive, error = open_archive(upload)
    if error:
        return {'imported_count': 0, 'failed_count': 0, 'failures': [], 'message': error}, 400

    valid_entries, failures, examined, total = [], [], 0, 0
    with archive:
        for info in archive_entries(archive):
            examined += 1
            ext, content, reason = read_entry(archive, info)
            if reason:
                failures.append({'archive_path': info.filename, 'reason': reason})
                continue
            total += len(content)
            if total > MAX_EXTRACTED_BYTES:
                message = 'The archive would extract to more than 500 MB, the extracted-size limit.'
                return {'imported_count': 0, 'failed_count': 0, 'failures': [], 'message': message}, 400
            valid_entries.append((info.filename, ext, content))

    added, save_failures = add_pictures(valid_entries) if valid_entries else ([], [])
    failures += save_failures

    if examined == 0:
        message = 'The archive contained no entries.'
    else:
        message = f"Imported {len(added)} picture(s); {len(failures)} failed."

    return {
        'imported_count': len(added),
        'failed_count': len(failures),
        'failures': failures,
        'message': message
    }, 200

@app.route('/api/import-zip', methods=['POST'])
def import_zip():
    if 'archive' not in request.files or request.files['archive'].filename == '':
        return jsonify({'error': 'No archive selected'}), 400
    report, status = import_archive(request.files['archive'])
    return jsonify(report), status

@app.route('/api/pictures', methods=['GET'])
def get_pictures():
    raw_tags = request.args.get('tags', '')
    search_tags = [t.strip().lower() for t in raw_tags.split(',') if t.strip()]

    with data_lock:
        data = load_data()

    if search_tags:
        filtered = [
            img for img in data
            if all(st in img['tags'] for st in search_tags)
        ]
    else:
        filtered = data

    return jsonify(filtered)

@app.route('/api/pictures/random', methods=['GET'])
def get_random_picture():
    raw_tags = request.args.get('tags', '')
    search_tags = [t.strip().lower() for t in raw_tags.split(',') if t.strip()]

    raw_excludes = request.args.get('exclude_ids', '')
    exclude_ids = [int(i) for i in raw_excludes.split(',') if i.strip().isdigit()]

    with data_lock:
        data = load_data()

    if search_tags:
        filtered = [
            img for img in data
            if all(st in img['tags'] for st in search_tags)
        ]
    else:
        filtered = data

    if not filtered:
        return jsonify({'error': 'No pictures match criteria'}), 404

    eligible_choices = [img for img in filtered if img['id'] not in exclude_ids]

    if not eligible_choices:
        eligible_choices = [img for img in filtered if img['id'] != (exclude_ids[0] if exclude_ids else None)]
        if not eligible_choices:
            eligible_choices = filtered

    selected = random.choice(eligible_choices)
    return jsonify(selected)

@app.route('/api/pictures/<int:picture_id>', methods=['DELETE'])
def delete_picture(picture_id):
    with data_lock:
        data = load_data()
        picture_to_delete = next((img for img in data if img['id'] == picture_id), None)

        if not picture_to_delete:
            return jsonify({'error': 'Picture not found'}), 404

        # Save the record removal first, so a crash can't leave a record with no file
        new_data = [img for img in data if img['id'] != picture_id]
        save_data(new_data)

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], picture_to_delete['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)

    return jsonify({'success': True})

if __name__ == '__main__':
    print("Running Flask app at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
