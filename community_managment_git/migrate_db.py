
#!/usr/bin/env python3
"""
Database Migration Script for Separate Bill Types
Run this script to update your existing database to support separate maintenance and water bills
"""

import sqlite3
import sys
from datetime import datetime

def migrate_database():
    """Migrate existing database to support separate bill types"""
    try:
        conn = sqlite3.connect('community_management.db')
        cursor = conn.cursor()
        
        print("Starting database migration...")
        
        # Check if bill_type column already exists
        cursor.execute("PRAGMA table_info(bills)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'bill_type' not in columns:
            print("Adding bill_type column to bills table...")
            
            # Add bill_type column
            cursor.execute('ALTER TABLE bills ADD COLUMN bill_type TEXT')
            
            # Update existing bills to have bill_type as 'combined'
            cursor.execute("UPDATE bills SET bill_type = 'combined'")
            
            print("✓ Added bill_type column and updated existing bills")
        else:
            print("✓ bill_type column already exists")
        
        # Create backup of existing data
        print("Creating backup of existing bills...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bills_backup AS 
            SELECT * FROM bills WHERE bill_type = 'combined'
        ''')
        
        conn.commit()
        print("✓ Database migration completed successfully!")
        
        print("\nMigration Summary:")
        print("- Added bill_type column to bills table")
        print("- Existing bills marked as 'combined' type")
        print("- Created backup table 'bills_backup'")
        print("\nYou can now generate separate maintenance and water bills!")
        
    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        conn.close()
    
    return True

def rollback_migration():
    """Rollback the migration if needed"""
    try:
        conn = sqlite3.connect('community_management.db')
        cursor = conn.cursor()
        
        print("Rolling back migration...")
        
        # Check if backup exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bills_backup'")
        if cursor.fetchone():
            # Restore from backup
            cursor.execute('DELETE FROM bills WHERE bill_type = "combined"')
            cursor.execute('INSERT INTO bills SELECT * FROM bills_backup')
            cursor.execute('DROP TABLE bills_backup')
            
            print("✓ Rollback completed successfully!")
        else:
            print("No backup found. Nothing to rollback.")
        
        conn.commit()
        
    except sqlite3.Error as e:
        print(f"Error during rollback: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Database Migration for Separate Bill Types")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        rollback_migration()
    else:
        print("This will modify your database to support separate maintenance and water bills.")
        response = input("Do you want to continue? (y/N): ")
        
        if response.lower() in ['y', 'yes']:
            if migrate_database():
                print("\n🎉 Migration completed! Please restart your application.")
            else:
                print("\n❌ Migration failed. Please check the errors above.")
        else:
            print("Migration cancelled.")
    
    print("\nTo rollback this migration, run: python migrate_db.py --rollback")