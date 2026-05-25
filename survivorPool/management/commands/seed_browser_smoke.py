import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from survivorPool.models import ChatMessage, Game, Pick, SeasonSettings, Team, WeekLockRun


class Command(BaseCommand):
    help = "Seed deterministic local data for Playwright browser smoke tests."

    def handle(self, *args, **options):
        WeekLockRun.objects.all().delete()
        ChatMessage.objects.all().delete()
        Pick.objects.all().delete()
        Game.objects.all().delete()
        Team.objects.all().delete()
        User.objects.filter(username__in=['browser_user', 'rival_player', 'admin_user']).delete()

        browser_user = User.objects.create_user(
            username='browser_user',
            password='Test4321!',
            email='browser@example.com',
        )
        rival = User.objects.create_user(
            username='rival_player',
            password='Test4321!',
            email='rival@example.com',
        )
        User.objects.create_superuser(
            username='admin_user',
            password='Test4321!',
            email='admin@example.com',
        )

        teams = {
            name: Team.objects.create(team_name=name)
            for name in [
                'Bills',
                'Dolphins',
                'Packers',
                'Bears',
                'Chiefs',
                'Raiders',
                'Patriots',
                'Jets',
            ]
        }

        SeasonSettings.objects.update_or_create(
            season_year=settings.NFL_SEASON_YEAR,
            defaults={
                'buy_in': Decimal('50.00'),
                'loss_amount': Decimal('10.00'),
                'favorite_loss_amount': Decimal('25.00'),
                'underdog_half_threshold': Decimal('5.00'),
            },
        )

        base = timezone.make_aware(
            datetime.datetime(settings.NFL_SEASON_YEAR, 9, 13, 13, 0),
            timezone.get_current_timezone(),
        )
        games = [
            (1, 'Bills', 'Dolphins', 0, True),
            (1, 'Packers', 'Bears', 3, False),
            (2, 'Chiefs', 'Raiders', 7, True),
            (2, 'Jets', 'Patriots', 7, False),
            (7, 'Patriots', 'Bills', 42, True),
            (7, 'Bears', 'Packers', 42, False),
        ]
        for week, home, away, days_offset, home_favorite in games:
            Game.objects.create(
                season_year=settings.NFL_SEASON_YEAR,
                week=week,
                home_team=teams[home],
                away_team=teams[away],
                game_time=base + datetime.timedelta(days=days_offset),
                home_spread=Decimal('3.5') if home_favorite else None,
                away_spread=None if home_favorite else Decimal('2.5'),
                home_moneyline=-150 if home_favorite else 120,
                away_moneyline=130 if home_favorite else -135,
                home_is_favorite=home_favorite,
                away_is_favorite=not home_favorite,
            )

        Pick.objects.create(user_name=browser_user, team=teams['Bills'], week=7, is_win=None)
        Pick.objects.create(user_name=browser_user, team=teams['Chiefs'], week=2, is_win=True)
        Pick.objects.create(user_name=rival, team=teams['Dolphins'], week=1, is_win=False)
        Pick.objects.create(user_name=rival, team=teams['Packers'], week=2, is_win=True)

        for i in range(205):
            ChatMessage.objects.create(
                author=browser_user if i % 2 == 0 else rival,
                body=f'Browser smoke message {i}',
            )

        ChatMessage.objects.create(
            author=None,
            body='Week 7 locked. Shame corner: no missed picks.',
            message_type=ChatMessage.MESSAGE_WEEKLY_LOCK,
            week=7,
        )

        self.stdout.write(self.style.SUCCESS('Seeded browser smoke data.'))
