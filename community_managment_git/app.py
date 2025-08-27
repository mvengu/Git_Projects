#!/usr/bin/env python3
"""
Gated Community Management System
A Flask-based web application for managing maintenance fees, water charges, and communication
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
from datetime import datetime, timedelta
import os
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Database configuration
DATABASE = 'community_management.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with required tables"""
    conn = get_db_connection()
    
    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'resident',
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            house_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Houses table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS houses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house_number TEXT UNIQUE NOT NULL,
            owner_name TEXT NOT NULL,
            contact_number TEXT,
            email TEXT,
            address TEXT,
            status TEXT DEFAULT 'occupied',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Meter readings table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS meter_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house_id INTEGER NOT NULL,
            reading_date DATE NOT NULL,
            current_reading REAL NOT NULL,
            previous_reading REAL,
            consumption REAL,
            submitted_by INTEGER,
            reading_type TEXT DEFAULT 'L&T_individual',
            status TEXT DEFAULT 'verified',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (house_id) REFERENCES houses (id),
            FOREIGN KEY (submitted_by) REFERENCES users (id)
        )
    ''')
    
    # Bills table - Updated to support separate bill types
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house_id INTEGER NOT NULL,
            bill_type TEXT NOT NULL,
            billing_cycle TEXT NOT NULL,
            generation_date DATE NOT NULL,
            due_date DATE NOT NULL,
            fixed_maintenance REAL DEFAULT 0,
            individual_water_consumption REAL DEFAULT 0,
            individual_water_charge REAL DEFAULT 0,
            water_maintenance_25_percent REAL DEFAULT 0,
            waste_water_charge REAL DEFAULT 0,
            repair_charge REAL DEFAULT 0,
            previous_balance REAL DEFAULT 0,
            total_amount_due REAL NOT NULL,
            total_amount_paid REAL DEFAULT 0,
            current_balance REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (house_id) REFERENCES houses (id)
        )
    ''')
    
    # Payments table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            house_id INTEGER NOT NULL,
            payment_date DATE NOT NULL,
            amount_paid REAL NOT NULL,
            payment_method TEXT,
            transaction_id TEXT,
            recorded_by INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bill_id) REFERENCES bills (id),
            FOREIGN KEY (house_id) REFERENCES houses (id),
            FOREIGN KEY (recorded_by) REFERENCES users (id)
        )
    ''')
    
    # Announcements table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            posted_by INTEGER NOT NULL,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            audience TEXT DEFAULT 'all_residents',
            FOREIGN KEY (posted_by) REFERENCES users (id)
        )
    ''')
    
    # Create default admin user
    admin_email = 'admin@community.com'
    admin_password = 'admin123'  # Change this in production
    
    existing_admin = conn.execute('SELECT id FROM users WHERE email = ?', (admin_email,)).fetchone()
    if not existing_admin:
        password_hash = generate_password_hash(admin_password)
        conn.execute('''
            INSERT INTO users (email, password_hash, role, first_name, last_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (admin_email, password_hash, 'admin', 'Admin', 'User'))
        logger.info(f"Created default admin user: {admin_email} / {admin_password}")
    
    conn.commit()
    conn.close()

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        user = conn.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        
        if not user or user['role'] != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def resident_required(f):
    """Decorator to require resident or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_house_id():
    """Get the house ID for the current user"""
    if session.get('user_role') == 'admin':
        return None  # Admins can see all
    
    conn = get_db_connection()
    user = conn.execute('SELECT house_id FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return user['house_id'] if user else None

@app.route('/')
def index():
    """Home page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = f"{user['first_name']} {user['last_name']}"
            
            # Update last login
            conn = get_db_connection()
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            conn.close()
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard - role-based content"""
    conn = get_db_connection()
    user_house_id = get_user_house_id()
    
    if session.get('user_role') == 'admin':
        # Admin Dashboard - Full Statistics
        total_houses = conn.execute('SELECT COUNT(*) as count FROM houses').fetchone()['count']
        total_residents = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "resident"').fetchone()['count']
        overdue_bills = conn.execute('SELECT COUNT(*) as count FROM bills WHERE status = "overdue"').fetchone()['count']
        
        # Get total collections for current month
        current_month = datetime.now().strftime('%Y-%m')
        total_collections = conn.execute('''
            SELECT COALESCE(SUM(amount_paid), 0) as total 
            FROM payments 
            WHERE strftime('%Y-%m', payment_date) = ?
        ''', (current_month,)).fetchone()['total']
        
        # Get recent announcements
        recent_announcements = conn.execute('''
            SELECT a.*, u.first_name, u.last_name 
            FROM announcements a
            JOIN users u ON a.posted_by = u.id
            ORDER BY a.posted_at DESC 
            LIMIT 5
        ''').fetchall()
        
        conn.close()
        
        return render_template('dashboard.html', 
                             user_role='admin',
                             total_houses=total_houses,
                             total_residents=total_residents,
                             overdue_bills=overdue_bills,
                             total_collections=total_collections,
                             recent_announcements=recent_announcements)
    
    else:
        # Resident Dashboard - Personal Information Only
        if not user_house_id:
            flash('No house assigned to your account. Please contact administrator.', 'warning')
            recent_announcements = conn.execute('''
                SELECT a.*, u.first_name, u.last_name 
                FROM announcements a
                JOIN users u ON a.posted_by = u.id
                ORDER BY a.posted_at DESC 
                LIMIT 5
            ''').fetchall()
            conn.close()
            return render_template('dashboard.html', 
                                 user_role='resident',
                                 no_house=True,
                                 outstanding_balance=0,
                                 recent_announcements=recent_announcements,
                                 recent_bills=[],
                                 recent_payments=[],
                                 house_info={})
        
        # Get resident's house information
        house_info = conn.execute('SELECT * FROM houses WHERE id = ?', (user_house_id,)).fetchone()
        
        # Get resident's outstanding balance
        outstanding_balance = conn.execute('''
            SELECT COALESCE(SUM(current_balance), 0) as total 
            FROM bills 
            WHERE house_id = ? AND current_balance > 0
        ''', (user_house_id,)).fetchone()['total']
        
        # Get recent bills for this house
        recent_bills = conn.execute('''
            SELECT * FROM bills 
            WHERE house_id = ? 
            ORDER BY billing_cycle DESC 
            LIMIT 3
        ''', (user_house_id,)).fetchall()
        
        # Get recent payments for this house
        recent_payments = conn.execute('''
            SELECT p.*, b.billing_cycle, b.bill_type
            FROM payments p
            JOIN bills b ON p.bill_id = b.id
            WHERE p.house_id = ?
            ORDER BY p.payment_date DESC 
            LIMIT 3
        ''', (user_house_id,)).fetchall()
        
        # Get recent announcements
        recent_announcements = conn.execute('''
            SELECT a.*, u.first_name, u.last_name 
            FROM announcements a
            JOIN users u ON a.posted_by = u.id
            ORDER BY a.posted_at DESC 
            LIMIT 5
        ''').fetchall()
        
        conn.close()
        
        return render_template('dashboard.html', 
                             user_role='resident',
                             no_house=False,
                             house_info=house_info,
                             outstanding_balance=outstanding_balance,
                             recent_bills=recent_bills,
                             recent_payments=recent_payments,
                             recent_announcements=recent_announcements)

@app.route('/houses')
@login_required
def houses():
    """Houses page - role-based access"""
    conn = get_db_connection()
    user_house_id = get_user_house_id()
    
    if session.get('user_role') == 'admin':
        # Admin can see all houses
        houses_list = conn.execute('SELECT * FROM houses ORDER BY house_number').fetchall()
    else:
        # Residents can only see their own house
        if not user_house_id:
            flash('No house assigned to your account.', 'warning')
            houses_list = []
        else:
            houses_list = conn.execute('SELECT * FROM houses WHERE id = ?', (user_house_id,)).fetchall()
    
    conn.close()
    return render_template('houses.html', houses=houses_list, user_role=session.get('user_role'))

@app.route('/houses/add', methods=['GET', 'POST'])
@admin_required
def add_house():
    """Add new house"""
    if request.method == 'POST':
        house_number = request.form['house_number']
        owner_name = request.form['owner_name']
        contact_number = request.form['contact_number']
        email = request.form['email']
        address = request.form['address']
        
        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO houses (house_number, owner_name, contact_number, email, address)
                VALUES (?, ?, ?, ?, ?)
            ''', (house_number, owner_name, contact_number, email, address))
            conn.commit()
            flash('House added successfully!', 'success')
            return redirect(url_for('houses'))
        except sqlite3.IntegrityError:
            flash('House number already exists!', 'error')
        finally:
            conn.close()
    
    return render_template('add_house.html')

@app.route('/houses/<int:house_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_house(house_id):
    """Edit house details"""
    conn = get_db_connection()
    house = conn.execute('SELECT * FROM houses WHERE id = ?', (house_id,)).fetchone()
    
    if not house:
        flash('House not found!', 'error')
        return redirect(url_for('houses'))
    
    if request.method == 'POST':
        house_number = request.form['house_number']
        owner_name = request.form['owner_name']
        contact_number = request.form['contact_number']
        email = request.form['email']
        address = request.form['address']
        status = request.form['status']
        
        try:
            conn.execute('''
                UPDATE houses 
                SET house_number = ?, owner_name = ?, contact_number = ?, 
                    email = ?, address = ?, status = ?
                WHERE id = ?
            ''', (house_number, owner_name, contact_number, email, address, status, house_id))
            conn.commit()
            flash('House updated successfully!', 'success')
            return redirect(url_for('houses'))
        except sqlite3.IntegrityError:
            flash('House number already exists!', 'error')
        finally:
            conn.close()
    
    conn.close()
    return render_template('edit_house.html', house=house)

@app.route('/houses/<int:house_id>/view')
@login_required
def view_house(house_id):
    """View house details page"""
    conn = get_db_connection()
    
    # Check if user can access this house data
    user_house_id = get_user_house_id()
    if session.get('user_role') != 'admin' and user_house_id != house_id:
        flash('Access denied.', 'error')
        return redirect(url_for('houses'))
    
    # Get house details
    house = conn.execute('SELECT * FROM houses WHERE id = ?', (house_id,)).fetchone()
    if not house:
        flash('House not found!', 'error')
        conn.close()
        return redirect(url_for('houses'))
    
    # Get bills summary for this house
    bills_summary = conn.execute('''
        SELECT 
            COUNT(*) as total_bills,
            SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_bills,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_bills,
            SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue_bills,
            COALESCE(SUM(current_balance), 0) as total_outstanding,
            COALESCE(SUM(total_amount_paid), 0) as total_paid,
            COALESCE(SUM(total_amount_due), 0) as total_due
        FROM bills 
        WHERE house_id = ?
    ''', (house_id,)).fetchone()
    
    # Get payments summary
    payments_summary = conn.execute('''
        SELECT 
            COUNT(*) as total_payments,
            COALESCE(SUM(amount_paid), 0) as total_amount_paid,
            MAX(payment_date) as last_payment_date,
            MIN(payment_date) as first_payment_date
        FROM payments 
        WHERE house_id = ?
    ''', (house_id,)).fetchone()
    
    # Get meter readings summary
    meter_readings_summary = conn.execute('''
        SELECT 
            COUNT(*) as total_readings,
            COALESCE(SUM(consumption), 0) as total_consumption,
            COALESCE(AVG(consumption), 0) as avg_consumption,
            MAX(reading_date) as last_reading_date,
            COALESCE(MAX(current_reading), 0) as last_reading_value
        FROM meter_readings 
        WHERE house_id = ?
    ''', (house_id,)).fetchone()
    
    # Get recent bills (last 5)
    recent_bills = conn.execute('''
        SELECT bill_type, billing_cycle, generation_date, due_date,
               total_amount_due, current_balance, status
        FROM bills 
        WHERE house_id = ? 
        ORDER BY generation_date DESC 
        LIMIT 5
    ''', (house_id,)).fetchall()
    
    # Get recent payments (last 5)
    recent_payments = conn.execute('''
        SELECT p.payment_date, p.amount_paid, p.payment_method, 
               b.bill_type, b.billing_cycle, p.transaction_id
        FROM payments p
        JOIN bills b ON p.bill_id = b.id
        WHERE p.house_id = ? 
        ORDER BY p.payment_date DESC 
        LIMIT 5
    ''', (house_id,)).fetchall()
    
    # Get recent meter readings (last 5)
    recent_readings = conn.execute('''
        SELECT reading_date, current_reading, previous_reading, 
               consumption, status
        FROM meter_readings 
        WHERE house_id = ? 
        ORDER BY reading_date DESC 
        LIMIT 5
    ''', (house_id,)).fetchall()
    
    # Get user assigned to this house
    assigned_user = conn.execute('''
        SELECT first_name, last_name, email, phone_number, 
               last_login, created_at, role
        FROM users 
        WHERE house_id = ?
    ''', (house_id,)).fetchone()
    
    conn.close()
    
    return render_template('view_house.html', 
                         house=house,
                         bills_summary=bills_summary,
                         payments_summary=payments_summary,
                         meter_readings_summary=meter_readings_summary,
                         recent_bills=recent_bills,
                         recent_payments=recent_payments,
                         recent_readings=recent_readings,
                         assigned_user=assigned_user)

@app.route('/bills')
@login_required
def bills():
    """Bills page - role-based access with year filtering and pagination"""
    conn = get_db_connection()
    user_house_id = get_user_house_id()
    
    # Get filter parameters
    bill_type_filter = request.args.get('bill_type', 'all')
    year_filter = request.args.get('year', datetime.now().year)
    page = int(request.args.get('page', 1))
    per_page = 20  # Records per page
    offset = (page - 1) * per_page
    
    # Get available years for dropdown
    if session.get('user_role') == 'admin':
        years_query = '''
            SELECT DISTINCT strftime('%Y', generation_date) as year 
            FROM bills 
            ORDER BY year DESC
        '''
        available_years = conn.execute(years_query).fetchall()
    else:
        if user_house_id:
            years_query = '''
                SELECT DISTINCT strftime('%Y', generation_date) as year 
                FROM bills 
                WHERE house_id = ?
                ORDER BY year DESC
            '''
            available_years = conn.execute(years_query, (user_house_id,)).fetchall()
        else:
            available_years = []
    
    # Build main query with filters
    base_conditions = []
    params = []
    
    # Year filter
    if year_filter and year_filter != 'all':
        base_conditions.append("strftime('%Y', b.generation_date) = ?")
        params.append(str(year_filter))
    
    # Bill type filter
    if bill_type_filter != 'all':
        base_conditions.append("b.bill_type = ?")
        params.append(bill_type_filter)
    
    # Role-based access
    if session.get('user_role') != 'admin' and user_house_id:
        base_conditions.append("b.house_id = ?")
        params.append(user_house_id)
    elif session.get('user_role') != 'admin':
        # No house assigned, show empty
        bills_list = []
        total_count = 0
        conn.close()
        return render_template('bills.html', 
                             bills=bills_list, 
                             current_filter=bill_type_filter,
                             current_year=year_filter,
                             available_years=available_years,
                             user_role=session.get('user_role'),
                             pagination={'page': page, 'per_page': per_page, 'total': 0, 'pages': 0})
    
    # Build WHERE clause
    where_clause = "WHERE " + " AND ".join(base_conditions) if base_conditions else ""
    
    # Get total count for pagination
    count_query = f'''
        SELECT COUNT(*) as total
        FROM bills b
        JOIN houses h ON b.house_id = h.id
        {where_clause}
    '''
    total_count = conn.execute(count_query, params).fetchone()['total']
    total_pages = (total_count + per_page - 1) // per_page
    
    # Get paginated bills
    bills_query = f'''
        SELECT b.*, h.house_number, h.owner_name
        FROM bills b
        JOIN houses h ON b.house_id = h.id
        {where_clause}
        ORDER BY b.billing_cycle DESC, b.bill_type, h.house_number
        LIMIT ? OFFSET ?
    '''
    bills_list = conn.execute(bills_query, params + [per_page, offset]).fetchall()
    
    conn.close()
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_count,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < total_pages else None
    }
    
    return render_template('bills.html', 
                         bills=bills_list, 
                         current_filter=bill_type_filter,
                         current_year=year_filter,
                         available_years=available_years,
                         user_role=session.get('user_role'),
                         pagination=pagination)

@app.route('/bills/generate', methods=['GET', 'POST'])
@admin_required
def generate_bills():
    """Generate bills for a billing cycle"""
    if request.method == 'POST':
        billing_cycle = request.form['billing_cycle']
        bill_type = request.form['bill_type']
        
        conn = get_db_connection()
        
        # Check if bills already exist for this cycle and type
        existing_bills = conn.execute('''
            SELECT COUNT(*) as count FROM bills WHERE billing_cycle = ? AND bill_type = ?
        ''', (billing_cycle, bill_type)).fetchone()
        
        if existing_bills['count'] > 0:
            flash(f'{bill_type.title()} bills already generated for this billing cycle!', 'error')
            conn.close()
            return render_template('generate_bills.html')
        
        # Get all occupied houses
        houses = conn.execute('SELECT * FROM houses WHERE status = "occupied"').fetchall()
        
        if bill_type == 'maintenance':
            # Generate Maintenance Bills
            for house in houses:
                # Get previous maintenance balance
                previous_bill = conn.execute('''
                    SELECT current_balance FROM bills 
                    WHERE house_id = ? AND bill_type = 'maintenance'
                    ORDER BY billing_cycle DESC 
                    LIMIT 1
                ''', (house['id'],)).fetchone()
                
                previous_balance = previous_bill['current_balance'] if previous_bill else 0
                total_due = 3000 + previous_balance  # Fixed maintenance amount
                
                # Set due date (15 days from generation)
                due_date = (datetime.now() + timedelta(days=15)).date()
                
                # Insert maintenance bill
                conn.execute('''
                    INSERT INTO bills (
                        house_id, bill_type, billing_cycle, generation_date, due_date,
                        fixed_maintenance, previous_balance, total_amount_due, current_balance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (house['id'], 'maintenance', billing_cycle, datetime.now().date(), due_date,
                      3000, previous_balance, total_due, total_due))
            
            flash(f'Maintenance bills generated successfully for {len(houses)} houses!', 'success')
            
        elif bill_type == 'water':
            # Check if this is a preview request or final generation
            if 'preview_bills' in request.form:
                # Generate preview - don't save to database yet
                conn.close()
                return generate_water_bill_preview(request.form, houses)
            else:
                # Final generation with edited amounts
                generate_water_bills_final(request.form, billing_cycle, houses, conn)
                flash(f'Water bills generated successfully for {len(houses)} houses!', 'success')
        
        conn.commit()
        conn.close()
        return redirect(url_for('bills'))
    
    return render_template('generate_bills.html')

def generate_water_bill_preview(form_data, houses):
    """Generate water bill preview with calculated amounts"""
    billing_cycle = form_data['billing_cycle']
    lnt_main_meter = float(form_data['lnt_main_meter'])
    lnt_total_bill = float(form_data['lnt_total_bill'])
    waste_water_charge = float(form_data.get('waste_water_charge', 0))
    repair_charge = float(form_data.get('repair_charge', 0))
    
    conn = get_db_connection()
    
    # Get total water consumption and individual consumptions
    total_consumption = 0
    house_data = []
    
    for house in houses:
        # Get latest meter reading
        reading = conn.execute('''
            SELECT current_reading, previous_reading, consumption
            FROM meter_readings 
            WHERE house_id = ? 
            ORDER BY reading_date DESC 
            LIMIT 1
        ''', (house['id'],)).fetchone()
        
        consumption = reading['consumption'] if reading and reading['consumption'] else 0
        total_consumption += consumption
        
        # Get previous water balance
        previous_bill = conn.execute('''
            SELECT current_balance FROM bills 
            WHERE house_id = ? AND bill_type = 'water'
            ORDER BY billing_cycle DESC 
            LIMIT 1
        ''', (house['id'],)).fetchone()
        
        previous_balance = previous_bill['current_balance'] if previous_bill else 0
        
        house_data.append({
            'house': house,
            'consumption': consumption,
            'previous_balance': previous_balance
        })
    
    conn.close()
    
    # Calculate charges for each house using new formula: consumption * ₹70
    for house_info in house_data:
        consumption = house_info['consumption']
        
        # Calculate water charge: consumption * ₹70 per unit
        individual_water_charge = consumption * 70
        
        # Calculate other charges
        water_maintenance = individual_water_charge * 0.25
        house_waste_water = waste_water_charge / len(houses)
        house_repair_charge = repair_charge / len(houses)
        
        # Calculate total additional amount (excluding previous balance)
        additional_amount = individual_water_charge + water_maintenance + house_waste_water + house_repair_charge
        total_due = additional_amount + house_info['previous_balance']
        
        house_info.update({
            'water_charge': individual_water_charge,
            'water_maintenance': water_maintenance,
            'waste_water': house_waste_water,
            'repair_charge': house_repair_charge,
            'additional_amount': additional_amount,
            'total_due': total_due
        })
    
    return render_template('water_bill_preview.html', 
                         house_data=house_data,
                         billing_cycle=billing_cycle,
                         lnt_main_meter=lnt_main_meter,
                         lnt_total_bill=lnt_total_bill,
                         waste_water_charge=waste_water_charge,
                         repair_charge=repair_charge,
                         total_consumption=total_consumption)

@app.route('/debug/meter_readings/<int:house_id>')
@admin_required
def debug_meter_readings(house_id):
    """Debug route to check meter readings for a specific house"""
    conn = get_db_connection()
    
    # Get house info
    house = conn.execute('SELECT * FROM houses WHERE id = ?', (house_id,)).fetchone()
    
    # Get all meter readings for this house
    readings = conn.execute('''
        SELECT id, reading_date, current_reading, previous_reading, consumption, created_at
        FROM meter_readings 
        WHERE house_id = ? 
        ORDER BY reading_date DESC, id DESC
    ''', (house_id,)).fetchall()
    
    conn.close()
    
    if not house:
        return jsonify({'error': 'House not found'}), 404
    
    debug_info = {
        'house': {
            'id': house['id'],
            'house_number': house['house_number'],
            'owner_name': house['owner_name']
        },
        'readings': []
    }
    
    for i, reading in enumerate(readings):
        calculated_consumption = 0
        if i < len(readings) - 1:  # Not the last (oldest) reading
            calculated_consumption = reading['current_reading'] - readings[i + 1]['current_reading']
        
        debug_info['readings'].append({
            'id': reading['id'],
            'reading_date': reading['reading_date'],
            'current_reading': float(reading['current_reading']),
            'stored_previous_reading': float(reading['previous_reading']) if reading['previous_reading'] else None,
            'stored_consumption': float(reading['consumption']) if reading['consumption'] else None,
            'calculated_consumption': calculated_consumption,
            'created_at': reading['created_at']
        })
    
    return jsonify(debug_info, indent=2)

# Add this route to check all houses meter readings summary
@app.route('/debug/all_consumptions')
@admin_required  
def debug_all_consumptions():
    """Debug route to check consumption calculations for all houses"""
    conn = get_db_connection()
    
    houses = conn.execute('SELECT * FROM houses WHERE status = "occupied" ORDER BY house_number').fetchall()
    
    debug_data = []
    
    for house in houses:
        # Get last 3 readings
        readings = conn.execute('''
            SELECT reading_date, current_reading, previous_reading, consumption
            FROM meter_readings 
            WHERE house_id = ? 
            ORDER BY reading_date DESC, id DESC
            LIMIT 3
        ''', (house['id'],)).fetchall()
        
        consumption_calc = 0
        if len(readings) >= 2:
            consumption_calc = readings[0]['current_reading'] - readings[1]['current_reading']
        
        debug_data.append({
            'house_number': house['house_number'],
            'owner_name': house['owner_name'],
            'readings_count': len(readings),
            'latest_reading': float(readings[0]['current_reading']) if readings else 0,
            'stored_consumption': float(readings[0]['consumption']) if readings and readings[0]['consumption'] else None,
            'calculated_consumption': consumption_calc,
            'readings': [
                {
                    'date': r['reading_date'],
                    'current': float(r['current_reading']),
                    'stored_consumption': float(r['consumption']) if r['consumption'] else None
                } for r in readings
            ]
        })
    
    conn.close()
    
    return jsonify(debug_data)

def generate_water_bills_final(form_data, billing_cycle, houses, conn):
    """Generate final water bills with edited amounts"""
    # Get edited amounts from form
    for house in houses:
        house_id = house['id']
        
        # Get edited values from form
        water_charge = float(form_data.get(f'water_charge_{house_id}', 0))
        water_maintenance = float(form_data.get(f'water_maintenance_{house_id}', 0))
        waste_water = float(form_data.get(f'waste_water_{house_id}', 0))
        repair_charge = float(form_data.get(f'repair_charge_{house_id}', 0))
        consumption = float(form_data.get(f'consumption_{house_id}', 0))
        previous_balance = float(form_data.get(f'previous_balance_{house_id}', 0))
        
        # Calculate total
        total_due = water_charge + water_maintenance + waste_water + repair_charge + previous_balance
        
        # Set due date (15 days from generation)
        due_date = (datetime.now() + timedelta(days=15)).date()
        
        # Insert water bill
        conn.execute('''
            INSERT INTO bills (
                house_id, bill_type, billing_cycle, generation_date, due_date,
                individual_water_consumption, individual_water_charge, 
                water_maintenance_25_percent, waste_water_charge, repair_charge, 
                previous_balance, total_amount_due, current_balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (house_id, 'water', billing_cycle, datetime.now().date(), due_date,
              consumption, water_charge, water_maintenance,
              waste_water, repair_charge, previous_balance,
              total_due, total_due))

@app.route('/payments')
@login_required
def payments():
    """Payments page - role-based access with year filtering and pagination"""
    conn = get_db_connection()
    user_house_id = get_user_house_id()
    
    # Get filter parameters
    year_filter = request.args.get('year', datetime.now().year)
    page = int(request.args.get('page', 1))
    per_page = 20  # Records per page
    offset = (page - 1) * per_page
    
    # Get available years for dropdown
    if session.get('user_role') == 'admin':
        years_query = '''
            SELECT DISTINCT strftime('%Y', payment_date) as year 
            FROM payments 
            ORDER BY year DESC
        '''
        available_years = conn.execute(years_query).fetchall()
    else:
        if user_house_id:
            years_query = '''
                SELECT DISTINCT strftime('%Y', payment_date) as year 
                FROM payments 
                WHERE house_id = ?
                ORDER BY year DESC
            '''
            available_years = conn.execute(years_query, (user_house_id,)).fetchall()
        else:
            available_years = []
    
    # Build query conditions
    base_conditions = []
    params = []
    
    # Year filter
    if year_filter and year_filter != 'all':
        base_conditions.append("strftime('%Y', p.payment_date) = ?")
        params.append(str(year_filter))
    
    # Role-based access
    if session.get('user_role') != 'admin' and user_house_id:
        base_conditions.append("p.house_id = ?")
        params.append(user_house_id)
    elif session.get('user_role') != 'admin':
        # No house assigned, show empty
        payments_list = []
        total_count = 0
        conn.close()
        return render_template('payments.html', 
                             payments=payments_list,
                             current_year=year_filter,
                             available_years=available_years,
                             user_role=session.get('user_role'),
                             pagination={'page': page, 'per_page': per_page, 'total': 0, 'pages': 0})
    
    # Build WHERE clause
    where_clause = "WHERE " + " AND ".join(base_conditions) if base_conditions else ""
    
    # Get total count for pagination
    count_query = f'''
        SELECT COUNT(*) as total
        FROM payments p
        JOIN houses h ON p.house_id = h.id
        JOIN bills b ON p.bill_id = b.id
        {where_clause}
    '''
    total_count = conn.execute(count_query, params).fetchone()['total']
    total_pages = (total_count + per_page - 1) // per_page
    
    # Get paginated payments
    payments_query = f'''
        SELECT p.*, h.house_number, h.owner_name, b.billing_cycle, b.bill_type
        FROM payments p
        JOIN houses h ON p.house_id = h.id
        JOIN bills b ON p.bill_id = b.id
        {where_clause}
        ORDER BY p.payment_date DESC
        LIMIT ? OFFSET ?
    '''
    payments_list = conn.execute(payments_query, params + [per_page, offset]).fetchall()
    
    conn.close()
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_count,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < total_pages else None
    }
    
    return render_template('payments.html', 
                         payments=payments_list,
                         current_year=year_filter,
                         available_years=available_years,
                         user_role=session.get('user_role'),
                         pagination=pagination)

@app.route('/payments/record', methods=['GET', 'POST'])
@admin_required
def record_payment():
    """Record a new payment"""
    conn = get_db_connection()
    
    if request.method == 'POST':
        house_id = request.form['house_id']
        bill_id = request.form['bill_id']
        amount_paid = float(request.form['amount_paid'])
        payment_date = request.form['payment_date']
        payment_method = request.form['payment_method']
        transaction_id = request.form.get('transaction_id', '')
        notes = request.form.get('notes', '')
        
        # Record payment
        conn.execute('''
            INSERT INTO payments (
                bill_id, house_id, payment_date, amount_paid,
                payment_method, transaction_id, recorded_by, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bill_id, house_id, payment_date, amount_paid,
              payment_method, transaction_id, session['user_id'], notes))
        
        # Update bill payment status
        conn.execute('''
            UPDATE bills 
            SET total_amount_paid = total_amount_paid + ?,
                current_balance = total_amount_due - (total_amount_paid + ?),
                status = CASE 
                    WHEN (total_amount_paid + ?) >= total_amount_due THEN 'paid'
                    WHEN (total_amount_paid + ?) > 0 THEN 'partially_paid'
                    ELSE 'pending'
                END
            WHERE id = ?
        ''', (amount_paid, amount_paid, amount_paid, amount_paid, bill_id))
        
        conn.commit()
        conn.close()
        
        flash('Payment recorded successfully!', 'success')
        return redirect(url_for('payments'))
    
    # Get houses and their pending bills for the form
    houses = conn.execute('SELECT * FROM houses ORDER BY house_number').fetchall()
    conn.close()
    
    return render_template('record_payment.html', houses=houses)

@app.route('/api/house_bills/<int:house_id>')
@login_required
def get_house_bills(house_id):
    """API endpoint to get bills for a specific house"""
    conn = get_db_connection()
    bills = conn.execute('''
        SELECT id, bill_type, billing_cycle, total_amount_due, current_balance, status
        FROM bills 
        WHERE house_id = ? AND current_balance > 0
        ORDER BY bill_type, billing_cycle DESC
    ''', (house_id,)).fetchall()
    conn.close()
    
    return jsonify([dict(bill) for bill in bills])

@app.route('/api/house_last_reading/<int:house_id>')
@login_required
def get_house_last_reading(house_id):
    """API endpoint to get the last meter reading for a specific house"""
    conn = get_db_connection()
    
    # Get the most recent reading for this house
    last_reading = conn.execute('''
        SELECT current_reading, reading_date, consumption
        FROM meter_readings 
        WHERE house_id = ? 
        ORDER BY reading_date DESC, id DESC
        LIMIT 1
    ''', (house_id,)).fetchone()
    
    conn.close()
    
    if last_reading:
        return jsonify({
            'reading': float(last_reading['current_reading']),
            'date': last_reading['reading_date'],
            'consumption': float(last_reading['consumption']) if last_reading['consumption'] else 0
        })
    else:
        return jsonify({
            'reading': 0,
            'date': 'No previous readings',
            'consumption': 0
        })

@app.route('/meter_readings')
@login_required
def meter_readings():
    """Meter readings page - role-based access with year filtering and pagination"""
    conn = get_db_connection()
    user_house_id = get_user_house_id()
    
    # Get filter parameters
    year_filter = request.args.get('year', 'all')  # Default to 'all' instead of current year
    page = int(request.args.get('page', 1))
    per_page = 20  # Records per page
    offset = (page - 1) * per_page
    
    # Get available years for dropdown
    if session.get('user_role') == 'admin':
        years_query = '''
            SELECT DISTINCT strftime('%Y', reading_date) as year 
            FROM meter_readings 
            ORDER BY year DESC
        '''
        available_years = conn.execute(years_query).fetchall()
    else:
        if user_house_id:
            years_query = '''
                SELECT DISTINCT strftime('%Y', reading_date) as year 
                FROM meter_readings 
                WHERE house_id = ?
                ORDER BY year DESC
            '''
            available_years = conn.execute(years_query, (user_house_id,)).fetchall()
        else:
            available_years = []
    
    # Build query conditions
    base_conditions = []
    params = []
    
    # Year filter
    if year_filter and year_filter != 'all':
        base_conditions.append("strftime('%Y', mr.reading_date) = ?")
        params.append(str(year_filter))
    
    # Role-based access
    if session.get('user_role') != 'admin' and user_house_id:
        base_conditions.append("mr.house_id = ?")
        params.append(user_house_id)
    elif session.get('user_role') != 'admin':
        # No house assigned, show empty with helpful message
        readings = []
        total_count = 0
        conn.close()
        return render_template('meter_readings.html', 
                             readings=readings,
                             current_year=year_filter,
                             available_years=available_years,
                             user_role=session.get('user_role'),
                             pagination={'page': page, 'per_page': per_page, 'total': 0, 'pages': 0, 'has_prev': False, 'has_next': False})
    
    # Build WHERE clause
    where_clause = "WHERE " + " AND ".join(base_conditions) if base_conditions else ""
    
    # Get total count for pagination
    count_query = f'''
        SELECT COUNT(*) as total
        FROM meter_readings mr
        JOIN houses h ON mr.house_id = h.id
        {where_clause}
    '''
    total_count = conn.execute(count_query, params).fetchone()['total']
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0
    
    # Get paginated readings
    readings_query = f'''
        SELECT mr.*, h.house_number, h.owner_name
        FROM meter_readings mr
        JOIN houses h ON mr.house_id = h.id
        {where_clause}
        ORDER BY mr.reading_date DESC
        LIMIT ? OFFSET ?
    '''
    readings = conn.execute(readings_query, params + [per_page, offset]).fetchall()
    
    conn.close()
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_count,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < total_pages else None
    }
    
    return render_template('meter_readings.html', 
                         readings=readings,
                         current_year=year_filter,
                         available_years=available_years,
                         user_role=session.get('user_role'),
                         pagination=pagination)

@app.route('/meter_readings/add', methods=['GET', 'POST'])
@admin_required
def add_meter_reading():
    """Add meter reading"""
    conn = get_db_connection()
    
    if request.method == 'POST':
        house_id = request.form['house_id']
        reading_date = request.form['reading_date']
        current_reading = float(request.form['current_reading'])
        
        # Get previous reading
        previous_reading_row = conn.execute('''
            SELECT current_reading FROM meter_readings 
            WHERE house_id = ? 
            ORDER BY reading_date DESC 
            LIMIT 1
        ''', (house_id,)).fetchone()
        
        previous_reading = previous_reading_row['current_reading'] if previous_reading_row else 0
        consumption = current_reading - previous_reading
        
        conn.execute('''
            INSERT INTO meter_readings (
                house_id, reading_date, current_reading, 
                previous_reading, consumption, submitted_by
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (house_id, reading_date, current_reading, 
              previous_reading, consumption, session['user_id']))
        
        conn.commit()
        conn.close()
        
        flash('Meter reading added successfully!', 'success')
        return redirect(url_for('meter_readings'))
    
    houses = conn.execute('SELECT * FROM houses ORDER BY house_number').fetchall()
    conn.close()
    
    return render_template('add_meter_reading.html', houses=houses)

@app.route('/announcements')
@login_required
def announcements():
    """Announcements page"""
    conn = get_db_connection()
    
    announcements_list = conn.execute('''
        SELECT a.*, u.first_name, u.last_name
        FROM announcements a
        JOIN users u ON a.posted_by = u.id
        ORDER BY a.posted_at DESC
    ''').fetchall()
    
    conn.close()
    return render_template('announcements.html', announcements=announcements_list)

@app.route('/announcements/add', methods=['GET', 'POST'])
@admin_required
def add_announcement():
    """Add new announcement"""
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO announcements (title, content, posted_by)
            VALUES (?, ?, ?)
        ''', (title, content, session['user_id']))
        conn.commit()
        conn.close()
        
        flash('Announcement posted successfully!', 'success')
        return redirect(url_for('announcements'))
    
    return render_template('add_announcement.html')

@app.route('/users')
@admin_required
def users():
    """Users management page"""
    conn = get_db_connection()
    
    # Get all users with house information
    users_list = conn.execute('''
        SELECT u.*, h.house_number, h.owner_name
        FROM users u
        LEFT JOIN houses h ON u.house_id = h.id
        ORDER BY u.role DESC, u.first_name, u.last_name
    ''').fetchall()
    
    conn.close()
    return render_template('users.html', users=users_list)

@app.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    """Add new user"""
    conn = get_db_connection()
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone_number = request.form.get('phone_number')
        house_id = request.form.get('house_id') if request.form.get('house_id') else None
        
        # Check if email already exists
        existing_user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing_user:
            flash('Email address already exists!', 'error')
        else:
            try:
                password_hash = generate_password_hash(password)
                conn.execute('''
                    INSERT INTO users (email, password_hash, role, first_name, last_name, phone_number, house_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (email, password_hash, role, first_name, last_name, phone_number, house_id))
                conn.commit()
                flash('User added successfully!', 'success')
                conn.close()
                return redirect(url_for('users'))
            except Exception as e:
                flash(f'Error adding user: {str(e)}', 'error')
    
    # Get houses for dropdown
    houses = conn.execute('SELECT id, house_number, owner_name FROM houses ORDER BY house_number').fetchall()
    conn.close()
    
    return render_template('add_user.html', houses=houses)

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit user details"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        flash('User not found!', 'error')
        conn.close()
        return redirect(url_for('users'))
    
    if request.method == 'POST':
        email = request.form['email']
        role = request.form['role']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone_number = request.form.get('phone_number')
        house_id = request.form.get('house_id') if request.form.get('house_id') else None
        
        # Check if email already exists (excluding current user)
        existing_user = conn.execute('SELECT id FROM users WHERE email = ? AND id != ?', (email, user_id)).fetchone()
        if existing_user:
            flash('Email address already exists!', 'error')
        else:
            try:
                conn.execute('''
                    UPDATE users 
                    SET email = ?, role = ?, first_name = ?, last_name = ?, phone_number = ?, house_id = ?
                    WHERE id = ?
                ''', (email, role, first_name, last_name, phone_number, house_id, user_id))
                conn.commit()
                flash('User updated successfully!', 'success')
                conn.close()
                return redirect(url_for('users'))
            except Exception as e:
                flash(f'Error updating user: {str(e)}', 'error')
    
    # Get houses for dropdown
    houses = conn.execute('SELECT id, house_number, owner_name FROM houses ORDER BY house_number').fetchall()
    conn.close()
    
    return render_template('edit_user.html', user=user, houses=houses)

@app.route('/users/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """Reset user password"""
    new_password = request.form['new_password']
    
    if len(new_password) < 6:
        flash('Password must be at least 6 characters long!', 'error')
        return redirect(url_for('edit_user', user_id=user_id))
    
    conn = get_db_connection()
    try:
        password_hash = generate_password_hash(new_password)
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
        conn.commit()
        flash('Password reset successfully!', 'success')
    except Exception as e:
        flash(f'Error resetting password: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('edit_user', user_id=user_id))

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete user (soft delete by changing email)"""
    # Prevent deleting the current admin user
    if user_id == session['user_id']:
        flash('You cannot delete your own account!', 'error')
        return redirect(url_for('users'))
    
    conn = get_db_connection()
    try:
        # Check if user exists and get details
        user = conn.execute('SELECT email, first_name, last_name FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            flash('User not found!', 'error')
        else:
            # Soft delete by adding timestamp to email and marking as deleted
            deleted_email = f"deleted_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user['email']}"
            conn.execute('UPDATE users SET email = ? WHERE id = ?', (deleted_email, user_id))
            conn.commit()
            flash(f'User {user["first_name"]} {user["last_name"]} deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting user: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('users'))

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    conn = get_db_connection()
    user = conn.execute('''
        SELECT u.*, h.house_number, h.owner_name
        FROM users u
        LEFT JOIN houses h ON u.house_id = h.id
        WHERE u.id = ?
    ''', (session['user_id'],)).fetchone()
    conn.close()
    
    return render_template('profile.html', user=user)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    phone_number = request.form.get('phone_number')
    
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE users 
            SET first_name = ?, last_name = ?, phone_number = ?
            WHERE id = ?
        ''', (first_name, last_name, phone_number, session['user_id']))
        conn.commit()
        
        # Update session name
        session['user_name'] = f"{first_name} {last_name}"
        
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('profile'))

@app.route('/reports')
@login_required
def reports():
    """Reports page - role-based access with year filtering"""
    conn = get_db_connection()
    user_house_id = get_user_house_id()
    
    # Get filter parameters
    year_filter = request.args.get('year', datetime.now().year)
    report_type = request.args.get('report_type', 'summary')
    
    if session.get('user_role') == 'admin':
        # Admin Dashboard - Full Statistics
        
        # Get available years for dropdown
        years_query = '''
            SELECT DISTINCT year FROM (
                SELECT strftime('%Y', generation_date) as year FROM bills
                UNION
                SELECT strftime('%Y', payment_date) as year FROM payments
                UNION
                SELECT strftime('%Y', reading_date) as year FROM meter_readings
            ) ORDER BY year DESC
        '''
        available_years = conn.execute(years_query).fetchall()
        
        # Outstanding dues report (always current, not year-filtered)
        outstanding_dues = conn.execute('''
            SELECT h.house_number, h.owner_name, 
                   COALESCE(SUM(CASE WHEN b.bill_type = 'maintenance' THEN b.current_balance ELSE 0 END), 0) as maintenance_outstanding,
                   COALESCE(SUM(CASE WHEN b.bill_type = 'water' THEN b.current_balance ELSE 0 END), 0) as water_outstanding,
                   COALESCE(SUM(b.current_balance), 0) as total_outstanding
            FROM houses h
            LEFT JOIN bills b ON h.id = b.house_id AND b.current_balance > 0
            GROUP BY h.id, h.house_number, h.owner_name
            ORDER BY total_outstanding DESC
        ''').fetchall()
        
        # Monthly collections report (year-filtered)
        if year_filter and year_filter != 'all':
            monthly_collections = conn.execute('''
                SELECT strftime('%Y-%m', payment_date) as month,
                       SUM(amount_paid) as total_collected,
                       COUNT(*) as payment_count
                FROM payments
                WHERE strftime('%Y', payment_date) = ?
                GROUP BY strftime('%Y-%m', payment_date)
                ORDER BY month DESC
            ''', (str(year_filter),)).fetchall()
        else:
            monthly_collections = conn.execute('''
                SELECT strftime('%Y-%m', payment_date) as month,
                       SUM(amount_paid) as total_collected,
                       COUNT(*) as payment_count
                FROM payments
                GROUP BY strftime('%Y-%m', payment_date)
                ORDER BY month DESC
                LIMIT 24
            ''').fetchall()
        
        # FIXED: Water consumption report (year-filtered)
        if year_filter and year_filter != 'all':
            water_consumption = conn.execute('''
                SELECT h.house_number, 
                       COALESCE(SUM(mr.consumption), 0) as total_consumption,
                       COALESCE(AVG(mr.consumption), 0) as avg_consumption,
                       COUNT(mr.id) as reading_count,
                       MAX(mr.reading_date) as last_reading_date,
                       COALESCE(mr.consumption, 0) as consumption
                FROM houses h
                LEFT JOIN meter_readings mr ON mr.house_id = h.id 
                WHERE (mr.reading_date IS NULL OR strftime('%Y', mr.reading_date) = ?)
                GROUP BY h.id, h.house_number
                ORDER BY total_consumption DESC
            ''', (str(year_filter),)).fetchall()
        else:
            water_consumption = conn.execute('''
                SELECT h.house_number, 
                       COALESCE(SUM(mr.consumption), 0) as total_consumption,
                       COALESCE(AVG(mr.consumption), 0) as avg_consumption,
                       COUNT(mr.id) as reading_count,
                       MAX(mr.reading_date) as last_reading_date,
                       COALESCE(mr.consumption, 0) as consumption
                FROM houses h
                LEFT JOIN meter_readings mr ON mr.house_id = h.id 
                WHERE (mr.reading_date IS NULL OR mr.reading_date >= date('now', '-1 year'))
                GROUP BY h.id, h.house_number
                ORDER BY total_consumption DESC
            ''').fetchall()
        
        # Bill generation summary (year-filtered)
        if year_filter and year_filter != 'all':
            bill_summary = conn.execute('''
                SELECT b.bill_type,
                       COUNT(*) as bill_count,
                       SUM(b.total_amount_due) as total_amount,
                       SUM(b.total_amount_paid) as total_paid,
                       SUM(b.current_balance) as total_outstanding
                FROM bills b
                WHERE strftime('%Y', b.generation_date) = ?
                GROUP BY b.bill_type
            ''', (str(year_filter),)).fetchall()
        else:
            bill_summary = conn.execute('''
                SELECT b.bill_type,
                       COUNT(*) as bill_count,
                       SUM(b.total_amount_due) as total_amount,
                       SUM(b.total_amount_paid) as total_paid,
                       SUM(b.current_balance) as total_outstanding
                FROM bills b
                GROUP BY b.bill_type
            ''').fetchall()
        
        # Payment method analysis (year-filtered)
        if year_filter and year_filter != 'all':
            payment_methods = conn.execute('''
                SELECT COALESCE(payment_method, 'Not specified') as method,
                       COUNT(*) as count,
                       SUM(amount_paid) as total_amount
                FROM payments
                WHERE strftime('%Y', payment_date) = ?
                GROUP BY payment_method
                ORDER BY total_amount DESC
            ''', (str(year_filter),)).fetchall()
        else:
            payment_methods = conn.execute('''
                SELECT COALESCE(payment_method, 'Not specified') as method,
                       COUNT(*) as count,
                       SUM(amount_paid) as total_amount
                FROM payments
                GROUP BY payment_method
                ORDER BY total_amount DESC
            ''').fetchall()

        # Water Bill Analysis by Billing Cycle (Admin only)
        if year_filter and year_filter != 'all':
            water_bill_analysis = conn.execute('''
                SELECT 
                    b.billing_cycle,
                    COUNT(*) as house_count,
                    SUM(b.individual_water_charge) as total_water_charge,
                    SUM(b.water_maintenance_25_percent) as total_water_maintenance,
                    SUM(b.waste_water_charge) as total_waste_water_charge,
                    SUM(b.repair_charge) as total_repair_charge,
                    SUM(b.total_amount_due) as total_bill_amount,
                    AVG(b.individual_water_charge) as avg_water_charge_per_house,
                    AVG(b.waste_water_charge) as avg_waste_water_per_house,
                    AVG(b.repair_charge) as avg_repair_charge_per_house,
                    SUM(b.individual_water_consumption) as total_consumption,
                    -- Calculate percentages
                    CASE 
                        WHEN SUM(b.total_amount_due) > 0 THEN 
                            ROUND((SUM(b.waste_water_charge) * 100.0) / SUM(b.total_amount_due), 2)
                        ELSE 0 
                    END as waste_water_percentage,
                    CASE 
                        WHEN SUM(b.total_amount_due) > 0 THEN 
                            ROUND((SUM(b.repair_charge) * 100.0) / SUM(b.total_amount_due), 2)
                        ELSE 0 
                    END as repair_charge_percentage,
                    CASE 
                        WHEN SUM(b.total_amount_due) > 0 THEN 
                            ROUND((SUM(b.individual_water_charge) * 100.0) / SUM(b.total_amount_due), 2)
                        ELSE 0 
                    END as water_charge_percentage,
                    CASE 
                        WHEN SUM(b.total_amount_due) > 0 THEN 
                            ROUND((SUM(b.water_maintenance_25_percent) * 100.0) / SUM(b.total_amount_due), 2)
                        ELSE 0 
                    END as water_maintenance_percentage
                FROM bills b
                WHERE b.bill_type = 'water' 
                AND strftime('%Y', b.generation_date) = ?
                GROUP BY b.billing_cycle
                ORDER BY b.billing_cycle DESC
            ''', (str(year_filter),)).fetchall()
        else:
            water_bill_analysis = conn.execute('''
                SELECT 
                    b.billing_cycle,
                    COUNT(*) as house_count,
                    SUM(b.individual_water_charge) as total_water_charge,
                    SUM(b.water_maintenance_25_percent) as total_water_maintenance,
                    SUM(b.waste_water_charge) as total_waste_water_charge,
                    SUM(b.repair_charge) as total_repair_charge,
                    SUM(b.total_amount_due) as total_bill_amount,
                    AVG(b.individual_water_charge) as avg_water_charge_per_house,
                    AVG(b.waste_water_charge) as avg_waste_water_per_house,
                    AVG(b.repair_charge) as avg_repair_charge_per_house,
                    SUM(b.individual_water_consumption) as total_consumption,
                    -- Calculate percentages
                    CASE 
                        WHEN SUM(b.total_amount_due) > 0 THEN 
                            ROUND((SUM(b.waste_water_charge) * 100.0) / SUM(b.total_amount_due), 2)
                        ELSE 0 
                    END as waste_water_percentage,
                    CASE 
                        WHEN SUM(b.total_amount_due) > 0 THEN 
                            ROUND((SUM(b.repair_charge) * 100.0) / SUM(b.total_amount_due), 2)
                        ELSE 0 
                    END as repair_charge_percentage,
                    CASE 
                        WHEN SUM(b.total_amount_due) > 0 THEN 
                            ROUND((SUM(b.individual_water_charge) * 100.0) / SUM(b.total_amount_due), 2)
                        ELSE 0 
                    END as water_charge_percentage,
                    CASE 
                        WHEN SUM(b.total_amount_due) > 0 THEN 
                            ROUND((SUM(b.water_maintenance_25_percent) * 100.0) / SUM(b.total_amount_due), 2)
                        ELSE 0 
                    END as water_maintenance_percentage
                FROM bills b
                WHERE b.bill_type = 'water'
                GROUP BY b.billing_cycle
                ORDER BY b.billing_cycle DESC
                LIMIT 12
            ''').fetchall()
        
        conn.close()
        
        return render_template('reports.html', 
                             user_role='admin',
                             current_year=year_filter,
                             available_years=available_years,
                             report_type=report_type,
                             outstanding_dues=outstanding_dues,
                             monthly_collections=monthly_collections,
                             water_consumption=water_consumption,
                             bill_summary=bill_summary,
                             payment_methods=payment_methods,
                             water_bill_analysis=water_bill_analysis)
    
    else:
        # Residents get personal reports only
        if not user_house_id:
            flash('No house assigned to your account.', 'warning')
            conn.close()
            return render_template('reports.html', user_role='resident', no_house=True)
        
        # Get available years for this house
        years_query = '''
            SELECT DISTINCT year FROM (
                SELECT strftime('%Y', generation_date) as year FROM bills WHERE house_id = ?
                UNION
                SELECT strftime('%Y', payment_date) as year FROM payments WHERE house_id = ?
                UNION
                SELECT strftime('%Y', reading_date) as year FROM meter_readings WHERE house_id = ?
            ) ORDER BY year DESC
        '''
        available_years = conn.execute(years_query, (user_house_id, user_house_id, user_house_id)).fetchall()
        
        # Personal outstanding dues (always current)
        outstanding_dues = conn.execute('''
            SELECT h.house_number, h.owner_name, 
                   COALESCE(SUM(CASE WHEN b.bill_type = 'maintenance' THEN b.current_balance ELSE 0 END), 0) as maintenance_outstanding,
                   COALESCE(SUM(CASE WHEN b.bill_type = 'water' THEN b.current_balance ELSE 0 END), 0) as water_outstanding,
                   COALESCE(SUM(b.current_balance), 0) as total_outstanding
            FROM houses h
            LEFT JOIN bills b ON h.id = b.house_id AND b.current_balance > 0
            WHERE h.id = ?
            GROUP BY h.id, h.house_number, h.owner_name
        ''', (user_house_id,)).fetchall()
        
        # Personal payment history (year-filtered)
        if year_filter and year_filter != 'all':
            payment_history = conn.execute('''
                SELECT strftime('%Y-%m', payment_date) as month,
                       SUM(amount_paid) as total_paid,
                       COUNT(*) as payment_count
                FROM payments
                WHERE house_id = ? AND strftime('%Y', payment_date) = ?
                GROUP BY strftime('%Y-%m', payment_date)
                ORDER BY month DESC
            ''', (user_house_id, str(year_filter))).fetchall()
        else:
            payment_history = conn.execute('''
                SELECT strftime('%Y-%m', payment_date) as month,
                       SUM(amount_paid) as total_paid,
                       COUNT(*) as payment_count
                FROM payments
                WHERE house_id = ?
                GROUP BY strftime('%Y-%m', payment_date)
                ORDER BY month DESC
                LIMIT 24
            ''', (user_house_id,)).fetchall()
        
        # Personal water consumption (year-filtered) - FIXED
        if year_filter and year_filter != 'all':
            water_consumption = conn.execute('''
                SELECT h.house_number, mr.consumption, mr.reading_date,
                       strftime('%Y-%m', mr.reading_date) as month
                FROM meter_readings mr
                JOIN houses h ON mr.house_id = h.id
                WHERE mr.house_id = ? AND strftime('%Y', mr.reading_date) = ?
                ORDER BY mr.reading_date DESC
            ''', (user_house_id, str(year_filter))).fetchall()
        else:
            water_consumption = conn.execute('''
                SELECT h.house_number, mr.consumption, mr.reading_date,
                       strftime('%Y-%m', mr.reading_date) as month
                FROM meter_readings mr
                JOIN houses h ON mr.house_id = h.id
                WHERE mr.house_id = ?
                ORDER BY mr.reading_date DESC
                LIMIT 24
            ''', (user_house_id,)).fetchall()
        
        # Personal bill summary (year-filtered)
        if year_filter and year_filter != 'all':
            bill_summary = conn.execute('''
                SELECT b.bill_type,
                       COUNT(*) as bill_count,
                       SUM(b.total_amount_due) as total_amount,
                       SUM(b.total_amount_paid) as total_paid,
                       SUM(b.current_balance) as total_outstanding
                FROM bills b
                WHERE b.house_id = ? AND strftime('%Y', b.generation_date) = ?
                GROUP BY b.bill_type
            ''', (user_house_id, str(year_filter))).fetchall()
        else:
            bill_summary = conn.execute('''
                SELECT b.bill_type,
                       COUNT(*) as bill_count,
                       SUM(b.total_amount_due) as total_amount,
                       SUM(b.total_amount_paid) as total_paid,
                       SUM(b.current_balance) as total_outstanding
                FROM bills b
                WHERE b.house_id = ?
                GROUP BY b.bill_type
            ''', (user_house_id,)).fetchall()
        
        conn.close()
        
        return render_template('reports.html', 
                             user_role='resident',
                             current_year=year_filter,
                             available_years=available_years,
                             report_type=report_type,
                             outstanding_dues=outstanding_dues,
                             payment_history=payment_history,
                             water_consumption=water_consumption,
                             bill_summary=bill_summary)



@app.route('/profile/change_password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    if new_password != confirm_password:
        flash('New passwords do not match!', 'error')
        return redirect(url_for('profile'))
    
    if len(new_password) < 6:
        flash('Password must be at least 6 characters long!', 'error')
        return redirect(url_for('profile'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT password_hash FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if not check_password_hash(user['password_hash'], current_password):
        flash('Current password is incorrect!', 'error')
        conn.close()
        return redirect(url_for('profile'))
    
    try:
        password_hash = generate_password_hash(new_password)
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, session['user_id']))
        conn.commit()
        flash('Password changed successfully!', 'success')
    except Exception as e:
        flash(f'Error changing password: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('profile'))
    """Reports page"""
    conn = get_db_connection()
    
    # Outstanding dues report
    outstanding_dues = conn.execute('''
        SELECT h.house_number, h.owner_name, 
               COALESCE(SUM(CASE WHEN b.bill_type = 'maintenance' THEN b.current_balance ELSE 0 END), 0) as maintenance_outstanding,
               COALESCE(SUM(CASE WHEN b.bill_type = 'water' THEN b.current_balance ELSE 0 END), 0) as water_outstanding,
               COALESCE(SUM(b.current_balance), 0) as total_outstanding
        FROM houses h
        LEFT JOIN bills b ON h.id = b.house_id AND b.current_balance > 0
        GROUP BY h.id, h.house_number, h.owner_name
        ORDER BY total_outstanding DESC
    ''').fetchall()
    
    # Monthly collections report
    monthly_collections = conn.execute('''
        SELECT strftime('%Y-%m', payment_date) as month,
               SUM(amount_paid) as total_collected
        FROM payments
        GROUP BY strftime('%Y-%m', payment_date)
        ORDER BY month DESC
        LIMIT 12
    ''').fetchall()
    
    # Water consumption report
    water_consumption = conn.execute('''
        SELECT h.house_number, mr.consumption, mr.reading_date
        FROM meter_readings mr
        JOIN houses h ON mr.house_id = h.id
        WHERE mr.reading_date >= date('now', '-1 month')
        ORDER BY mr.reading_date DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('reports.html', 
                         outstanding_dues=outstanding_dues,
                         monthly_collections=monthly_collections,
                         water_consumption=water_consumption)

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Create static directory if it doesn't exist
    if not os.path.exists('static'):
        os.makedirs('static')
    
    print("Starting Gated Community Management System...")
    print("Default admin credentials: admin@community.com / admin123")
    print("Access the application at: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)