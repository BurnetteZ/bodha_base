from django.urls import path
from . import views

app_name = "benford"

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload, name="upload"),
    path("status/<str:job_id>/", views.status, name="status"),
]
