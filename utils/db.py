import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime

def get_db_connection():
    """Create database connection with error handling"""
    try:
        # Use localhost with default settings if env vars not set
        host = os.getenv('DB_HOST', 'localhost')
        port = int(os.getenv('DB_PORT', 3306))
        user = os.getenv('DB_USER', 'root')
        password = os.getenv('DB_PASSWORD', '')
        database = os.getenv('DB_NAME', 'coherence_tutor')
        
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            auth_plugin='mysql_native_password',
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci',
            autocommit=False
        )
        return conn
    except Error as e:
        print(f"Database connection error: {e}")
        # Return None instead of raising to allow graceful fallback
        return None

def ensure_student_exists(student_id, email, name=None):
    """Create or update student record"""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Database not available - skipping student creation")
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO students (student_id, email, name) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                last_active = CURRENT_TIMESTAMP,
                name = COALESCE(%s, name)
        """, (student_id, email, name, name))
        conn.commit()
    except Error as e:
        print(f"Error ensuring student exists: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_conversation_history(student_id, limit=10):
    """Fetch recent conversation history for a student"""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Database not available - returning empty history")
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT role, message, created_at 
            FROM conversation_history 
            WHERE student_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (student_id, limit))
        rows = cursor.fetchall()
        rows.reverse()  # Return oldest first for context
        return rows
    except Error as e:
        print(f"Error fetching history: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def save_message(student_id, role, message, session_id=None, tokens_est=None, response_time_ms=None):
    """Save a conversation message"""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Database not available - skipping message save")
        return 1  # Return dummy ID for compatibility
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO conversation_history 
            (student_id, role, message, session_id, tokens_est, response_time_ms)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (student_id, role, message, session_id, tokens_est, response_time_ms))
        
        message_id = cursor.lastrowid
        
        # Update student message count
        cursor.execute("""
            UPDATE students 
            SET total_messages = total_messages + 1,
                last_active = CURRENT_TIMESTAMP
            WHERE student_id = %s
        """, (student_id,))
        
        conn.commit()
        return message_id
    except Error as e:
        print(f"Error saving message: {e}")
        conn.rollback()
        return 1  # Return dummy ID for compatibility
    finally:
        cursor.close()
        conn.close()

def flag_content(student_id, message_id, message_text, reason):
    """Flag content for review"""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Database not available - skipping content flagging")
        return
    cursor = conn.cursor()
    try:
        print(f"🚩 Flagging content for student {student_id}: {reason}")
        
        cursor.execute("""
            INSERT INTO flagged_content (student_id, message_id, message_text, reason)
            VALUES (%s, %s, %s, %s)
        """, (student_id, message_id, message_text, reason))
        
        conn.commit()
        
        print(f"✅ Content flagged successfully (ID: {cursor.lastrowid})")
        
        # Send alert email to admin (optional - implement if needed)
        if "Critical safety concern" in reason:
            send_alert_email(student_id, message_text, reason)
        
    except Error as e:
        print(f"❌ Error flagging content: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_flagged_content(limit=100, reviewed=None):
    """Get flagged content for admin review"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if reviewed is None:
            cursor.execute("""
                SELECT f.*, s.name, s.email 
                FROM flagged_content f
                LEFT JOIN students s ON f.student_id = s.student_id
                ORDER BY f.flagged_at DESC
                LIMIT %s
            """, (limit,))
        else:
            cursor.execute("""
                SELECT f.*, s.name, s.email 
                FROM flagged_content f
                LEFT JOIN students s ON f.student_id = s.student_id
                WHERE f.reviewed = %s
                ORDER BY f.flagged_at DESC
                LIMIT %s
            """, (reviewed, limit))
        return cursor.fetchall()
    except Error as e:
        print(f"Error fetching flagged content: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def mark_flagged_reviewed(flagged_id, reviewed_by):
    """Mark flagged content as reviewed"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE flagged_content 
            SET reviewed = TRUE,
                reviewed_by = %s,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (reviewed_by, flagged_id))
        conn.commit()
    except Error as e:
        print(f"Error marking content as reviewed: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_all_conversations(limit=100, offset=0):
    """Admin: Get all recent conversations"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT c.*, s.name, s.email 
            FROM conversation_history c
            JOIN students s ON c.student_id = s.student_id
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return cursor.fetchall()
    except Error as e:
        print(f"Error fetching all conversations: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_student_stats():
    """Get statistics for admin dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Total students
        cursor.execute("SELECT COUNT(*) as count FROM students")
        total_students = cursor.fetchone()['count']
        
        # Total messages
        cursor.execute("SELECT COUNT(*) as count FROM conversation_history")
        total_messages = cursor.fetchone()['count']
        
        # Active today
        cursor.execute("""
            SELECT COUNT(DISTINCT student_id) as count 
            FROM conversation_history 
            WHERE DATE(created_at) = CURDATE()
        """)
        active_today = cursor.fetchone()['count']
        
        # Active this week
        cursor.execute("""
            SELECT COUNT(DISTINCT student_id) as count 
            FROM conversation_history 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        """)
        active_week = cursor.fetchone()['count']
        
        # Flagged content count (unreviewed)
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM flagged_content 
            WHERE reviewed = FALSE
        """)
        flagged_count = cursor.fetchone()['count']
        
        # Average messages per student
        cursor.execute("""
            SELECT AVG(total_messages) as avg_msgs 
            FROM students 
            WHERE total_messages > 0
        """)
        avg_messages = cursor.fetchone()['avg_msgs'] or 0
        
        return {
            'total_students': total_students,
            'total_messages': total_messages,
            'active_today': active_today,
            'active_week': active_week,
            'flagged_count': flagged_count,
            'avg_messages_per_student': round(avg_messages, 1)
        }
    except Error as e:
        print(f"Error fetching stats: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()

def get_student_info(student_id):
    """Get detailed student information"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM students 
            WHERE student_id = %s
        """, (student_id,))
        return cursor.fetchone()
    except Error as e:
        print(f"Error fetching student info: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def search_conversations(query, limit=50):
    """Search conversations by keyword"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT c.*, s.name, s.email 
            FROM conversation_history c
            JOIN students s ON c.student_id = s.student_id
            WHERE c.message LIKE %s
            ORDER BY c.created_at DESC
            LIMIT %s
        """, (f"%{query}%", limit))
        return cursor.fetchall()
    except Error as e:
        print(f"Error searching conversations: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def send_alert_email(student_id, message_text, reason):
    """Send alert email for critical safety concerns (implement with SendGrid/SES)"""
    # This is a placeholder - implement with your email service
    try:
        print(f"🚨 CRITICAL ALERT: Student {student_id} - {reason}")
        print(f"Message: {message_text[:100]}")
        
        # TODO: Implement actual email sending
        # Example with SendGrid:
        # from sendgrid import SendGridAPIClient
        # from sendgrid.helpers.mail import Mail
        # 
        # message = Mail(
        #     from_email='alerts@coherenceeducation.com',
        #     to_emails='admin@coherenceeducation.com',
        #     subject=f'URGENT: Safety Alert - Student {student_id}',
        #     html_content=f'<p>Critical safety concern detected...</p>'
        # )
        # sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        # response = sg.send(message)
        
    except Exception as e:
        print(f"Error sending alert email: {e}")

def cleanup_old_sessions(days=30):
    """Clean up old conversation history (optional maintenance task)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM conversation_history
            WHERE created_at < DATE_SUB(CURDATE(), INTERVAL %s DAY)
        """, (days,))
        deleted = cursor.rowcount
        conn.commit()
        print(f"Cleaned up {deleted} old messages")
        return deleted
    except Error as e:
        print(f"Error cleaning up old sessions: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()

def check_rate_limit_mysql(student_id, window_seconds=60, max_requests=5):
    """
    MySQL-based rate limiting that persists across app restarts
    Returns: (is_allowed: bool, remaining_requests: int)
    """
    conn = get_db_connection()
    if not conn:
        print("⚠️ Database not available - allowing request")
        return True, max_requests
    
    cursor = conn.cursor()
    try:
        # Clean up old rate limit entries
        cursor.execute("""
            DELETE FROM rate_limits 
            WHERE created_at < DATE_SUB(NOW(), INTERVAL %s SECOND)
        """, (window_seconds,))
        
        # Count current requests in window
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM rate_limits 
            WHERE student_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL %s SECOND)
        """, (student_id, window_seconds))
        
        current_count = cursor.fetchone()[0]
        
        if current_count >= max_requests:
            conn.commit()
            return False, 0
        
        # Add current request
        cursor.execute("""
            INSERT INTO rate_limits (student_id, created_at) 
            VALUES (%s, NOW())
        """, (student_id,))
        
        conn.commit()
        remaining = max_requests - current_count - 1
        return True, remaining
        
    except Error as e:
        print(f"Error checking rate limit: {e}")
        conn.rollback()
        return True, max_requests  # Allow on error
    finally:
        cursor.close()
        conn.close()

def create_rate_limits_table():
    """Create rate_limits table if it doesn't exist"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_student_time (student_id, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
        print("✅ Rate limits table created/verified")
        return True
    except Error as e:
        print(f"Error creating rate_limits table: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def create_admins_table():
    """Create admins table if it doesn't exist"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                admin_id VARCHAR(255) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                name VARCHAR(255),
                role ENUM('admin', 'super_admin') DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                INDEX idx_email (email),
                INDEX idx_admin_id (admin_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
        print("✅ Admins table created/verified")
        return True
    except Error as e:
        print(f"Error creating admins table: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def ensure_admin_exists(admin_id, email, name=None):
    """Create or update admin record"""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Database not available - skipping admin creation")
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO admins (admin_id, email, name) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                last_active = CURRENT_TIMESTAMP,
                name = COALESCE(%s, name),
                is_active = TRUE
        """, (admin_id, email, name, name))
        conn.commit()
    except Error as e:
        print(f"Error ensuring admin exists: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_admin_info(admin_id):
    """Get admin information"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM admins 
            WHERE admin_id = %s AND is_active = TRUE
        """, (admin_id,))
        return cursor.fetchone()
    except Error as e:
        print(f"Error fetching admin info: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_all_students(limit=100, offset=0):
    """Get all students with their details"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                s.*,
                COUNT(c.id) as total_messages,
                MAX(c.created_at) as last_message_at
            FROM students s
            LEFT JOIN conversation_history c ON s.student_id = c.student_id
            GROUP BY s.student_id
            ORDER BY s.last_active DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return cursor.fetchall()
    except Error as e:
        print(f"Error fetching all students: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_student_conversations(student_id, limit=50):
    """Get conversations for a specific student"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT c.*, s.name, s.email 
            FROM conversation_history c
            JOIN students s ON c.student_id = s.student_id
            WHERE c.student_id = %s
            ORDER BY c.created_at DESC
            LIMIT %s
        """, (student_id, limit))
        return cursor.fetchall()
    except Error as e:
        print(f"Error fetching student conversations: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_platform_analytics():
    """Get detailed platform analytics"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Basic stats
        cursor.execute("SELECT COUNT(*) as total_students FROM students")
        total_students = cursor.fetchone()['total_students']
        
        cursor.execute("SELECT COUNT(*) as total_messages FROM conversation_history")
        total_messages = cursor.fetchone()['total_messages']
        
        # Daily activity
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as messages
            FROM conversation_history 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)
        daily_activity = cursor.fetchall()
        
        # Top active students
        cursor.execute("""
            SELECT s.name, s.email, COUNT(c.id) as message_count
            FROM students s
            JOIN conversation_history c ON s.student_id = c.student_id
            WHERE c.created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY s.student_id
            ORDER BY message_count DESC
            LIMIT 10
        """)
        top_students = cursor.fetchall()
        
        # Flagged content stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_flagged,
                COUNT(CASE WHEN reviewed = FALSE THEN 1 END) as unreviewed,
                COUNT(CASE WHEN reviewed = TRUE THEN 1 END) as reviewed
            FROM flagged_content
        """)
        flagged_stats = cursor.fetchone()
        
        # Response time analytics
        cursor.execute("""
            SELECT 
                AVG(response_time_ms) as avg_response_time,
                MIN(response_time_ms) as min_response_time,
                MAX(response_time_ms) as max_response_time
            FROM conversation_history 
            WHERE response_time_ms IS NOT NULL
            AND created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        """)
        response_stats = cursor.fetchone()
        
        return {
            'total_students': total_students,
            'total_messages': total_messages,
            'daily_activity': daily_activity,
            'top_students': top_students,
            'flagged_stats': flagged_stats,
            'response_stats': response_stats
        }
    except Error as e:
        print(f"Error fetching platform analytics: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()