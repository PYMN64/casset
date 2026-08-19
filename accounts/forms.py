from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.validators import RegexValidator

from .models import UserProfile

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"autocomplete": "username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class ProfileSettingsForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False, max_length=150, widget=forms.TextInput(attrs={"placeholder": "نام"}))
    last_name = forms.CharField(required=False, max_length=150, widget=forms.TextInput(attrs={"placeholder": "نام خانوادگی"}))

    class Meta:
        model = UserProfile
        fields = [
            "display_name",
            "bio",
            "cover",
            "avatar",
            "website_url",
            "instagram_url",
            "telegram_url",
            "youtube_url",
            "twitter_url",
        ]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3, "placeholder": "یک بیو کوتاه (حداکثر 160 کاراکتر)..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # user.email is the source of truth
        if self.instance and getattr(self.instance, "user", None):
            self.fields["email"].initial = self.instance.user.email
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        email = (self.cleaned_data.get("email") or "").strip()
        if getattr(profile, "user", None) is not None:
            profile.user.email = email
            profile.user.first_name = (self.cleaned_data.get("first_name") or "").strip()
            profile.user.last_name = (self.cleaned_data.get("last_name") or "").strip()
            if commit:
                profile.user.save(update_fields=["email","first_name","last_name"])

        if commit:
            profile.save()
        return profile


class PhoneStartForm(forms.Form):
    phone_number = forms.CharField(
        max_length=32,
        widget=forms.TextInput(attrs={"placeholder": "09xxxxxxxxx", "autocomplete": "tel"}),
    )


class PhoneVerifyForm(forms.Form):
    phone_number = forms.CharField(max_length=32, widget=forms.HiddenInput())
    code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={"placeholder": "کد ۶ رقمی", "inputmode": "numeric"}),
    )


class OnboardingForm(forms.ModelForm):
    # Email is required for product + monetization readiness.
    email = forms.EmailField(required=True)

    first_name = forms.CharField(required=True, max_length=150, widget=forms.TextInput(attrs={"placeholder": "نام"}))
    last_name = forms.CharField(required=True, max_length=150, widget=forms.TextInput(attrs={"placeholder": "نام خانوادگی"}))

    INTEREST_CHOICES = [
        ("music", "موزیک"),
        ("podcast", "پادکست"),
        ("book", "کتاب"),
        ("video", "ویدیو"),
    ]

    interests = forms.MultipleChoiceField(
        required=False,
        choices=INTEREST_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = UserProfile
        fields = [
            "display_name",
            "website_url",
            "instagram_url",
            "telegram_url",
            "youtube_url",
            "twitter_url",
        ]

    def __init__(self, *args, platform=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform = platform
        if self.instance and getattr(self.instance, "user", None):
            self.fields["email"].initial = self.instance.user.email
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["interests"].initial = list(self.instance.interests or [])

        # We enforce disabled types in clean_interests().
        # UI disabling is handled in template (to keep code simple).
        self.disabled_interest_types = set()
        if platform is not None:
            for k in ("book", "video"):
                if not platform.is_content_type_enabled(k):
                    self.disabled_interest_types.add(k)

    def clean_interests(self):
        interests = self.cleaned_data.get("interests") or []
        platform = getattr(self, "platform", None)
        if platform is None:
            return interests
        # Enforce backend: don't allow disabled types
        out = []
        for k in interests:
            if platform.is_content_type_enabled(k):
                out.append(k)
        return out

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.interests = self.cleaned_data.get("interests") or []
        profile.onboarding_complete = True
        email = (self.cleaned_data.get("email") or "").strip()
        if getattr(profile, "user", None) is not None:
            profile.user.email = email
            profile.user.first_name = (self.cleaned_data.get("first_name") or "").strip()
            profile.user.last_name = (self.cleaned_data.get("last_name") or "").strip()
            if commit:
                profile.user.save(update_fields=["email","first_name","last_name"])
        if commit:
            profile.save()
        return profile


class CreatorHandleForm(forms.ModelForm):
    """One-time public handle selection for creators.

    We keep Django's User.username as an internal identifier (u-xxxx...).
    The public handle is used for sharing profile pages at /<handle>/.
    """

    public_handle = forms.CharField(
        max_length=30,
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z0-9_\-]{3,30}$",
                message="یوزرنیم فقط می‌تواند شامل حروف انگلیسی، عدد، _ و - باشد (۳ تا ۳۰ کاراکتر).",
            )
        ],
        widget=forms.TextInput(attrs={"placeholder": "مثلاً: ali_music"}),
    )

    class Meta:
        model = UserProfile
        fields = ["public_handle"]

    def __init__(self, *args, reserved=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reserved = set(reserved or [])

        # If already set, lock it in UI.
        if self.instance and self.instance.public_handle:
            self.fields["public_handle"].disabled = True

    def clean_public_handle(self):
        handle = (self.cleaned_data.get("public_handle") or "").strip()
        handle_lower = handle.lower()

        if handle_lower in self.reserved:
            raise forms.ValidationError("این یوزرنیم رزرو شده است. لطفاً یک گزینه دیگر انتخاب کنید.")

        # Enforce one-time set: if already set, don't allow change.
        if self.instance and self.instance.public_handle:
            return self.instance.public_handle

        # Uniqueness (case-insensitive)
        if UserProfile.objects.filter(public_handle__iexact=handle).exists():
            raise forms.ValidationError("این یوزرنیم قبلاً گرفته شده است.")

        return handle

    def save(self, commit=True):
        profile = super().save(commit=False)
        if not profile.public_handle_set_at and profile.public_handle:
            # set timestamp only the first time
            from django.utils import timezone

            profile.public_handle_set_at = timezone.now()
        if commit:
            profile.save(update_fields=["public_handle", "public_handle_set_at"])
        return profile
