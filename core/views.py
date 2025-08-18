import hmac, hashlib, json, os, requests
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

PAGE_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
APP_SECRET = os.getenv("FB_APP_SECRET").encode()
VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")

SEND_API_URL = "https://graph.facebook.com/v23.0/me/messages"  

def send_text(recipient_id: str, text: str):
    params = {"access_token": PAGE_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    r = requests.post(SEND_API_URL, params=params, json=payload, timeout=10)
    r.raise_for_status()

def ai_reply(user_text: str) -> str:
    # placeholder
    return 'Hello world'

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

            # Text messages
            msg = evt.get("message", {})
            if "text" in msg:
                user_text = msg["text"]
                try:
                    reply = ai_reply(user_text)
                except Exception:
                    reply = "Sorry, I ran into an error. Please try again."
                try:
                    send_text(sender, reply)
                except Exception:
                    pass

            # Postback buttons (optional)
            postback = evt.get("postback")
            if postback and postback.get("payload"):
                payload = postback["payload"]
                send_text(sender, f"You tapped: {payload}")

    return JsonResponse({"status": "ok"})