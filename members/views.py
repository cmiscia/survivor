import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, views as auth_views
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import InviteForm, LeaguePasswordResetForm, send_password_link
from .tokens import account_token_generator

logger = logging.getLogger(__name__)
User = get_user_model()


@staff_member_required(login_url='login')
def accounts(request):
    form = InviteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error(None, 'That username or email is already in use.')
        else:
            # Keep the account if delivery fails, so staff can retry without recreating it.
            try:
                send_password_link(user, invitation=True)
            except Exception:
                logger.error('Invitation email delivery failed for user ID %s', user.pk)
                messages.error(request, 'Account created, but email delivery failed. Check email configuration, then resend the link.')
            else:
                messages.success(request, 'Account created and invitation sent.')
            return redirect('member_accounts')
    return render(request, 'members/accounts.html', {
        'form': form,
        'accounts': User.objects.order_by('username'),
    })


@staff_member_required(login_url='login')
@require_POST
def account_action(request, pk):
    user = get_object_or_404(User, pk=pk)
    # Ordinary staff manage league participants, not their own or other staff access.
    if user.pk == request.user.pk or user.is_staff or user.is_superuser:
        return HttpResponseForbidden('Use the admin console to manage staff accounts.')
    action = request.POST.get('action')
    if action == 'deactivate':
        user.is_active = False
        user.save(update_fields=['is_active'])
        messages.success(request, 'Account deactivated. Existing picks are preserved.')
    elif action == 'resend' and user.is_active:
        try:
            send_password_link(user, invitation=not user.has_usable_password())
        except Exception:
            logger.error('Account email delivery failed for user ID %s', user.pk)
            messages.error(request, 'Could not send the link. Check the account email and email configuration, then retry.')
        else:
            messages.success(request, 'Password setup/reset link sent.')
    else:
        messages.error(request, 'That action is unavailable for this account.')
    return redirect('member_accounts')


class PasswordResetView(auth_views.PasswordResetView):
    template_name = 'members/password_reset_form.html'
    form_class = LeaguePasswordResetForm
    token_generator = account_token_generator

    def form_valid(self, form):
        # Delivery failures must not reveal whether the submitted account exists.
        try:
            form.send_links()
        except Exception:
            logger.error('Password reset email delivery failed')
        return redirect(self.get_success_url())


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'members/password_reset_confirm.html'
    token_generator = account_token_generator

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        return user if user and user.is_active else None
