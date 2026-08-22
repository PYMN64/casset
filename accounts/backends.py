from django.contrib.auth import get_user_model
from django.contrib.auth.backends import AllowAllUsersModelBackend

UserModel = get_user_model()


class EmailOrUsernameBackend(AllowAllUsersModelBackend):
    """Log in with the internal username OR the account's e-mail address.

    Registration no longer asks a new user to pick a username (S12 UX pass —
    it was a second, redundant "choose a username" step on top of the
    publisher-only `public_handle`, see accounts/forms.py::CreatorHandleForm).
    Password accounts now get an opaque `u-xxxxxxxxxx` internal username
    (accounts/services.py::unique_username) that the user never sees, so the
    login form's "username" field must also accept the one identifier they
    actually know: their e-mail.

    Still `AllowAllUsersModelBackend`, not the default `ModelBackend`: this
    must keep returning a matched-but-inactive user so
    `LoginForm.confirm_login_allowed()` can tell "suspended" apart from
    "wrong password" (see the comment on `AUTHENTICATION_BACKENDS` in
    config/settings/base.py).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        user = None
        if "@" in username:
            user = UserModel.objects.filter(email__iexact=username).first()
        if user is None:
            user = UserModel.objects.filter(username__iexact=username).first()

        if user is None:
            # Same timing-attack mitigation as django.contrib.auth.backends.ModelBackend:
            # run the password hasher even on a miss so a valid vs. invalid
            # identifier can't be distinguished by response time.
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
