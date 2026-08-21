"""End-to-end journey QA.

Walks the flows a real person walks, in order, asserting at each step —
rather than checking that pages merely return 200. It exercises the live
database, so it complements the test suite rather than replacing it: run
it against a seeded dev database before a release.

    python manage.py seed_demo --users 33 --flush-demo
    python scripts/qa/journey_qa.py

Two real defects were found by this script that the unit suite missed:
a stale reverse-OneToOne cache silently ignoring a notification opt-out,
and the publisher gate's redirect target.
"""
import os
import re
import sys
from pathlib import Path

# Runnable from anywhere: put the project root on sys.path and load its
# .env the same way manage.py does.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402

from accounts.models import PhoneOTP, UserProfile  # noqa: E402
from tracks.models import Track  # noqa: E402

User = get_user_model()
PASSWORD = "qa12345678"

FAILS = []
STEPS = 0


def check(label, condition, detail=""):
    global STEPS
    STEPS += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(f"{label} {detail}")


def client():
    return Client(SERVER_NAME="localhost")


def fresh_user(username, **profile_kwargs):
    User.objects.filter(username=username).delete()
    user = User.objects.create_user(username, f"{username}@example.com", PASSWORD)
    profile = user.profile
    profile.onboarding_complete = True
    for key, value in profile_kwargs.items():
        setattr(profile, key, value)
    profile.save()
    return user


# ===========================================================================
print("\n=== Journey 1: sign up -> onboarding -> discover ===")
# ===========================================================================
c = client()
User.objects.filter(username="qa_signup").delete()

resp = c.post("/register/", {
    "username": "qa_signup", "email": "qa_signup@example.com",
    "password1": "V3ryStr0ngPass!", "password2": "V3ryStr0ngPass!",
    "accept_terms": "on",
})
check("registration redirects to onboarding", resp.status_code == 302 and resp.url == "/onboarding/", resp.get("Location", ""))
check("account exists", User.objects.filter(username="qa_signup").exists())

resp = c.post("/onboarding/", {
    "email": "qa_signup@example.com", "first_name": "سارا", "last_name": "احمدی",
    "display_name": "سارا احمدی", "interests": ["music", "podcast"],
    "next_action": "viewer",
}, follow=True)
check("listener path lands on discover", resp.request["PATH_INFO"] == "/discover/", resp.request["PATH_INFO"])
profile = User.objects.get(username="qa_signup").profile
check("onboarding recorded", profile.onboarding_complete)
check("interests saved", set(profile.interests) == {"music", "podcast"}, profile.interests)
check("display name saved", profile.display_name == "سارا احمدی")

# ===========================================================================
print("\n=== Journey 2: listener tries to publish (the gate) ===")
# ===========================================================================
listener = fresh_user("qa_gate")
c = client()
c.login(username="qa_gate", password=PASSWORD)

resp = c.get("/upload/")
check("upload page open to a listener (drafts are private)", resp.status_code == 200)
check("upload page warns publishing is not unlocked", "تکمیل مراحل انتشار" in resp.content.decode())

track = Track.objects.create(
    creator=listener, title="QA Draft", content_type="music",
    duration_seconds=90, status=Track.Status.DRAFT,
)
resp = c.post(f"/my/tracks/{track.id}/submit/")
check("submit blocked, redirected to the publisher checklist",
      resp.status_code == 302 and resp.url == "/creator/apply/", resp.get("Location", ""))
track.refresh_from_db()
check("track stayed a draft", track.status == Track.Status.DRAFT, track.status)

resp = c.get("/creator/apply/")
body = resp.content.decode()
check("checklist shows the phone step", "تایید شماره" in body)
check("checklist shows the handle step", "انتخاب یوزرنیم" in body)

resp = c.get("/creator/handle/")
check("handle page sends you to verify a phone first",
      resp.status_code == 302 and resp.url == "/account/phone/", resp.get("Location", ""))

# --- verify a phone the way the UI does ---
resp = c.post("/account/phone/", {"phone_number": "09121110001"})
check("OTP requested", resp.status_code == 302, resp.status_code)
otp = PhoneOTP.objects.filter(phone_number="09121110001").order_by("-created_at").first()
check("OTP row created", otp is not None)

# Brute-force the 6-digit code the way the app would receive it: read the
# code from the hash by trying the known plaintext the service generated.
from accounts.services import hash_otp_code  # noqa: E402

code = None
for candidate in range(1000000):
    if hash_otp_code("09121110001", f"{candidate:06d}") == otp.code_hash:
        code = f"{candidate:06d}"
        break
check("OTP code recovered for the test", code is not None)

resp = c.post("/account/phone/verify/", {"phone_number": "09121110001", "code": code}, follow=True)
listener.profile.refresh_from_db()
check("phone now verified", listener.profile.phone_verified)
check("still cannot publish (no handle yet)", not listener.profile.can_publish)
check("remaining blocker is the handle", listener.profile.publish_blockers() == ["handle"],
      listener.profile.publish_blockers())

resp = c.post("/creator/handle/", {"public_handle": "qa_gate_music"})
check("handle accepted, redirected to studio",
      resp.status_code == 302 and resp.url == "/creator/studio/", resp.get("Location", ""))
listener.profile.refresh_from_db()
check("can publish now", listener.profile.can_publish)
check("creator status approved", listener.profile.creator_status == UserProfile.CreatorStatus.APPROVED)

resp = c.post(f"/my/tracks/{track.id}/submit/")
track.refresh_from_db()
check("submit now succeeds", resp.status_code == 302 and resp.url == "/my/tracks/", resp.get("Location", ""))
check("track moved out of draft", track.status != Track.Status.DRAFT, track.status)

resp = c.get("/creator/studio/")
check("studio reachable", resp.status_code == 200)
resp = c.get(f"/{listener.profile.public_handle}/")
check("public profile live at the handle", resp.status_code == 200)

# ===========================================================================
print("\n=== Journey 3: reserved + duplicate handles ===")
# ===========================================================================
other = fresh_user("qa_handle2", phone_number="09121110002")
from django.utils import timezone  # noqa: E402

other.profile.phone_verified_at = timezone.now()
other.profile.save()
c2 = client()
c2.login(username="qa_handle2", password=PASSWORD)

resp = c2.post("/creator/handle/", {"public_handle": "settings"})
other.profile.refresh_from_db()
check("a reserved route name is refused as a handle", other.profile.public_handle is None)

resp = c2.post("/creator/handle/", {"public_handle": "qa_gate_music"})
other.profile.refresh_from_db()
check("an already-taken handle is refused", other.profile.public_handle is None)

resp = c2.post("/creator/handle/", {"public_handle": "qa_handle_two"})
other.profile.refresh_from_db()
check("a free handle is accepted", other.profile.public_handle == "qa_handle_two")

# ===========================================================================
print("\n=== Journey 4: notification preferences reach the writer ===")
# ===========================================================================
from notifications.models import Notification, NotificationPreference  # noqa: E402
from notifications.services import notify_new_follower  # noqa: E402

recipient = fresh_user("qa_notif")
actor = fresh_user("qa_notif_actor")
c3 = client()
c3.login(username="qa_notif", password=PASSWORD)

notify_new_follower(follower=actor, creator=recipient)
check("notification delivered by default", Notification.objects.filter(recipient=recipient).count() == 1)

Notification.objects.filter(recipient=recipient).delete()
resp = c3.post("/settings/", {"section": "notifications"})  # all switches off
check("preferences saved", resp.status_code == 302)
pref = NotificationPreference.objects.get(user=recipient)
check("new_follower switched off", pref.new_follower is False)

notify_new_follower(follower=actor, creator=recipient)
check("notification suppressed after opt-out",
      Notification.objects.filter(recipient=recipient).count() == 0)

# ===========================================================================
print("\n=== Journey 5: privacy boundaries ===")
# ===========================================================================
owner = fresh_user("qa_owner")
stranger = fresh_user("qa_stranger")
private_track = Track.objects.create(
    creator=owner, title="QA Private", content_type="music",
    status=Track.Status.APPROVED, visibility=Track.Visibility.PRIVATE,
)
pending_track = Track.objects.create(
    creator=owner, title="QA Pending", content_type="music",
    status=Track.Status.SUBMITTED, visibility=Track.Visibility.PUBLIC,
)

anon = client()
check("anonymous cannot open a private track", anon.get(f"/t/{private_track.slug}/").status_code == 404)
check("anonymous cannot open an unapproved track", anon.get(f"/t/{pending_track.slug}/").status_code == 404)
check("anonymous cannot embed a private track", anon.get(f"/embed/t/{private_track.slug}/").status_code == 404)

c4 = client()
c4.login(username="qa_stranger", password=PASSWORD)
check("another user cannot open a private track", c4.get(f"/t/{private_track.slug}/").status_code == 404)
check("another user cannot edit someone's track", c4.get(f"/my/tracks/{private_track.id}/edit/").status_code == 404)

c5 = client()
c5.login(username="qa_owner", password=PASSWORD)
check("the owner can still see their own private track", c5.get(f"/t/{private_track.slug}/").status_code == 200)

# 404 is as valid as 403 here — and better: it does not confirm the page
# exists to someone who may not use it.
DENIED = (302, 403, 404)
check("staff console refuses a non-staff user", c4.get("/staff/users/").status_code in DENIED)
check("moderation track queue refuses a non-staff user", c4.get("/moderation/tracks/").status_code in DENIED)
check("moderation report queue refuses a non-staff user", c4.get("/moderation/reports/").status_code in DENIED)
check("payout queue refuses a non-staff user", c4.get("/staff/payouts/").status_code in DENIED)
check("staff creator detail refuses a non-staff user", c4.get(f"/staff/creators/{owner.id}/").status_code in DENIED)
check("admin refuses a non-staff user", c4.get("/admin/").status_code in DENIED)

# ===========================================================================
print("\n=== Journey 6: CSRF is enforced on state changes ===")
# ===========================================================================
csrf_client = Client(SERVER_NAME="localhost", enforce_csrf_checks=True)
csrf_client.login(username="qa_owner", password=PASSWORD)
resp = csrf_client.post("/api/v1/playlist/create/", {"name": "no csrf"})
check("POST without a CSRF token is rejected", resp.status_code == 403, resp.status_code)

# ===========================================================================
print("\n=== Journey 7: rendered-page hygiene ===")
# ===========================================================================
c6 = client()
c6.login(username="qa_gate", password=PASSWORD)
pages = ["/discover/", "/trending/", "/search/?q=a", "/library/", "/dashboard/",
         "/settings/", "/upload/", "/my/tracks/", "/albums/", "/creator/studio/",
         "/vip/", "/payout/", "/notifications/", f"/{listener.profile.public_handle}/"]
for url in pages:
    body = c6.get(url).content.decode()
    problems = []
    if "{#" in body or "{%" in body:
        problems.append("template marker")
    if re.search(r'\bstyle="[^"]*(?:color|font-size|margin|padding):', body):
        problems.append("inline style")
    if "None" in re.findall(r">\s*(None)\s*<", body):
        problems.append("literal None")
    check(f"clean render {url}", not problems, ", ".join(problems))

# ===========================================================================
print("\n" + "=" * 62)
if FAILS:
    print(f"{len(FAILS)} of {STEPS} checks FAILED:")
    for f in FAILS:
        print("  -", f)
    raise SystemExit(1)
print(f"ALL {STEPS} CHECKS PASSED")
