import json
import logging
import os
import hmac
import hashlib
import requests

from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from google import genai
from google.genai import types

from .models import Conversation, APIKey
from .sys_prompt import get_prompt

# --- Setup and Configuration ---
logger = logging.getLogger(__name__)

# --- Environment Variables ---
PAGE_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
APP_SECRET = os.getenv("FB_APP_SECRET")
VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODELS = ["gemini-2.5-pro", "gemini-2.5-flash"]

API_KEYS = [key.get_api_key() for key in APIKey.objects.all()]

# --- Constants ---
SEND_API_URL = "https://graph.facebook.com/v23.0/me/messages"

# --- Database & History Management ---

def get_or_create_conversation(sender_id: str):
    """Retrieves or creates a conversation record for a given sender ID."""
    try:
        return Conversation.objects.get(sender_id=sender_id)
    except Conversation.DoesNotExist:
        return Conversation.objects.create(sender_id=sender_id)

def add_user_message_to_history(history: list, msg: dict) -> list | None:
    """
    Parses a user's message, adds it to the history, and returns the updated history.
    Returns None if the message is not processable.
    """
    if msg.get("text"):
        user_text = msg["text"]
    elif msg.get("attachments"):
        attachment = msg["attachments"][0] # Process the first attachment
        attachment_type = attachment.get("type")
        payload = attachment.get("payload", {})
        
        if payload.get("sticker_id") == 369239263222822: # Thumbs-up sticker
             user_text = ">thumbsup sticker"
        else:
             user_text = f'>user sent an "{attachment_type}"'
    else:
        return None # Not a processable message type

    history.append({"role": "user", "content": user_text})
    logger.info(f"User {history[-1]}")
    print(f"User {history[-1]}")
    return history

def add_model_message_to_history(history: list, model_responses: list) -> list:
    """
    Parses the AI's JSON response and adds a clean, textual representation to the history.
    """
    for res_part in model_responses:
        content = ""
        
        if "text" in res_part:
            content = res_part["text"]
        elif "attachment" in res_part:
            attachment_type = res_part.get("attachment", {}).get("type", "attachment")
            url = res_part.get("attachment", {}).get("payload", {}).get("url")
            content = f'>model sent an "{attachment_type}" {url}'
        else:
            # Fallback for unexpected format from AI
            content = json.dumps(res_part)

        history.append({"role": "assistant", "content": content})
        print(f"Model {history[-1]}")
    return history


# --- Facebook Messenger API Helpers ---

def send_api_request(payload: dict) -> bool:
    """Generic function to send a POST request to the Messenger Send API."""
    params = {"access_token": PAGE_TOKEN}
    try:
        r = requests.post(SEND_API_URL, params=params, json=payload, timeout=10)
        r.raise_for_status()
        response_data = r.json()
        if "error" in response_data:
            logger.error(f"FB Send API Error: {response_data['error']}")
            return False
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send FB API request: {e}")
        return False

def send_message(recipient_id: str, message: dict):
    """Sends a message object (text, attachment, quick replies) via Facebook."""
    payload = {"recipient": {"id": recipient_id}, "message": message, "messaging_type": "RESPONSE"}
    return send_api_request(payload)

def send_action(recipient_id: str, action: str):
    """Sends sender actions like 'typing_on' or 'mark_seen'."""
    payload = {"recipient": {"id": recipient_id}, "sender_action": action}
    return send_api_request(payload)


# --- Security ---

def verify_signature(request) -> bool:
    """Verifies the Facebook webhook signature for security."""
    if not APP_SECRET:
        logger.error("APP_SECRET is not configured. Signature verification failed.")
        return False
        
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not sig_header.startswith("sha256="):
        logger.warning(f"Invalid signature header format: {sig_header}")
        return False
        
    provided_signature = sig_header.split("=", 1)[1]
    
    app_secret_bytes = APP_SECRET.encode('utf-8')
    expected_signature = hmac.new(app_secret_bytes, request.body, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(provided_signature, expected_signature)


# --- AI Core Logic ---

def process_reply(history: list, model: str, api_key: str) -> list:
    """Generate AI response using Gemini API"""
    try:
        client = genai.Client(api_key=api_key)
        
        # Convert history to proper format for Gemini

        response = client.models.generate_content(
            model=model,
            contents=str(history),
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
        logger.error(f"AI generation error: {e}")
        return []
    
def ai_reply(history: list) -> list:
    # Try with Gemini API key first
    if GEMINI_API_KEY:
        for model in MODELS:
            try:
                response = process_reply(history, model, GEMINI_API_KEY)
                if response:
                    return response
            except Exception as e:
                print(f"Failed to get response from {model} using GEMINI_API_KEY(.env)")

    # Fallback: try with other API keys
    for model in MODELS:
        for key in API_KEYS:
            try:
                response = process_reply(history, model, key)
                if response:
                    return response
            except Exception as e:
                print(f"Failed to get response from {model} using {key[:4]}...{key[-4:]}")

    print("[FAIL] No valid response from any model/key")
    return []

# --- Main Webhook Logic ---

def process_event(event: dict):
    """Handles a single messaging event from the Facebook webhook."""
    sender_id = event.get("sender", {}).get("id")
    if not sender_id:
        return

    conversation = get_or_create_conversation(sender_id)
    history = json.loads(conversation.get_history() or "[]")
    
    user_input_received = False
    
    # Case 1: User sent a standard message (text, attachment)
    if "message" in event:
        updated_history = add_user_message_to_history(history, event["message"])
        if updated_history:
            history = updated_history
            user_input_received = True

    # Case 2: User clicked a postback button (from quick replies, etc.)
    elif "postback" in event:
        payload = event["postback"].get("payload", "")
        title = event["postback"].get("title", payload)
        user_text = f'user clicked: "{title}"' # Treat button click as user input
        history.append({"role": "user", "content": user_text})
        logger.info(f"User Postback: {user_text}")
        user_input_received = True

    if not user_input_received:
        # Ignore events without user input (e.g., delivery receipts, read receipts)
        return

    # --- Generate and Send AI Response ---
    send_action(sender_id, "mark_seen")
    send_action(sender_id, "typing_on")

    # Get AI response, keeping context to the last 15 turns (30 messages)
    model_responses = ai_reply(history[-30:])
    
    send_action(sender_id, "typing_off")

    # Send all parts of the AI's response
    #success = all(send_message(sender_id, res_part) for res_part in model_responses)
    success = []
    for res_part in model_responses:
        if not send_message(sender_id, res_part):
            print(f"Failed to send message: {res_part}")
            success.append(False)
        else:
            success.append(True)

    if all(success):
        final_history = add_model_message_to_history(history, model_responses)
        conversation.history = json.dumps(final_history)
        conversation.save()
    else:
        failed_count = success.count(False)
        logger.error(f"Failed to send {failed_count} messages to {sender_id}")


@require_http_methods(["GET", "POST"])
@csrf_exempt
def webhook_view(request):
    """Main webhook endpoint for Facebook Messenger."""
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully.")
            return HttpResponse(challenge, status=200)
        logger.warning(f"Webhook verification failed. Mode: {mode}, Token: {token}")
        return HttpResponseForbidden("Verification failed")

    # --- POST: Handle Incoming Events ---
    if not verify_signature(request):
        logger.warning("Invalid signature in webhook request.")
        return HttpResponseForbidden("Invalid signature")

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        logger.error("Invalid JSON received in webhook request body.")
        return HttpResponse("Invalid JSON", status=400)

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            try:
                process_event(event)
            except Exception as e:
                # Catch errors in single event processing to not fail the whole batch
                logger.error(f"Error processing event: {event}. Exception: {e}", exc_info=True)

    return JsonResponse({"status": "ok"})