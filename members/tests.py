import datetime
import re
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from survivorPool.models import Pick, Team
from .forms import AccountChangeForm, InviteForm, send_password_link
from .tokens import account_token_generator


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    LEAGUE_SITE_URL='https://league.example.com',
    DEFAULT_FROM_EMAIL='Survivor Pool <league@example.com>',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class AccountLifecycleTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('organizer', 'organizer@example.com', 'OriginalPass123!', is_staff=True)
        self.member = User.objects.create_user('player', 'player@example.com', 'OriginalPass123!')

    def invite(self, username='newplayer', email='new@example.com'):
        self.client.force_login(self.staff)
        return self.client.post(reverse('member_accounts'), {'username': username, 'email': email})

    def email_path(self):
        return urlsplit(re.search(r'https://[^\s]+', mail.outbox[-1].body).group()).path

    def open_link(self, path):
        self.client.logout()
        return self.client.get(path, follow=True)

    def test_registration_is_removed_and_no_public_links_remain(self):
        before = User.objects.count()
        self.assertEqual(self.client.get('/members/register/').status_code, 404)
        self.assertEqual(self.client.post('/members/register/', {'username': 'outsider'}).status_code, 404)
        self.assertEqual(User.objects.count(), before)
        for url in ('/', reverse('login')):
            response = self.client.get(url)
            self.assertNotContains(response, '/members/register/')
            self.assertIn('invite-only', response.content.decode().lower())

    def test_only_active_staff_can_provision_or_manage_accounts(self):
        for user in (None, self.member):
            self.client.logout()
            if user:
                self.client.force_login(user)
            self.assertEqual(self.client.post(reverse('member_accounts'), {'username': 'outsider', 'email': 'o@example.com'}).status_code, 302)
            self.assertEqual(self.client.post(reverse('member_account_action', args=[self.member.pk]), {'action': 'deactivate'}).status_code, 302)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)
        self.assertFalse(User.objects.filter(username='outsider').exists())

    def test_invitation_sets_no_password_and_uses_canonical_https_origin(self):
        self.assertRedirects(self.invite(email='NEW@Example.com'), reverse('member_accounts'))
        user = User.objects.get(username='newplayer')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.email, 'new@example.com')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['new@example.com'])
        self.assertIn('https://league.example.com/members/reset/', message.body)
        self.assertIn('24 hours', message.body)
        self.assertIn('newplayer', message.body)
        self.assertEqual(message.alternatives[0].mimetype, 'text/html')

    def test_invitee_can_set_password_and_login_but_cannot_reuse_link(self):
        self.invite()
        path = self.email_path()
        response = self.open_link(path)
        self.assertTrue(response.context['validlink'])
        form_path = response.redirect_chain[-1][0]
        response = self.client.post(form_path, {'new_password1': 'FreshPass456!', 'new_password2': 'FreshPass456!'})
        self.assertRedirects(response, reverse('password_reset_complete'))
        self.assertTrue(self.client.login(username='newplayer', password='FreshPass456!'))
        self.assertFalse(self.open_link(path).context['validlink'])

    def test_weak_and_mismatched_passwords_fail(self):
        self.invite()
        response = self.open_link(self.email_path())
        form_path = response.redirect_chain[-1][0]
        for first, second in [('password', 'password'), ('GoodPass456!', 'DifferentPass123!')]:
            response = self.client.post(form_path, {'new_password1': first, 'new_password2': second})
            self.assertTrue(response.context['form'].errors)
        self.assertFalse(User.objects.get(username='newplayer').has_usable_password())

    def test_duplicate_username_email_and_missing_email_rejected(self):
        for data in [
            {'username': 'player', 'email': 'other@example.com'},
            {'username': 'another', 'email': 'PLAYER@EXAMPLE.COM'},
            {'username': 'another', 'email': ''},
        ]:
            self.assertFalse(InviteForm(data).is_valid())
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('racinginvite', 'PLAYER@example.com')
        # Old accounts without email remain valid; no destructive migration is needed.
        User.objects.create_user('legacy_one')
        User.objects.create_user('legacy_two')

    def test_admin_email_edits_reject_duplicates(self):
        form = AccountChangeForm(instance=self.member)
        form.cleaned_data = {'email': ' ORGANIZER@example.com '}
        with self.assertRaisesMessage(Exception, 'already uses this email'):
            form.clean_email()

    def test_invitation_failure_preserves_account_for_retry(self):
        with patch('members.forms.send_mail', side_effect=OSError('mail unavailable')):
            response = self.invite()
        self.assertRedirects(response, reverse('member_accounts'))
        user = User.objects.get(username='newplayer')
        self.assertFalse(user.has_usable_password())
        response = self.client.post(reverse('member_account_action', args=[user.pk]), {'action': 'resend'})
        self.assertRedirects(response, reverse('member_accounts'))
        self.assertEqual(len(mail.outbox), 1)

    def test_existing_and_unknown_reset_requests_have_same_response(self):
        known = self.client.post(reverse('password_reset'), {'email': 'PLAYER@example.com'}, follow=True)
        unknown = self.client.post(reverse('password_reset'), {'email': 'unknown@example.com'}, follow=True)
        self.assertEqual(known.redirect_chain, unknown.redirect_chain)
        self.assertEqual(known.content, unknown.content)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_failure_returns_same_confirmation(self):
        with patch('members.forms.send_mail', side_effect=OSError('mail unavailable')):
            response = self.client.post(reverse('password_reset'), {'email': self.member.email})
        self.assertRedirects(response, reverse('password_reset_done'))

    def test_invited_user_can_request_a_new_setup_link(self):
        self.invite()
        self.client.logout()
        self.client.post(reverse('password_reset'), {'email': 'new@example.com'})
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Set up', mail.outbox[-1].subject)

    def test_invalid_and_expired_tokens_fail(self):
        with patch.object(account_token_generator, '_now', return_value=datetime.datetime(2026, 1, 1)):
            self.invite()
        path = self.email_path()
        with patch.object(account_token_generator, '_now', return_value=datetime.datetime(2026, 1, 3)):
            self.assertFalse(self.open_link(path).context['validlink'])
        self.assertFalse(self.client.get('/members/reset/invalid/invalid/').context['validlink'])

    def test_reset_changes_existing_password_and_invalidates_other_links(self):
        self.client.post(reverse('password_reset'), {'email': self.member.email})
        path = self.email_path()
        response = self.open_link(path)
        self.client.post(response.redirect_chain[-1][0], {'new_password1': 'FreshPass456!', 'new_password2': 'FreshPass456!'})
        self.assertFalse(self.client.login(username='player', password='OriginalPass123!'))
        self.assertTrue(self.client.login(username='player', password='FreshPass456!'))
        self.assertFalse(self.open_link(path).context['validlink'])

    def test_deactivation_blocks_login_session_reset_and_token_without_deleting_picks(self):
        pick = Pick.objects.create(user_name=self.member, team=Team.objects.create(team_name='Bills'), week=1)
        member_client = Client()
        member_client.force_login(self.member)
        send_password_link(self.member)
        path = self.email_path()
        self.client.force_login(self.staff)
        self.client.post(reverse('member_account_action', args=[self.member.pk]), {'action': 'deactivate'})
        self.assertTrue(Pick.objects.filter(pk=pick.pk, user_name=self.member).exists())
        self.assertFalse(self.client.login(username='player', password='OriginalPass123!'))
        self.assertFalse(self.open_link(path).context['validlink'])
        self.assertFalse(member_client.get('/').wsgi_request.user.is_authenticated)
        self.client.post(reverse('password_reset'), {'email': self.member.email})
        self.assertEqual(len(mail.outbox), 1)

    def test_staff_and_self_cannot_be_deactivated_or_reset_by_staff_controls(self):
        self.client.force_login(self.staff)
        for action in ('deactivate', 'resend'):
            response = self.client.post(reverse('member_account_action', args=[self.staff.pk]), {'action': action})
            self.assertEqual(response.status_code, 403)

    def test_actions_require_post_and_csrf(self):
        self.client.force_login(self.staff)
        url = reverse('member_account_action', args=[self.member.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        self.assertEqual(csrf_client.post(url, {'action': 'deactivate'}).status_code, 403)
        self.assertEqual(csrf_client.post(reverse('member_accounts'), {'username': 'x', 'email': 'x@example.com'}).status_code, 403)

    def test_password_change_keeps_current_session(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('password_change'), {
            'old_password': 'OriginalPass123!', 'new_password1': 'FreshPass456!', 'new_password2': 'FreshPass456!',
        }, follow=True)
        self.assertContains(response, 'Password changed')
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('FreshPass456!'))

    @override_settings(DEBUG=False, LEAGUE_SITE_URL='http://league.example.com')
    def test_production_email_requires_https(self):
        with self.assertRaises(ImproperlyConfigured):
            send_password_link(self.member)

    def test_request_host_cannot_change_email_link(self):
        with override_settings(ALLOWED_HOSTS=['*']):
            self.client.post(reverse('password_reset'), {'email': self.member.email}, HTTP_HOST='attacker.example.com')
        self.assertIn('https://league.example.com/', mail.outbox[0].body)
        self.assertNotIn('attacker.example.com', mail.outbox[0].body)
