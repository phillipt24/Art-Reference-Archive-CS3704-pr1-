import os
import json
import random
import time
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

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
    filename = f"{int(time.time() * 1000)}{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    data = load_data()
    picture_record = {
        'id': int(time.time() * 1000),
        'filename': filename,
        'tags': tags
    }
    data.append(picture_record)
    save_data(data)

    return jsonify({'success': True, 'picture': picture_record})

@app.route('/api/pictures', methods=['GET'])
def get_pictures():
    raw_tags = request.args.get('tags', '')
    search_tags = [t.strip().lower() for t in raw_tags.split(',') if t.strip()]

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
    data = load_data()
    picture_to_delete = next((img for img in data if img['id'] == picture_id), None)

    if not picture_to_delete:
        return jsonify({'error': 'Picture not found'}), 404

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], picture_to_delete['filename'])
    if os.path.exists(file_path):
        os.remove(file_path)

    new_data = [img for img in data if img['id'] != picture_id]
    save_data(new_data)

    return jsonify({'success': True})

if __name__ == '__main__':
    print("Running Flask app at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)