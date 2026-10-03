from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .forms import AccountChangeForm


class LeagueUserAdmin(UserAdmin):
    form = AccountChangeForm


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), LeagueUserAdmin)
