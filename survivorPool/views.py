from typing import Any, Dict
from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django_tables2 import SingleTableView
from .models import Pick, User, Team
from django.urls import reverse_lazy
from .forms import PostForm
from .tables import PickTable
import pandas as pd
import datetime
from django.contrib.auth.models import User

LEADERBOARD_COLUMNS = [
    'User Name',
    'Team',
    "IsWin",
    "Week"
]


# Create your views here.
#def index(request):
    #return HttpResponse("Hello, world. You're at the Survivor Pool index.")

class HomeView(ListView):
    model = Pick
    template_name = 'home.html'
    ordering = ['week']

class AddPickView(CreateView):
    model = Pick
    form_class = PostForm
    template_name = 'add_pick.html'
    #fields = ['team', 'user_name', 'week']

class PickDetailView(DetailView):
    model = Pick
    template_name = 'pick_details.html'

class UpdatePickView(UpdateView):
    model = Pick
    template_name = 'update_pick.html'
    fields = ['team']

class DeletePickView(DeleteView):
    model = Pick
    template_name = 'delete_pick.html'
    fields = ['week']
    success_url = reverse_lazy('home')

class PickView(SingleTableView):
    model = Pick
    table_class = PickTable
    template_name = 'leaderboard.html'

def buildPickDataFrame():
    userMapping = {}
    teamMapping = {}
    pickList = []
    users = list(User.objects.all().values())
    picks = list(Pick.objects.all().values())
    teams = list(Team.objects.all().values())

    for user in users:
        id = user.get("id")
        userMapping[id] = user.get('username')
    
    for team in teams:
        id = team.get("id")
        teamMapping[id] = team.get('team_name')

    
    for pick in picks:
        pickUserName = userMapping.get(pick['user_name_id'])
        pickTeam = teamMapping.get(pick['team_id'])
        isWin = pick.get('is_win')
        week = pick.get('week')
        pickList.append((pickUserName, pickTeam, isWin, week) )
    
    df = pd.DataFrame(pickList, columns=LEADERBOARD_COLUMNS)
    return df

def modelToDataFrame(request):
    ''' Builds a dataframe to display the league leaderboard'''
    df = buildPickDataFrame()
    
    #create leaderboard Note: will only work once there is a pick for first week
    df['Win Count'] = df[df["IsWin"]].groupby("User Name")["IsWin"].transform("sum")
    dfLeaderBoard = df.loc[df['Week'] == 1, ['User Name', 'Win Count']]
    dfLeaderBoard.sort_values('Win Count')

    print(dfLeaderBoard)

    context = {
        'df': dfLeaderBoard.to_html(classes=["table-bordered", "table-striped", "table-hover"], index=False),
        

    }

    return render(request, 'league_leaderboard.html', context)

def allPicksView(request):
    '''Builds a dataframe to display all picks up to given week'''
    df = buildPickDataFrame()

    #tweak dataframe to create a view of all picks up to current week sorted by week chronologically
    # df['Combined'] = df['Team'] + '_' + df['IsWin'].astype(str)
    df = df.sort_values(by=['Week'])
    df = df.pivot(index=['User Name'], columns='Week', values='Team')
    df = df.rename_axis(columns=None).reset_index()
    df = df.fillna("Not Picked")

    print(df)

    context = {
        'df': df.to_html(classes=["table-bordered", "table-striped", "table-hover"], index=False),
    }

    return render(request, 'allPicks.html', context)
    
    

        

