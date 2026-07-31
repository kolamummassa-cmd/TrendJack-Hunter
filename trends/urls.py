from django.urls import path
from . import views

app_name = 'trends'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('<int:pk>/', views.trend_detail, name='trend_detail'),
    path('<int:pk>/generate-brief/', views.generate_brief, name='generate_brief'),
    path('refresh/', views.refresh_trends, name='refresh_trends'),
    path('internal/expire-trends/', views.trigger_expire_trends, name='trigger_expire_trends'),
]
