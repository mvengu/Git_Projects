#!/usr/bin/env python3
"""
Database Fix Script - Complete Database Recreation
This script will backup your existing data and recreate the database with the new schema
"""

import sqlite3
import json
from datetime import datetime

def backup_and_recreate_database():
    """Backup existing data and recreate database with new schema"""
    try:
        print("Starting database fix...")
        
        # Connect to existing database
        conn = sqlite3.connect('community_management.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Backup existing data
        print("Backing up existing data...")
        
        # Backup users
        users_data = []
        try:
            cursor.execute("SELECT * FROM users")
            users_data = [dict(row) for row in cursor.fetchall()]
            print(f"✓ Backed up {len(users_data)} users")
        except:
            print("No users table found")
        
        # Backup houses
        houses_data = []
        try:
            cursor.execute("SELECT * FROM houses")
            houses_data = [dict(row) for row in cursor.fetchall()]
            print(f"✓ Backed up {len(houses_data)} houses")
        except:
            print("No houses table found")
        
        # Backup meter readings
        meter_readings_data = []
        try:
            cursor.execute("SELECT * FROM meter_readings")
            meter_readings_data = [dict(row) for row in cursor.fetchall()]
            print(f"✓ Backed up {len(meter_readings_data)} meter readings")
        except:
            print("No meter readings table found")
        
        # Backup bills (old format)
        bills_data = []
        try:
            cursor.execute("SELECT * FROM bills")
            bills_data = [dict(row) for row in cursor.fetchall()]
            print(f"✓ Backed up {len(bills_data)} bills")
        except:
            print("No bills table found")
        
        # Backup payments
        payments_data = []
        try:
            cursor.execute("SELECT * FROM payments")
            payments_data = [dict(row) for row in cursor.fetchall()]
            print(f"✓ Backed up {len(payments_data)} payments")
        except:
            print("No payments table found")
        
        # Backup announcements
        announcements_data = []
        try:
            cursor.execute("SELECT * FROM announcements")
            announcements_data = [dict(row) for row in cursor.fetchall()]
            print(f"✓ Backed up {len(announcements_data)} announcements")
        except:
            print("No announcements table found")
        
        conn.close()
        
        # Save backup to file
        backup_data = {
            'users': users_data,
            'houses': houses_data,
            'meter_readings': meter_readings_data,
            'bills': bills_data,
            'payments': payments_data,
            'announcements': announcements_data,
            'backup_date': datetime.now().isoformat()
        }
        
        with open('database_backup.json', 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        print("✓ Saved backup to database_backup.json")
        
        # Recreate database with new schema
        print("\nRecreating database with new schema...")
        
        # Delete old database
        import os
        if os.path.exists('community_management.db'):
            os.rename('community_management.db', 'community_management_old.db')
            print("✓ Renamed old database to community_management_old.db")
        
        # Create new database
        conn = sqlite3.connect('community_management.db')
        cursor = conn.cursor()
        
        # Create tables with new schema
        print("Creating new tables...")
        
        # Users table
        cursor.execute('''
            CREATE TABLE users (
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
        cursor.execute('''
            CREATE TABLE houses (
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
        cursor.execute('''
            CREATE TABLE meter_readings (
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
        
        # Bills table with new schema
        cursor.execute('''
            CREATE TABLE bills (
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
        cursor.execute('''
            CREATE TABLE payments (
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
        cursor.execute('''
            CREATE TABLE announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                posted_by INTEGER NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                audience TEXT DEFAULT 'all_residents',
                FOREIGN KEY (posted_by) REFERENCES users (id)
            )
        ''')
        
        print("✓ Created new tables with updated schema")
        
        # Restore data
        print("\nRestoring data...")
        
        # Restore users
        for user in users_data:
            cursor.execute('''
                INSERT INTO users (id, email, password_hash, role, first_name, last_name, 
                                 phone_number, house_id, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user.get('id'), user.get('email'), user.get('password_hash'), 
                  user.get('role'), user.get('first_name'), user.get('last_name'),
                  user.get('phone_number'), user.get('house_id'), 
                  user.get('created_at'), user.get('last_login')))
        print(f"✓ Restored {len(users_data)} users")
        
        # Restore houses
        for house in houses_data:
            cursor.execute('''
                INSERT INTO houses (id, house_number, owner_name, contact_number, 
                                  email, address, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (house.get('id'), house.get('house_number'), house.get('owner_name'),
                  house.get('contact_number'), house.get('email'), house.get('address'),
                  house.get('status'), house.get('created_at')))
        print(f"✓ Restored {len(houses_data)} houses")
        
        # Restore meter readings
        for reading in meter_readings_data:
            cursor.execute('''
                INSERT INTO meter_readings (id, house_id, reading_date, current_reading,
                                          previous_reading, consumption, submitted_by,
                                          reading_type, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (reading.get('id'), reading.get('house_id'), reading.get('reading_date'),
                  reading.get('current_reading'), reading.get('previous_reading'),
                  reading.get('consumption'), reading.get('submitted_by'),
                  reading.get('reading_type'), reading.get('status'), reading.get('created_at')))
        print(f"✓ Restored {len(meter_readings_data)} meter readings")
        
        # Convert old bills to new format (as combined bills)
        for bill in bills_data:
            cursor.execute('''
                INSERT INTO bills (id, house_id, bill_type, billing_cycle, generation_date,
                                 due_date, fixed_maintenance, individual_water_consumption,
                                 individual_water_charge, water_maintenance_25_percent,
                                 waste_water_charge, repair_charge, previous_balance,
                                 total_amount_due, total_amount_paid, current_balance,
                                 status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bill.get('id'), bill.get('house_id'), 'combined', bill.get('billing_cycle'),
                  bill.get('generation_date'), bill.get('due_date'), bill.get('fixed_maintenance', 0),
                  bill.get('individual_water_consumption', 0), bill.get('individual_water_charge', 0),
                  bill.get('water_maintenance_25_percent', 0), bill.get('waste_water_charge', 0),
                  bill.get('repair_charge', 0), bill.get('previous_balance', 0),
                  bill.get('total_amount_due'), bill.get('total_amount_paid', 0),
                  bill.get('current_balance'), bill.get('status'), bill.get('created_at')))
        print(f"✓ Restored {len(bills_data)} bills (marked as 'combined' type)")
        
        # Restore payments
        for payment in payments_data:
            cursor.execute('''
                INSERT INTO payments (id, bill_id, house_id, payment_date, amount_paid,
                                    payment_method, transaction_id, recorded_by, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (payment.get('id'), payment.get('bill_id'), payment.get('house_id'),
                  payment.get('payment_date'), payment.get('amount_paid'),
                  payment.get('payment_method'), payment.get('transaction_id'),
                  payment.get('recorded_by'), payment.get('notes'), payment.get('created_at')))
        print(f"✓ Restored {len(payments_data)} payments")
        
        # Restore announcements
        for announcement in announcements_data:
            cursor.execute('''
                INSERT INTO announcements (id, title, content, posted_by, posted_at, audience)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (announcement.get('id'), announcement.get('title'), announcement.get('content'),
                  announcement.get('posted_by'), announcement.get('posted_at'),
                  announcement.get('audience')))
        print(f"✓ Restored {len(announcements_data)} announcements")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Database fix completed successfully!")
        print("\nSummary:")
        print("- Old database backed up to 'community_management_old.db'")
        print("- Data backed up to 'database_backup.json'")
        print("- New database created with updated schema")
        print("- All existing data restored")
        print("- Old bills converted to 'combined' type")
        print("\nYou can now use separate Maintenance and Water bill generation!")
        
        return True
        
    except Exception as e:
        print(f"Error during database fix: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Database Fix Script for Separate Bill Types")
    print("=" * 60)
    print("This will backup your data and recreate the database with the new schema.")
    print("Your existing data will be preserved.")
    
    response = input("\nDo you want to continue? (y/N): ")
    
    if response.lower() in ['y', 'yes']:
        if backup_and_recreate_database():
            print("\n🎉 Database fix completed! Please restart your application.")
            print("You should now see 'Maintenance Bills' and 'Water Bills' options.")
        else:
            print("\n❌ Database fix failed. Please check the errors above.")
            print("Your original database is still intact.")
    else:
        print("Database fix cancelled.")