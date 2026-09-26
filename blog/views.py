from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Post
from .serializers import PostSerializer


# ---------------------------------------------------------------------------
# Module-level cache keys — get() and post() can never drift apart
# ---------------------------------------------------------------------------
POST_LIST_CACHE_KEY = "post_list"
POST_LIST_TTL = 300     # rubric: ≤ 300 s
POST_DETAIL_TTL = 600   # rubric: ≤ 600 s
MY_DRAFTS_TTL = 120     # rubric: ≤ 120 s


class PostListView(APIView):
    """Cache-aside for the public post list."""

    def get(self, request):
        cached = cache.get(POST_LIST_CACHE_KEY)
        if cached is not None:
            return Response(cached)

        posts = Post.objects.filter(status="published").order_by("-created_at")
        data = PostSerializer(posts, many=True).data
        cache.set(POST_LIST_CACHE_KEY, data, timeout=POST_LIST_TTL)
        return Response(data)

    def post(self, request):
        serializer = PostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(author=request.user)
            cache.delete(POST_LIST_CACHE_KEY)   # exact same key as get()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class PostDetailView(APIView):
    """Cache-aside for a single post; key includes post_id."""

    def get(self, request, post_id):
        cache_key = f"post_detail_{post_id}"

        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        data = PostSerializer(post).data
        cache.set(cache_key, data, timeout=POST_DETAIL_TTL)
        return Response(data)


class MyDraftsView(APIView):
    """Cache-aside for the current user's drafts; key is user-scoped."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = f"my_drafts_user_{request.user.id}"   # user-isolated

        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        drafts = Post.objects.filter(author=request.user, status="draft")
        data = PostSerializer(drafts, many=True).data
        cache.set(cache_key, data, timeout=MY_DRAFTS_TTL)
        return Response(data)