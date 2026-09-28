from django.urls import path
from . import views

app_name = "supplier-return"

urlpatterns = [
    path("api/returns/", views.returns, name="returns"),
    path("api/returns/<int:pk>/", views.return_detail, name="return-detail"),
    path("api/returns/<int:pk>/lines/", views.add_line, name="add-line"),
    path("api/returns/<int:pk>/ready/", views.ready, name="ready"),
    path("api/returns/<int:pk>/ship/", views.ship, name="ship"),
    path("api/returns/<int:pk>/lines/<int:line_pk>/receive/", views.receive, name="receive"),
    path("api/returns/<int:pk>/lines/<int:line_pk>/resolve/", views.resolve, name="resolve"),
]
