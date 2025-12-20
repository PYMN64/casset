from django.contrib.auth.models import User
from django.test import Client, TestCase

from tracks.models import Track
from .models import Report


class ModerationReportTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(username="rep", password="pass12345")
        self.creator = User.objects.create_user(username="cre", password="pass12345")
        self.track = Track.objects.create(creator=self.creator, title="T", slug="t", status=Track.Status.APPROVED)

    def test_report_track_once_per_day(self):
        c = Client()
        c.login(username="rep", password="pass12345")
        r1 = c.post(f"/report/track/{self.track.id}/", {"reason": "spam"})
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["ok"])

        r2 = c.post(f"/report/track/{self.track.id}/", {"reason": "spam"})
        self.assertEqual(r2.status_code, 429)
        self.assertEqual(r2.json()["error"], "already_reported_today")

        self.assertEqual(Report.objects.count(), 1)
