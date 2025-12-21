from .models import UserProfile


def user_profile(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    return {"user_profile": profile}
