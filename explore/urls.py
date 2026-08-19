from django.urls import path

from . import views

urlpatterns = [
    path("", views.discover_view, name="home"),
    path("discover/", views.discover_view, name="discover"),
    path("search/", views.search_view, name="search"),
    path("trending/", views.trending_view, name="trending"),
    path("api/v1/search/", views.api_search, name="api_search"),
]
