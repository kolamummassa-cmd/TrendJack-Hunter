"""
Root URL configuration for Trendjack Hunter.

Delegates to each app's own urls.py to keep routing modular:
- '' (homepage)        -> core app
- 'trends/'            -> trends app (dashboard + trend detail)
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('trends/', include('trends.urls')),
    path('accounts/', include('accounts.urls')),
]
