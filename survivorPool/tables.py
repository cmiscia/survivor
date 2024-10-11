import django_tables2 as tables
from .models import Pick

class PickTable(tables.Table):
    class Meta:
        model = Pick
        template_name = "django_tables2/bootstrap.html"
        fields = ("week", "user_name", "team", )