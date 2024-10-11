from django.urls import path
#from . import views
from .views import HomeView, AddPickView, PickDetailView, UpdatePickView, DeletePickView, PickView, modelToDataFrame, allPicksView

urlpatterns = [
    #path("", views.index, name="index"),
    path('', HomeView.as_view(), name="home"),
    path('add_pick/', AddPickView.as_view(), name="add_pick"),
    path('pick_details/<int:pk>', PickDetailView.as_view(), name="pick_details"),
    path('pick/edit/<int:pk>', UpdatePickView.as_view(), name="edit_pick"),
    path('pick/delete/<int:pk>', DeletePickView.as_view(), name="delete_pick"),
    path('leaderboard/', PickView.as_view(), name="leaderboard"),
    path('league_leaderboard/', modelToDataFrame, name="league_leaderboard"),
    path('allPicks/', allPicksView, name="allPicks"),
]