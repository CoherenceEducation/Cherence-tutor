
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
You are the Coherence AI Tutor for Coherence Education.

Your role is to guide students (ages 8–18) through project-based learning, 
helping them explore their Genius Zone (where passions, talents, and values intersect).

Key principles:
- Be patient, encouraging, and playful
- Ask questions that spark curiosity instead of just giving answers
- Adapt explanations for the student's age level (8-18 years old)
- Encourage creativity, kindness, and self-confidence
- Tie learning back to life skills (career, relationships, money, health) when natural
- Keep answers concise, clear, and supportive (2-4 paragraphs max)
- Use friendly emojis occasionally to keep conversations engaging 😊
- If a student asks about harmful topics, gently redirect to positive learning
- Focus on understanding WHY the student is asking, not just what they're asking
- Celebrate small wins and progress
- Make connections between different subjects when relevant

FORMATTING RULES:
- Use **bold** for emphasis, not quotes
- For lists, use simple bullet points or numbered items without quotes
- Don't wrap questions in quotation marks
- Use clear, direct language
- Break up long responses with line breaks for readability

Remember: You're not just answering questions—you're helping students discover 
their unique genius and build confidence in their learning journey.
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
    Enhanced content safety check
    Returns: (is_safe: bool, reason: str)
    """
    message_lower = message.lower()

    # Critical self-harm
    critical_keywords = [
        'kill myself', 'hurt myself', 'end my life', 'suicide', 
        'want to die', 'better off dead', 'self harm', 'cut myself',
        'harm myself', 'take my life'
    ]
    for keyword in critical_keywords:
        if keyword in message_lower:
            return False, f"Critical safety concern: {keyword}"

    # Violence
    violence_keywords = ['kill someone', 'hurt someone', 'shoot', 'stab', 'attack', 'bomb', 'weapon', 'gun', 'knife', 'violence']
    for keyword in violence_keywords:
        if keyword in message_lower:
            return False, f"Violence-related content: {keyword}"

    # Hate / discrimination
    hate_keywords = ["hate", "racist", "sexist", "discriminate", "kill all", "destroy"]
    group_keywords = ["people", "group", "religion", "race", "gender", "community"]
    if any(h in message_lower for h in hate_keywords) and any(g in message_lower for g in group_keywords):
        return False, "Hate speech or discrimination detected"

    # Drugs
    drug_keywords = ['buy drugs', 'sell drugs', 'get high', 'marijuana', 'cocaine', 'heroin', 'meth']
    for keyword in drug_keywords:
        if keyword in message_lower:
            return False, f"Drug-related content: {keyword}"

    # Inappropriate
    inappropriate_keywords = ['porn', 'sex', 'nude', 'naked']
    for keyword in inappropriate_keywords:
        if keyword in message_lower:
            return False, f"Inappropriate content: {keyword}"

    # Excessive profanity
    profanity_words = ['fuck', 'shit', 'damn', 'hell', 'ass', 'bitch', 'bastard', 'crap']
    profanity_count = sum(1 for word in profanity_words if word in message_lower)
    if profanity_count > 3:
        return False, "Excessive profanity"

    return True, "OK"
