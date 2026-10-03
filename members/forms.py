from urllib.parse import urlsplit

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserChangeForm, UsernameField
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import account_token_generator

User = get_user_model()


class InviteForm(forms.ModelForm):
    username = UsernameField(max_length=150)
    email = forms.EmailField(max_length=254)

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email address.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # No password exists until the invitee redeems their personal setup link.
        user.set_unusable_password()
        if commit:
            user.save()
        return user


class AccountChangeForm(UserChangeForm):
    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('An account already uses this email address.')
        return email


def send_password_link(user, *, invitation=False):
    if not user.is_active or not user.email:
        raise ValueError('An active account with an email address is required.')
    if User.objects.filter(email__iexact=user.email).exclude(pk=user.pk).exists():
        raise ValueError('Resolve duplicate account emails before sending a link.')
    origin = settings.LEAGUE_SITE_URL.rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ImproperlyConfigured('LEAGUE_SITE_URL must be an absolute site origin.')
    if not settings.DEBUG and parsed.scheme != 'https':
        raise ImproperlyConfigured('LEAGUE_SITE_URL must use HTTPS in production.')
    path = reverse('password_reset_confirm', kwargs={
        'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': account_token_generator.make_token(user),
    })
    context = {
        'username': user.get_username(),
        'link': origin + path,
        'invitation': invitation,
        'expiry_hours': settings.PASSWORD_RESET_TIMEOUT / 3600,
    }
    subject = 'Set up your Survivor Pool account' if invitation else 'Reset your Survivor Pool password'
    delivered = send_mail(
        subject,
        render_to_string('registration/password_link_email.txt', context),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=render_to_string('registration/password_link_email.html', context),
    )
    if delivered != 1:
        raise RuntimeError('Email backend did not accept the message.')


class LeaguePasswordResetForm(PasswordResetForm):
    def send_links(self):
        # Include invited accounts with unusable passwords; never guess between duplicates.
        users = list(User.objects.filter(email__iexact=self.cleaned_data['email'], is_active=True)[:2])
        if len(users) == 1:
            send_password_link(users[0], invitation=not users[0].has_usable_password())
