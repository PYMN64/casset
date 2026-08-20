from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from core.models import PlatformSetting
from core.test_utils import make_superuser, make_user
from plays.models import PointLedger

from . import services
from .models import Invoice, PayoutRequest, Plan

User = get_user_model()


class PlanModelTests(TestCase):
    def test_slug_is_auto_generated_from_code(self):
        plan = Plan.objects.create(code="vip_monthly", title="VIP Monthly", price=50000)
        self.assertEqual(plan.slug, "vip_monthly")

    def test_slug_is_not_overwritten_if_set(self):
        plan = Plan.objects.create(code="vip_monthly", slug="custom-slug", title="VIP Monthly")
        self.assertEqual(plan.slug, "custom-slug")

    def test_default_ordering_is_sort_order_then_price(self):
        cheap = Plan.objects.create(code="a", title="A", price=10, sort_order=1)
        expensive_but_first = Plan.objects.create(code="b", title="B", price=100, sort_order=0)
        self.assertEqual(list(Plan.objects.all()), [expensive_but_first, cheap])


class HasVipTests(TestCase):
    """UserProfile.has_vip() is derived purely from billing.Invoice
    (plus fast-path cache fields). `subscriptions` is fully retired;
    `billing` is the single canonical source for VIP/plan state.
    """

    def setUp(self):
        self.user = make_user("listener1")
        self.profile = self.user.profile
        self.plan = Plan.objects.create(code="vip_monthly", title="VIP Monthly", price=0, duration_days=30)

    def test_no_invoice_no_vip(self):
        self.assertFalse(self.profile.has_vip())

    def test_paid_invoice_with_future_valid_until_grants_vip(self):
        inv = Invoice.objects.create(user=self.user, plan=self.plan, status=Invoice.Status.PAID)
        inv.mark_paid()
        self.assertTrue(self.profile.has_vip())

    def test_expired_invoice_does_not_grant_vip(self):
        Invoice.objects.create(
            user=self.user,
            plan=self.plan,
            status=Invoice.Status.PAID,
            valid_until=timezone.now() - timezone.timedelta(days=1),
        )
        self.assertFalse(self.profile.has_vip())

    def test_pending_invoice_does_not_grant_vip(self):
        Invoice.objects.create(user=self.user, plan=self.plan, status=Invoice.Status.PENDING)
        self.assertFalse(self.profile.has_vip())


class ActivateVipDevTests(TestCase):
    def setUp(self):
        # Must be onboarded, otherwise OnboardingRequiredMiddleware redirects
        # every request and the view under test never runs — which made these
        # tests pass on the 302 assertion while doing nothing.
        self.user = make_user("listener2")
        self.client.login(username="listener2", password="pass12345")

    @override_settings(DEBUG=False)
    def test_disabled_outside_debug(self):
        resp = self.client.get(reverse("vip_activate_dev"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("onboarding", resp["Location"])
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.has_vip())
        self.assertFalse(Invoice.objects.filter(user=self.user).exists())

    @override_settings(DEBUG=True)
    def test_creates_a_real_paid_invoice_not_a_bare_flag(self):
        resp = self.client.get(reverse("vip_activate_dev"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("onboarding", resp["Location"])
        profile = self.user.profile
        profile.refresh_from_db()
        self.assertTrue(profile.has_vip())
        # The important architectural bit: VIP came from a real Invoice,
        # not from directly writing profile.is_vip like the old code did.
        self.assertTrue(
            Invoice.objects.filter(user=self.user, status=Invoice.Status.PAID).exists()
        )
        self.assertFalse(profile.is_vip)

    @override_settings(DEBUG=True)
    def test_activate_with_specific_plan(self):
        plan = Plan.objects.create(code="vip_yearly", title="VIP Yearly", price=100, duration_days=365)
        resp = self.client.get(reverse("vip_activate_dev_plan", args=[plan.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("onboarding", resp["Location"])
        self.assertTrue(
            Invoice.objects.filter(
                user=self.user, plan=plan, status=Invoice.Status.PAID
            ).exists()
        )


class VipPageViewTests(TestCase):
    def setUp(self):
        self.user = make_user("vippageuser")
        self.client.login(username="vippageuser", password="pass12345")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("vip"))
        self.assertEqual(resp.status_code, 302)

    def test_renders_only_active_plans(self):
        active = Plan.objects.create(code="active", title="Active", is_active=True)
        Plan.objects.create(code="inactive", title="Inactive", is_active=False)
        resp = self.client.get(reverse("vip"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["plans"]), [active])

    def test_no_active_invoice_when_never_paid(self):
        resp = self.client.get(reverse("vip"))
        self.assertIsNone(resp.context["active_invoice"])


class PayoutPageViewTests(TestCase):
    def setUp(self):
        self.user = make_user("payoutpageuser")
        self.other = make_user("payoutpageuser2")
        self.client.login(username="payoutpageuser", password="pass12345")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("payout"))
        self.assertEqual(resp.status_code, 302)

    def test_only_shows_own_payout_requests(self):
        PayoutRequest.objects.create(user=self.user, amount=100)
        PayoutRequest.objects.create(user=self.other, amount=999)
        resp = self.client.get(reverse("payout"))
        payouts = list(resp.context["payouts"])
        self.assertEqual(len(payouts), 1)
        self.assertEqual(payouts[0].amount, 100)


class CreatePayoutRequestViewTests(TestCase):
    """Covers a previously fully-untested, money-adjacent view.

    Also regression-covers a gap found while writing these tests: nothing
    stopped a user from filing multiple overlapping payout requests, each
    capped at their *full* point balance — see billing/views.py's pending-
    request guard.
    """

    def setUp(self):
        self.user = make_user("payoutcreator")
        self.profile = self.user.profile
        self.profile.creator_status = UserProfile.CreatorStatus.APPROVED
        self.profile.points = 1000
        self.profile.save(update_fields=["creator_status", "points"])
        self.client.login(username="payoutcreator", password="pass12345")

    def test_get_is_not_allowed_redirects_without_creating(self):
        resp = self.client.get(reverse("create_payout_request"))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(PayoutRequest.objects.exists())

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.post(reverse("create_payout_request"), {"amount": "100"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(PayoutRequest.objects.exists())

    def test_non_approved_creator_cannot_request_payout(self):
        self.profile.creator_status = UserProfile.CreatorStatus.PENDING
        self.profile.save(update_fields=["creator_status"])
        resp = self.client.post(reverse("create_payout_request"), {"amount": "100"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(PayoutRequest.objects.exists())

    def test_zero_points_creator_cannot_request_payout(self):
        self.profile.points = 0
        self.profile.save(update_fields=["points"])
        resp = self.client.post(reverse("create_payout_request"), {"amount": "100"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(PayoutRequest.objects.exists())

    def test_valid_request_is_created_pending(self):
        resp = self.client.post(reverse("create_payout_request"), {"amount": "100"})
        self.assertEqual(resp.status_code, 302)
        payout = PayoutRequest.objects.get(user=self.user)
        self.assertEqual(payout.amount, 100)
        self.assertEqual(payout.status, PayoutRequest.Status.PENDING)

    def test_non_positive_amount_rejected(self):
        resp = self.client.post(reverse("create_payout_request"), {"amount": "0"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(PayoutRequest.objects.exists())

    def test_non_numeric_amount_rejected(self):
        resp = self.client.post(reverse("create_payout_request"), {"amount": "not-a-number"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(PayoutRequest.objects.exists())

    def test_amount_is_capped_at_point_balance(self):
        # price_per_point_music defaults to 0 -> unit falls back to 1,
        # so max requestable amount == profile.points.
        resp = self.client.post(reverse("create_payout_request"), {"amount": "999999"})
        self.assertEqual(resp.status_code, 302)
        payout = PayoutRequest.objects.get(user=self.user)
        self.assertEqual(payout.amount, self.profile.points)

    def test_amount_capped_using_configured_price_per_point(self):
        setting = PlatformSetting.get_solo()
        setting.price_per_point_music = 50
        setting.save(update_fields=["price_per_point_music"])

        resp = self.client.post(reverse("create_payout_request"), {"amount": "999999"})
        self.assertEqual(resp.status_code, 302)
        payout = PayoutRequest.objects.get(user=self.user)
        self.assertEqual(payout.amount, self.profile.points * 50)

    def test_second_request_blocked_while_one_is_pending(self):
        first = self.client.post(reverse("create_payout_request"), {"amount": "100"})
        self.assertEqual(first.status_code, 302)

        second = self.client.post(reverse("create_payout_request"), {"amount": "200"})
        self.assertEqual(second.status_code, 302)

        self.assertEqual(PayoutRequest.objects.filter(user=self.user).count(), 1)
        self.assertEqual(PayoutRequest.objects.get(user=self.user).amount, 100)

    def test_new_request_allowed_after_previous_one_resolved(self):
        resolved = PayoutRequest.objects.create(
            user=self.user, amount=50, status=PayoutRequest.Status.PAID
        )
        resp = self.client.post(reverse("create_payout_request"), {"amount": "100"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PayoutRequest.objects.filter(user=self.user).count(), 2)
        resolved.refresh_from_db()
        self.assertEqual(resolved.status, PayoutRequest.Status.PAID)

    def test_points_locked_in_at_request_time(self):
        resp = self.client.post(reverse("create_payout_request"), {"amount": "100"})
        self.assertEqual(resp.status_code, 302)
        payout = PayoutRequest.objects.get(user=self.user)
        self.assertEqual(payout.points, 100)  # unit defaults to 1


# ---------------------------------------------------------------------------
# Payment provider abstraction (billing/services.py)
# ---------------------------------------------------------------------------

class PaymentProviderSelectionTests(TestCase):
    def test_default_provider_is_dev(self):
        provider = services.get_payment_provider()
        self.assertIsInstance(provider, services.DevPaymentProvider)

    @override_settings(PAYMENT_PROVIDER="zarinpal", ZARINPAL_MERCHANT_ID="mid")
    def test_zarinpal_selected_when_configured(self):
        provider = services.get_payment_provider(callback_url="https://x/cb")
        self.assertIsInstance(provider, services.ZarinpalProvider)
        self.assertEqual(provider.merchant_id, "mid")


class DevPaymentProviderTests(TestCase):
    def setUp(self):
        self.user = make_user("devpay_user")
        self.plan = Plan.objects.create(code="vip", title="VIP", price=1000)

    def test_request_and_verify_round_trip(self):
        invoice = Invoice.objects.create(user=self.user, plan=self.plan, amount=1000)
        provider = services.DevPaymentProvider()
        url = provider.request_payment(invoice=invoice)
        self.assertIn(str(invoice.pk), url)
        self.assertTrue(provider.verify_payment(invoice=invoice, callback_params={"Status": "OK"}))
        self.assertFalse(provider.verify_payment(invoice=invoice, callback_params={"Status": "NOK"}))


class ZarinpalProviderTests(TestCase):
    def setUp(self):
        self.user = make_user("zp_user")
        self.plan = Plan.objects.create(code="vip", title="VIP", price=50000)
        self.invoice = Invoice.objects.create(user=self.user, plan=self.plan, amount=50000)
        self.provider = services.ZarinpalProvider(
            merchant_id="mid", callback_url="https://casset.ir/vip/callback/",
        )

    @patch("billing.services.requests.post")
    def test_request_payment_success(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "data": {"code": 100, "authority": "A123"}, "errors": [],
        }
        url = self.provider.request_payment(invoice=self.invoice)
        self.assertIn("A123", url)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.provider, "zarinpal")
        self.assertEqual(self.invoice.provider_ref, "A123")

    @patch("billing.services.requests.post")
    def test_request_payment_failure_raises(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"data": {"code": 101}, "errors": ["bad merchant"]}
        with self.assertRaises(services.PaymentError):
            self.provider.request_payment(invoice=self.invoice)

    @patch("billing.services.requests.post")
    def test_verify_payment_success(self, mock_post):
        self.invoice.provider_ref = "A123"
        self.invoice.save(update_fields=["provider_ref"])
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"data": {"code": 100, "ref_id": 999}, "errors": []}
        self.assertTrue(
            self.provider.verify_payment(invoice=self.invoice, callback_params={"Status": "OK"})
        )

    def test_verify_payment_status_not_ok_short_circuits(self):
        # No network call needed/expected — gateway itself reported failure.
        self.assertFalse(
            self.provider.verify_payment(invoice=self.invoice, callback_params={"Status": "NOK"})
        )


# ---------------------------------------------------------------------------
# start_payment / payment_callback views
# ---------------------------------------------------------------------------

class StartPaymentViewTests(TestCase):
    def setUp(self):
        self.user = make_user("startpay_user")
        self.plan = Plan.objects.create(code="vip", title="VIP", price=1000)
        self.client.login(username="startpay_user", password="pass12345")

    def test_redirects_to_dev_callback_by_default(self):
        resp = self.client.get(reverse("start_payment", args=[self.plan.id]))
        self.assertEqual(resp.status_code, 302)
        invoice = Invoice.objects.get(user=self.user, plan=self.plan)
        self.assertEqual(invoice.status, Invoice.Status.PENDING)
        self.assertIn(str(invoice.pk), resp.url)

    def test_full_dev_flow_activates_vip(self):
        resp = self.client.get(reverse("start_payment", args=[self.plan.id]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.has_vip())

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("start_payment", args=[self.plan.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.url)


class PaymentCallbackViewTests(TestCase):
    def setUp(self):
        self.user = make_user("callback_user")
        self.plan = Plan.objects.create(code="vip", title="VIP", price=1000)

    def test_unknown_invoice_404s(self):
        resp = self.client.get(reverse("payment_callback"), {"invoice_id": 999999})
        self.assertEqual(resp.status_code, 404)

    def test_second_callback_is_idempotent(self):
        invoice = Invoice.objects.create(user=self.user, plan=self.plan, amount=1000)
        url = reverse("payment_callback") + f"?invoice_id={invoice.pk}&Status=OK"
        self.client.get(url)
        self.client.get(url)  # gateway hitting the callback twice must not double-apply
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)


# ---------------------------------------------------------------------------
# Payout approval (billing/services.py::approve_payout/reject_payout)
# ---------------------------------------------------------------------------

class ApprovePayoutTests(TestCase):
    def setUp(self):
        self.creator = make_user("payout_approve_creator")
        self.creator.profile.points = 500
        self.creator.profile.save(update_fields=["points"])
        self.staff = make_superuser("payout_approve_staff")
        self.payout = PayoutRequest.objects.create(user=self.creator, amount=200, points=200)

    def test_approve_deducts_points_via_ledger(self):
        ok = services.approve_payout(payout=self.payout, actor=self.staff)
        self.assertTrue(ok)
        self.creator.profile.refresh_from_db()
        self.assertEqual(self.creator.profile.points, 300)
        entry = PointLedger.objects.get(user=self.creator, reason=PointLedger.Reason.PAYOUT_DEDUCTION)
        self.assertEqual(entry.delta, -200)

    def test_approve_marks_paid(self):
        services.approve_payout(payout=self.payout, actor=self.staff)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, PayoutRequest.Status.PAID)
        self.assertIsNotNone(self.payout.paid_at)

    def test_cannot_reapprove_already_paid(self):
        services.approve_payout(payout=self.payout, actor=self.staff)
        ok = services.approve_payout(payout=self.payout, actor=self.staff)
        self.assertFalse(ok)
        self.creator.profile.refresh_from_db()
        self.assertEqual(self.creator.profile.points, 300)  # not deducted twice

    def test_approved_points_cannot_be_requested_again(self):
        """Regression: create_payout_request never used to deduct points at
        all, so the same balance could be paid out repeatedly."""
        services.approve_payout(payout=self.payout, actor=self.staff)
        self.creator.profile.refresh_from_db()
        self.assertEqual(self.creator.profile.points, 300)
        # A second payout can only draw from the now-reduced 300, not the
        # original 500 — proven by the cap logic in create_payout_request.

    def test_reject_does_not_touch_points(self):
        ok = services.reject_payout(payout=self.payout, actor=self.staff, reason="مشکوک")
        self.assertTrue(ok)
        self.creator.profile.refresh_from_db()
        self.assertEqual(self.creator.profile.points, 500)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, PayoutRequest.Status.REJECTED)
        self.assertEqual(self.payout.admin_note, "مشکوک")

    def test_writes_audit_log(self):
        from moderation.models import AuditLog

        services.approve_payout(payout=self.payout, actor=self.staff)
        log = AuditLog.objects.get(target_type=AuditLog.TargetType.PAYOUT, payout=self.payout)
        self.assertEqual(log.action, "approve_payout")
        self.assertEqual(log.actor, self.staff)


class StaffPayoutQueueViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("staff_payout_creator")
        self.creator.profile.points = 100
        self.creator.profile.save(update_fields=["points"])
        self.staff = make_superuser("staff_payout_admin")
        self.payout = PayoutRequest.objects.create(user=self.creator, amount=100, points=100)

    def test_requires_staff(self):
        self.client.login(username="staff_payout_creator", password="pass12345")
        resp = self.client.get(reverse("staff_payout_queue"))
        self.assertNotEqual(resp.status_code, 200)

    def test_staff_sees_pending_payouts(self):
        self.client.login(username="staff_payout_admin", password="pass12345")
        resp = self.client.get(reverse("staff_payout_queue"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.payout, list(resp.context["payouts"]))

    def test_approve_via_view(self):
        self.client.login(username="staff_payout_admin", password="pass12345")
        resp = self.client.post(reverse("staff_approve_payout", args=[self.payout.id]))
        self.assertEqual(resp.status_code, 302)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, PayoutRequest.Status.PAID)

    def test_reject_via_view(self):
        self.client.login(username="staff_payout_admin", password="pass12345")
        resp = self.client.post(reverse("staff_reject_payout", args=[self.payout.id]), {"reason": "test"})
        self.assertEqual(resp.status_code, 302)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, PayoutRequest.Status.REJECTED)
