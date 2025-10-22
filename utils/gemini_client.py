
# utils/gemini_client.py

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini with detailed error logging
try:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    # Avoid logging any part of the API key in production
    genai.configure(api_key=api_key)
    print("✅ Gemini configured")
except Exception as e:
    print(f"❌ Error configuring Gemini: {e}")
    raise

# System instruction
SYSTEM_INSTRUCTION = """
You are the Coherence AI Tutor for Coherence Education. Your job is to teach students (ages 8–18) as efficiently as possible on the topic they ask about—using a playful, encouraging voice—while staying on topic. Do not ask about their passions/interests/life story; that discovery work is already done.

PRIMARY GOALS (in order)
1. Streamlined understanding of the requested topic/skill.
2. Teach by Leading (guide with small steps, not info-dumps).
3. Keep it fun and jocular without getting silly or off-task.

Key Principles
• Be patient, upbeat, and a bit witty; use light humor to lower anxiety.
• Stay laser-focused on the student’s request. No tangents; no probing for personal passions or backgrounds.
• Adapt explanations to age and prior knowledge only using what the student has told you about this task (not their biography).
• Ask task-focused questions that move learning forward (e.g., What power rule do you think fits here?).
• Keep answers concise and scannable (aim for 2–4 short paragraphs or equivalent bullets).
• Celebrate small wins and progress (Nice! You nailed the base rule 🎯).
• If the topic is harmful/inappropriate, gently redirect to safe, constructive learning.

Teaching by Leading Protocol (use by default)
1. Clarify the target (one line max): Rephrase the request and the exact skill to hit.
2. Micro-diagnose: Ask one bite-size, on-task question to see where to start (e.g., Do exponents with the same base add or multiply?).
3. Tiny step → check: Give a minimal hint/example, then ask the student to try a mini step.
4. Name the idea: State the key concept/rule in **bold** once it “clicks.”
5. Apply & vary: 1–2 quick practice items with immediate feedback.
6. Snapshot summary: One-line recap + what to do next (and optional challenge).
*If the student explicitly asks for the answer now, give it—then show the 1-step reason.*

Do/Don’t Guardrails
❌ Don’t ask about passions, values, life goals, or “why you’re learning this.”
❌ Don’t meander into other subjects unless the student requests it.
✅ Do keep a friendly, focused vibe; light emojis are okay (1–2 max per reply).
✅ Do switch depth on request: “Speed run” vs “Go deeper.”

Formatting Rules
• Use **bold** for key terms/rules.
• For lists, use • bullets.
• Use 1., 2., 3. for step-by-step instructions.
• Use clear, direct sentences and line breaks for readability.
• *Italics* for emphasis; `code` for short technical tokens.
• No quotation marks around questions.

Response Structure
1. Friendly, on-topic opener (one line, playful).
2. Guided teaching (use the protocol above).
3. End with a tiny next step or one practice item.

Quick Examples (behavioral style)
Student: Teach me exponents.
Tutor:
Let’s power up ⚡ Exponents first: same base, add powers when multiplying.
Warm-up: What’s 2^3 × 2^4? (Think: keep base 2, add powers.)
Try this: x^2 ⋅ x^5 = ?
Rule: **a^m ⋅ a^n = a^(m+n)**
Nice work—next we’ll handle division (subtract powers) or power of a power. Which one?

Student: I need help with topic X.
Tutor:
On it! We’ll hit the key rule and try one together 🙂 What part of X trips you up most: formulas, steps, or word problems? (Pick one, and we’ll speed-run it.)

Safety Redirect (if needed)
If asked for harmful/unsafe content, decline briefly and offer a safe, educational alternative on the same subject.

Remember: You’re here to teach this skill fast, with heart and humor—no detours into personal profiling.
"""

def get_tutor_response(student_message, conversation_history=None, student_age=None):
    """
    Generate AI tutor response using Gemini
    
    Args:
        student_message: Current student question
        conversation_history: List of {"role": "student/tutor", "message": "..."}
        student_age: Optional age for better age-appropriate responses
    
    Returns:
        Tutor response text
    """
    try:
        print(f"📝 Generating response for: {student_message[:50]}...")
        
        # Use gemini-2.0-flash for cost efficiency and reliability
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        print(f"✅ Model initialized: gemini-2.0-flash")
        
        # Build context from history (last 6-8 turns to manage token usage)
        context_parts = []
        if conversation_history:
            for turn in conversation_history[-8:]:  # Last 8 turns
                role_label = "Student" if turn['role'] == 'student' else "Tutor"
                context_parts.append(f"{role_label}: {turn['message']}")
        
        # Add current message
        context_parts.append(f"Student: {student_message}")
        full_prompt = "\n\n".join(context_parts)
        
        print(f"📤 Sending prompt ({len(full_prompt)} chars)...")
        
        # Generate response
        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=800,
                top_p=0.95,
                top_k=40
            )
        )
        
        print(f"✅ Response received")
        
        # Check if response was blocked
        if not response.text:
            print("⚠️ Empty response - checking safety ratings...")
            if hasattr(response, 'prompt_feedback'):
                print(f"Prompt feedback: {response.prompt_feedback}")
            return "I'm not sure how to respond to that. Could you rephrase your question? 🤔"
        
        return response.text
    
    except Exception as e:
        # Detailed error logging
        print(f"❌ Gemini API Error: {type(e).__name__}")
        print(f"❌ Error details: {str(e)}")
        
        # Check for specific error types
        if "API_KEY_INVALID" in str(e) or "invalid API key" in str(e).lower():
            print("🚨 ISSUE: Invalid API Key detected!")
            print("   1. Go to https://aistudio.google.com/app/apikey")
            print("   2. Create a new API key")
            print("   3. Update GEMINI_API_KEY in .env")
            return "Configuration error. Please contact your teacher! 🔧"
        
        elif "quota" in str(e).lower() or "rate limit" in str(e).lower():
            print("🚨 ISSUE: Rate limit or quota exceeded!")
            return "I'm getting too many requests right now. Please wait a minute and try again! ⏰"
        
        elif "permission" in str(e).lower():
            print("🚨 ISSUE: API permission error!")
            return "I don't have permission to respond right now. Please contact your teacher! 🔒"
        
        else:
            # Generic error
            import traceback
            traceback.print_exc()
            return "I'm having a little trouble thinking right now 🤔 Could you try asking your question again? If this keeps happening, let your teacher know!"


def check_content_safety(message):
    """
    Comprehensive content safety check for educational environment
    Returns: (is_safe: bool, reason: str, severity: str)
    """
    import re
    
    message_lower = message.lower().strip()
    original_message = message.strip()
    
    # Skip empty or very short messages
    if len(message_lower) < 2:
        return True, "OK", "low"
    
    # Check for message length (prevent spam)
    if len(message) > 2000:
        return False, "Message too long", "medium"
    
    # 1. CRITICAL SAFETY CONCERNS (Immediate intervention needed)
    critical_patterns = [
        r'\b(kill\s+myself|hurt\s+myself|end\s+my\s+life|suicide|want\s+to\s+die|better\s+off\s+dead|self\s*harm|cut\s+myself|harm\s+myself|take\s+my\s+life)\b',
        r'\b(planning\s+to\s+die|going\s+to\s+kill\s+myself|ending\s+it\s+all|not\s+worth\s+living)\b',
        r'\b(overdose|poison\s+myself|jump\s+off|hang\s+myself)\b'
    ]
    
    for pattern in critical_patterns:
        if re.search(pattern, message_lower):
            return False, f"Critical safety concern detected", "critical"
    
    # 2. VIOLENCE & THREATS (High priority)
    violence_patterns = [
        r'\b(kill\s+someone|hurt\s+someone|shoot\s+someone|stab\s+someone|attack\s+someone|bomb\s+someone)\b',
        r'\b(threaten\s+to\s+kill|going\s+to\s+shoot|planning\s+to\s+hurt|revenge\s+violence)\b',
        r'\b(weapon|gun|knife|bomb|explosive|poison)\b.*\b(school|teacher|student|classmate)\b',
        r'\b(violence|fight|beat\s+up|punch|hit)\b.*\b(someone|people|them)\b'
    ]
    
    for pattern in violence_patterns:
        if re.search(pattern, message_lower):
            return False, f"Violence or threat detected", "high"
    
    # 3. HATE SPEECH & DISCRIMINATION
    hate_patterns = [
        r'\b(hate|despise|loathe)\b.*\b(people|group|religion|race|gender|community|minority)\b',
        r'\b(racist|sexist|homophobic|transphobic|discriminate)\b',
        r'\b(kill\s+all|destroy\s+all|eliminate\s+all)\b.*\b(people|group|race|religion)\b',
        r'\b(inferior|superior)\b.*\b(race|people|group)\b',
        r'\b(slur|insult)\b.*\b(racial|ethnic|religious)\b'
    ]
    
    for pattern in hate_patterns:
        if re.search(pattern, message_lower):
            return False, f"Hate speech or discrimination detected", "high"
    
    # 4. DRUGS & SUBSTANCE ABUSE
    drug_patterns = [
        r'\b(buy\s+drugs|sell\s+drugs|get\s+high|smoke\s+weed|do\s+drugs)\b',
        r'\b(marijuana|cocaine|heroin|meth|ecstasy|lsd|pills)\b.*\b(buy|sell|use|take)\b',
        r'\b(overdose|drug\s+dealer|drug\s+dealing)\b',
        r'\b(alcohol|beer|wine|drunk|drinking)\b.*\b(underage|minor|teen)\b'
    ]
    
    for pattern in drug_patterns:
        if re.search(pattern, message_lower):
            return False, f"Drug-related content detected", "medium"
    
    # 5. INAPPROPRIATE SEXUAL CONTENT
    sexual_patterns = [
        r'\b(porn|pornography|nude|naked|sex|sexual)\b.*\b(video|photo|image|picture)\b',
        r'\b(sexting|nude\s+photo|sexual\s+content)\b',
        r'\b(inappropriate\s+relationship|adult\s+content)\b'
    ]
    
    for pattern in sexual_patterns:
        if re.search(pattern, message_lower):
            return False, f"Inappropriate sexual content detected", "high"
    
    # 6. ACADEMIC DISHONESTY
    academic_patterns = [
        r'\b(cheat\s+on\s+test|copy\s+homework|plagiarize|steal\s+answers)\b',
        r'\b(essay\s+service|homework\s+help\s+for\s+money|buy\s+essay)\b',
        r'\b(cheating\s+website|test\s+answers\s+online)\b'
    ]
    
    for pattern in academic_patterns:
        if re.search(pattern, message_lower):
            return False, f"Academic dishonesty detected", "medium"
    
    # 7. PERSONAL INFORMATION SHARING
    personal_info_patterns = [
        r'\b(phone\s+number|address|home\s+address|social\s+security)\b',
        r'\b(credit\s+card|bank\s+account|password|login)\b',
        r'\b(personal\s+information|private\s+details)\b.*\b(share|give|tell)\b'
    ]
    
    for pattern in personal_info_patterns:
        if re.search(pattern, message_lower):
            return False, f"Personal information sharing detected", "medium"
    
    # 8. CYBERBULLYING & HARASSMENT
    bullying_patterns = [
        r'\b(bully|harass|intimidate|threaten)\b.*\b(someone|student|classmate)\b',
        r'\b(spread\s+rumors|gossip\s+about|make\s+fun\s+of)\b',
        r'\b(exclude|ostracize|ignore)\b.*\b(someone|student|classmate)\b'
    ]
    
    for pattern in bullying_patterns:
        if re.search(pattern, message_lower):
            return False, f"Cyberbullying or harassment detected", "high"
    
    # 9. EXCESSIVE PROFANITY
    profanity_words = [
        'fuck', 'shit', 'damn', 'hell', 'ass', 'bitch', 'bastard', 'crap',
        'piss', 'dick', 'pussy', 'whore', 'slut', 'fag', 'retard'
    ]
    
    profanity_count = sum(1 for word in profanity_words if word in message_lower)
    if profanity_count > 2:
        return False, f"Excessive profanity detected ({profanity_count} instances)", "medium"
    
    # 10. SPAM & REPETITIVE CONTENT
    if len(set(message_lower.split())) < 3 and len(message_lower) > 20:
        return False, "Repetitive or spam-like content", "low"
    
    # 11. OFF-TOPIC/INAPPROPRIATE FOR EDUCATIONAL SETTING
    off_topic_patterns = [
        r'\b(gambling|casino|betting|lottery)\b',
        r'\b(illegal\s+activities|criminal\s+behavior)\b',
        r'\b(adult\s+content|mature\s+content)\b'
    ]
    
    for pattern in off_topic_patterns:
        if re.search(pattern, message_lower):
            return False, f"Content inappropriate for educational setting", "medium"
    
    # 12. CHECK FOR SUSPICIOUS PATTERNS
    # Multiple question marks (potential spam)
    if message.count('?') > 5:
        return False, "Excessive question marks detected", "low"
    
    # All caps (potential shouting/aggression)
    if len(message) > 10 and message.isupper():
        return False, "Excessive capitalization detected", "low"
    
    # Repeated characters (potential spam)
    if re.search(r'(.)\1{4,}', message):
        return False, "Repeated characters detected", "low"
    
    return True, "OK", "low"
