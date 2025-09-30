"""
Pollen Application Setup Script
==============================

This script helps you set up the Pollen application with either:
1. Demo mode (no database required)
2. PostgreSQL database mode

Usage:
    python setup.py
"""

import os
import subprocess
import sys
import re

def check_postgresql_installed():
    """Check if PostgreSQL is installed."""
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PostgreSQL found: {result.stdout.strip()}")
            return True
        else:
            print("❌ PostgreSQL not found")
            return False
    except FileNotFoundError:
        print("❌ PostgreSQL not found")
        return False

def check_postgresql_running():
    """Check if PostgreSQL is running."""
    try:
        result = subprocess.run(['pg_isready'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ PostgreSQL is running")
            return True
        else:
            print("❌ PostgreSQL is not running")
            return False
    except FileNotFoundError:
        print("❌ pg_isready not found")
        return False

def setup_database():
    """Set up the PostgreSQL database."""
    print("\n🔧 Setting up PostgreSQL database...")
    
    # Database configuration
    db_name = "pollen_store"
    db_user = "stefanstapinski"
    db_password = "pollen"
    
    # SQL commands to execute
    sql_commands = [
        f"CREATE USER {db_user} WITH PASSWORD '{db_password}';",
        f"CREATE DATABASE {db_name} OWNER {db_user};",
        f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};"
    ]
    
    print("📝 Creating database and user...")
    
    for i, sql in enumerate(sql_commands, 1):
        print(f"   Step {i}/3: {sql}")
        try:
            result = subprocess.run(['psql', '-d', 'postgres', '-c', sql], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"   ✅ Success")
            else:
                print(f"   ⚠️  Warning: {result.stderr.strip()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test connection
    print("\n🧪 Testing database connection...")
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            database=db_name,
            user=db_user,
            password=db_password
        )
        print("✅ Database connection successful!")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def update_env_file(use_database=True):
    """Update .env file for the chosen mode."""
    print(f"\n🔧 Updating .env file for {'database' if use_database else 'demo'} mode...")
    
    env_file = '.env'
    if not os.path.exists(env_file):
        print("❌ .env file not found!")
        return False
    
    # Read current content
    with open(env_file, 'r') as f:
        content = f.read()
    
    if use_database:
        # Enable database mode
        content = re.sub(r'pg_migration\s*=\s*[\'"]?False[\'"]?', 'pg_migration=True', content, flags=re.IGNORECASE)
        content = re.sub(r'server\s*=\s*[\'"]?False[\'"]?', 'server=True', content, flags=re.IGNORECASE)
        content = re.sub(r'demo_mode\s*=\s*[\'"]?True[\'"]?', 'demo_mode=False', content, flags=re.IGNORECASE)
    else:
        # Enable demo mode
        content = re.sub(r'pg_migration\s*=\s*[\'"]?True[\'"]?', 'pg_migration=False', content, flags=re.IGNORECASE)
        content = re.sub(r'server\s*=\s*[\'"]?True[\'"]?', 'server=False', content, flags=re.IGNORECASE)
        content = re.sub(r'demo_mode\s*=\s*[\'"]?False[\'"]?', 'demo_mode=True', content, flags=re.IGNORECASE)
        
        # Add demo mode settings if not present
        if 'use_demo_data=' not in content:
            content += '\nuse_demo_data=True\n'
    
    # Write updated content
    with open(env_file, 'w') as f:
        f.write(content)
    
    mode = "database" if use_database else "demo"
    print(f"✅ .env file updated for {mode} mode")
    return True

def test_application():
    """Test if the application works."""
    print("\n🧪 Testing application...")
    try:
        from pages.LiveBot import demo_bot
        print("✅ Application test successful!")
        return True
    except Exception as e:
        print(f"❌ Application test failed: {e}")
        return False

def main():
    """Main setup function."""
    print("🚀 Pollen Application Setup")
    print("=" * 40)
    
    print("\nChoose your setup option:")
    print("1. Demo Mode (no database required)")
    print("2. PostgreSQL Database Mode")
    print("3. Test current setup")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == '1':
        print("\n🎯 Setting up Demo Mode...")
        update_env_file(use_database=False)
        print("✅ Demo mode configured!")
        print("🚀 You can now run: streamlit run pollen.py")
        
    elif choice == '2':
        print("\n🗄️ Setting up PostgreSQL Database Mode...")
        
        if not check_postgresql_installed():
            print("\n📋 To install PostgreSQL:")
            print("   macOS: brew install postgresql")
            print("   Ubuntu: sudo apt-get install postgresql postgresql-contrib")
            print("   Windows: Download from https://www.postgresql.org/download/")
            return
        
        if not check_postgresql_running():
            print("\n📋 To start PostgreSQL:")
            print("   macOS: brew services start postgresql")
            print("   Ubuntu: sudo systemctl start postgresql")
            print("   Windows: Start PostgreSQL service")
            return
        
        if setup_database():
            update_env_file(use_database=True)
            print("\n🎉 PostgreSQL setup complete!")
            print("🚀 You can now run: streamlit run pollen.py")
        else:
            print("\n❌ Database setup failed. Falling back to demo mode...")
            update_env_file(use_database=False)
            print("✅ Demo mode configured as fallback!")
            
    elif choice == '3':
        print("\n🧪 Testing current setup...")
        if test_application():
            print("✅ Application is working correctly!")
        else:
            print("❌ Application has issues. Try running setup again.")
            
    else:
        print("❌ Invalid choice. Exiting...")
        return
    
    print("\n📋 Next Steps:")
    print("1. Run: streamlit run pollen.py")
    print("2. Open your browser to the URL shown")
    print("3. Start using your Pollen application!")

if __name__ == "__main__":
    main()
