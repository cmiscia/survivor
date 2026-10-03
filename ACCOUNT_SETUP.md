# Invite-only accounts and Resend

Existing Django users, passwords, IDs, and picks remain in place. Public registration
is removed. Active staff use **League Accounts** to invite one username/email,
resend setup/reset links, or deactivate a non-staff participant. Deactivation
preserves picks and blocks login, existing sessions, and password setup/reset.
Staff access and email corrections remain in Django Admin for authorized admins.

## Before deployment

1. Back up the production database. Development and production may share Neon;
   never seed, test, or migrate against an inherited connection accidentally.
2. Check nonblank email duplicates, without changing records:
   ```sql
   SELECT LOWER(email), COUNT(*) FROM auth_user
   WHERE email <> '' GROUP BY LOWER(email) HAVING COUNT(*) > 1;
   ```
   Resolve each conflict with the organizer. Do not merge users or assign emails
   by guessing. The migration adds a case-insensitive unique index to Django's
   existing user table and intentionally fails if conflicts exist. Blank legacy
   emails are permitted; those users can still log in but need a verified email
   supplied by an administrator before password reset works.
3. Set the environment variables below. Keep `DJANGO_SECRET_KEY` stable; changing
   it invalidates existing sessions and links. Set explicit `DJANGO_ALLOWED_HOSTS`
   where the host supports them and keep `DJANGO_DEBUG=False` in production.
4. Configure shared edge/proxy rate limits before exposing the account endpoints.
   Django's built-in auth views do not throttle. Suggested starting policy:
   login POSTs (`/members/login/`, `/admin/login/`): 10 per minute per client IP;
   reset POSTs (`/members/password_reset/`): 3 per hour per client IP, plus a
   global email budget below the Resend plan's daily cap. Staff invitation/resend
   POSTs also consume that budget. Use the trusted edge's actual client IP,
   never an arbitrary forwarded header. Validate limits across app replicas and
   check that successful requests resume after the window. Per-IP limits alone
   do not stop distributed attacks. If the hosting edge cannot enforce this,
   implement a shared server-side limiter before launch. No application throttle
   is included in this change.
5. Run `python manage.py migrate --plan`, review, then `python manage.py migrate`.
   The migration changes only an index, not user or pick data. Deploy code and
   collected static assets together using `python manage.py collectstatic --noinput`.
6. With permission, invite one controlled test recipient and verify receipt,
   HTTPS link origin, password setup, login, reset, and deactivation before inviting
   the league. An SMTP success is provider acceptance, not proof of inbox delivery.

## Resend configuration

Register/use a domain controlled by the league. A Replit-provided shared domain
or a Gmail address cannot be verified as your sending domain. The sending domain
can differ from the website domain. A mailbox subscription is not required to
send, but the From address should be monitored or have forwarding for replies.

In Resend, add the sending domain (a subdomain such as `mail.example.com` is also
fine). Add the exact SPF/DKIM records Resend provides at your DNS provider, then
verify the domain. Review DMARC for the domain and use monitoring before tightening
policy; do not replace existing DNS/mail records blindly. Disable click/open
tracking for password emails, which contain bearer links.

Set these in deployment secrets/environment, never in source control:

| Variable | Value |
| --- | --- |
| `LEAGUE_SITE_URL` | The actual public HTTPS origin, e.g. `https://your-league.replit.app` (no path). This is the website, not necessarily the sending domain. |
| `DEFAULT_FROM_EMAIL` | `Survivor Pool <league@your-verified-domain.com>` |
| `RESEND_API_KEY` | Resend sending key restricted to the verified domain where possible |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | `smtp.resend.com` (default) |
| `EMAIL_PORT` | `587` (default; STARTTLS enabled) |
| `EMAIL_HOST_USER` | `resend` (default) |
| `PASSWORD_RESET_TIMEOUT` | `86400` seconds (default: 24 hours for setup/reset) |

SMTP has a 10-second timeout. Staff see delivery errors and can retry. Account
creation remains saved if sending fails; avoid duplicate invitations by using
the existing account's resend control. Public reset requests always show the
same confirmation, including for missing/inactive users or delivery failures.
Logs identify staff-send failures by user ID only and never log tokens or keys.
Resend's dashboard supplies provider delivery/bounce status; resolve failed or
bounced addresses with the organizer before resending. There is no automatic
retry queue or background email worker.

The free tier currently permits 3,000 emails/month and 100/day. Budget all
invitations and resets together. This feature sends no weekly reminders.

## Local verification

Explicitly clear `NEON_DATABASE_URL`, `PGHOST`, and `SENTRY_DSN`, and set a local
`DATABASE_URL` before any management command. Example PowerShell:

```powershell
$env:NEON_DATABASE_URL=''
$env:PGHOST=''
$env:SENTRY_DSN=''
$env:DATABASE_URL='sqlite:///account-local.sqlite3'
$env:DJANGO_DEBUG='True'
$env:DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1,testserver'
$env:LEAGUE_SITE_URL='http://127.0.0.1:8005'
$env:EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
python manage.py check
python manage.py makemigrations survivorPool members --check --dry-run
python manage.py test survivorPool members
```

Console email stays local; test cases use the in-memory outbox. Browser tests use
only an isolated database and fake accounts. Never put production credentials in
test environments. Test links printed locally are credentials too; don't share
logs containing live tokens.

For a code rollback, revert the application deployment; the unique index can
remain. To remove the index deliberately, reverse only this app migration with
`python manage.py migrate members zero` after reviewing the plan. Neither action
deletes accounts/picks. Invited accounts with no password need the new setup flow
restored to finish onboarding.

References: [Resend SMTP](https://resend.com/docs/send-with-smtp),
[domain verification](https://resend.com/docs/dashboard/domains/introduction),
[pricing](https://resend.com/pricing).
