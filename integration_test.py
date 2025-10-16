#!/usr/bin/env python3
"""
LearnWorlds Integration Test Script
Verifies that all components are ready for deployment
"""

import os
import sys
from dotenv import load_dotenv

def test_environment():
    """Test environment variables"""
    print("🔧 Testing Environment Variables...")
    load_dotenv()
    
    required_vars = [
        'DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME',
        'JWT_SECRET', 'FLASK_SECRET_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ All required environment variables are set")
        return True

def test_database():
    """Test database connection"""
    print("\n🗄️ Testing Database Connection...")
    try:
        from utils.db import get_db_connection
        conn = get_db_connection()
        if conn:
            print("✅ Database connection successful")
            conn.close()
            return True
        else:
            print("❌ Database connection failed")
            return False
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_imports():
    """Test all required imports"""
    print("\n📦 Testing Imports...")
    try:
        from utils.db import get_comprehensive_analytics
        from utils.gemini_client import get_tutor_response, check_content_safety
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_admin_emails():
    """Test admin email configuration"""
    print("\n👥 Testing Admin Email Configuration...")
    admin_emails = os.getenv('ADMIN_EMAILS', '')
    if admin_emails:
        emails = [e.strip() for e in admin_emails.split(',') if e.strip()]
        print(f"✅ Admin emails configured: {len(emails)} emails")
        for email in emails:
            print(f"   - {email}")
        return True
    else:
        print("❌ No admin emails configured")
        return False

def test_integration_files():
    """Test integration files exist and are valid"""
    print("\n📄 Testing Integration Files...")
    
    files_to_check = [
        'learnworlds-integration.html',
        'admin-learnworlds-integration.html',
        'static/admin.html',
        'app.py'
    ]
    
    all_exist = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests"""
    print("🚀 LearnWorlds Integration Test")
    print("=" * 50)
    
    tests = [
        test_environment,
        test_database,
        test_imports,
        test_admin_emails,
        test_integration_files
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    
    if all(results):
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ Your system is ready for LearnWorlds integration!")
        print("\n📋 Next Steps:")
        print("1. Deploy to Vercel: vercel --prod")
        print("2. Add learnworlds-integration.html to LearnWorlds")
        print("3. Create admin page with admin-learnworlds-integration.html")
        print("4. Test with admin email accounts")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
