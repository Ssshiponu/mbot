import json
import logging
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from google import genai
from google.genai import types
from .sys_prompt import get_prompt

from .models import Conversation
import requests, os, hmac, hashlib

# Set up logging
logger = logging.getLogger(__name__)

PAGE_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
APP_SECRET = os.getenv("FB_APP_SECRET")
VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")

SEND_API_URL = "https://graph.facebook.com/v23.0/me/messages"

def get_or_create_conversation(sender_id: str):
    try:
        return Conversation.objects.get(sender_id=sender_id)
    except Conversation.DoesNotExist:
        return Conversation.objects.create(sender_id=sender_id)

def send_text(recipient_id: str, message: dict):
    """Send a message via Facebook Messenger API"""
    params = {"access_token": PAGE_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": message}
    try:
        r = requests.post(SEND_API_URL, params=params, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send message to {recipient_id}: {e}")
        return False

def send_action(recipient_id: str, action: str):
    """Send sender actions like typing indicators"""
    params = {"access_token": PAGE_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "sender_action": action}
    try:
        r = requests.post(SEND_API_URL, params=params, json=payload, timeout=5)
        r.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send action {action} to {recipient_id}: {e}")
        return False

def verify_signature(request) -> bool:
    """Verify Facebook webhook signature for security"""
    if not APP_SECRET:
        logger.warning("APP_SECRET not configured")
        return False
        
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not sig.startswith("sha256="):
        return False
        
    provided = sig.split("=", 1)[1]
    app_secret_bytes = APP_SECRET.encode('utf-8')
    digest = hmac.new(app_secret_bytes, request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, digest)

def ai_reply(history) -> list:
    """Generate AI response using Gemini API"""
    try:
        client = genai.Client()
        
        # Convert history to proper format for Gemini
        formatted_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            formatted_history.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=formatted_history,
            config=types.GenerateContentConfig(
                temperature=0.8,
                system_instruction=get_prompt(),
                response_mime_type="application/json",
            ),
        )
        
        # Parse the JSON response
        parsed_response = json.loads(response.text)
        
        # Validate response format
        if not isinstance(parsed_response, list):
            logger.error(f"Invalid response format: {type(parsed_response)}")
            return []
            
        return parsed_response
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return []
    except Exception as e:
        logger.error(f"AI reply error: {e}")
        return []

@require_http_methods(["GET", "POST"])
@csrf_exempt
def webhook_view(request):
    # GET: verification
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return HttpResponse(challenge, status=200)
        
        logger.warning(f"Verification failed: mode={mode}, token={token}")
        return HttpResponseForbidden("Verification failed")

    # POST: events
    if not verify_signature(request):
        logger.warning("Invalid signature in webhook request")
        return HttpResponseForbidden("Invalid signature")

    try:
        data = json.loads(request.body.decode("utf-8"))
        print(data)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return HttpResponseForbidden("Invalid JSON")

    for entry in data.get("entry", []):
        for evt in entry.get("messaging", []):
            sender = evt.get("sender", {}).get("id")
            if not sender:
                continue

            try:
                conversation = get_or_create_conversation(sender)
                history = json.loads(conversation.get_history() or "[]")

                # Handle text messages and attachments
                msg = evt.get("message", {})
                attachments = msg.get("attachments", [])

                is_text = msg.get("text") is not None
                sticker_id = None
                attachment_type = ""

                for attachment in attachments:
                    attachment_type = attachment.get("type")
                    sticker_id = attachment.get("payload", {}).get("sticker_id")

                if is_text or sticker_id or attachment_type:
                    # Determine user message content
                    if sticker_id and sticker_id == 369239383222814:
                        user_text = "<thumbsup sticker>"
                    elif is_text:
                        user_text = msg["text"]
                    else:
                        user_text = f'user sent an "{attachment_type}"'

                    # Add user message to history
                    history.append({"role": "user", "content": user_text})
                    logger.info(f"User {sender}: {user_text}")

                    # Send typing indicators
                    send_action(sender, "mark_seen")
                    send_action(sender, "typing_on")

                    # Get AI response
                    reply = ai_reply(history[-30:])  # Keep last 30 messages for context
                    print(reply)
                    
                    send_action(sender, "typing_off")

                    # Send responses
                    success = True
                    for r in reply:
                        if not send_text(sender, r):
                            success = False
                            break
                        history.append({"role": "assistant", "content": r.get("text", str(r))})

                    if success:
                        # Save conversation history
                        conversation.history = json.dumps(history)
                        conversation.save()
                    else:
                        logger.error(f"Failed to send all messages to {sender}")

                # Handle postback buttons
                postback = evt.get("postback")
                if postback and postback.get("payload"):
                    payload = postback["payload"]
                    send_text(sender, {"text": f"You tapped: {payload}"})

            except Exception as e:
                logger.error(f"Error processing message from {sender}: {e}")
                # Send error message to user
                send_text(sender, {"text": "দুঃখিত, একটি সমস্যা হয়েছে। আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন।"})

    return JsonResponse({"status": "ok"})