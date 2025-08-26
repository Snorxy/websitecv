from flask import Flask, render_template, request, jsonify, session, send_file, flash, redirect, url_for, make_response
import json
import os
import secrets
import string
import time
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import io
import zipfile
from utils import parse_txt_to_vcf, split_txt_file, parse_vcf_to_txt, analyze_vcf_file, parse_admin_navy_to_vcf, parse_admin_navy_to_vcf_with_start, merge_vcf_files

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'  # Ganti dengan secret key yang aman

# Storage untuk file temporary (in-memory)
temp_file_storage = {}

# Storage untuk active sessions (in-memory) - 1 API key = 1 user
active_sessions = {}

# Template helper functions
@app.template_global()
def moment():
    return datetime.now()

@app.context_processor
def inject_user_info():
    """Inject user information (including API key expiry) to all templates"""
    if 'api_key_valid' in session and session['api_key_valid']:
        api_key = session.get('api_key')
        if api_key:
            api_keys = load_api_keys()
            if api_key in api_keys:
                expiry_date_str = api_keys[api_key]['expiry_date']
                expiry_date = datetime.fromisoformat(expiry_date_str)
                
                # Format tanggal lebih compact
                expiry_formatted = expiry_date.strftime('%d/%m/%y %H:%M')
                
                # Hitung sisa hari
                remaining_days = (expiry_date - datetime.now()).days
                
                return {
                    'api_key_expiry': expiry_formatted,
                    'api_key_remaining_days': remaining_days
                }
    
    return {}

# Konfigurasi
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'vcf'}
API_KEYS_FILE = os.path.join(os.path.dirname(__file__), 'api_keys.json')  # Fix path to website directory
ADMIN_PASSWORD = 'admin123'  # Ganti dengan password yang aman

# Pastikan folder upload ada
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_api_keys():
    """Load API keys dari file JSON"""
    if os.path.exists(API_KEYS_FILE):
        try:
            with open(API_KEYS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_api_keys(api_keys):
    """Simpan API keys ke file JSON"""
    with open(API_KEYS_FILE, 'w') as f:
        json.dump(api_keys, f, indent=4, default=str)

def generate_api_key():
    """Generate API key 12 karakter dengan huruf besar semua"""
    chars = string.ascii_uppercase + string.digits  # Hanya huruf besar dan angka
    return ''.join(secrets.choice(chars) for _ in range(12))

def check_api_key(api_key):
    """Cek apakah API key valid dan belum expired"""
    print(f"DEBUG: Checking API key: {api_key}")
    api_keys = load_api_keys()
    print(f"DEBUG: Loaded API keys: {api_keys}")
    
    # Case-insensitive lookup
    api_key_lower = api_key.lower()
    found_key = None
    
    for key in api_keys:
        if key.lower() == api_key_lower:
            found_key = key
            break
    
    if not found_key:
        print(f"DEBUG: API key {api_key} not found in keys")
        return False, "API key tidak valid", None
    
    key_data = api_keys[found_key]
    expiry_date = datetime.fromisoformat(key_data['expiry_date'])
    current_time = datetime.now()
    
    print(f"DEBUG: Current time: {current_time}")
    print(f"DEBUG: Expiry time: {expiry_date}")
    
    if current_time > expiry_date:
        print(f"DEBUG: API key expired")
        return False, "API key sudah expired", None
    
    print(f"DEBUG: API key valid")
    return True, "API key valid", found_key

def create_session_id():
    """Generate unique session ID"""
    return secrets.token_urlsafe(32)

def register_session(api_key, session_id, user_info=None):
    """Register new session and force logout previous session"""
    current_time = datetime.now()
    
    # Jika API key sudah ada session aktif, tandai sebagai invalid
    if api_key in active_sessions:
        old_session = active_sessions[api_key]
        print(f"DEBUG: Force logout previous session {old_session['session_id']} for API key {api_key}")
    
    # Register session baru
    active_sessions[api_key] = {
        'session_id': session_id,
        'login_time': current_time,
        'last_activity': current_time,
        'user_info': user_info or {},
        'is_active': True
    }
    
    print(f"DEBUG: Registered new session {session_id} for API key {api_key}")
    return True

def is_session_valid(api_key, session_id):
    """Check if session is still valid (not replaced by newer session) AND API key still exists in database"""
    # PERTAMA: Cek apakah API key masih ada dan valid di database
    api_valid, api_message, actual_api_key = check_api_key(api_key)
    if not api_valid:
        # API key sudah dihapus atau expired, invalidate session
        if api_key in active_sessions:
            del active_sessions[api_key]
        return False, f"API key tidak valid: {api_message}"
    
    # KEDUA: Cek session di memori
    if api_key not in active_sessions:
        return False, "Session tidak ditemukan"
    
    session_data = active_sessions[api_key]
    
    if not session_data.get('is_active', False):
        return False, "Session sudah dinonaktifkan"
    
    if session_data['session_id'] != session_id:
        return False, "Session digantikan oleh login baru"
    
    # Update last activity
    session_data['last_activity'] = datetime.now()
    
    return True, "Session valid"

def invalidate_session(api_key):
    """Invalidate session for API key"""
    if api_key in active_sessions:
        active_sessions[api_key]['is_active'] = False
        print(f"DEBUG: Invalidated session for API key {api_key}")

def require_valid_session(return_json=False):
    """Check if current session is valid, redirect if not"""
    # Basic session check
    if 'api_key_valid' not in session or not session['api_key_valid']:
        if return_json:
            return jsonify({'error': 'Silakan masukkan API key terlebih dahulu'}), 401
        flash('Silakan masukkan API key terlebih dahulu.', 'error')
        return redirect(url_for('index'))
    
    # Advanced session tracking check
    api_key = session.get('api_key')
    session_id = session.get('session_id')
    
    if not api_key or not session_id:
        if return_json:
            return jsonify({'error': 'Session tidak valid. Silakan login ulang'}), 401
        flash('Session tidak valid. Silakan login ulang.', 'error')
        session.clear()
        return redirect(url_for('index'))
    
    # Check if session masih aktif
    is_valid, message = is_session_valid(api_key, session_id)
    
    if not is_valid:
        if return_json:
            return jsonify({'error': f'Session berakhir: {message}. Silakan login ulang'}), 401
        flash(f'Session berakhir: {message}. Silakan login ulang.', 'error')
        session.clear()
        return redirect(url_for('index'))
    
    return None  # Session valid

@app.route('/')
def index():
    """Halaman utama untuk input API key"""
    if 'api_key_valid' in session and session['api_key_valid']:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/verify_api', methods=['POST'])
def verify_api():
    """Verifikasi API key dengan session tracking"""
    api_key = request.form.get('api_key', '').strip()
    
    if not api_key:
        flash('Masukkan API key!', 'error')
        return redirect(url_for('index'))
    
    is_valid, message, actual_api_key = check_api_key(api_key)
    
    if is_valid:
        # Generate unique session ID
        session_id = create_session_id()
        
        # Get user info (IP address, user agent)
        user_info = {
            'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR')),
            'user_agent': request.environ.get('HTTP_USER_AGENT', ''),
            'login_time': datetime.now().isoformat()
        }
        
        # Register session (akan force logout session lama)
        register_session(actual_api_key, session_id, user_info)
        
        # Set session data - GUNAKAN ACTUAL API KEY YANG BENAR
        session['api_key'] = actual_api_key
        session['session_id'] = session_id
        session['api_key_valid'] = True
        
        print(f"DEBUG: New session created - API: {actual_api_key}, Session: {session_id}")
        flash('API key valid! Selamat datang.', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash(f'Error: {message}', 'error')
        return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    """Dashboard utama dengan pilihan fitur"""
    print(f"DEBUG: Dashboard accessed. Session: {dict(session)}")
    
    # Check session validity with tracking
    redirect_response = require_valid_session()
    if redirect_response:
        return redirect_response
    
    print(f"DEBUG: Session valid, showing dashboard")
    return render_template('dashboard.html')

@app.route('/txt-to-vcf')
def txt_to_vcf():
    """Halaman converter TXT to VCF"""
    print("DEBUG: Accessing /txt-to-vcf route")
    
    # Check session validity with tracking
    redirect_response = require_valid_session()
    if redirect_response:
        return redirect_response
    
    print("DEBUG: Rendering txt_to_vcf.html template")
    return render_template('txt_to_vcf.html')

@app.route('/convert_single', methods=['POST'])
def convert_single():
    """Proses single convert - 1 file TXT dibagi menjadi beberapa file VCF"""
    print(f"DEBUG: convert_single called")
    print(f"DEBUG: request.files keys: {list(request.files.keys())}")
    print(f"DEBUG: request.form keys: {list(request.form.keys())}")
    print(f"DEBUG: session api_key_valid: {session.get('api_key_valid', 'NOT_SET')}")
    
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        print(f"DEBUG: Session validation failed")
        return error_response
    
    if 'txt_file' not in request.files:
        print(f"DEBUG: txt_file not in request.files")
        return jsonify({'error': 'File tidak ditemukan'}), 400
    
    file = request.files['txt_file']
    if file.filename == '':
        print(f"DEBUG: file.filename is empty")
        return jsonify({'error': 'File tidak dipilih'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Baca isi file
            content = file.read().decode('utf-8')
            
            # Ambil parameter
            contacts_per_file = int(request.form.get('contacts_per_file', 1000))
            name_prefix = request.form.get('contact_name_prefix', '').strip()
            output_prefix = request.form.get('output_prefix', '').strip()
            file_start_number = int(request.form.get('file_start_number', 1))
            
            # Validasi contacts per file
            if contacts_per_file < 1 or contacts_per_file > 10000:
                return jsonify({'error': 'Jumlah kontak per file harus antara 1-10000'}), 400
            
            # Parse kontak
            all_contacts = parse_txt_to_vcf(content, name_prefix)
            
            if not all_contacts:
                return jsonify({'error': 'Tidak ada kontak valid ditemukan dalam file'}), 400
            
            # Bagi kontak ke beberapa file berdasarkan contacts_per_file
            total_contacts = len(all_contacts)
            file_count = (total_contacts + contacts_per_file - 1) // contacts_per_file  # Ceiling division
            split_vcf_files = []
            
            print(f"DEBUG: total_contacts={total_contacts}, contacts_per_file={contacts_per_file}, file_count={file_count}")
            print(f"DEBUG: name_prefix='{name_prefix}', output_prefix='{output_prefix}', file_start_number={file_start_number}")
            
            for i in range(file_count):
                start_idx = i * contacts_per_file
                if i == file_count - 1:  # File terakhir dapat berisi sisa kontak
                    end_idx = len(all_contacts)
                else:
                    end_idx = start_idx + contacts_per_file
                
                file_contacts = all_contacts[start_idx:end_idx]
                if file_contacts:  # Hanya tambahkan jika ada kontak
                    vcf_content = '\n'.join(file_contacts)
                    split_vcf_files.append(vcf_content)
            
            # Jika total kontak <= kontak per file, return sebagai .vcf langsung
            print(f"DEBUG: Checking condition - total_contacts ({total_contacts}) <= contacts_per_file ({contacts_per_file})")
            if total_contacts <= contacts_per_file:
                print("DEBUG: Single file condition - returning VCF directly")
                vcf_content = '\n'.join(all_contacts)
                filename = secure_filename(file.filename)
                base_name = filename.rsplit('.', 1)[0]
                
                if output_prefix:
                    vcf_filename = f"{output_prefix} {file_start_number}.vcf"
                else:
                    vcf_filename = f"{base_name} {file_start_number}.vcf"
                
                response = make_response(vcf_content)
                response.headers['Content-Type'] = 'text/vcard'
                response.headers['Content-Disposition'] = f'attachment; filename="{vcf_filename}"'
                return response
            
            # Jika perlu dibagi ke multiple files, return JSON dengan file info
            print(f"DEBUG: Multiple files condition - returning {len(split_vcf_files)} files info")
            
            filename = secure_filename(file.filename)
            base_name = filename.rsplit('.', 1)[0]
            
            files_info = []
            for i, vcf_content in enumerate(split_vcf_files):
                file_number = file_start_number + i
                if output_prefix:
                    vcf_filename = f"{output_prefix} {file_number}.vcf"
                else:
                    vcf_filename = f"{base_name} {file_number}.vcf"
                
                # Store file content in temp storage
                file_id = f"single_{int(time.time())}_{i}"
                temp_file_storage[file_id] = {
                    'content': vcf_content,
                    'filename': vcf_filename,
                    'mimetype': 'text/vcard'
                }
                
                files_info.append({
                    'file_id': file_id,
                    'filename': vcf_filename,
                    'size': len(vcf_content.encode('utf-8'))
                })
            
            return jsonify({
                'success': True,
                'multiple_files': True,
                'total_files': len(files_info),
                'total_contacts': total_contacts,  # TAMBAH TOTAL CONTACTS ASLI
                'files': files_info
            })
            
        except Exception as e:
            return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500
    
    return jsonify({'error': 'Format file tidak didukung. Gunakan file .txt'}), 400

@app.route('/download_file/<file_id>')
def download_file(file_id):
    """Download individual file by ID"""
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        return error_response
    
    if file_id not in temp_file_storage:
        return jsonify({'error': 'File tidak ditemukan'}), 404
    
    file_data = temp_file_storage[file_id]
    
    response = make_response(file_data['content'])
    response.headers['Content-Type'] = file_data['mimetype']
    response.headers['Content-Disposition'] = f'attachment; filename="{file_data["filename"]}"'
    
    # Clean up temp storage after download
    del temp_file_storage[file_id]
    
    return response

@app.route('/download')
def download():
    """Download file from temporary storage"""
    # Check session validity
    error_response = require_valid_session(return_json=False)
    if error_response:
        return error_response
    
    if 'download_file_id' not in session:
        flash('File download tidak tersedia. Silakan proses ulang.', 'error')
        return redirect(url_for('dashboard'))
    
    file_id = session['download_file_id']
    
    if file_id not in temp_file_storage:
        flash('File sudah tidak tersedia. Silakan proses ulang.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get data from temp storage
    file_data = temp_file_storage[file_id]
    
    # Create response
    response = make_response(file_data['content'])
    response.headers['Content-Type'] = f"{file_data['mimetype']}; charset=utf-8"
    response.headers['Content-Disposition'] = f'attachment; filename="{file_data["filename"]}"'
    
    # Clear session and temp storage after download
    session.pop('download_file_id', None)
    del temp_file_storage[file_id]
    
    return response

@app.route('/convert_multi', methods=['POST'])
def convert_multi():
    """Proses multi convert - beberapa file TXT masing-masing jadi 1 file VCF"""
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        return error_response
    
    files = request.files.getlist('txt_files')
    if not files or len(files) == 0:
        return jsonify({'error': 'Tidak ada file yang ditemukan'}), 400
    
    try:
        # Ambil parameter
        name_prefix = request.form.get('contact_name_prefix', '').strip()
        filename_option = request.form.get('filename_option', 'original')
        output_prefix = request.form.get('output_prefix', '').strip()
        start_number = int(request.form.get('start_number', 1))
        
        print(f"DEBUG MULTI: files_count={len(files)}, name_prefix='{name_prefix}', filename_option='{filename_option}', output_prefix='{output_prefix}', start_number={start_number}")
        
        # Process files and store in temp storage
        files_info = []
        processed_files = 0
        
        for i, file in enumerate(files):
            if file.filename == '' or not allowed_file(file.filename):
                continue
            
            # Baca isi file
            content = file.read().decode('utf-8')
            
            # Parse ke VCF
            vcf_contacts = parse_txt_to_vcf(content, name_prefix)
            
            if vcf_contacts:
                vcf_content = '\n'.join(vcf_contacts)
                
                # Tentukan nama file output
                if filename_option == 'custom' and output_prefix:
                    file_number = start_number + i
                    # Tambahkan spasi antara prefix dan angka
                    vcf_filename = f"{output_prefix} {file_number}.vcf"
                else:
                    original_name = secure_filename(file.filename)
                    base_name = original_name.rsplit('.', 1)[0]
                    vcf_filename = f"{base_name}.vcf"
                
                # Store file content in temp storage
                file_id = f"multi_{int(time.time())}_{i}"
                temp_file_storage[file_id] = {
                    'content': vcf_content,
                    'filename': vcf_filename,
                    'mimetype': 'text/vcard'
                }
                
                files_info.append({
                    'file_id': file_id,
                    'filename': vcf_filename,
                    'size': len(vcf_content.encode('utf-8')),
                    'contacts': len(vcf_contacts)
                })
                
                processed_files += 1
        
        if processed_files == 0:
            return jsonify({'error': 'Tidak ada file yang berhasil diproses'}), 400
        
        return jsonify({
            'success': True,
            'multiple_files': True,
            'total_files': len(files_info),
            'files': files_info
        })
        
    except Exception as e:
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500

@app.route('/convert', methods=['POST'])
def convert():
    """Proses konversi TXT to VCF - ROUTE LAMA"""
    print("DEBUG: User menggunakan route /convert LAMA!")
    
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        return error_response
    
    if 'file' not in request.files:
        return jsonify({'error': 'File tidak ditemukan'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'File tidak dipilih'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Baca isi file
            content = file.read().decode('utf-8')
            
            # Ambil parameter tambahan
            name_prefix = request.form.get('name_prefix', '').strip()
            output_filename = request.form.get('output_filename', '').strip()
            
            # Parse ke VCF dengan prefix nama jika ada
            vcf_contacts = parse_txt_to_vcf(content, name_prefix)
            
            if not vcf_contacts:
                return jsonify({'error': 'Tidak ada kontak valid ditemukan dalam file'}), 400
            
            # Buat file VCF
            vcf_content = '\n'.join(vcf_contacts)
            
            # Buat file untuk download
            output = io.StringIO()
            output.write(vcf_content)
            output.seek(0)
            
            # Convert ke bytes
            vcf_bytes = io.BytesIO()
            vcf_bytes.write(vcf_content.encode('utf-8'))
            vcf_bytes.seek(0)
            
            # Tentukan nama file output
            if output_filename:
                if not output_filename.lower().endswith('.vcf'):
                    output_filename += '.vcf'
                vcf_filename = secure_filename(output_filename)
            else:
                filename = secure_filename(file.filename)
                vcf_filename = f"{filename.rsplit('.', 1)[0]}_contacts.vcf"
            
            return send_file(
                vcf_bytes,
                as_attachment=True,
                download_name=vcf_filename,
                mimetype='text/vcard'
            )
            
        except Exception as e:
            return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500
    
    return jsonify({'error': 'Format file tidak didukung. Gunakan file .txt'}), 400

@app.route('/split-txt')
def split_txt():
    """Halaman split TXT file"""
    # Check session validity with tracking
    redirect_response = require_valid_session()
    if redirect_response:
        return redirect_response
    
    return render_template('split_txt.html')

@app.route('/split_txt', methods=['POST'])
def split_txt_route():
    """Split TXT file - individual downloads with simple naming"""
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        return error_response
    
    if 'file' not in request.files:
        return jsonify({'error': 'File tidak ditemukan'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'File tidak dipilih'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Baca isi file
            content = file.read().decode('utf-8', errors='ignore')
            
            # Ambil parameter tambahan
            split_count = int(request.form.get('split_count', 2))
            output_prefix = request.form.get('output_prefix', '').strip()
            
            # Validasi split count
            if split_count < 2 or split_count > 100:
                return jsonify({'error': 'Jumlah split harus antara 2-100'}), 400
            
            # Jika tidak ada prefix, gunakan nama file tanpa ekstensi
            if not output_prefix:
                base_name = secure_filename(file.filename).rsplit('.', 1)[0]
                output_prefix = base_name
            
            # Split file dengan split count
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            if not lines:
                return jsonify({'error': 'File kosong atau tidak ada baris yang valid'}), 400
            
            # Hitung baris per file
            lines_per_file = max(1, len(lines) // split_count)
            split_files = []
            
            for i in range(split_count):
                start_idx = i * lines_per_file
                if i == split_count - 1:  # File terakhir dapat berisi sisa baris
                    end_idx = len(lines)
                else:
                    end_idx = start_idx + lines_per_file
                
                chunk_lines = lines[start_idx:end_idx]
                if chunk_lines:  # Hanya tambahkan jika ada konten
                    split_files.append('\n'.join(chunk_lines))
            
            if not split_files:
                return jsonify({'error': 'Tidak ada data untuk di-split'}), 400
            
            # Store files in temp storage untuk download individual
            file_ids = []
            timestamp = int(time.time())
            
            for i, chunk_content in enumerate(split_files, 1):
                # Format nama sederhana: "kintil 1.txt", "kintil 2.txt", dll
                chunk_filename = f"{output_prefix} {i}.txt"
                file_id = f"split_{timestamp}_{i}"
                
                temp_file_storage[file_id] = {
                    'content': chunk_content,
                    'filename': chunk_filename,
                    'mimetype': 'text/plain',
                    'timestamp': time.time()
                }
                
                file_ids.append({
                    'id': file_id,
                    'filename': chunk_filename,
                    'size': len(chunk_content.encode('utf-8')),
                    'lines': len(chunk_content.split('\n'))
                })
            
            # Calculate statistics
            original_lines = len(lines)
            total_size = len(content.encode('utf-8'))
            
            return jsonify({
                'success': True,
                'message': f'File berhasil di-split menjadi {len(split_files)} bagian',
                'original_filename': file.filename,
                'original_lines': original_lines,
                'total_size': total_size,
                'split_count': len(split_files),
                'prefix_name': output_prefix,
                'files': file_ids
            })
            
        except Exception as e:
            print(f"Error in split_txt_route: {e}")
            return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500
    
    return jsonify({'error': 'Format file tidak didukung. Gunakan file .txt'}), 400

@app.route('/split', methods=['POST'])
def split():
    """Proses split TXT file"""
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        return error_response
    
    if 'file' not in request.files:
        return jsonify({'error': 'File tidak ditemukan'}), 400
    
    file = request.files['file']
    chunk_size = request.form.get('chunk_size', '1000')
    
    try:
        chunk_size = int(chunk_size)
        if chunk_size <= 0:
            return jsonify({'error': 'Ukuran chunk harus lebih dari 0'}), 400
    except ValueError:
        return jsonify({'error': 'Ukuran chunk harus berupa angka'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'File tidak dipilih'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Baca isi file
            content = file.read().decode('utf-8')
            
            # Split file menggunakan fungsi dari utils.py
            split_files = split_txt_file(content, chunk_size)
            
            if not split_files:
                return jsonify({'error': 'File kosong atau tidak bisa di-split'}), 400
            
            # Buat ZIP file
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                filename = secure_filename(file.filename)
                base_name = filename.rsplit('.', 1)[0]
                
                for i, chunk_content in enumerate(split_files, 1):
                    chunk_filename = f"{base_name}_part_{i}.txt"
                    zip_file.writestr(chunk_filename, chunk_content)
            
            zip_buffer.seek(0)
            
            zip_filename = f"{filename.rsplit('.', 1)[0]}_split.zip"
            
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name=zip_filename,
                mimetype='application/zip'
            )
            
        except Exception as e:
            return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500
    
    return jsonify({'error': 'Format file tidak didukung. Gunakan file .txt'}), 400

# ========================
# VCF TO TXT ROUTES
# ========================

@app.route('/vcf-to-txt')
def vcf_to_txt():
    """Halaman converter VCF to TXT"""
    print("DEBUG: Accessing /vcf-to-txt route")
    
    # Check session validity with tracking
    redirect_response = require_valid_session()
    if redirect_response:
        return redirect_response
    
    print("DEBUG: Rendering vcf_to_txt.html template")
    return render_template('vcf_to_txt.html')

@app.route('/convert_vcf_single', methods=['POST'])
def convert_vcf_single():
    """Proses single VCF convert - 1 file VCF diextract ke 1 file TXT"""
    print(f"DEBUG: convert_vcf_single called")
    print(f"DEBUG: request.files keys: {list(request.files.keys())}")
    print(f"DEBUG: request.form keys: {list(request.form.keys())}")
    
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        print(f"DEBUG: Session validation failed")
        return error_response
    
    if 'vcf_file' not in request.files:
        print(f"DEBUG: vcf_file not in request.files")
        return jsonify({'error': 'File tidak ditemukan'}), 400
    
    file = request.files['vcf_file']
    if file.filename == '':
        print(f"DEBUG: file.filename is empty")
        return jsonify({'error': 'File tidak dipilih'}), 400
    
    if file and file.filename.lower().endswith('.vcf'):
        try:
            # Baca isi file
            content = file.read().decode('utf-8')
            
            # Ambil parameter
            output_format = request.form.get('output_format', 'comma')
            output_prefix = request.form.get('output_prefix', '').strip()
            
            # Parse VCF ke TXT
            txt_contacts = parse_vcf_to_txt(content, output_format)
            
            if not txt_contacts:
                return jsonify({'error': 'Tidak ada kontak valid ditemukan dalam file VCF'}), 400
            
            # Generate TXT content
            txt_content = '\n'.join(txt_contacts)
            
            # Generate filename
            filename = secure_filename(file.filename)
            base_name = filename.rsplit('.', 1)[0]
            
            if output_prefix:
                txt_filename = f"{output_prefix}.txt"
            else:
                txt_filename = f"{base_name}.txt"
            
            response = make_response(txt_content)
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="{txt_filename}"'
            return response
            
        except Exception as e:
            return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500
    
    return jsonify({'error': 'Format file tidak didukung. Gunakan file .vcf'}), 400

@app.route('/convert_vcf_multi', methods=['POST'])
def convert_vcf_multi():
    """Proses multi VCF convert - multiple file VCF diextract ke multiple TXT"""
    print(f"DEBUG: convert_vcf_multi called")
    print(f"DEBUG: request.files keys: {list(request.files.keys())}")
    print(f"DEBUG: request.form keys: {list(request.form.keys())}")
    
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        print(f"DEBUG: Session validation failed")
        return error_response
    
    if 'vcf_files' not in request.files:
        print(f"DEBUG: vcf_files not in request.files")
        return jsonify({'error': 'File tidak ditemukan'}), 400
    
    files = request.files.getlist('vcf_files')
    if not files or len(files) == 0:
        print(f"DEBUG: files is empty")
        return jsonify({'error': 'File tidak dipilih'}), 400
    
    try:
        # Ambil parameter
        output_format = request.form.get('output_format', 'comma')
        output_prefix = request.form.get('output_prefix', '').strip()
        merge_files = request.form.get('merge_files') == 'true'
        
        all_contacts = []
        files_info = []
        
        for i, file in enumerate(files):
            if file.filename == '':
                continue
                
            if not file.filename.lower().endswith('.vcf'):
                continue
            
            # Baca isi file
            content = file.read().decode('utf-8')
            
            # Parse VCF ke TXT
            txt_contacts = parse_vcf_to_txt(content, output_format)
            
            if txt_contacts:
                if merge_files:
                    # Tambahkan ke list gabungan
                    all_contacts.extend(txt_contacts)
                else:
                    # Buat file terpisah
                    txt_content = '\n'.join(txt_contacts)
                    
                    # Generate filename
                    filename = secure_filename(file.filename)
                    base_name = filename.rsplit('.', 1)[0]
                    
                    if output_prefix:
                        txt_filename = f"{output_prefix}_{base_name}.txt"
                    else:
                        txt_filename = f"{base_name}.txt"
                    
                    # Store file content in temp storage
                    file_id = f"vcf_multi_{int(time.time())}_{i}"
                    temp_file_storage[file_id] = {
                        'content': txt_content,
                        'filename': txt_filename,
                        'mimetype': 'text/plain'
                    }
                    
                    files_info.append({
                        'file_id': file_id,
                        'filename': txt_filename,
                        'size': len(txt_content.encode('utf-8')),
                        'contacts': len(txt_contacts)
                    })
        
        if merge_files and all_contacts:
            # Gabungkan semua kontak ke 1 file
            txt_content = '\n'.join(all_contacts)
            
            if output_prefix:
                txt_filename = f"{output_prefix}.txt"
            else:
                txt_filename = "merged_contacts.txt"
            
            response = make_response(txt_content)
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="{txt_filename}"'
            return response
        
        elif files_info:
            # Return multiple files info
            return jsonify({
                'success': True,
                'multiple_files': True,
                'total_files': len(files_info),
                'total_contacts': sum(f['contacts'] for f in files_info),
                'files': files_info
            })
        
        else:
            return jsonify({'error': 'Tidak ada kontak valid ditemukan dalam file VCF'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500

# ========================
# ADMIN & NAVY ROUTES
# ========================

@app.route('/gabung-vcf')
def gabung_vcf():
    return render_template('gabung_vcf.html')

@app.route('/gabung_vcf_files', methods=['POST'])
def gabung_vcf_files():
    try:
        if 'vcf_files' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400
        
        uploaded_files = request.files.getlist('vcf_files')
        
        if not uploaded_files or len(uploaded_files) < 2:
            return jsonify({'error': 'Please upload at least 2 VCF files'}), 400
        
        # Quick validation - check file extensions only
        for file in uploaded_files:
            if not file.filename.lower().endswith('.vcf'):
                return jsonify({'error': f'File {file.filename} is not a VCF file'}), 400
        
        # Get form data
        contact_name_prefix = request.form.get('contact_name', 'Gabung').strip()
        output_filename = request.form.get('output_filename', 'merged_contacts').strip()
        
        if not contact_name_prefix:
            contact_name_prefix = 'Gabung'
        
        if not output_filename:
            output_filename = 'merged_contacts'
        
        # Read and process all VCF files - Optimized
        vcf_contents = []
        original_stats = []
        
        for file in uploaded_files:
            try:
                content = file.read().decode('utf-8', errors='ignore')  # Ignore encoding errors
                vcf_contents.append(content)
                
                # Quick count for stats
                import re
                tel_count = len(re.findall(r'TEL[^:]*:', content))
                original_stats.append({
                    'filename': file.filename,
                    'contacts': tel_count
                })
            except Exception as e:
                print(f"Error reading file {file.filename}: {e}")
                continue
        
        if not vcf_contents:
            return jsonify({'error': 'No valid VCF content found'}), 400
        
        # Merge VCF files - Optimized function
        merged_contacts = merge_vcf_files(vcf_contents, contact_name_prefix)
        
        if not merged_contacts:
            return jsonify({'error': 'No valid contacts found in uploaded files'}), 400
        
        # Create final VCF content
        final_vcf_content = '\n\n'.join(merged_contacts)  # Add spacing between contacts
        
        # Store in temp storage instead of session (to avoid cookie size limit)
        import uuid
        file_id = f"gabung_vcf_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        temp_file_storage[file_id] = {
            'content': final_vcf_content,
            'filename': f"{output_filename}.vcf",
            'mimetype': 'text/vcard',
            'timestamp': time.time()
        }
        
        # Store only file ID in session
        session['download_file_id'] = file_id
        
        # Create summary
        total_original_contacts = sum(stat['contacts'] for stat in original_stats)
        
        return jsonify({
            'success': True,
            'message': f'Successfully merged {len(uploaded_files)} VCF files',
            'original_files': original_stats,
            'total_original_contacts': total_original_contacts,
            'merged_contacts': len(merged_contacts),
            'contact_name_prefix': contact_name_prefix,
            'output_filename': f"{output_filename}.vcf",
            'download_url': '/download'
        })
        
    except Exception as e:
        print(f"Error in gabung_vcf_files: {e}")
        return jsonify({'error': f'Error processing files: {str(e)}'}), 500

@app.route('/admin-navy')
def admin_navy():
    """Halaman converter Admin & Navy"""
    print("DEBUG: Accessing /admin-navy route")
    
    # Check session validity with tracking
    redirect_response = require_valid_session()
    if redirect_response:
        return redirect_response
    
    print("DEBUG: Rendering admin_navy.html template")
    return render_template('admin_navy.html')

@app.route('/convert_admin_navy', methods=['POST'])
def convert_admin_navy():
    """Proses konversi Admin & Navy numbers ke VCF"""
    print(f"DEBUG: convert_admin_navy called")
    print(f"DEBUG: request.form keys: {list(request.form.keys())}")
    
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        print(f"DEBUG: Session validation failed")
        return error_response
    
    try:
        # Ambil parameter dari form - sesuai dengan template baru
        admin_numbers = request.form.get('admin_numbers', '').strip()
        navy_numbers = request.form.get('navy_numbers', '').strip()
        admin_name_prefix = request.form.get('admin_name_prefix', 'Admin').strip()
        navy_name_prefix = request.form.get('navy_name_prefix', 'Navy').strip()
        admin_start_number = int(request.form.get('admin_start_number', 1))
        navy_start_number = int(request.form.get('navy_start_number', 1))
        output_filename = request.form.get('output_filename', '').strip()
        
        print(f"DEBUG: admin_numbers length: {len(admin_numbers.split()) if admin_numbers else 0}")
        print(f"DEBUG: navy_numbers length: {len(navy_numbers.split()) if navy_numbers else 0}")
        print(f"DEBUG: admin_name_prefix: '{admin_name_prefix}'")
        print(f"DEBUG: navy_name_prefix: '{navy_name_prefix}'")
        print(f"DEBUG: admin_start_number: {admin_start_number}")
        print(f"DEBUG: navy_start_number: {navy_start_number}")
        print(f"DEBUG: output_filename: '{output_filename}'")
        
        # Validasi input
        if not admin_numbers and not navy_numbers:
            return jsonify({'error': 'Minimal salah satu nomor (admin atau navy) harus diisi'}), 400
        
        # Validasi nama kontak
        if admin_numbers and not admin_name_prefix:
            admin_name_prefix = 'Admin'
        if navy_numbers and not navy_name_prefix:
            navy_name_prefix = 'Navy'
        
        # Parse ke VCF dengan fungsi yang mendukung start number
        vcf_contacts = parse_admin_navy_to_vcf_with_start(
            admin_numbers, 
            navy_numbers, 
            admin_name_prefix, 
            navy_name_prefix,
            admin_start_number,
            navy_start_number
        )
        
        if not vcf_contacts:
            return jsonify({'error': 'Tidak ada nomor valid ditemukan'}), 400
        
        # Generate VCF content
        vcf_content = '\n'.join(vcf_contacts)
        
        # Generate filename
        if output_filename:
            if not output_filename.lower().endswith('.vcf'):
                output_filename += '.vcf'
            vcf_filename = secure_filename(output_filename)
        else:
            vcf_filename = "admin_navy_contacts.vcf"
        
        print(f"DEBUG: Generated {len(vcf_contacts)} contacts, filename: {vcf_filename}")
        
        response = make_response(vcf_content)
        response.headers['Content-Type'] = 'text/vcard'
        response.headers['Content-Disposition'] = f'attachment; filename="{vcf_filename}"'
        return response
        
    except Exception as e:
        print(f"DEBUG: Error in convert_admin_navy: {str(e)}")
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500

# ========================
# GABUNG TXT ROUTES
# ========================

@app.route('/gabung-txt')
def gabung_txt():
    """Halaman gabung multiple TXT files"""
    print("DEBUG: Accessing /gabung-txt route")
    
    # Check session validity with tracking
    redirect_response = require_valid_session()
    if redirect_response:
        return redirect_response
    
    print("DEBUG: Rendering gabung_txt.html template")
    return render_template('gabung_txt.html')

@app.route('/gabung_txt_files', methods=['POST'])
def gabung_txt_files():
    """Proses gabung multiple TXT files menjadi 1 file TXT"""
    print(f"DEBUG: gabung_txt_files called")
    print(f"DEBUG: request.files keys: {list(request.files.keys())}")
    print(f"DEBUG: request.form keys: {list(request.form.keys())}")
    
    # Check session validity with tracking
    error_response = require_valid_session(return_json=True)
    if error_response:
        print(f"DEBUG: Session validation failed")
        return error_response
    
    if 'txt_files' not in request.files:
        print(f"DEBUG: txt_files not in request.files")
        return jsonify({'error': 'File tidak ditemukan'}), 400
    
    files = request.files.getlist('txt_files')
    if not files or len(files) < 2:
        print(f"DEBUG: Not enough files: {len(files) if files else 0}")
        return jsonify({'error': 'Minimal 2 file TXT diperlukan untuk digabung'}), 400
    
    try:
        # Ambil parameter
        output_filename = request.form.get('output_filename', '').strip()
        separator_option = request.form.get('separator_option', 'none')
        custom_separator = request.form.get('custom_separator', '').strip()
        add_filename_headers = request.form.get('add_filename_headers') == 'true'
        
        print(f"DEBUG: output_filename: '{output_filename}'")
        print(f"DEBUG: separator_option: '{separator_option}'")
        print(f"DEBUG: custom_separator: '{custom_separator}'")
        print(f"DEBUG: add_filename_headers: {add_filename_headers}")
        print(f"DEBUG: files_count: {len(files)}")
        
        # Validasi nama file output
        if not output_filename:
            output_filename = "merged_files"
        
        # Process files and merge content
        merged_content = []
        processed_files = 0
        valid_files = [f for f in files if f.filename != '' and allowed_file(f.filename)]
        
        for i, file in enumerate(valid_files):
            try:
                # Baca isi file
                content = file.read().decode('utf-8').strip()
                
                if content:  # Hanya proses jika ada content
                    # Tambah header nama file jika diperlukan
                    if add_filename_headers:
                        header = f"=== {file.filename} ==="
                        merged_content.append(header)
                    
                    # Tambah content file
                    merged_content.append(content)
                    processed_files += 1
                    
                    # Tambah separator jika bukan file terakhir dan separator diperlukan
                    if processed_files < len(valid_files) and separator_option != 'none':
                        if separator_option == 'newline':
                            merged_content.append('')  # Baris kosong
                        elif separator_option == 'double_newline':
                            merged_content.append('')
                            merged_content.append('')  # 2 baris kosong
                        elif separator_option == 'dash':
                            merged_content.append('---')
                        elif separator_option == 'custom' and custom_separator:
                            merged_content.append(custom_separator)
                
            except UnicodeDecodeError:
                # Coba dengan encoding lain
                try:
                    file.seek(0)
                    content = file.read().decode('latin-1').strip()
                    if content:
                        if add_filename_headers:
                            header = f"=== {file.filename} ==="
                            merged_content.append(header)
                        merged_content.append(content)
                        processed_files += 1
                        
                        # Tambah separator untuk encoding latin-1 juga
                        if processed_files < len(valid_files) and separator_option != 'none':
                            if separator_option == 'newline':
                                merged_content.append('')
                            elif separator_option == 'double_newline':
                                merged_content.append('')
                                merged_content.append('')
                            elif separator_option == 'dash':
                                merged_content.append('---')
                            elif separator_option == 'custom' and custom_separator:
                                merged_content.append(custom_separator)
                except Exception as e:
                    print(f"DEBUG: Error reading file {file.filename}: {e}")
                    continue
            except Exception as e:
                print(f"DEBUG: Error processing file {file.filename}: {e}")
                continue
        
        if processed_files < 2:
            return jsonify({'error': 'Minimal 2 file berhasil diproses diperlukan untuk digabung'}), 400
        
        # Generate final merged content
        final_content = '\n'.join(merged_content)
        
        # Generate filename
        if not output_filename.lower().endswith('.txt'):
            output_filename += '.txt'
        final_filename = secure_filename(output_filename)
        
        print(f"DEBUG: Generated merged file - {processed_files} files processed, filename: {final_filename}")
        print(f"DEBUG: Content length: {len(final_content)} characters")
        
        response = make_response(final_content)
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="{final_filename}"'
        return response
        
    except Exception as e:
        print(f"DEBUG: Error in gabung_txt_files: {str(e)}")
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500

@app.route('/logout')
def logout():
    """Logout user dan clear session"""
    api_key = session.get('api_key')
    
    # Invalidate session tracking
    if api_key:
        invalidate_session(api_key)
        print(f"DEBUG: User logged out, invalidated session for API key {api_key}")
    
    # Clear session
    session.clear()
    flash('Berhasil logout. Terima kasih!', 'success')
    return redirect(url_for('index'))

@app.route('/admin')
def admin_login():
    """Halaman login admin"""
    return render_template('admin_login.html')

@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    """Verifikasi login admin"""
    password = request.form.get('password', '')
    
    if password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        flash('Login admin berhasil!', 'success')
        return redirect(url_for('admin_panel'))
    else:
        flash('Password admin salah!', 'error')
        return redirect(url_for('admin_login'))

@app.route('/admin/panel')
def admin_panel():
    """Panel admin untuk manage API keys"""
    if 'admin_logged_in' not in session or not session['admin_logged_in']:
        flash('Silakan login sebagai admin terlebih dahulu.', 'error')
        return redirect(url_for('admin_login'))
    
    api_keys = load_api_keys()
    return render_template('admin_panel.html', api_keys=api_keys)

@app.route('/admin/generate_key', methods=['POST'])
def generate_key():
    """Generate API key baru"""
    if 'admin_logged_in' not in session or not session['admin_logged_in']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    duration_months = request.form.get('duration', '1')
    description = request.form.get('description', '')
    
    try:
        duration_months = int(duration_months)
        if duration_months <= 0:
            return jsonify({'error': 'Durasi harus lebih dari 0'}), 400
    except ValueError:
        return jsonify({'error': 'Durasi harus berupa angka'}), 400
    
    # Generate API key
    new_api_key = generate_api_key()
    
    # Hitung tanggal expired
    expiry_date = datetime.now() + timedelta(days=duration_months * 30)
    
    # Load existing keys
    api_keys = load_api_keys()
    
    # Tambah key baru
    api_keys[new_api_key] = {
        'created_date': datetime.now().isoformat(),
        'expiry_date': expiry_date.isoformat(),
        'description': description,
        'duration_months': duration_months
    }
    
    # Save
    save_api_keys(api_keys)
    
    flash(f'API key berhasil dibuat: {new_api_key}', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_key/<api_key>', methods=['POST'])
def delete_key(api_key):
    """Hapus API key"""
    if 'admin_logged_in' not in session or not session['admin_logged_in']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    api_keys = load_api_keys()
    
    if api_key in api_keys:
        # Hapus API key dari database
        del api_keys[api_key]
        save_api_keys(api_keys)
        
        # PENTING: Hapus session aktif yang menggunakan API key ini
        if api_key in active_sessions:
            del active_sessions[api_key]
            print(f"DEBUG: Deleted active session for API key {api_key}")
        
        flash('API key berhasil dihapus!', 'success')
    else:
        flash('API key tidak ditemukan!', 'error')
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/logout')
def admin_logout():
    """Logout admin"""
    session.pop('admin_logged_in', None)
    flash('Admin logout berhasil.', 'info')
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    # Development
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # Production - untuk deployment
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
