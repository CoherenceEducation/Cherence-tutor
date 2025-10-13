import os
import jwt
import time
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
from collections import defaultdict
from flask_cors import CORS

# Import utilities
from utils.db import (
    ensure_student_exists, 
    get_conversation_history, 
    save_message,
    flag_content,
    get_all_conversations,
    get_student_stats
)
from utils.gemini_client import get_tutor_response, check_content_safety

load_dotenv()
app = Flask(__name__, static_folder='static', template_folder='static')
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
app.config['JWT_SECRET'] = os.getenv('JWT_SECRET')

# Enable CORS for LearnWorlds domain
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
CORS(app, origins=allowed_origins, supports_credentials=True)

# Rate limiting (consider using Redis in production)
request_counts = defaultdict(list)

def check_rate_limit(student_id, window_seconds=60, max_requests=5):
    """
    Basic per-student rate limiter.
    Limits to max_requests per window_seconds.
    """
    now = time.time()
    request_times = request_counts[student_id].copy()  # Make a copy to avoid reference issues
    # remove old entries
    request_times = [t for t in request_times if now - t < window_seconds]
    request_times.append(now)
    request_counts[student_id] = request_times

    print(f"🚦 Rate check for {student_id}: {len(request_times)}/{max_requests} requests in last {window_seconds}s")
    return len(request_times) <= max_requests

def generate_jwt_token(student_id, email, name):
    """Generate JWT token for secure authentication"""
    payload = {
        'student_id': student_id,
        'email': email,
        'name': name,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, app.config['JWT_SECRET'], algorithm='HS256')

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
        
        # Add student info to request context
        request.student_id = payload['student_id']
        request.student_email = payload['email']
        request.student_name = payload.get('name')
        
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

        ensure_student_exists(student_id, email, name)
        token = generate_jwt_token(student_id, email, name)

        print("✅ Token generated successfully")
        return jsonify({"token": token, "expires_in": 86400}), 200

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
        
        # Get authenticated student info from JWT
        student_id = request.student_id
        email = request.student_email
        name = request.student_name
        
        # Rate limiting - very strict for testing
        max_req = int(os.getenv("MAX_REQUESTS_PER_MINUTE", 2))  # Very low for testing
        print(f"🚦 Checking rate limit for student {student_id}: max {max_req} requests per minute")
        if not check_rate_limit(student_id, 60, max_req):
            print(f"🚦 Rate limit hit for student {student_id}")
            return jsonify({
                "error": "You're asking too many questions too quickly! Take a breath and try again in a minute 😊"
            }), 429

        
        # Content safety check
        is_safe, safety_reason = check_content_safety(message)
        
        # Save student message
        start_time = time.time()
        message_id = save_message(student_id, 'student', message, session_id=session_id)

        if not is_safe:
            print(f"⚠️ Content flagged: {safety_reason}")
            flag_content(student_id, message_id, message, safety_reason)

            if "critical safety concern" in safety_reason.lower():
                safe_response = (
                    "I'm really concerned about what you've shared. Your safety is the most important thing.\n\n"
                    "Please talk to a trusted adult right away — a parent, teacher, or school counselor.\n"
                    "- Call or text 988 (Suicide & Crisis Lifeline, 24/7)\n"
                    "- Text 'HELLO' to 741741 (Crisis Text Line)\n"
                    "- Call 911 if you're in immediate danger\n\n"
                    "You don't have to face difficult feelings alone. There are people who care and want to help. 💙"
                )

            elif any(keyword in safety_reason.lower() for keyword in ["violence", "hate", "harassment", "bullying"]):
                safe_response = (
                    "I understand you're feeling strong emotions right now. "
                    "It's okay to feel frustrated, but let's try to keep things respectful and positive. "
                    "Instead of focusing on hate or harm, how about we talk about something educational or inspiring? 🌱 "
                    "Maybe we can explore a topic you're curious about today? 🎓"
                )

            else:
                safe_response = (
                    "I'm here to help with your learning! Let's keep our conversation positive and educational. "
                    "What subject or topic interests you most today? 🎓"
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
    student_id = request.student_id
    
    history = get_conversation_history(student_id, limit=limit)
    return jsonify({"history": history}), 200

@app.route('/api/admin/conversations', methods=['GET'])
def admin_conversations():
    """Admin: Get all conversations"""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != os.getenv('ADMIN_SECRET_KEY'):
        return jsonify({"error": "Unauthorized"}), 401
    
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    conversations = get_all_conversations(limit=limit, offset=offset)
    return jsonify({
        "conversations": conversations,
        "count": len(conversations)
    }), 200

@app.route('/api/admin/flagged', methods=['GET'])
def admin_flagged():
    """Admin: Get flagged content"""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != os.getenv('ADMIN_SECRET_KEY'):
        return jsonify({"error": "Unauthorized"}), 401
    
    from utils.db import get_flagged_content
    flagged = get_flagged_content(limit=100)
    return jsonify({"flagged": flagged}), 200

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    """Admin: Get platform statistics"""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != os.getenv('ADMIN_SECRET_KEY'):
        return jsonify({"error": "Unauthorized"}), 401
    
    stats = get_student_stats()
    return jsonify(stats), 200

@app.route('/chat', methods=['GET'])
def chat_ui():
    """Serve chat UI for embedding in LearnWorlds"""
    return send_from_directory('static', 'chat.html')

@app.route('/admin', methods=['GET'])
def admin_dashboard():
    """Admin dashboard"""
    admin_key = request.args.get('key')
    if admin_key != os.getenv('ADMIN_SECRET_KEY'):
        return "Unauthorized", 401
    
    stats = get_student_stats()
    recent = get_all_conversations(limit=50)
    from utils.db import get_flagged_content
    flagged = get_flagged_content(limit=20)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Coherence AI Tutor - Admin</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f5f7fa;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 15px;
                margin-bottom: 30px;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .stat-card {{
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            }}
            .stat-card .number {{
                font-size: 42px;
                font-weight: bold;
                color: #667eea;
            }}
            .section {{
                background: white;
                padding: 25px;
                border-radius: 15px;
                margin-bottom: 20px;
            }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
            .alert {{ background: #fff3cd; border-left: 4px solid #ff6b6b; padding: 15px; margin: 10px 0; }}
            .flagged {{ background: #fee; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎓 Coherence AI Tutor - Admin</h1>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>Total Students</h3>
                <div class="number">{stats.get('total_students', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Total Messages</h3>
                <div class="number">{stats.get('total_messages', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Flagged Content</h3>
                <div class="number" style="color: #ff6b6b;">{len(flagged)}</div>
            </div>
            <div class="stat-card">
                <h3>Active Today</h3>
                <div class="number">{stats.get('active_today', 0)}</div>
            </div>
        </div>
        
        {f'''
        <div class="section">
            <h2>🚩 Flagged Content (Requires Review)</h2>
            <table>
                <tr>
                    <th>Time</th>
                    <th>Student</th>
                    <th>Message</th>
                    <th>Reason</th>
                </tr>
                {''.join([f"<tr class='flagged'><td>{f['flagged_at']}</td><td>{f.get('student_id', 'N/A')}</td><td>{f['message_text'][:100]}</td><td>{f['reason']}</td></tr>" for f in flagged])}
            </table>
        </div>
        ''' if flagged else ''}
        
        <div class="section">
            <h2>Recent Activity</h2>
            <table>
                <tr>
                    <th>Time</th>
                    <th>Student</th>
                    <th>Message</th>
                </tr>
                {''.join([f"<tr><td>{r['created_at']}</td><td>{r.get('name', 'Unknown')}</td><td>{r['message'][:80]}</td></tr>" for r in recent[:20]])}
            </table>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)
    
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
    port = int(os.getenv("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=(os.getenv("FLASK_ENV") == "development"),
    )
