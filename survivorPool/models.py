from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from django.urls import reverse

class Team(models.Model):
    team_name = models.CharField(max_length=50)
    is_favorite = models.BooleanField(default=False)

    def __str__(self):
        favorite = " - Is Favorite" if self.is_favorite else " "
        return str(self.team_name) + favorite

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
    
    

