import json
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from google import genai
from google.genai import types
from .sys_prompt import get_prompt

from .models import Conversation
import requests, os, hmac, hashlib

PAGE_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
APP_SECRET = os.getenv("FB_APP_SECRET").encode()
VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")

SEND_API_URL = "https://graph.facebook.com/v23.0/me/messages"

def get_or_create_conversation(sender_id: str):
    try:
        return Conversation.objects.get(sender_id=sender_id)
    except Conversation.DoesNotExist:
        return Conversation.objects.create(sender_id=sender_id)

def send_text(recipient_id: str, message: dict):
    params = {"access_token": PAGE_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": message}
    r = requests.post(SEND_API_URL, params=params, json=payload, timeout=10)
    r.raise_for_status()

def send_action(recipient_id: str, action: str):
    params = {"access_token": PAGE_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "sender_action": action}
    r = requests.post(SEND_API_URL, params=params, json=payload, timeout=2)
    r.raise_for_status()

def verify_signature(request) -> bool:
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not sig.startswith("sha256="):
        return False
    provided = sig.split("=", 1)[1]
    digest = hmac.new(APP_SECRET, request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, digest)


def ai_reply(hostory) -> str:
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=str(hostory),
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            temperature=1,
            system_instruction=get_prompt(),
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


@require_http_methods(["GET", "POST"])
@csrf_exempt
def webhook_view(request):
    # GET: verification
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)  # plain text echo
        return HttpResponseForbidden("Verification failed")

    # POST: events
    if not verify_signature(request):
        return HttpResponseForbidden("Invalid signature")

    data = json.loads(request.body.decode("utf-8"))
    for entry in data.get("entry", []):
        for evt in entry.get("messaging", []):
            sender = evt.get("sender", {}).get("id")
            if not sender:
                continue

            conversation = get_or_create_conversation(sender)
            history = json.loads(conversation.get_history())

            # Text messages
            msg = evt.get("message", {})
            attachments = msg.get("attachments", [])

            is_text = msg.get("text") is not None
            sticker_id = None
            attachment_type = ""

            for attachment in attachments:
                attachment_type = attachment.get("type")
                sticker_id = attachment.get("payload", {}).get("sticker_id")

            if is_text or sticker_id or attachment_type:
                if sticker_id and sticker_id == 369239383222814:
                    user_text = "<thambsup sticker>"
                elif is_text:
                    user_text = msg["text"]
                else:
                    user_text = f'user sent an "{attachment_type}"'

                history.append({"role": "user", "content": user_text})
                print("user:", user_text)
                send_action(sender, "mark_seen")
                send_action(sender, "typing_on")
                reply = ai_reply(history[-30:])
                send_action(sender, "typing_off")
                try:
                    print(reply)
                except Exception as e:
                    print(e)
                try:
                    for r in reply:
                        send_text(sender, r)
                        history.append({"role": "assistant", "content": r})
                except Exception as e:
                    print(e)

                conversation.history = json.dumps(history)
                conversation.save()

            # Postback buttons (optional)
            postback = evt.get("postback")
            if postback and postback.get("payload"):
                payload = postback["payload"]
                send_text(sender, f"You tapped: {payload}")

    return JsonResponse({"status": "ok"})
