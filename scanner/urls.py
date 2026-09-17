from django.urls import path
from . import views, auth
urlpatterns = [path('', views.index), path('health/', views.health), path('api/config/', views.config),
    path('api/usage/',views.usage),
    path('auth/google/',auth.google_start),path('auth/google/callback/',auth.google_callback),path('auth/pin/setup/',auth.pin_setup),path('auth/pin/unlock/',auth.pin_unlock),path('auth/logout/',auth.sign_out),
    path('api/unlock/', views.unlock), path('api/logout/', views.logout), path('api/scan/', views.scan),
    path('api/examples/<str:name>/', views.example)]
