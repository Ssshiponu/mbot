from django.contrib import admin
from django.urls import path
from core.views import webhook_view
from django.http import HttpResponse

privacy_policy="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Privacy Policy</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 2rem auto; line-height: 1.6; }
        h1 { text-align: center; }
    </style>
</head>
<body>
    <h1>Privacy Policy</h1>
    <p>
        This Privacy Policy describes how our Messenger Bot collects, 
        uses, and protects information when you interact with our Facebook Page.
    </p>

    <h2>Information We Collect</h2>
    <p>
        We only collect the information you provide when messaging our Page, such as 
        your Facebook profile name and the text you send to the bot.
    </p>

    <h2>How We Use Information</h2>
    <p>
        The collected information is only used to provide automated responses 
        and improve customer service.
    </p>

    <h2>Data Sharing</h2>
    <p>
        We do not sell, trade, or share your personal data with third parties. 
        Information is only shared with Facebook as part of the Messenger platform.
    </p>

    <h2>Data Security</h2>
    <p>
        We take reasonable measures to protect your information from unauthorized 
        access, use, or disclosure.
    </p>
</body>
</html>

"""

urlpatterns = [
    path("admin/", admin.site.urls),
    path("webhook/", webhook_view, name="webhook"),
    path("privacy/", lambda request: HttpResponse(privacy_policy), name="privacy"),
]