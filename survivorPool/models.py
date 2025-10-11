from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from django.urls import reverse

class Team(models.Model):
    team_name = models.CharField(max_length=50)
    is_favorite = models.BooleanField(default=False)

    def __str__(self):
        return str(self.team_name)

class Matchup(models.Model):
    game_id = models.CharField(max_length=100, unique=True)
    week = models.IntegerField()
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_games')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_games')
    commence_time = models.DateTimeField()
    spread = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    favorite_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='favored_games')
    moneyline_home = models.IntegerField(null=True, blank=True)  # American odds format
    moneyline_away = models.IntegerField(null=True, blank=True)  # American odds format
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('week', 'home_team', 'away_team')
        ordering = ['week', 'commence_time']

    def __str__(self):
        return f"Week {self.week}: {self.away_team} @ {self.home_team}"
    
    def get_opponent(self, team):
        """Given a team, return their opponent in this matchup"""
        if self.home_team == team:
            return self.away_team
        elif self.away_team == team:
            return self.home_team
        return None

class Pick(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    user_name = models.ForeignKey(User, on_delete=models.CASCADE)
    publication_date = models.DateTimeField("date published", default=datetime.now)
    week = models.IntegerField()
    is_win = models.BooleanField(null=True, blank=True, default=None)

    class Meta:
        unique_together = ('user_name', 'week')

    def __str__(self):
        return str(self.team) + ' | ' + str(self.user_name)
    
    def get_absolute_url(self):
        return reverse('home') 
    
    

