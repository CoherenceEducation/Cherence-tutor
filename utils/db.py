import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date

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

def get_comprehensive_analytics(since_days: int = 30):
    """Get comprehensive analytics including engagement, topics, sentiment, and progress"""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Database not available - returning empty analytics")
        return {
            'engagement': {},
            'topics': {},
            'sentiment': {},
            'progress': {},
            'academic_focus': {},
            'curiosity': {}
        }
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Engagement Metrics
        engagement_stats = get_engagement_metrics(cursor, since_days)
        
        # Topic Analysis
        topic_stats = get_topic_analysis(cursor, since_days)
        
        # Sentiment Analysis
        sentiment_stats = get_sentiment_analysis(cursor, since_days)
        
        # Progress Indicators
        progress_stats = get_progress_indicators(cursor, since_days)
        
        # Academic Focus
        academic_focus = get_academic_focus(cursor, since_days)
        
        # Curiosity & Creativity
        curiosity_stats = get_curiosity_metrics(cursor, since_days)
        
        return {
            'engagement': engagement_stats,
            'topics': topic_stats,
            'sentiment': sentiment_stats,
            'progress': progress_stats,
            'academic_focus': academic_focus,
            'curiosity': curiosity_stats
        }
    except Error as e:
        print(f"Error fetching comprehensive analytics: {e}")
        import traceback
        traceback.print_exc()
        return {
            'engagement': {},
            'topics': {},
            'sentiment': {},
            'progress': {},
            'academic_focus': {},
            'curiosity': {}
        }
    finally:
        cursor.close()
        conn.close()

def get_engagement_metrics(cursor, since_days: int = 0):
    """Get engagement metrics: chats, avg messages/session, duration"""
    try:
        interval = _interval_clause(since_days)
        # First, check whether we have any non-null session_id rows
        cursor.execute(
            f"""
            SELECT COUNT(*) AS non_null_sessions
            FROM (
                SELECT session_id
                FROM conversation_history
                WHERE session_id IS NOT NULL{interval}
                GROUP BY session_id
            ) t
            """
        )
        row = cursor.fetchone()
        has_real_sessions = bool(row and row.get('non_null_sessions', 0))

        if has_real_sessions:
            # Use true sessions based on session_id
            cursor.execute(
                f"""
                SELECT COUNT(*) as total_chats
                FROM (
                    SELECT session_id
                    FROM conversation_history 
                    WHERE session_id IS NOT NULL{interval}
                    GROUP BY session_id
                ) s
                """
            )
            result = cursor.fetchone()
            total_chats = result['total_chats'] if result else 0

            cursor.execute(
                f"""
                SELECT AVG(session_messages) as avg_messages_per_session
                FROM (
                    SELECT session_id, COUNT(*) as session_messages
                    FROM conversation_history 
                    WHERE session_id IS NOT NULL{interval}
                    GROUP BY session_id
                ) as session_counts
                """
            )
            result = cursor.fetchone()
            avg_messages_per_session = float(result['avg_messages_per_session']) if result and result['avg_messages_per_session'] is not None else 0.0

            cursor.execute(
                f"""
                SELECT AVG(session_duration_minutes) as avg_session_duration
                FROM (
                    SELECT session_id, 
                           TIMESTAMPDIFF(MINUTE, MIN(created_at), MAX(created_at)) as session_duration_minutes
                    FROM conversation_history 
                    WHERE session_id IS NOT NULL{interval}
                    GROUP BY session_id
                    HAVING COUNT(*) > 1
                ) as session_durations
                """
            )
            result = cursor.fetchone()
            avg_session_duration = float(result['avg_session_duration']) if result and result['avg_session_duration'] is not None else 0.0
        else:
            # Fallback sessions approximation: per-student per-day conversations
            cursor.execute(
                f"""
                SELECT COUNT(*) AS total_chats
                FROM (
                    SELECT student_id, DATE(created_at) AS day_key
                    FROM conversation_history
                    WHERE 1=1{interval}
                    GROUP BY student_id, DATE(created_at)
                ) d
                """
            )
            result = cursor.fetchone()
            total_chats = result['total_chats'] if result else 0

            cursor.execute(
                f"""
                SELECT AVG(day_messages) as avg_messages_per_session
                FROM (
                    SELECT student_id, DATE(created_at) AS day_key, COUNT(*) AS day_messages
                    FROM conversation_history
                    WHERE 1=1{interval}
                    GROUP BY student_id, DATE(created_at)
                ) day_counts
                """
            )
            result = cursor.fetchone()
            avg_messages_per_session = result['avg_messages_per_session'] if result and result['avg_messages_per_session'] else 0

            cursor.execute(
                f"""
                SELECT AVG(day_duration_minutes) AS avg_session_duration
                FROM (
                    SELECT student_id, DATE(created_at) AS day_key,
                           TIMESTAMPDIFF(MINUTE, MIN(created_at), MAX(created_at)) AS day_duration_minutes
                    FROM conversation_history
                    WHERE 1=1{interval}
                    GROUP BY student_id, DATE(created_at)
                    HAVING COUNT(*) > 1
                ) day_durations
                """
            )
            result = cursor.fetchone()
            avg_session_duration = result['avg_session_duration'] if result and result['avg_session_duration'] else 0
        
        # Unique students with activity (7d fixed)
        cursor.execute(
            """
            SELECT COUNT(DISTINCT student_id) as unique_active_students
            FROM conversation_history 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            """
        )
        result = cursor.fetchone()
        unique_active_students = result['unique_active_students'] if result else 0
        
        return {
            'total_chats': int(total_chats),
            'avg_messages_per_session': round(float(avg_messages_per_session), 1),
            'avg_session_duration_minutes': round(float(avg_session_duration), 1),
            'unique_active_students_7d': int(unique_active_students)
        }
    except Error as e:
        print(f"Error fetching engagement metrics: {e}")
        return {
            'total_chats': 0,
            'avg_messages_per_session': 0,
            'avg_session_duration_minutes': 0,
            'unique_active_students_7d': 0
        }

def get_topic_analysis(cursor, since_days: int = 0):
    """Analyze topics and subjects most commonly asked by students"""
    try:
        interval = _interval_clause(since_days)
        cursor.execute(
            f"""
            SELECT message, student_id, created_at
            FROM conversation_history 
            WHERE role = 'student'{interval}
            ORDER BY created_at DESC
            """
        )
        messages = cursor.fetchall()
        
        # Simple topic extraction based on keywords
        topic_keywords = {
            'Mathematics': ['math', 'algebra', 'geometry', 'calculus', 'equation', 'solve', 'problem', 'number', 'formula'],
            'Science': ['science', 'physics', 'chemistry', 'biology', 'experiment', 'theory', 'hypothesis', 'molecule'],
            'English': ['english', 'grammar', 'writing', 'essay', 'poetry', 'literature', 'novel', 'story', 'paragraph'],
            'History': ['history', 'historical', 'war', 'ancient', 'century', 'empire', 'revolution', 'timeline'],
            'Technology': ['computer', 'programming', 'code', 'software', 'technology', 'digital', 'internet', 'app'],
            'Art': ['art', 'drawing', 'painting', 'creative', 'design', 'color', 'artist', 'gallery'],
            'Music': ['music', 'song', 'instrument', 'piano', 'guitar', 'melody', 'rhythm', 'concert'],
            'Health': ['health', 'exercise', 'nutrition', 'body', 'fitness', 'wellness', 'medical', 'disease']
        }
        
        topic_counts = {}
        topic_students = {}
        
        for message in messages:
            message_text = message['message'].lower()
            student_id = message['student_id']
            
            for topic, keywords in topic_keywords.items():
                if any(keyword in message_text for keyword in keywords):
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
                    if topic not in topic_students:
                        topic_students[topic] = set()
                    topic_students[topic].add(student_id)
        
        # Convert to list with unique student counts
        top_topics = []
        for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
            top_topics.append({
                'topic': topic,
                'total_questions': count,
                'unique_students': len(topic_students[topic])
            })
        
        return {
            'top_topics': top_topics[:10],  # Top 10 topics
            'total_topics_identified': len(topic_counts)
        }
    except Error as e:
        print(f"Error fetching topic analysis: {e}")
        return {
            'top_topics': [],
            'total_topics_identified': 0
        }


def to_date_key(val):
    try:
        if isinstance(val, datetime):
            return val.date().isoformat()
        if isinstance(val, date):
            return val.isoformat()
        return str(val)[:10]  # fallback
    except Exception:
        return ''

def get_sentiment_analysis(cursor, since_days: int = 0):
    """Analyze sentiment trends in student messages"""
    try:
        interval = _interval_clause(since_days)
        # Simple sentiment analysis based on keywords
        positive_keywords = ['good', 'great', 'awesome', 'amazing', 'love', 'like', 'excited', 'happy', 'wonderful', 'fantastic', 'excellent', 'perfect', 'thank', 'helpful', 'understand', 'clear', 'easy']
        negative_keywords = ['bad', 'terrible', 'awful', 'hate', 'difficult', 'confused', 'frustrated', 'angry', 'sad', 'worried', 'stressed', 'hard', 'complicated', "don't understand", 'stuck']
        
        cursor.execute(
            f"""
            SELECT message, created_at, student_id
            FROM conversation_history 
            WHERE role = 'student'{interval}
            ORDER BY created_at DESC
            """
        )
        messages = cursor.fetchall()
        
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        daily_sentiment = {}
        
        for message in messages:
            message_text = message['message'].lower()
            date_key = to_date_key(message['created_at'])

            
            positive_score = sum(1 for word in positive_keywords if word in message_text)
            negative_score = sum(1 for word in negative_keywords if word in message_text)
            
            if positive_score > negative_score:
                sentiment = 'positive'
            elif negative_score > positive_score:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            
            sentiment_counts[sentiment] += 1
            
            if date_key not in daily_sentiment:
                daily_sentiment[date_key] = {'positive': 0, 'negative': 0, 'neutral': 0}
            daily_sentiment[date_key][sentiment] += 1
        
        # Calculate percentages
        total_messages = sum(sentiment_counts.values())
        sentiment_percentages = {
            'positive': round((sentiment_counts['positive'] / total_messages * 100), 1) if total_messages > 0 else 0,
            'negative': round((sentiment_counts['negative'] / total_messages * 100), 1) if total_messages > 0 else 0,
            'neutral': round((sentiment_counts['neutral'] / total_messages * 100), 1) if total_messages > 0 else 0
        }
        
        return {
            'sentiment_distribution': sentiment_percentages,
            'total_analyzed': total_messages,
            'daily_trends': daily_sentiment
        }
    except Error as e:
        print(f"Error fetching sentiment analysis: {e}")
        return {
            'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0},
            'total_analyzed': 0,
            'daily_trends': {}
        }

def get_progress_indicators(cursor, since_days: int = 0):
    try:
        interval = _interval_clause(since_days)
        cursor.execute(
            f"""
            SELECT 
                student_id,
                DATE(created_at) as date,
                AVG(LENGTH(message)) as avg_message_length,
                COUNT(*) as daily_messages
            FROM conversation_history 
            WHERE role = 'student'{interval}
            GROUP BY student_id, DATE(created_at)
            ORDER BY student_id, date
            """
        )
        progress_data = cursor.fetchall()

        student_progress = {}
        for row in progress_data:
            student_id = row['student_id']
            if student_id not in student_progress:
                student_progress[student_id] = []
            # ensure ISO date
            date_iso = row['date'].isoformat() if hasattr(row['date'], 'isoformat') else str(row['date'])
            # 🔽 cast Decimals to float
            avg_len = float(row.get('avg_message_length') or 0)
            day_msgs = int(row.get('daily_messages') or 0)
            student_progress[student_id].append({
                'date': date_iso,
                'avg_length': avg_len,
                'message_count': day_msgs
            })

        # Compute growth using floats
        growing_students = 0
        for student_id, data in student_progress.items():
            if len(data) >= 3:
                recent_avg = sum(float(d['avg_length']) for d in data[-3:]) / 3.0
                early_avg  = sum(float(d['avg_length']) for d in data[:3])  / 3.0
                if early_avg > 0 and recent_avg > early_avg * 1.1:
                    growing_students += 1

        total = len(student_progress)
        growth_pct = round(100.0 * growing_students / float(total), 1) if total else 0.0

        return {
            'students_with_growth': growing_students,
            'total_tracked_students': total,
            'growth_percentage': growth_pct,
            'series_by_student': student_progress
        }
    except Exception as e:
        print(f"Error fetching progress indicators: {e}")
        return {
            'students_with_growth': 0,
            'total_tracked_students': 0,
            'growth_percentage': 0,
            'series_by_student': {}
        }

def get_academic_focus(cursor, since_days: int = 0):
    """Get top 5 subjects/topics asked about"""
    try:
        interval = _interval_clause(since_days)
        # Enhanced academic subject detection
        academic_subjects = {
            'Mathematics': ['math', 'algebra', 'geometry', 'calculus', 'trigonometry', 'statistics', 'equation', 'solve', 'problem', 'number', 'formula', 'theorem', 'proof'],
            'Science': ['science', 'physics', 'chemistry', 'biology', 'experiment', 'theory', 'hypothesis', 'molecule', 'atom', 'cell', 'organism', 'lab', 'research'],
            'English Literature': ['english', 'literature', 'novel', 'poetry', 'essay', 'writing', 'grammar', 'story', 'character', 'theme', 'author', 'book'],
            'History': ['history', 'historical', 'war', 'ancient', 'century', 'empire', 'revolution', 'timeline', 'civilization', 'culture', 'historical event'],
            'Computer Science': ['programming', 'code', 'computer', 'software', 'algorithm', 'python', 'javascript', 'coding', 'development', 'app', 'website'],
            'Art & Design': ['art', 'drawing', 'painting', 'creative', 'design', 'color', 'artist', 'gallery', 'sculpture', 'visual', 'aesthetic'],
            'Music': ['music', 'song', 'instrument', 'piano', 'guitar', 'melody', 'rhythm', 'concert', 'composer', 'musical', 'band'],
            'Health & PE': ['health', 'exercise', 'nutrition', 'body', 'fitness', 'wellness', 'medical', 'disease', 'sports', 'physical education']
        }
        
        cursor.execute(
            f"""
            SELECT message, student_id
            FROM conversation_history 
            WHERE role = 'student'{interval}
            """
        )
        messages = cursor.fetchall()
        
        subject_counts = {}
        subject_students = {}
        
        for message in messages:
            message_text = message['message'].lower()
            student_id = message['student_id']
            
            for subject, keywords in academic_subjects.items():
                if any(keyword in message_text for keyword in keywords):
                    subject_counts[subject] = subject_counts.get(subject, 0) + 1
                    if subject not in subject_students:
                        subject_students[subject] = set()
                    subject_students[subject].add(student_id)
        
        # Get top 5 subjects
        top_subjects = []
        for subject, count in sorted(subject_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            top_subjects.append({
                'subject': subject,
                'question_count': count,
                'unique_students': len(subject_students[subject])
            })
        
        return {
            'top_5_subjects': top_subjects,
            'total_subjects_identified': len(subject_counts)
        }
    except Error as e:
        print(f"Error fetching academic focus: {e}")
        return {
            'top_5_subjects': [],
            'total_subjects_identified': 0
        }

def get_curiosity_metrics(cursor, since_days: int = 0):
    """Analyze curiosity and creativity: % open-ended vs factual questions"""
    try:
        interval = _interval_clause(since_days)
        # Define patterns for different question types
        open_ended_patterns = ['why', 'how', 'what if', 'explain', 'describe', 'compare', 'analyze', 'evaluate', 'create', 'design', 'imagine', 'think about']
        factual_patterns = ['what is', 'when', 'where', 'who', 'define', 'list', 'name', 'identify', 'calculate', 'solve', 'find']
        
        # Do not require '?' so we capture conversational prompts too
        cursor.execute(
            f"""
            SELECT message
            FROM conversation_history 
            WHERE role = 'student'{interval}
            """
        )
        questions = cursor.fetchall()
        
        open_ended_count = 0
        factual_count = 0
        total_questions = len(questions)
        
        for question in questions:
            question_text = question['message'].lower()
            
            open_ended_score = sum(1 for pattern in open_ended_patterns if pattern in question_text)
            factual_score = sum(1 for pattern in factual_patterns if pattern in question_text)
            
            if open_ended_score > factual_score:
                open_ended_count += 1
            elif factual_score > open_ended_score:
                factual_count += 1
        
        return {
            'total_questions_analyzed': total_questions,
            'open_ended_percentage': round((open_ended_count / total_questions * 100), 1) if total_questions > 0 else 0,
            'factual_percentage': round((factual_count / total_questions * 100), 1) if total_questions > 0 else 0,
            'open_ended_count': open_ended_count,
            'factual_count': factual_count
        }
    except Error as e:
        print(f"Error fetching curiosity metrics: {e}")
        return {
            'total_questions_analyzed': 0,
            'open_ended_percentage': 0,
            'factual_percentage': 0,
            'open_ended_count': 0,
            'factual_count': 0
        }

def _interval_clause(since_days: int) -> str:
    try:
        days = int(since_days)
    except Exception:
        days = 0
    return "" if days <= 0 else f" AND created_at >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"



# Add these new functions to your utils/db.py file

def get_student_specific_analytics(student_id, since_days=30):
    """Get comprehensive analytics for a specific student"""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Database not available - returning empty analytics")
        return {}
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Basic student info
        cursor.execute("""
            SELECT * FROM students 
            WHERE student_id = %s
        """, (student_id,))
        student_info = cursor.fetchone()
        
        if not student_info:
            return {"error": "Student not found"}
        
        interval = _interval_clause(since_days)
        
        # Message count and activity
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT DATE(created_at)) as active_days,
                MIN(created_at) as first_message,
                MAX(created_at) as last_message
            FROM conversation_history 
            WHERE student_id = %s{interval}
        """, (student_id,))
        activity_stats = cursor.fetchone()
        
        # Session analysis
        cursor.execute(f"""
            SELECT 
                COUNT(DISTINCT session_id) as total_sessions,
                AVG(session_length) as avg_session_length
            FROM (
                SELECT 
                    session_id,
                    COUNT(*) as session_length
                FROM conversation_history 
                WHERE student_id = %s 
                AND session_id IS NOT NULL{interval}
                GROUP BY session_id
            ) sessions
        """, (student_id,))
        session_stats = cursor.fetchone()
        
        # Topic preferences
        cursor.execute(f"""
            SELECT message
            FROM conversation_history 
            WHERE student_id = %s 
            AND role = 'student'{interval}
        """, (student_id,))
        messages = cursor.fetchall()
        
        # Analyze topics
        topic_keywords = {
            'Mathematics': ['math', 'algebra', 'geometry', 'calculus', 'equation'],
            'Science': ['science', 'physics', 'chemistry', 'biology', 'experiment'],
            'English': ['english', 'grammar', 'writing', 'essay', 'literature'],
            'History': ['history', 'historical', 'war', 'ancient', 'century'],
            'Technology': ['computer', 'programming', 'code', 'software', 'technology'],
            'Art': ['art', 'drawing', 'painting', 'creative', 'design'],
            'Music': ['music', 'song', 'instrument', 'piano', 'guitar']
        }
        
        topic_counts = {}
        sentiment_scores = {'positive': 0, 'negative': 0, 'neutral': 0}
        question_types = {'open_ended': 0, 'factual': 0}
        
        positive_keywords = ['good', 'great', 'love', 'excited', 'thank', 'understand']
        negative_keywords = ['bad', 'difficult', 'confused', 'frustrated', "don't understand"]
        open_patterns = ['why', 'how', 'explain', 'describe', 'what if']
        factual_patterns = ['what is', 'when', 'where', 'who', 'define']
        
        for msg in messages:
            text = msg['message'].lower()
            
            # Topic analysis
            for topic, keywords in topic_keywords.items():
                if any(kw in text for kw in keywords):
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
            # Sentiment analysis
            pos_score = sum(1 for kw in positive_keywords if kw in text)
            neg_score = sum(1 for kw in negative_keywords if kw in text)
            if pos_score > neg_score:
                sentiment_scores['positive'] += 1
            elif neg_score > pos_score:
                sentiment_scores['negative'] += 1
            else:
                sentiment_scores['neutral'] += 1
            
            # Question type analysis
            if any(p in text for p in open_patterns):
                question_types['open_ended'] += 1
            elif any(p in text for p in factual_patterns):
                question_types['factual'] += 1
        
        # Message length progression
        cursor.execute(f"""
            SELECT 
                DATE(created_at) as date,
                AVG(LENGTH(message)) as avg_length,
                COUNT(*) as message_count
            FROM conversation_history 
            WHERE student_id = %s 
            AND role = 'student'{interval}
            GROUP BY DATE(created_at)
            ORDER BY date
        """, (student_id,))
        progression_data = cursor.fetchall()
        
        # Response time stats
        cursor.execute(f"""
            SELECT 
                AVG(response_time_ms) as avg_response_time,
                MIN(response_time_ms) as min_response_time,
                MAX(response_time_ms) as max_response_time
            FROM conversation_history 
            WHERE student_id = %s 
            AND response_time_ms IS NOT NULL{interval}
        """, (student_id,))
        response_stats = cursor.fetchone()
        
        # Calculate engagement score (0-100)
        engagement_score = 0
        if activity_stats:
            days_active = activity_stats.get('active_days', 0)
            total_msgs = activity_stats.get('total_messages', 0)
            
            # Score components
            activity_score = min((days_active / since_days) * 40, 40)  # Max 40 points
            volume_score = min((total_msgs / 50) * 30, 30)  # Max 30 points
            diversity_score = min(len(topic_counts) * 5, 30)  # Max 30 points
            
            engagement_score = round(activity_score + volume_score + diversity_score, 1)
        
        # Top 5 topics for this student
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Calculate sentiment percentages
        total_sentiment = sum(sentiment_scores.values())
        sentiment_percentages = {}
        if total_sentiment > 0:
            for key, val in sentiment_scores.items():
                sentiment_percentages[key] = round((val / total_sentiment) * 100, 1)
        
        # Calculate question type percentages
        total_questions = sum(question_types.values())
        question_percentages = {}
        if total_questions > 0:
            for key, val in question_types.items():
                question_percentages[key] = round((val / total_questions) * 100, 1)
        
        return {
            'student_info': student_info,
            'activity': {
                'total_messages': activity_stats.get('total_messages', 0) if activity_stats else 0,
                'active_days': activity_stats.get('active_days', 0) if activity_stats else 0,
                'first_message': activity_stats.get('first_message') if activity_stats else None,
                'last_message': activity_stats.get('last_message') if activity_stats else None,
                'total_sessions': session_stats.get('total_sessions', 0) if session_stats else 0,
                'avg_session_length': round(float(session_stats.get('avg_session_length', 0)), 1) if session_stats else 0
            },
            'engagement_score': engagement_score,
            'topics': {
                'top_topics': [{'topic': t[0], 'count': t[1]} for t in top_topics],
                'total_topics': len(topic_counts)
            },
            'sentiment': {
                'distribution': sentiment_percentages,
                'counts': sentiment_scores
            },
            'curiosity': {
                'question_types': question_percentages,
                'counts': question_types
            },
            'progression': [
                {
                    'date': row['date'].isoformat() if hasattr(row['date'], 'isoformat') else str(row['date']),
                    'avg_length': float(row.get('avg_length', 0)),
                    'message_count': int(row.get('message_count', 0))
                }
                for row in progression_data
            ],
            'response_times': {
                'avg_ms': round(float(response_stats.get('avg_response_time', 0)), 1) if response_stats else 0,
                'min_ms': round(float(response_stats.get('min_response_time', 0)), 1) if response_stats else 0,
                'max_ms': round(float(response_stats.get('max_response_time', 0)), 1) if response_stats else 0
            }
        }
        
    except Exception as e:
        print(f"Error fetching student-specific analytics: {e}")
        import traceback
        traceback.print_exc()
        return {}
    finally:
        cursor.close()
        conn.close()


def search_students(query):
    """Search students by name or email"""
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                s.*,
                COUNT(c.id) as message_count,
                MAX(c.created_at) as last_message_at
            FROM students s
            LEFT JOIN conversation_history c ON s.student_id = c.student_id
            WHERE s.name LIKE %s OR s.email LIKE %s
            GROUP BY s.student_id
            ORDER BY s.last_active DESC
            LIMIT 20
        """, (f"%{query}%", f"%{query}%"))
        return cursor.fetchall()
    except Error as e:
        print(f"Error searching students: {e}")
        return []
    finally:
        cursor.close()
        conn.close()