"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, register_converter

from accounts import views as accounts_views
from core.converters import UnicodeSlugConverter

# Registered before any urlpatterns below (and before app urlconfs are
# imported by include()) so "<uslug:...>" resolves everywhere.
register_converter(UnicodeSlugConverter, "uslug")

admin.site.site_header = 'Casset Admin'
admin.site.site_title = 'Casset Admin'
admin.site.index_title = 'Management'

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    # NOTE: core.staff_urls existed on disk but was never include()'d here
    # until this line — the entire staff console (users/creators consoles,
    # creator_detail) was unreachable at any URL. Fixed here.
    path("staff/", include("core.staff_urls")),
    path("staff/", include("billing.staff_urls")),
    path("", include("accounts.urls")),
    path("", include("tracks.urls")),
    path("", include("uploads.urls")),
    path("", include("plays.urls")),
    path("", include("interactions.urls")),
    path("", include("playlists.urls")),
    path("", include("explore.urls")),
    path("", include("billing.urls")),
    path("", include("moderation.urls")),
    path("", include("notifications.urls")),
    # IMPORTANT: Keep this at the VERY END so it doesn't shadow real routes.
    path("<slug:handle>/", accounts_views.public_profile_by_handle, name="public_profile_by_handle"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
