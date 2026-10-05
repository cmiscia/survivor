from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from survivorPool.utils import all_week_games_started, get_current_nfl_week


class Command(BaseCommand):
    help = (
        'Finalize the selected week, create automatic losses for missing picks, '
        'then fetch and post game results.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--week', type=int, help='NFL week number (default: current week)')

    def handle(self, *args, **options):
        week = options['week'] or get_current_nfl_week()
        if not all_week_games_started(week):
            raise CommandError(
                f'Week {week} still has games available. Results cannot be posted yet.'
            )

        call_command(
            'lock_week_and_post_chat',
            week=week,
            force=True,
            stdout=self.stdout,
            stderr=self.stderr,
        )
        call_command(
            'fetch_nfl_winners',
            week=week,
            stdout=self.stdout,
            stderr=self.stderr,
        )