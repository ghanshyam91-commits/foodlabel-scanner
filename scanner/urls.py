from django.urls import path
from . import views
urlpatterns = [path('', views.index), path('health/', views.health), path('api/config/', views.config),
    path('api/unlock/', views.unlock), path('api/logout/', views.logout), path('api/scan/', views.scan),
    path('api/examples/<str:name>/', views.example)]
