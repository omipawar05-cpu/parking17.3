"""
Pay and Parking Management System
Flask Backend with PostgreSQL (psycopg2)
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import os

app = Flask(__name__)
app.secret_key = 'parking_secret_key_2024'  # Change this in production

# ─────────────────────────────────────────
# DATABASE CONNECTION
# ─────────────────────────────────────────

def get_db():
    """Return a new database connection."""
    conn = psycopg2.connect(
        host="localhost",
        database="parking_db",
        user="postgres",
        password="root123"       # ← change to your DB password
    )
    return conn

def hash_password(password):
    """Simple SHA-256 password hashing."""
    return hashlib.sha256(password.encode()).hexdigest()

# ─────────────────────────────────────────
# AUTH DECORATOR
# ─────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Admin access required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────
# DATABASE SETUP  (run once)
# ─────────────────────────────────────────

def init_db():
    """Create tables and seed initial data."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(256) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            id SERIAL PRIMARY KEY,
            slot_number VARCHAR(10) UNIQUE NOT NULL,
            slot_type VARCHAR(20) DEFAULT 'regular',
            is_available BOOLEAN DEFAULT TRUE,
            price_per_hour NUMERIC(6,2) DEFAULT 50.00
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            slot_id INTEGER REFERENCES parking_slots(id),
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            duration_hours NUMERIC(5,2),
            total_cost NUMERIC(8,2),
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Seed admin user
    cur.execute("SELECT COUNT(*) FROM users WHERE is_admin = TRUE")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO users (name, email, password, is_admin)
            VALUES (%s, %s, %s, TRUE)
        """, ('Admin', 'admin@parking.com', hash_password('admin123')))

    # Seed 20 parking slots (A1–A5, B1–B5, C1–C5, D1–D5)
    cur.execute("SELECT COUNT(*) FROM parking_slots")
    if cur.fetchone()[0] == 0:
        slots = []
        for row, letter in enumerate(['A', 'B', 'C', 'D']):
            for num in range(1, 6):
                slot_type = 'premium' if letter in ['A'] else 'regular'
                price = 80.00 if slot_type == 'premium' else 50.00
                slots.append((f"{letter}{num}", slot_type, price))
        cur.executemany("""
            INSERT INTO parking_slots (slot_number, slot_type, price_per_hour)
            VALUES (%s, %s, %s)
        """, slots)

    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────

def expire_bookings():
    """Mark slots as available if booking end_time has passed."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE bookings SET status = 'completed'
        WHERE status = 'active' AND end_time < NOW()
    """)
    cur.execute("""
        UPDATE parking_slots SET is_available = TRUE
        WHERE id IN (
            SELECT slot_id FROM bookings
            WHERE status = 'completed'
        )
        AND id NOT IN (
            SELECT slot_id FROM bookings
            WHERE status = 'active'
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

# 1. HOME PAGE
@app.route('/')
def home():
    expire_bookings()
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT COUNT(*) as total FROM parking_slots")
    total = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) as available FROM parking_slots WHERE is_available = TRUE")
    available = cur.fetchone()['available']
    cur.close()
    conn.close()
    return render_template('home.html', total=total, available=available)


# 2. REGISTER PAGE
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validation
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO users (name, email, password)
                VALUES (%s, %s, %s)
            """, (name, email, hash_password(password)))
            conn.commit()
            cur.close()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except psycopg2.errors.UniqueViolation:
            flash('Email already registered.', 'error')
            return render_template('register.html')

    return render_template('register.html')


# 3. LOGIN PAGE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s AND password = %s",
                    (email, hash_password(password)))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['is_admin'] = user['is_admin']
            flash(f'Welcome back, {user["name"]}!', 'success')
            if user['is_admin']:
                return redirect(url_for('admin'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))


# 4. DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():
    expire_bookings()
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Active bookings
    cur.execute("""
        SELECT b.*, s.slot_number, s.slot_type
        FROM bookings b
        JOIN parking_slots s ON b.slot_id = s.id
        WHERE b.user_id = %s AND b.status = 'active'
        ORDER BY b.created_at DESC
    """, (session['user_id'],))
    active_bookings = cur.fetchall()

    # Booking history
    cur.execute("""
        SELECT b.*, s.slot_number, s.slot_type
        FROM bookings b
        JOIN parking_slots s ON b.slot_id = s.id
        WHERE b.user_id = %s AND b.status = 'completed'
        ORDER BY b.created_at DESC LIMIT 10
    """, (session['user_id'],))
    history = cur.fetchall()

    # Total spent
    cur.execute("""
        SELECT COALESCE(SUM(total_cost), 0) as total
        FROM bookings WHERE user_id = %s
    """, (session['user_id'],))
    total_spent = cur.fetchone()['total']

    cur.close()
    conn.close()
    return render_template('dashboard.html',
                           active_bookings=active_bookings,
                           history=history,
                           total_spent=total_spent)


# 5. PARKING SLOTS PAGE
@app.route('/slots')
def slots():
    expire_bookings()
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM parking_slots ORDER BY slot_number")
    all_slots = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('slots.html', slots=all_slots)


# 6. BOOKING PAGE
@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    expire_bookings()
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == 'POST':
        slot_id = request.form.get('slot_id')
        hours = float(request.form.get('hours', 1))

        # Validate slot
        cur.execute("SELECT * FROM parking_slots WHERE id = %s AND is_available = TRUE", (slot_id,))
        slot = cur.fetchone()
        if not slot:
            flash('Slot not available or already booked.', 'error')
            return redirect(url_for('book'))

        # Validate hours
        if hours < 0.5 or hours > 24:
            flash('Duration must be between 0.5 and 24 hours.', 'error')
            return redirect(url_for('book'))

        start_time = datetime.now()
        end_time = start_time + timedelta(hours=hours)
        total_cost = round(slot['price_per_hour'] * hours, 2)

        # Store booking details in session for payment page
        session['pending_booking'] = {
            'slot_id': slot_id,
            'slot_number': slot['slot_number'],
            'slot_type': slot['slot_type'],
            'hours': hours,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'total_cost': total_cost,
            'price_per_hour': float(slot['price_per_hour'])
        }

        cur.close()
        conn.close()
        return redirect(url_for('payment'))

    cur.execute("SELECT * FROM parking_slots WHERE is_available = TRUE ORDER BY slot_number")
    available_slots = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('book.html', slots=available_slots)


# 7. PAYMENT PAGE
@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    booking = session.get('pending_booking')
    if not booking:
        flash('No pending booking found.', 'error')
        return redirect(url_for('book'))

    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()

        # Double-booking check
        cur.execute("SELECT is_available FROM parking_slots WHERE id = %s", (booking['slot_id'],))
        slot_check = cur.fetchone()
        if not slot_check or not slot_check[0]:
            flash('Sorry, this slot was just booked by someone else.', 'error')
            session.pop('pending_booking', None)
            cur.close()
            conn.close()
            return redirect(url_for('book'))

        # Insert booking
        cur.execute("""
            INSERT INTO bookings (user_id, slot_id, start_time, end_time, duration_hours, total_cost, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'active')
        """, (
            session['user_id'],
            booking['slot_id'],
            booking['start_time'],
            booking['end_time'],
            booking['hours'],
            booking['total_cost']
        ))

        # Mark slot as occupied
        cur.execute("UPDATE parking_slots SET is_available = FALSE WHERE id = %s", (booking['slot_id'],))

        conn.commit()
        cur.close()
        conn.close()

        session.pop('pending_booking', None)
        flash(f'Payment successful! Slot {booking["slot_number"]} booked.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('payment.html', booking=booking)


# 8. ADMIN PANEL
@app.route('/admin')
@admin_required
def admin():
    expire_bookings()
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # All bookings
    cur.execute("""
        SELECT b.*, u.name as user_name, u.email, s.slot_number
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN parking_slots s ON b.slot_id = s.id
        ORDER BY b.created_at DESC
    """)
    all_bookings = cur.fetchall()

    # All slots
    cur.execute("SELECT * FROM parking_slots ORDER BY slot_number")
    all_slots = cur.fetchall()

    # Total earnings
    cur.execute("SELECT COALESCE(SUM(total_cost), 0) as total FROM bookings")
    total_earnings = cur.fetchone()['total']

    # Stats
    cur.execute("SELECT COUNT(*) as total FROM users WHERE is_admin = FALSE")
    total_users = cur.fetchone()['total']

    cur.close()
    conn.close()
    return render_template('admin.html',
                           all_bookings=all_bookings,
                           all_slots=all_slots,
                           total_earnings=total_earnings,
                           total_users=total_users)


# ADMIN: Add Slot
@app.route('/admin/add_slot', methods=['POST'])
@admin_required
def add_slot():
    slot_number = request.form.get('slot_number', '').strip().upper()
    slot_type = request.form.get('slot_type', 'regular')
    price = request.form.get('price', 50.00)

    if not slot_number:
        flash('Slot number is required.', 'error')
        return redirect(url_for('admin'))

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO parking_slots (slot_number, slot_type, price_per_hour)
            VALUES (%s, %s, %s)
        """, (slot_number, slot_type, price))
        conn.commit()
        cur.close()
        conn.close()
        flash(f'Slot {slot_number} added successfully.', 'success')
    except psycopg2.errors.UniqueViolation:
        flash('Slot number already exists.', 'error')

    return redirect(url_for('admin'))


# ADMIN: Remove Slot
@app.route('/admin/remove_slot/<int:slot_id>', methods=['POST'])
@admin_required
def remove_slot(slot_id):
    conn = get_db()
    cur = conn.cursor()

    # Check if slot has active bookings
    cur.execute("SELECT COUNT(*) FROM bookings WHERE slot_id = %s AND status = 'active'", (slot_id,))
    if cur.fetchone()[0] > 0:
        flash('Cannot remove slot with active bookings.', 'error')
    else:
        cur.execute("DELETE FROM parking_slots WHERE id = %s", (slot_id,))
        conn.commit()
        flash('Slot removed successfully.', 'success')

    cur.close()
    conn.close()
    return redirect(url_for('admin'))


# ─────────────────────────────────────────
# API ENDPOINT
# ─────────────────────────────────────────

@app.route('/api/slots')
def api_slots():
    """JSON API endpoint for dynamic slot status updates."""
    expire_bookings()
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, slot_number, slot_type, is_available, price_per_hour FROM parking_slots ORDER BY slot_number")
    slots = [dict(row) for row in cur.fetchall()]
    for s in slots:
        s['price_per_hour'] = float(s['price_per_hour'])
    cur.close()
    conn.close()
    return jsonify({'slots': slots, 'timestamp': datetime.now().isoformat()})


# ─────────────────────────────────────────
# ERROR PAGES
# ─────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('404.html', error="Internal Server Error"), 500


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
