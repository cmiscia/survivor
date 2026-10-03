from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('auth', '0012_alter_user_first_name_max_length')]

    # Preserve Django's user model and existing blank emails. Legacy conflicts
    # must be resolved by staff before deployment, never merged automatically.
    operations = [
        migrations.RunSQL(
            "CREATE UNIQUE INDEX members_user_email_unique ON auth_user (LOWER(email)) WHERE email <> '';",
            'DROP INDEX members_user_email_unique;',
        ),
    ]
