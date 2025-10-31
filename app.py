from flask_cors import CORS
import os
import secrets
import json
import zipfile
import shutil
from urllib.parse import urlparse, urlunparse
from flask import Flask, request, render_template, send_from_directory, jsonify, Response, url_for

# --- GEVEVT IMPORTS ---
from gevent.pywsgi import WSGIServer
from gevent import monkey; monkey.patch_all() # Apply patches early
from gevent import spawn # Use gevent's spawn for background tasks
from gevent import sleep # Import gevent.sleep for non-blocking delays

# --- Flask-SocketIO Import ---
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import abort

# --- Third-party library for PDF metadata handling ---
import pikepdf


# --- Task Function Imports ---
from werkzeug.utils import secure_filename
from pathlib import Path

# Removed: from subject_generator import run_subject_task
from extract_title_author import get_ai_suggestions
from embed_metadata import embed_metadata 
from task3_alt_text import run_alt_text_task
from ai_interface import load_subject_list, generate_subjects # Import generate_subjects directly


# --- CONFIGURATION ---
APP_PASSWORD = "your-secret-password" 
SECRET_KEY = secrets.token_hex(16)
SESSIONS_DIR = Path("sessions")

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config['SECRET_KEY'] = SECRET_KEY
SESSIONS_DIR.mkdir(exist_ok=True)

# Add SERVER_NAME and PREFERRED_URL_SCHEME for url_for in background contexts
app.config['PREFERRED_URL_SCHEME'] = 'http'

# Initialize Flask-SocketIO
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*")
JOBS = {}


# --- Helper Functions for background tasks ---

def send_socketio_message(task_id, message_type, data):
    """Sends a structured SocketIO message to the client's room."""
    # Ensure data is a dictionary or list of dictionaries.
    # If it's a simple string (e.g., from send_progress_message), wrap it in a dict.
    if isinstance(data, str):
        payload_data = {"message": data} 
    else:
        payload_data = data

    message_content = {"type": message_type, "data": payload_data}
    print(f"DEBUG: Emitting SocketIO message to room {task_id}: {message_content['type']} - {str(message_content['data'])[:100]}...")
    socketio.emit('task_update', message_content, room=task_id)


def send_progress_message(task_id, message, level='info'):
    """Sends a general progress message to the client's room."""
    print(f"DEBUG: Emitting progress message to room {task_id}: {message[:100]}... (Level: {level})")
    # Pass a dictionary as the data payload for 'PROGRESS' type
    send_socketio_message(task_id, "PROGRESS", {"message": message, "type": level})


def get_session_paths(task_id):
    """Returns the Path objects for a given session's directories."""
    base_path = SESSIONS_DIR / task_id
    return {
        'base': base_path,
        'input': base_path / "input",
        'output': base_path / "output",
        'structured_output': base_path / "structured_output",
        'visuals': base_path / "visuals"
    }

def process_all_tasks(task_id, files_data, initial_tasks, final_tasks, use_predefined_subjects_str, custom_subject_list_path_str, default_subject, base_url):
    """
    Background task (spawned by gevent) to orchestrate all processing tasks for a session.
    This function handles the initial AI extraction, sends suggestions,
    and then, if no confirmation is needed, proceeds directly to final processing.
    If confirmation is needed, it waits for the /finalize_task endpoint to trigger
    the final processing steps.
    """
    # Push an application context for this background task
    with app.app_context():
        paths = get_session_paths(task_id)
        
        try:
            # --- Stage 1: Initial Extraction & Send Suggestions (if requested) ---
            initial_suggestions_payload = []
            requires_confirmation = False

            if "title_author" in initial_tasks or "subjects" in initial_tasks:
                send_progress_message(task_id, "⚙️ Running initial extraction for Title/Author and/or Subjects...")
                requires_confirmation = True

                # Load subject list if specified for initial processing
                loaded_subject_list = None
                if use_predefined_subjects_str == 'true' and custom_subject_list_path_str and Path(custom_subject_list_path_str).exists():
                    try:
                        loaded_subject_list = load_subject_list(Path(custom_subject_list_path_str))
                        send_progress_message(task_id, f"   -> Loaded custom subject list from: {Path(custom_subject_list_path_str).name}")
                    except Exception as e:
                        send_progress_message(task_id, f"   ⚠️ Warning: Could not load custom subject list from {Path(custom_subject_list_path_str).name}: {e}. Proceeding without predefined subjects for AI generation.")
                elif use_predefined_subjects_str == 'true':
                    send_progress_message(task_id, "   ⚠️ Warning: 'Use predefined subject list' was checked, but no custom subject file was uploaded or found. Falling back to freeform generation (or user-provided default).")


                for file_info in files_data:
                    filename = file_info['original_filename']
                    input_pdf_path = paths['input'] / filename
                    
                    current_file_data = {
                        'original_filename': filename,
                        'original_metadata': {}, # To store metadata read from the PDF
                        'ai_suggestions': {}     # To store AI-generated suggestions
                    }

                    # --- Extract existing metadata from PDF (using pikepdf) ---
                    try:
                        with pikepdf.Pdf.open(input_pdf_path) as pdf:
                            info = pdf.docinfo
                            current_file_data['original_metadata']['title'] = str(info.get("/Title", "")).strip()
                            current_file_data['original_metadata']['author'] = str(info.get("/Author", "")).strip()
                            # Keywords are often comma-separated, store as a list
                            keywords_str = str(info.get("/Keywords", "")).strip()
                            current_file_data['original_metadata']['subjects'] = [s.strip() for s in keywords_str.split(',') if s.strip()]
                        send_progress_message(task_id, f"   -> Read existing metadata from: {filename}")
                    except Exception as e:
                        send_progress_message(task_id, f"   ⚠️ Warning: Could not read existing metadata from {filename}: {e}. Proceeding without original metadata.")
                        current_file_data['original_metadata'] = {'title': '', 'author': '', 'subjects': []}


                    if "title_author" in initial_tasks:
                        send_progress_message(task_id, f"   -> Extracting Title/Author from: {filename}")
                        ai_ta_suggestions = get_ai_suggestions(input_pdf_path, paths['visuals'])
                        current_file_data['ai_suggestions']['title_author'] = ai_ta_suggestions
                        send_progress_message(task_id, f"   -> Title/Author extraction complete for {filename}.")

                    if "subjects" in initial_tasks:
                        send_progress_message(task_id, f"   -> Extracting Subjects from: {filename}")
                        
                        import fitz # PyMuPDF for text extraction
                        text = ""
                        try:
                            doc = fitz.open(input_pdf_path)
                            for page_num in range(min(5, doc.page_count)):
                                text += doc.load_page(page_num).get_text()
                            doc.close()
                        except Exception as e:
                            send_progress_message(task_id, f"   -> Error extracting text from {filename} for subjects: {e}")
                            text = ""

                        if text.strip():
                            ai_subject_suggestions = generate_subjects(text, loaded_subject_list)
                            
                            # Apply default subject fallback if AI returns empty and a default is provided
                            if not ai_subject_suggestions and default_subject:
                                ai_subject_suggestions = [default_subject]
                                send_progress_message(task_id, f"   -> AI returned no subjects. Applying default fallback: '{default_subject}'.")
                            elif not ai_subject_suggestions:
                                ai_subject_suggestions = ["Unknown"] # Hardcoded fallback if no default
                                send_progress_message(task_id, "   -> AI returned no subjects and no default fallback provided. Using 'Unknown'.")

                            current_file_data['ai_suggestions']['subjects'] = ai_subject_suggestions
                            send_progress_message(task_id, f"   -> Subject extraction complete for {filename}.")
                        else:
                            send_progress_message(task_id, f"   -> No significant text found for subject analysis in {filename}. Skipping subject extraction.")
                            current_file_data['ai_suggestions']['subjects'] = []

                    initial_suggestions_payload.append(current_file_data)
            
            JOBS[task_id]['initial_tasks_selected'] = initial_tasks
            JOBS[task_id]['final_tasks_selected'] = final_tasks
            JOBS[task_id]['initial_suggestions_payload'] = initial_suggestions_payload # Store for re-sending if needed

            if requires_confirmation:
                JOBS[task_id]['status'] = 'awaiting_confirmation'
                send_socketio_message(task_id, "DATA:EXTRACTED_SUGGESTIONS", initial_suggestions_payload)
                send_progress_message(task_id, "✅ Initial extraction complete. Awaiting user confirmation.")
                print(f"DEBUG: Sent DATA:EXTRACTED_SUGGESTIONS for task {task_id}")
                send_progress_message(task_id, "HEARTBEAT: Waiting for user confirmation...")
            else:
                send_progress_message(task_id, "No initial confirmation needed. Proceeding to final tasks...")
                # If no confirmation is needed, we'll use original metadata if available, else AI suggestions
                confirmed_metadata_for_final_tasks = []
                for file_data in initial_suggestions_payload:
                    confirmed_ta = {}
                    confirmed_subjects = []

                    # Prioritize original metadata if available and not empty
                    if file_data['original_metadata'].get('title'):
                        confirmed_ta['title'] = file_data['original_metadata']['title']
                    elif file_data['ai_suggestions'].get('title_author', {}).get('article_title'):
                        confirmed_ta['title'] = file_data['ai_suggestions']['title_author']['article_title']
                    
                    if file_data['original_metadata'].get('author'):
                        confirmed_ta['author'] = file_data['original_metadata']['author']
                    elif file_data['ai_suggestions'].get('title_author', {}).get('author'):
                        confirmed_ta['author'] = file_data['ai_suggestions']['title_author']['author']

                    if file_data['original_metadata'].get('subjects'):
                        confirmed_subjects = file_data['original_metadata']['subjects']
                    elif file_data['ai_suggestions'].get('subjects'):
                        confirmed_subjects = file_data['ai_suggestions']['subjects']
                    
                    confirmed_metadata_for_final_tasks.append({
                        'original_filename': file_data['original_filename'],
                        'confirmed_title_author': confirmed_ta,
                        'confirmed_subjects': confirmed_subjects
                    })
                _run_final_processing_steps(task_id, confirmed_metadata_for_final_tasks, final_tasks, base_url)

        except Exception as e:
            send_progress_message(task_id, f"ERROR: A critical error occurred during initial processing: {e}", 'error')
            JOBS[task_id]['status'] = 'error'
            print(f"ERROR in process_all_tasks for {task_id}: {e}")


def _run_final_processing_steps(task_id, confirmed_metadata_list, final_tasks, base_url):
    """Internal function to run the actual final processing steps."""
    # Push an application context for this background task
    with app.app_context():
        paths = get_session_paths(task_id)
        alt_text_report_filenames = []
        metadata_log_filenames = [] # To collect CSV log filenames
        subject_log_filename = None # To collect subject log filename

        try:
            send_progress_message(task_id, "📝 Embedding confirmed metadata into output PDFs...")
            
            for data in confirmed_metadata_list:
                filename = data['original_filename']
                input_pdf_path_for_embedding = paths['input'] / filename
                output_pdf_path_for_embedding = paths['output'] / filename
                pdf_base_name = Path(filename).stem # Get base name for log file

                if not input_pdf_path_for_embedding.exists():
                    send_progress_message(task_id, f"   ⚠️ Warning: Input file not found for embedding: {filename}. Skipping.")
                    continue

                # Copy the original PDF to the output directory before embedding
                shutil.copy2(input_pdf_path_for_embedding, output_pdf_path_for_embedding)
                send_progress_message(task_id, f"   -> Copied {filename} to output directory.")
                
                title = data.get('confirmed_title_author', {}).get('title')
                author = data.get('confirmed_title_author', {}).get('author')
                subjects = data.get('confirmed_subjects', [])

                # Call embed_metadata, which now also generates the CSV log
                # The embed_metadata function saves the log to output_dir_for_logs, which is structured_output
                if embed_metadata(
                    input_pdf_path=output_pdf_path_for_embedding,
                    output_pdf_path=output_pdf_path_for_embedding, # Embed into the copied file
                    pdf_base_name=pdf_base_name, # Pass pdf_base_name
                    output_dir_for_logs=paths['structured_output'], # Pass structured_output_dir for the log path
                    title=title,
                    author=author,
                    subjects=subjects
                ):
                    send_progress_message(task_id, f"   -> Embedded metadata for {filename}")
                    # Add the generated CSV log file to the list for zipping, relative to base dir
                    metadata_log_filenames.append(str(Path("structured_output") / f"{pdf_base_name}_metadata_log.csv"))
                else:
                    send_progress_message(task_id, f"   -> ❌ Failed to embed metadata for {filename}")

            # Run subject task if selected (this will generate subject_log.csv in paths['output'])
            if "subjects" in final_tasks:
                send_progress_message(task_id, "🧠 Running Subject Extraction Task (final stage)...")
                # The subject generation logic is now in process_all_tasks (initial phase)
                # and the confirmed subjects are passed via confirmed_metadata_list.
                # No need to re-run run_subject_task here.
                # We just need to ensure the subject_log.csv is generated if subjects were processed.
                # The subject_log.csv is generated during the initial processing and saved to structured_output.
                # So we just need to add its path to the zip list if it exists.
                subject_log_filename = str(Path("structured_output") / "subject_log.csv")
                if not (paths['structured_output'] / "subject_log.csv").exists():
                    # If for some reason it wasn't created, create an empty one or handle
                    # This case should ideally not happen if initial processing for subjects ran.
                    send_progress_message(task_id, "   ⚠️ Warning: Subject log CSV not found. It should have been generated during initial processing.", 'warning')
                    subject_log_filename = None # Do not include in zip if not found

                send_progress_message(task_id, "✅ Subject processing (final stage) complete.")


            if "alt_text" in final_tasks:
                send_progress_message(task_id, "🖼️ Generating Alt Text reports...")
                # Add a debug message to show contents of output directory before alt-text task
                output_dir_contents = [f.name for f in paths['output'].iterdir()]
                send_progress_message(task_id, f"   -> Contents of output directory before alt-text: {output_dir_contents}")

                # Pass send_progress_message function directly
                run_alt_text_task(paths['output'], paths['visuals'], paths['structured_output'], 
                                  send_progress_func=lambda msg, level='info': send_progress_message(task_id, msg, level))
                
                for report_file in os.listdir(paths['structured_output']):
                    if report_file.endswith('_alt_text_report.json'):
                        alt_text_report_filenames.append(str(Path("structured_output") / report_file))
                send_progress_message(task_id, "✅ Alt Text generation complete.")


            send_progress_message(task_id, "📦 Compressing processed files...")
            zip_filename = f"processed_pdfs_{task_id}.zip"
            zip_filepath = paths['base'] / zip_filename
            
            with zipfile.ZipFile(zip_filepath, 'w') as zf:
                for folder_name in ['output', 'structured_output', 'visuals']:
                    folder_path = paths['base'] / folder_name
                    if folder_path.exists():
                        for root, _, files in os.walk(folder_path):
                            for file in files:
                                file_path = Path(root) / file
                                arcname = file_path.relative_to(paths['base'])
                                zf.write(file_path, arcname)
            
            def force_https_url(url):
                parsed = urlparse(url)
                if parsed.scheme == "https":
                    return url
                return urlunparse(('https',) + parsed[1:])

            download_link = force_https_url(f"{base_url.rstrip('/')}/download/{task_id}/{zip_filename}")

            
            done_payload = {
                "download_link": download_link,
                "alt_text_reports": alt_text_report_filenames,
                "metadata_logs": metadata_log_filenames,
                "subject_log": subject_log_filename # Include subject log filename
            }
            send_socketio_message(task_id, "DONE", done_payload)
            JOBS[task_id]['status'] = 'complete'
            print(f"DEBUG: Sent DONE message for task {task_id}")

        except Exception as e:
            send_progress_message(task_id, f"ERROR: A critical error occurred during final processing: {e}", 'error')
            JOBS[task_id]['status'] = 'error'
            print(f"ERROR in _run_final_processing_steps for {task_id}: {e}")
        finally:
            if JOBS[task_id]['status'] not in ['complete', 'error']:
                JOBS[task_id]['status'] = 'error'


# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """
    Handles PDF file uploads and initiates the initial processing phase.
    If initial_tasks are selected, it triggers AI extraction and awaits user confirmation.
    Otherwise, it proceeds directly to final processing.
    """
    if 'pdf_files' not in request.files:
        return jsonify({"error": "No files part in the request."}), 400
    
    uploaded_files = request.files.getlist('pdf_files')
    if not uploaded_files or uploaded_files[0].filename == '':
        return jsonify({"error": "No PDF files selected for upload."}), 400

    initial_tasks = request.form.getlist('initial_tasks')
    final_tasks = request.form.getlist('final_tasks')
    # Get the value of the new checkbox
    use_predefined_subjects = request.form.get('use_predefined_subjects', 'false') # Default to 'false' if not present

    # Get custom subject list file if provided
    custom_subject_list_file = request.files.get('custom_subject_list_file')
    custom_subject_list_path = None

    default_subject = request.form.get('default_subject', None) # Get default subject from form

    if not initial_tasks and not final_tasks:
        return jsonify({"error": "No processing tasks selected. Please select at least one task."}), 400

    task_id = secrets.token_hex(16)
    base_url = request.host_url
    
    paths = get_session_paths(task_id)
    for d in [paths['input'], paths['output'], paths['structured_output'], paths['visuals']]:
        d.mkdir(parents=True, exist_ok=True)
    
    files_data = []
    for file in uploaded_files:
        filename = secure_filename(file.filename)
        file_path = paths['input'] / filename
        file.save(file_path)
        files_data.append({'original_filename': filename})

    # Save custom subject list file if uploaded
    if custom_subject_list_file and custom_subject_list_file.filename != '':
        custom_subject_list_filename = secure_filename(custom_subject_list_file.filename)
        custom_subject_list_path = paths['input'] / custom_subject_list_filename
        custom_subject_list_file.save(custom_subject_list_path)
        print(f"DEBUG: Custom subject list uploaded to: {custom_subject_list_path}")


    JOBS[task_id] = {
        'status': 'running',
        'files_data': files_data, # Store files_data here for access in _run_final_processing_steps
        'initial_tasks_selected': initial_tasks,
        'final_tasks_selected': final_tasks,
        'use_predefined_subjects': use_predefined_subjects, # Store this
        'custom_subject_list_path': str(custom_subject_list_path) if custom_subject_list_path else None, # Store path
        'default_subject': default_subject # Store default subject
    }
    
    spawn(process_all_tasks, task_id, files_data, initial_tasks, final_tasks, use_predefined_subjects, JOBS[task_id]['custom_subject_list_path'], JOBS[task_id]['default_subject'], base_url)

    requires_confirmation = bool(initial_tasks)

    return jsonify({"task_id": task_id, "requires_confirmation": requires_confirmation})


@app.route('/finalize_task', methods=['POST'])
def finalize_task():
    """
    Receives user-confirmed metadata and triggers the final processing steps.
    """
    # Changed to request.form to handle FormData from frontend
    task_id = request.form.get('task_id')
    confirmed_data_json = request.form.get('confirmed_data')
    
    if not task_id or not confirmed_data_json:
        return jsonify({"error": "Missing task ID or confirmed data."}), 400

    try:
        confirmed_metadata_list = json.loads(confirmed_data_json)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON format for confirmed data."}), 400
    
    job_info = JOBS.get(task_id)
    base_url = job_info.get('base_url', request.host_url)
    if not job_info:
        return jsonify({"error": "Task not found or expired."}), 404
    
    final_tasks_to_run = job_info.get('final_tasks_selected', [])

    JOBS[task_id]['status'] = 'running'

    spawn(_run_final_processing_steps, task_id, confirmed_metadata_list, final_tasks_to_run, base_url)

    return jsonify({"status": "Final processing started.", "task_id": task_id})


# --- SocketIO Event Handlers ---
@socketio.on('connect')
def test_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def test_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_task_room')
def on_join_task_room(data):
    task_id = data.get('task_id')
    if task_id:
        join_room(task_id)
        print(f"Client {request.sid} joined room {task_id}")
        emit('room_joined', {'task_id': task_id, 'message': f'Joined room {task_id}'}, room=task_id)
        # If the task is already awaiting confirmation, resend the suggestions
        if task_id in JOBS and JOBS[task_id].get('status') == 'awaiting_confirmation':
            send_socketio_message(task_id, "DATA:EXTRACTED_SUGGESTIONS", JOBS[task_id]['initial_suggestions_payload'])
    else:
        print(f"Client {request.sid} attempted to join room without task_id")


@app.route('/download/<task_id>/<filename>')
def download(task_id, filename):
    """Allows downloading of the final processed ZIP file."""
    paths = get_session_paths(task_id)
    return send_from_directory(paths['base'], filename, as_attachment=True)

@app.route('/session_file/<task_id>/<path:filename>')
def session_file(task_id, filename):
    """Serves specific files from the session directory (e.g., alt text JSON reports) for display."""
    paths = get_session_paths(task_id)
    
    # Construct the full path to the requested file within the session's base directory
    requested_file_path = paths['base'] / filename
    
    # Check if the resolved path exists and is a file
    if not requested_file_path.exists() or not requested_file_path.is_file():
        return jsonify({"error": f"File not found: {filename}"}), 404 

    # Serve the file directly using paths['base'] as the root directory
    # Flask's send_from_directory handles security for subdirectories relative to the base.
    return send_from_directory(paths['base'], filename)

@app.route('/sessions/<task_id>/<folder>/<path:filename>')
def serve_session_file(task_id, folder, filename):
    """Serve files from session subdirectories (output, structured_output, visuals)."""
    allowed_folders = ['output', 'structured_output', 'visuals']
    if folder not in allowed_folders:
        abort(404)
    paths = get_session_paths(task_id)
    folder_path = paths[folder]
    # Prevent path traversal:
    safe_path = folder_path / filename
    try:
        safe_path.resolve().relative_to(folder_path.resolve())
    except Exception:
        abort(404)
    if not safe_path.exists():
        abort(404)
    return send_from_directory(folder_path, filename)


if __name__ == '__main__':
    print("Starting Gevent WSGI server with Flask-SocketIO on http://127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000)


@app.route('/favicon.ico')
def favicon():
    return '', 204
