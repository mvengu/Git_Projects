#!/usr/bin/env python3
"""
Troubleshooting Script for Community Management System
This script will check your installation and help identify issues
"""

import os
import sqlite3
import sys

def check_files():
    """Check if all required files exist"""
    print("🔍 Checking file structure...")
    
    required_files = [
        'app.py',
        'templates/base.html',
        'templates/generate_bills.html',
        'templates/bills.html',
        'community_management.db'
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - MISSING")
            missing_files.append(file)
    
    return missing_files

def check_database_schema():
    """Check database schema"""
    print("\n🔍 Checking database schema...")
    
    try:
        conn = sqlite3.connect('community_management.db')
        cursor = conn.cursor()
        
        # Check bills table structure
        cursor.execute("PRAGMA table_info(bills)")
        columns = cursor.fetchall()
        
        print("Bills table columns:")
        bill_type_exists = False
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
            if col[1] == 'bill_type':
                bill_type_exists = True
        
        if bill_type_exists:
            print("✅ bill_type column exists")
            
            # Check if there are any bills with bill_type
            cursor.execute("SELECT DISTINCT bill_type FROM bills")
            bill_types = cursor.fetchall()
            print(f"Existing bill types: {[bt[0] for bt in bill_types]}")
            
        else:
            print("❌ bill_type column missing - THIS IS THE PROBLEM!")
            return False
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False

def check_template_content():
    """Check if the generate_bills.html template has the correct content"""
    print("\n🔍 Checking template content...")
    
    try:
        with open('templates/generate_bills.html', 'r') as f:
            content = f.read()
        
        checks = [
            ('bill_type select field', 'name="bill_type"'),
            ('maintenance option', 'value="maintenance"'),
            ('water option', 'value="water"'),
            ('toggleBillTypeFields function', 'toggleBillTypeFields'),
        ]
        
        for check_name, check_string in checks:
            if check_string in content:
                print(f"✅ {check_name} found")
            else:
                print(f"❌ {check_name} missing")
                return False
        
        return True
        
    except FileNotFoundError:
        print("❌ templates/generate_bills.html not found")
        return False

def check_flask_app():
    """Check Flask app configuration"""
    print("\n🔍 Checking Flask app...")
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('bill_type in generate_bills route', "request.form['bill_type']"),
            ('separate bill generation logic', 'if bill_type == \'maintenance\''),
            ('water bill generation', 'elif bill_type == \'water\''),
        ]
        
        for check_name, check_string in checks:
            if check_string in content:
                print(f"✅ {check_name} found")
            else:
                print(f"❌ {check_name} missing")
                return False
        
        return True
        
    except FileNotFoundError:
        print("❌ app.py not found")
        return False

def suggest_fixes():
    """Suggest fixes based on the checks"""
    print("\n💡 SUGGESTED FIXES:")
    print("=" * 50)
    
    print("1. REPLACE YOUR templates/generate_bills.html file with the new template")
    print("2. Make sure your app.py has the updated generate_bills route")
    print("3. Ensure your database has the bill_type column")
    print("4. Clear browser cache (Ctrl+F5 or Ctrl+Shift+R)")
    print("5. Restart your Flask application")
    
    print("\n📋 STEP-BY-STEP FIX:")
    print("1. Stop your Flask app (Ctrl+C)")
    print("2. Replace templates/generate_bills.html with the new template")
    print("3. If bill_type column is missing, run the database fix script")
    print("4. Restart Flask app: python app.py")
    print("5. Clear browser cache and reload page")

def main():
    print("🔧 Community Management System Troubleshooting")
    print("=" * 60)
    
    # Check files
    missing_files = check_files()
    
    # Check database
    db_ok = check_database_schema()
    
    # Check template
    template_ok = check_template_content()
    
    # Check Flask app
    app_ok = check_flask_app()
    
    print("\n📊 SUMMARY:")
    print("=" * 30)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
    else:
        print("✅ All required files present")
    
    print(f"✅ Database schema: {'OK' if db_ok else 'NEEDS FIX'}")
    print(f"✅ Template content: {'OK' if template_ok else 'NEEDS FIX'}")
    print(f"✅ Flask app: {'OK' if app_ok else 'NEEDS FIX'}")
    
    if not all([db_ok, template_ok, app_ok]) or missing_files:
        suggest_fixes()
    else:
        print("\n🎉 Everything looks good!")
        print("If you still don't see the bill type dropdown:")
        print("1. Clear your browser cache (Ctrl+F5)")
        print("2. Restart your Flask application")
        print("3. Make sure you're on the correct URL: /bills/generate")

if __name__ == '__main__':
    main()