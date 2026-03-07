"""
Search API URL Configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.search.views import SearchViewSet, CacheManagementViewSet, search_api

router = DefaultRouter()
router.register(r'search', SearchViewSet, basename='search')
router.register(r'cache', CacheManagementViewSet, basename='cache')

urlpatterns = [
    path('', include(router.urls)),
    path('quick-search/', search_api, name='quick-search'),
]
