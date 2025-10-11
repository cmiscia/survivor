from django.core.management.base import BaseCommand
from survivorPool.models import Team, Matchup
import requests
from datetime import datetime
import os

class Command(BaseCommand):
    help = 'Fetches NFL matchups and betting odds from The Odds API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week',
            type=int,
            help='NFL week number to fetch odds for',
        )

    def handle(self, *args, **options):
        # Get API key from environment (user will need to set this in Replit Secrets)
        api_key = os.environ.get('ODDS_API_KEY')
        
        if not api_key:
            self.stdout.write(
                self.style.ERROR('ODDS_API_KEY not found in environment variables.')
            )
            self.stdout.write(
                'Please set ODDS_API_KEY in Replit Secrets with your API key from https://the-odds-api.com/'
            )
            return
        
        week = options.get('week')
        if not week:
            self.stdout.write(self.style.ERROR('Please specify a week number with --week'))
            return

        # Fetch odds from The Odds API
        url = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds'
        params = {
            'apiKey': api_key,
            'regions': 'us',
            'markets': 'h2h,spreads',  # moneyline (h2h) and spreads
            'oddsFormat': 'american'
        }
        
        try:
            self.stdout.write('Fetching NFL odds from The Odds API...')
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # Check remaining API requests
            remaining_requests = response.headers.get('x-requests-remaining')
            if remaining_requests:
                self.stdout.write(f'API requests remaining: {remaining_requests}')
            
            games = response.json()
            self.stdout.write(f'Found {len(games)} games')
            
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            for game in games:
                home_team_name = self.extract_team_nickname(game['home_team'])
                away_team_name = self.extract_team_nickname(game['away_team'])
                
                # Find teams in database
                try:
                    home_team = Team.objects.get(team_name__iexact=home_team_name)
                    away_team = Team.objects.get(team_name__iexact=away_team_name)
                except Team.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Team not found: {home_team_name} or {away_team_name} - Skipping'
                        )
                    )
                    skipped_count += 1
                    continue
                
                # Parse game data
                game_id = game['id']
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                
                # Extract odds from first bookmaker (if available)
                spread = None
                favorite_team = None
                moneyline_home = None
                moneyline_away = None
                
                if game.get('bookmakers'):
                    bookmaker = game['bookmakers'][0]  # Use first bookmaker
                    
                    # Get spreads
                    spread_market = next((m for m in bookmaker['markets'] if m['key'] == 'spreads'), None)
                    if spread_market:
                        for outcome in spread_market['outcomes']:
                            if outcome['name'] == game['home_team']:
                                home_spread = outcome.get('point', 0)
                                if home_spread < 0:  # Negative spread means favorite
                                    favorite_team = home_team
                                    spread = abs(home_spread)
                            elif outcome['name'] == game['away_team']:
                                away_spread = outcome.get('point', 0)
                                if away_spread < 0:  # Negative spread means favorite
                                    favorite_team = away_team
                                    spread = abs(away_spread)
                    
                    # Get moneyline
                    h2h_market = next((m for m in bookmaker['markets'] if m['key'] == 'h2h'), None)
                    if h2h_market:
                        for outcome in h2h_market['outcomes']:
                            if outcome['name'] == game['home_team']:
                                moneyline_home = outcome['price']
                            elif outcome['name'] == game['away_team']:
                                moneyline_away = outcome['price']
                
                # Create or update matchup
                matchup, created = Matchup.objects.update_or_create(
                    game_id=game_id,
                    defaults={
                        'week': week,
                        'home_team': home_team,
                        'away_team': away_team,
                        'commence_time': commence_time,
                        'spread': spread,
                        'favorite_team': favorite_team,
                        'moneyline_home': moneyline_home,
                        'moneyline_away': moneyline_away,
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created: {away_team} @ {home_team} (Week {week})')
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Updated: {away_team} @ {home_team} (Week {week})')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nCompleted! Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}'
                )
            )
            
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'Error fetching data from The Odds API: {str(e)}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )

    def extract_team_nickname(self, full_name):
        """Extract team nickname from full name (e.g., 'Kansas City Chiefs' -> 'Chiefs')"""
        return full_name.split()[-1]
