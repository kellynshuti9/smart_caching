from rest_framework import serializers
from .models import Post


class PostSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Post
        fields = ["id", "title", "body", "author", "author_username", "status", "created_at"]
        read_only_fields = ["author", "created_at"]