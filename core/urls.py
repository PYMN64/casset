from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.generic import TemplateView

from core import views
from core.sitemaps import SITEMAPS

urlpatterns = [
    path("healthz/", views.health_check, name="health_check"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": SITEMAPS},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    # Legal pages. Required by the sign-up consent checkbox and by every
    # payment provider's onboarding review, so they are real routes rather
    # than links to nowhere.
    path("terms/", TemplateView.as_view(template_name="legal/terms.html"), name="terms"),
    path("privacy/", TemplateView.as_view(template_name="legal/privacy.html"), name="privacy"),
]
