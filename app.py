
from flask import Flask, request, jsonify, send_file
from utils.chunker import split_pdf
from utils.rebuilder import rebuild_pdf
from utils.remediator import remediate_chunk
import os
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
CHUNK_FOLDER = 'chunks'
RESULT_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHUNK_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_pdf():
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400

    session_id = str(uuid.uuid4())
    upload_path = os.path.join(UPLOAD_FOLDER, session_id + '.pdf')
    file.save(upload_path)

    chunk_dir = os.path.join(CHUNK_FOLDER, session_id)
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_paths = split_pdf(upload_path, chunk_dir)

    remediated_paths = []
    for chunk_path in chunk_paths:
        remediated_path = remediate_chunk(chunk_path)
        remediated_paths.append(remediated_path)

    output_pdf = os.path.join(RESULT_FOLDER, session_id + '_accessible.pdf')
    rebuild_pdf(remediated_paths, output_pdf)

    return send_file(output_pdf, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
