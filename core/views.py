import hmac, hashlib, json, os, requests
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from google import genai
from google.genai import types
from core.models import Conversation

PAGE_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
APP_SECRET = os.getenv("FB_APP_SECRET").encode()
VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")

SEND_API_URL = "https://graph.facebook.com/v23.0/me/messages"

def get_or_create_conversation(sender_id: str):
    try:
        return Conversation.objects.get(sender_id=sender_id)
    except Conversation.DoesNotExist:
        return Conversation.objects.create(sender_id=sender_id)

def send_text(recipient_id: str, text: str):
    params = {"access_token": PAGE_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    r = requests.post(SEND_API_URL, params=params, json=payload, timeout=10)
    r.raise_for_status()

def ai_reply(hostory) -> str:
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=str(hostory),
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            temperature=0.5,
            # only plain text is supported
            system_instruction="you are an ai assistant named dotshirt to assist users in facebook page messaging. it is a business of t-shirt in bangladesh, you normally use bangla, reply plain_text only. you should not give any other information. if you are not sure about the question please reply that you don't know about the question.",
        ),
    )
    return str(response.text)

def _verify_signature(request) -> bool:
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not sig.startswith("sha256="):
        return False
    provided = sig.split("=", 1)[1]
    digest = hmac.new(APP_SECRET, request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, digest)

@require_http_methods(["GET", "POST"])
@csrf_exempt
def webhook_view(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)  # plain text echo
        return HttpResponseForbidden("Verification failed")

    # POST: events
    if not _verify_signature(request):
        return HttpResponseForbidden("Invalid signature")

    data = json.loads(request.body.decode("utf-8"))
    for entry in data.get("entry", []):
        for evt in entry.get("messaging", []):
            sender = evt.get("sender", {}).get("id")
            if not sender:
                continue

            conversation = get_or_create_conversation(sender)
            history = json.loads(conversation.history)

            # Text messages
            msg = evt.get("message", {})
            if "text" in msg:
                user_text = msg["text"]
                history.append({"role": "user", "content": user_text})

                try:
                    reply = ai_reply(history[:30])
                except Exception as e:
                    print(e)
                    reply = "Sorry, I ran into an error. Please try again."
                try:
                    send_text(sender, reply)
                    history.append({"role": "assistant", "content": reply})
                except Exception:
                    pass
                
                print(history[:30])
                conversation.history = json.dumps(history)
                conversation.save()

            # Postback buttons (optional)
            postback = evt.get("postback")
            if postback and postback.get("payload"):
                payload = postback["payload"]
                send_text(sender, f"You tapped: {payload}")

    return JsonResponse({"status": "ok"})