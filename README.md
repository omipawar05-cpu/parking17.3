# 🅿 ParkEase — Pay & Parking Management System

A full-stack web application built with Flask + PostgreSQL.

---

## Project Structure

```
parking_app/
├── app.py                  # Flask backend (all routes, DB logic)
├── requirements.txt        # Python dependencies
├── static/
│   └── style.css           # Global stylesheet
└── templates/
    ├── base.html           # Navbar + flash messages layout
    ├── home.html           # Landing page
    ├── register.html       # User registration
    ├── login.html          # Login page
    ├── dashboard.html      # User dashboard
    ├── slots.html          # Live parking grid
    ├── book.html           # Booking form
    ├── payment.html        # Payment simulation
    ├── admin.html          # Admin panel
    └── 404.html            # Error page
```

---

## Setup

### 1. Create PostgreSQL Database

```sql
CREATE DATABASE parking_db;
```

### 2. Update DB credentials in app.py

```python
conn = psycopg2.connect(
    host="localhost",
    database="parking_db",
    user="postgres",
    password="YOUR_PASSWORD"   # ← change this
)
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python app.py
```

Tables and seed data are created automatically on first run via `init_db()`.

Visit: **http://localhost:5000**

---

## Demo Credentials

| Role  | Email               | Password  |
|-------|---------------------|-----------|
| Admin | admin@parking.com   | admin123  |

Register a new account for a regular user.

---

## Pages

| Route           | Description              |
|-----------------|--------------------------|
| /               | Home page                |
| /register       | User registration        |
| /login          | Login                    |
| /dashboard      | User dashboard           |
| /slots          | Live parking grid        |
| /book           | Book a slot              |
| /payment        | Simulated payment        |
| /admin          | Admin panel              |
| /api/slots      | JSON API for slot data   |

---

## Features

- Session-based auth (Flask sessions)
- Double-booking prevention
- Auto-expire bookings after end time
- Dynamic cost calculator (JS)
- Live slot grid with fetch() API refresh
- Flash messages (success/error)
- Responsive mobile design
- Admin panel: view bookings, add/remove slots, earnings
