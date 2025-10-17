import os
import jwt
import time
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, render_template, render_template_string
from flask_cors import CORS
from collections import defaultdict

# Import utilities
from utils.db import (
    ensure_student_exists, 
    get_conversation_history, 
    save_message,
    flag_content,
    get_all_conversations,
    get_student_stats,
    check_rate_limit_mysql,
    create_rate_limits_table,
    ensure_admin_exists,
    get_admin_info,
    get_all_students,
    get_student_conversations,
    get_platform_analytics,
    get_comprehensive_analytics,
    create_admins_table
)
from utils.gemini_client import get_tutor_response, check_content_safety

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='static')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
app.config['JWT_SECRET'] = os.getenv('JWT_SECRET')

# --- CORS (single setup, allow-list based) ---
# Put your deployed origin(s) in ALLOWED_ORIGINS env, comma-separated.
# Fallback includes LW + ngrok + example vercel host.
allowed_origins = [o.strip() for o in os.getenv('ALLOWED_ORIGINS', '').split(',') if o.strip()]
CORS(app, origins=allowed_origins or [
    "https://classes.coherenceeducation.org",
    "https://coherenceeducation.learnworlds.com",
    "https://df3e8ea9dd4c.ngrok-free.app",
    "https://*.vercel.app",
    "https://cherence-tutor.vercel.app"
], supports_credentials=True)

# --- Admin email list (ENV-driven, with safe fallback) ---
ADMIN_EMAILS = {
    e.strip().lower() for e in os.getenv(
        'ADMIN_EMAILS',
        'andrew@coherence.org,mina@coherenceeducation.org,'
        'support@coherenceeducation.org,evan.senour@gmail.com,'
        'gavinli.automation@gmail.com'
    ).split(',') if e.strip()
}

# Rate limiting - hybrid approach (in-memory + MySQL)
request_counts = defaultdict(list)


def check_rate_limit(student_id, window_seconds=60, max_requests=5):
    """
    Hybrid rate limiter: tries MySQL first, falls back to in-memory
    Limits to max_requests per window_seconds.
    """
    # Try MySQL-based rate limiting first (persistent)
    try:
        is_allowed, remaining = check_rate_limit_mysql(student_id, window_seconds, max_requests)
        if is_allowed:
            print(f"🚦 MySQL Rate check for {student_id}: {max_requests - remaining}/{max_requests} requests in last {window_seconds}s")
            return True
        else:
            print(f"🚦 MySQL Rate limit hit for {student_id}")
            return False
    except Exception as e:
        print(f"⚠️ MySQL rate limiting failed, falling back to in-memory: {e}")
    
    # Fallback to in-memory rate limiting
    now = time.time()
    request_times = request_counts[student_id].copy()
    # remove old entries
    request_times = [t for t in request_times if now - t < window_seconds]
    request_times.append(now)
    request_counts[student_id] = request_times

    print(f"🚦 In-memory Rate check for {student_id}: {len(request_times)}/{max_requests} requests in last {window_seconds}s")
    return len(request_times) <= max_requests

def generate_jwt_token(student_id, email, name, role='student'):
    """Generate JWT token for secure authentication"""
    payload = {
        'student_id': student_id,
        'email': email,
        'name': name,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, app.config['JWT_SECRET'], algorithm='HS256')

def is_admin_email(email):
    """Check if email is in admin list"""
    return bool(email) and email.lower() in ADMIN_EMAILS


def verify_jwt_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, app.config['JWT_SECRET'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    """Decorator to require JWT authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "No token provided"}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        
        # Add user info to request context
        request.user_id = payload['student_id']
        request.user_email = payload['email']
        request.user_name = payload.get('name')
        request.user_role = payload.get('role', 'student')
        
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        # Fallback: check cookie-based session if no Authorization header
        if not token:
            token = request.cookies.get('admin_session')
        if not token:
            return jsonify({"error": "No token provided"}), 401
        
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        
        # Check if user is admin
        if payload.get('role') != 'admin' or not is_admin_email(payload['email']):
            return jsonify({"error": "Admin access required"}), 403
        
        # Add admin info to request context
        request.admin_id = payload['student_id']
        request.admin_email = payload['email']
        request.admin_name = payload.get('name')
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "service": "coherence-ai-tutor",
        "version": "2.0.0"
    }), 200

@app.route('/api/auth/token', methods=['POST'])
def generate_token():
    try:
        print("📩 Incoming request to /api/auth/token")

        data = request.get_json(force=True) or {}
        # supports either {student_id,email,name} or LW webhook {data:{user:{...}}}
        user_data = data.get("data", {}).get("user", data)

        student_id = user_data.get("id") or user_data.get("student_id")
        email = user_data.get("email")
        name = user_data.get("username") or user_data.get("name") or user_data.get("full_name")

        print(f"🎓 Extracted student_id={student_id}, email={email}, name={name}")

        if not student_id or not email:
            print("⚠️ Missing required fields")
            return jsonify({"error": "Missing required fields"}), 400

        # Determine if user is admin or student
        is_admin = is_admin_email(email)
        role = 'admin' if is_admin else 'student'
        
        if is_admin:
            ensure_admin_exists(student_id, email, name)
            print(f"🔐 Admin access granted to {email}")
        else:
            ensure_student_exists(student_id, email, name)
            print(f"🎓 Student access granted to {email}")
        
        token = generate_jwt_token(student_id, email, name, role)

        print("✅ Token generated successfully")
        return jsonify({
            "token": token, 
            "expires_in": 86400,
            "role": role,
            "is_admin": is_admin
        }), 200

    except Exception as e:
        print("💥 Exception in /api/auth/token:", str(e))
        return jsonify({"error": str(e)}), 400




def verify_learnworlds_signature(payload, signature):
    """
    Verify webhook signature from LearnWorlds
    LearnWorlds signs webhooks with HMAC-SHA256
    """
    import hmac
    import hashlib
    
    webhook_secret = os.getenv('LEARNWORLDS_WEBHOOK_SECRET')
    if not webhook_secret or not signature:
        return False
    
    expected_signature = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@app.route('/api/chat', methods=['POST'])
@require_auth
def chat():
    """
    Secured chat endpoint using JWT authentication
    """
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        # Get authenticated user info from JWT
        student_id = request.user_id
        email = request.user_email
        name = request.user_name
        
        # Rate limiting - production settings
        max_req = int(os.getenv("MAX_REQUESTS_PER_MINUTE", 10))  # Reasonable for production
        print(f"🚦 Checking rate limit for student {student_id}: max {max_req} requests per minute")
        if not check_rate_limit(student_id, 60, max_req):
            print(f"🚦 Rate limit hit for student {student_id}")
            return jsonify({
                "error": "You're asking too many questions too quickly! Take a breath and try again in a minute 😊"
            }), 429

        
        # Content safety check
        is_safe, safety_reason, severity = check_content_safety(message)
        
        # Save student message
        start_time = time.time()
        message_id = save_message(student_id, 'student', message, session_id=session_id)

        if not is_safe:
            print(f"⚠️ Content flagged: {safety_reason} (Severity: {severity})")
            flag_content(student_id, message_id, message, f"{safety_reason} (Severity: {severity})")

            # Handle different severity levels with appropriate responses
            if severity == "critical":
                safe_response = (
                    "I'm really concerned about what you've shared. Your safety is the most important thing.\n\n"
                    "Please talk to a trusted adult right away — a parent, teacher, or school counselor.\n"
                    "- Call or text 988 (Suicide & Crisis Lifeline, 24/7)\n"
                    "- Text 'HELLO' to 741741 (Crisis Text Line)\n"
                    "- Call 911 if you're in immediate danger\n\n"
                    "You don't have to face difficult feelings alone. There are people who care and want to help. 💙"
                )

            elif severity == "high":
                safe_response = (
                    "I understand you're feeling strong emotions right now. "
                    "It's okay to feel frustrated, but let's try to keep things respectful and positive. "
                    "Instead of focusing on negative thoughts, how about we talk about something educational or inspiring? 🌱 "
                    "Maybe we can explore a topic you're curious about today? 🎓"
                )

            elif severity == "medium":
                safe_response = (
                    "I'm here to help with your learning! Let's keep our conversation positive and educational. "
                    "What subject or topic interests you most today? 🎓"
                )

            else:  # low severity
                safe_response = (
                    "Let's keep our conversation focused on learning! What would you like to explore today? 🌟"
                )

            save_message(student_id, 'tutor', safe_response, session_id=session_id)
            return jsonify({"reply": safe_response}), 200



        # Get conversation history
        history = get_conversation_history(student_id, limit=10)
        
        # Get AI response
        tutor_response = get_tutor_response(message, history)
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Estimate tokens
        tokens_est = len(message + tutor_response) // 4
        
        # Save tutor response
        save_message(
            student_id, 
            'tutor', 
            tutor_response, 
            session_id=session_id,
            tokens_est=tokens_est,
            response_time_ms=response_time_ms
        )
        
        return jsonify({
            "reply": tutor_response,
            "response_time_ms": response_time_ms
        }), 200
    
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Something went wrong. Please try again!"
        }), 500

@app.route('/api/history', methods=['GET'])
@require_auth
def get_history():
    """Get conversation history (JWT protected)"""
    limit = int(request.args.get('limit', 20))
    student_id = request.user_id
    
    history = get_conversation_history(student_id, limit=limit)
    return jsonify({"history": history}), 200

@app.route('/api/admin/conversations', methods=['GET'])
@require_admin
def admin_conversations():
    """Admin: Get all conversations"""
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    conversations = get_all_conversations(limit=limit, offset=offset)
    return jsonify({
        "conversations": conversations,
        "count": len(conversations)
    }), 200

@app.route('/api/admin/flagged', methods=['GET'])
@require_admin
def admin_flagged():
    """Admin: Get flagged content"""
    from utils.db import get_flagged_content
    flagged = get_flagged_content(limit=100)
    return jsonify({"flagged": flagged}), 200

@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_stats():
    """Admin: Get platform statistics"""
    stats = get_student_stats()
    return jsonify(stats), 200

@app.route('/api/admin/students', methods=['GET'])
@require_admin
def admin_students():
    """Admin: Get all students with their details"""
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    students = get_all_students(limit=limit, offset=offset)
    return jsonify({
        "students": students,
        "count": len(students)
    }), 200

@app.route('/api/admin/student/<student_id>/conversations', methods=['GET'])
@require_admin
def admin_student_conversations(student_id):
    """Admin: Get conversations for a specific student"""
    limit = int(request.args.get('limit', 50))
    
    conversations = get_student_conversations(student_id, limit=limit)
    return jsonify({
        "conversations": conversations,
        "student_id": student_id,
        "count": len(conversations)
    }), 200

@app.route('/api/admin/analytics', methods=['GET'])
@require_admin
def admin_analytics():
    """Admin: Get detailed platform analytics"""
    analytics = get_platform_analytics()
    return jsonify(analytics), 200

@app.route('/api/admin/comprehensive-analytics', methods=['GET'])
@require_admin
def admin_comprehensive_analytics():
    try:
        days_raw = request.args.get('days')
        try:
            days = int(days_raw) if days_raw is not None else 0
            if days < 0:
                days = 0
        except Exception:
            days = 0

        print(f"📊 Fetching comprehensive analytics for last {days} days...")
        analytics = get_comprehensive_analytics(days)
        print("✅ Comprehensive analytics generated successfully")
        return jsonify(analytics), 200

    except Exception as e:
        import traceback
        print("💥 Error in comprehensive analytics:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/chat', methods=['GET'])
def chat_ui():
    """Serve chat UI for embedding in LearnWorlds"""
    return send_from_directory('static', 'chat.html')

@app.route('/admin', methods=['GET'])
def admin_dashboard():
    """Serve admin UI if a valid admin token is in the query string"""
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "No token provided"}), 401

    payload = verify_jwt_token(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401

    if payload.get('role') != 'admin' or not is_admin_email(payload.get('email', '')):
        return jsonify({"error": "Admin access required"}), 403

    # Set a short-lived cookie for subsequent XHR from this origin
    resp = send_from_directory('static', 'admin.html')
    try:
        from flask import make_response
        resp = make_response(resp)
        # 1 hour cookie; secure/samesite for embedded usage
        resp.set_cookie('admin_session', token, max_age=3600, secure=True, samesite='None')
    except Exception:
        pass
    return resp


@app.after_request
def add_security_headers(resp):
    """Allow LearnWorlds pages to embed the chat iframe."""
    lw_allow = [
        "https://classes.coherenceeducation.org",
        "https://*.learnworlds.com",
        "https://coherenceeducation.learnworlds.com",
    ]

    # Allow the LW site to frame /chat
    resp.headers["Content-Security-Policy"] = (
        "frame-ancestors 'self' " + " ".join(lw_allow)
    )

    # Remove X-Frame-Options if present
    if "X-Frame-Options" in resp.headers:
        resp.headers.pop("X-Frame-Options")

    # Skip ngrok’s browser warning inside iframes
    resp.headers["ngrok-skip-browser-warning"] = "true"

    # Optional: make iframes happier
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    resp.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
    return resp


@app.route("/")
def home():
    return render_template("chat.html")

if __name__ == "__main__":
    # Initialize database tables
    print("🔧 Initializing database tables...")
    create_rate_limits_table()
    create_admins_table()
    
    port = int(os.getenv("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=(os.getenv("FLASK_ENV") == "development"),
    )
