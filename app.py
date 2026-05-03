from flask import Flask, render_template, request, redirect, session, send_from_directory
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        full_name TEXT,
        phone TEXT,
        age INTEGER,
        unique_id TEXT,
        id_proof TEXT,
        has_voted INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        role TEXT DEFAULT 'user'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        candidate TEXT
    )
    """)

    # Admin user
    admin_pass = generate_password_hash("admin123")
    try:
        cur.execute("INSERT INTO users (username, password, role, is_verified) VALUES (?, ?, ?, ?)",
                    ("admin", admin_pass, "admin", 1))
    except:
        pass

    conn.commit()
    conn.close()

init_db()

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

    file = request.files['id_proof']
    filename = file.filename

    if filename:
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    if cur.fetchone():
        return "User already exists!"

    hashed_password = generate_password_hash(password)

    cur.execute("""
    INSERT INTO users (username, password, full_name, phone, age, unique_id, id_proof)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (username, hashed_password, full_name, phone, age, unique_id, filename))

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

    cur.execute("SELECT password, role, has_voted FROM users WHERE username=?", (username,))
    user = cur.fetchone()

    if user and check_password_hash(user[0], password):
        session['user'] = username
        session['role'] = user[1]

        if user[1] == 'admin':
            return redirect('/admin')

        if user[2] == 1:
            return redirect('/results')

        return redirect('/vote')

    else:
        return "Invalid login!"

# ---------------- VOTE ----------------
@app.route('/vote')
def vote():
    if 'user' not in session:
        return redirect('/login')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT has_voted, is_verified FROM users WHERE username=?", (session['user'],))
    user = cur.fetchone()

    if user[1] == 0:
        return "You are not verified by admin yet!"

    if user[0] == 1:
        return redirect('/results')

    return render_template('vote.html')

# ---------------- SUBMIT ----------------
@app.route('/submit', methods=['POST'])
def submit():
    candidate = request.form['candidate']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("INSERT INTO votes (candidate) VALUES (?)", (candidate,))
    cur.execute("UPDATE users SET has_voted=1 WHERE username=?", (session['user'],))

    conn.commit()
    return redirect('/results')

# ---------------- RESULTS ----------------
@app.route('/results')
def results():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT candidate, COUNT(*) FROM votes GROUP BY candidate")
    data = cur.fetchall()

    return render_template('result.html', results=data)

# ---------------- ADMIN ----------------
@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect('/login')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT username, full_name, unique_id, is_verified, has_voted, id_proof 
    FROM users WHERE role='user'
    """)
    users = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM users WHERE role='user'")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE is_verified=1")
    verified_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM votes")
    total_votes = cur.fetchone()[0]

    return render_template('admin.html',
                           users=users,
                           total_users=total_users,
                           verified_users=verified_users,
                           total_votes=total_votes)

# ---------------- VERIFY ----------------
@app.route('/verify/<username>')
def verify(username):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_verified=1 WHERE username=?", (username,))
    conn.commit()
    return redirect('/admin')

# ---------------- FILE VIEW ----------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)