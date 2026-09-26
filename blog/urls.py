from django.urls import path
from .views import PostListView, PostDetailView, MyDraftsView

urlpatterns = [
    path("posts/", PostListView.as_view(), name="post-list"),
    path("posts/<int:post_id>/", PostDetailView.as_view(), name="post-detail"),
    path("my-drafts/", MyDraftsView.as_view(), name="my-drafts"),
]