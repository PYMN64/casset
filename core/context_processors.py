from .models import PlatformSetting


def platform_settings(request):
    s = PlatformSetting.get_solo()
    return {
        'platform': s,
    }
