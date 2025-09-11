from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload, name='excel_merge_upload'),
]
