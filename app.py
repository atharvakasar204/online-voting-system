from flask import Flask, render_template, request, redirect, session, send_from_directory
import sqlite3
import os
import base64

from werkzeug.security import generate_password_hash, check_password_hash
from deepface import DeepFace

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = 'uploads'
FACE_FOLDER = 'faces'
CANDIDATE_FOLDER = 'candidate_photos'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------------- CREATE FOLDERS ----------------
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(FACE_FOLDER):
    os.makedirs(FACE_FOLDER)

if not os.path.exists(CANDIDATE_FOLDER):
    os.makedirs(CANDIDATE_FOLDER)

# ---------------- DATABASE ----------------
def init_db():

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # USERS TABLE
    cur.execute("""

    CREATE TABLE IF NOT EXISTS users (

        username TEXT PRIMARY KEY,
        password TEXT,

        full_name TEXT,
        phone TEXT,
        age INTEGER,

        unique_id TEXT UNIQUE,

        id_proof TEXT,
        face_image TEXT,

        has_voted INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,

        role TEXT DEFAULT 'user'
    )

    """)

    # VOTES TABLE
    cur.execute("""

    CREATE TABLE IF NOT EXISTS votes (

        candidate TEXT

    )

    """)

    # CANDIDATES TABLE
    cur.execute("""

    CREATE TABLE IF NOT EXISTS candidates (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        username TEXT,

        candidate_name TEXT,

        party_name TEXT,

        manifesto TEXT,

        photo TEXT,

        approved INTEGER DEFAULT 0

    )

    """)

    # CREATE ADMIN
    admin_pass = generate_password_hash("admin123")

    try:

        cur.execute("""

        INSERT INTO users (
            username,
            password,
            role,
            is_verified
        )

        VALUES (?, ?, ?, ?)

        """, (

            "admin",
            admin_pass,
            "admin",
            1

        ))

    except:
        pass

    conn.commit()
    conn.close()

init_db()

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    return sqlite3.connect("database.db")

# ---------------- HOME ----------------
@app.route('/')
def home():
    return redirect('/login')

# ---------------- REGISTER PAGE ----------------
@app.route('/register')
def register_page():
    return render_template('register.html')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['POST'])
def register():

    full_name = request.form['full_name']
    username = request.form['username']
    password = request.form['password']

    phone = request.form['phone']
    age = request.form['age']

    unique_id = request.form['unique_id']

    # ID PROOF
    file = request.files['id_proof']
    filename = file.filename

    if filename:
        file.save(os.path.join(UPLOAD_FOLDER, filename))

    # FACE IMAGE
    face_file = request.files['face_image']
    face_filename = username + ".jpg"

    face_file.save(os.path.join(FACE_FOLDER, face_filename))

    conn = get_db()
    cur = conn.cursor()

    # CHECK USERNAME
    cur.execute("""

    SELECT * FROM users
    WHERE username=?

    """, (username,))

    if cur.fetchone():
        return "Username already exists!"

    # CHECK UNIQUE ID
    cur.execute("""

    SELECT * FROM users
    WHERE unique_id=?

    """, (unique_id,))

    if cur.fetchone():
        return "This ID already registered!"

    hashed_password = generate_password_hash(password)

    # INSERT USER
    cur.execute("""

    INSERT INTO users (

        username,
        password,
        full_name,
        phone,
        age,
        unique_id,
        id_proof,
        face_image

    )

    VALUES (?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        username,
        hashed_password,
        full_name,
        phone,
        age,
        unique_id,
        filename,
        face_filename

    ))

    conn.commit()

    return redirect('/login')

# ---------------- LOGIN PAGE ----------------
@app.route('/login')
def login_page():
    return render_template('login.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['POST'])
def login():

    username = request.form['username']
    password = request.form['password']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

    SELECT password, role, has_voted
    FROM users
    WHERE username=?

    """, (username,))

    user = cur.fetchone()

    if user and check_password_hash(user[0], password):

        session['user'] = username
        session['role'] = user[1]

        # ADMIN
        if user[1] == 'admin':
            return redirect('/admin')

        # ALREADY VOTED
        if user[2] == 1:
            return redirect('/results')

        # FACE VERIFY
        return redirect('/face_verify_page')

    else:
        return "Invalid login!"

# ---------------- FACE VERIFY PAGE ----------------
@app.route('/face_verify_page')
def face_verify_page():

    if 'user' not in session:
        return redirect('/login')

    return render_template('face_verify.html')

# ---------------- FACE VERIFY ----------------
@app.route('/face_verify', methods=['POST'])
def face_verify():

    if 'user' not in session:
        return redirect('/login')

    try:

        username = session['user']

        # GET IMAGE DATA
        image_data = request.form.get('image_data')

        if not image_data:
            return "No webcam image received!"

        # CHECK FORMAT
        if "," not in image_data:
            return "Invalid webcam image!"

        # REMOVE BASE64 HEADER
        image_data = image_data.split(",")[1]

        # SAVE LIVE IMAGE
        live_path = os.path.join(
            FACE_FOLDER,
            "live.jpg"
        )

        with open(live_path, "wb") as f:

            f.write(base64.b64decode(image_data))

        # REGISTERED IMAGE
        registered_path = os.path.join(
            FACE_FOLDER,
            username + ".jpg"
        )

        if not os.path.exists(registered_path):
            return "Registered face image missing!"

        # VERIFY FACE
        result = DeepFace.verify(

            img1_path=registered_path,
            img2_path=live_path,

            detector_backend="opencv",
            enforce_detection=False

        )

        # MATCHED
        if result["verified"]:

            return redirect('/vote')

        else:

            return "Face not matched!"

    except Exception as e:

        return f"Verification Error: {str(e)}"

# ---------------- APPLY CANDIDATE PAGE ----------------
@app.route('/apply_candidate')
def apply_candidate_page():

    return render_template('apply_candidate.html')

# ---------------- APPLY CANDIDATE ----------------
@app.route('/apply_candidate', methods=['POST'])
def apply_candidate():

    # GET USERNAME FROM SESSION
    username = session.get(
        'user',
        'guest_user'
    )

    candidate_name = request.form['candidate_name']
    party_name = request.form['party_name']
    manifesto = request.form['manifesto']

    # PHOTO
    photo = request.files['photo']

    photo_filename = username + ".jpg"

    photo.save(
        os.path.join(
            CANDIDATE_FOLDER,
            photo_filename
        )
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

    INSERT INTO candidates (

        username,
        candidate_name,
        party_name,
        manifesto,
        photo

    )

    VALUES (?, ?, ?, ?, ?)

    """, (

        username,
        candidate_name,
        party_name,
        manifesto,
        photo_filename

    ))

    conn.commit()

    return "Candidate application submitted successfully!"

# ---------------- VOTE PAGE ----------------
@app.route('/vote')
def vote():

    if 'user' not in session:
        return redirect('/login')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

    SELECT has_voted, is_verified
    FROM users
    WHERE username=?

    """, (session['user'],))

    user = cur.fetchone()

    # NOT VERIFIED
    if user[1] == 0:
        return "You are not verified by admin yet!"

    # ALREADY VOTED
    if user[0] == 1:
        return redirect('/results')

    # GET APPROVED CANDIDATES
    cur.execute("""

    SELECT
    candidate_name,
    party_name,
    photo

    FROM candidates

    WHERE approved=1

    """)

    candidates = cur.fetchall()

    return render_template(
        'vote.html',
        candidates=candidates
    )

# ---------------- SUBMIT VOTE ----------------
@app.route('/submit', methods=['POST'])
def submit():

    candidate = request.form['candidate']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

    INSERT INTO votes (candidate)
    VALUES (?)

    """, (candidate,))

    cur.execute("""

    UPDATE users
    SET has_voted=1
    WHERE username=?

    """, (session['user'],))

    conn.commit()

    return redirect('/results')

# ---------------- RESULTS ----------------
@app.route('/results')
def results():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

    SELECT candidate, COUNT(*)
    FROM votes
    GROUP BY candidate
    ORDER BY COUNT(*) DESC

    """)

    data = cur.fetchall()

    return render_template(
        'result.html',
        results=data
    )

# ---------------- ADMIN PAGE ----------------
@app.route('/admin')
def admin():

    if session.get('role') != 'admin':
        return redirect('/login')

    conn = get_db()
    cur = conn.cursor()

    # USERS
    cur.execute("""

    SELECT
    username,
    full_name,
    unique_id,
    is_verified,
    has_voted,
    id_proof

    FROM users

    WHERE role='user'

    """)

    users = cur.fetchall()

    # TOTAL USERS
    cur.execute("""

    SELECT COUNT(*)
    FROM users
    WHERE role='user'

    """)

    total_users = cur.fetchone()[0]

    # VERIFIED USERS
    cur.execute("""

    SELECT COUNT(*)
    FROM users
    WHERE is_verified=1

    """)

    verified_users = cur.fetchone()[0]

    # TOTAL VOTES
    cur.execute("""

    SELECT COUNT(*)
    FROM votes

    """)

    total_votes = cur.fetchone()[0]

    # GET CANDIDATES
    cur.execute("""

    SELECT
    id,
    candidate_name,
    party_name,
    manifesto,
    photo,
    approved

    FROM candidates

    """)

    candidate_list = cur.fetchall()

    return render_template(

        'admin.html',

        users=users,
        total_users=total_users,
        verified_users=verified_users,
        total_votes=total_votes,
        candidate_list=candidate_list

    )

# ---------------- VERIFY USER ----------------
@app.route('/verify/<username>')
def verify(username):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

    UPDATE users
    SET is_verified=1
    WHERE username=?

    """, (username,))

    conn.commit()

    return redirect('/admin')

# ---------------- DELETE USER ----------------
@app.route('/delete_user/<username>')
def delete_user(username):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

    DELETE FROM users
    WHERE username=?

    """, (username,))

    conn.commit()

    return redirect('/admin')

# ---------------- APPROVE CANDIDATE ----------------
@app.route('/approve_candidate/<int:id>')
def approve_candidate(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

    UPDATE candidates
    SET approved=1
    WHERE id=?

    """, (id,))

    conn.commit()

    return redirect('/admin')

# ---------------- CANDIDATE PHOTO ----------------
@app.route('/candidate_photos/<filename>')
def candidate_photo(filename):

    return send_from_directory(
        CANDIDATE_FOLDER,
        filename
    )

# ---------------- VIEW FILE ----------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):

    return send_from_directory(
        UPLOAD_FOLDER,
        filename
    )

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')

# ---------------- RUN ----------------
if __name__ == '__main__':

    port = int(
        os.environ.get("PORT", 5000)
    )

    app.run(
        host='0.0.0.0',
        port=port
    )