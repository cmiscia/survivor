from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # Django invalidates on password/email change and login; also bind activity.
        return super()._make_hash_value(user, timestamp) + str(user.is_active)


account_token_generator = AccountTokenGenerator()
