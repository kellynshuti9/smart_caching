# Smart Caching — Django REST Blog API

A Django REST API for a blog with 500 posts and 3 users. The API is wrapped in a
level-by-level cache layer so it is fast, correct, and secure.

## Endpoints

| Method | URL | Cache | TTL | Key |
|---|---|---|---|---|
| GET | `/api/posts/` | cache-aside | 300 s | `post_list` |
| POST | `/api/posts/` | invalidates | — | `cache.delete("post_list")` |
| GET | `/api/posts/<id>/` | cache-aside | 600 s | `post_detail_<id>` |
| GET | `/api/my-drafts/` | cache-aside, user-scoped | 120 s | `my_drafts_user_<user_id>` |

## Setup

```bash
python -m venv venv
venv\Scripts\activate           # Windows
pip install -r requirements.txt
python manage.py migrate
python seed.py                  # creates 3 users + 500 posts
python manage.py runserver
```

Test users (all passwords `password123`): `alice`, `bob`, `carol`.

## Cache design

- **PostListView** — the published list is cached under one constant key
  `POST_LIST_CACHE_KEY = "post_list"` for 300 s. On `POST`, the same constant
  is passed to `cache.delete`, so the key can never drift between the view and
  the invalidator.
- **PostDetailView** — the key is `f"post_detail_{post_id}"`, so post 1 and
  post 2 occupy different cache slots. TTL is 600 s.
- **MyDraftsView** — the key is `f"my_drafts_user_{request.user.id}"`, so each
  user has a private cache slot. TTL is 120 s. The view requires
  `IsAuthenticated`.

## Security analysis — the `BrokenDraftsView` vulnerability

The rubric requires an explicit explanation of why a **non-user-scoped** cache
key in `MyDraftsView` is a security vulnerability. Here it is.

### The broken version

```python
class BrokenDraftsView(APIView):
    def get(self, request):
        cache_key = "my_drafts"          # ❌ no user ID — shared across all users
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        drafts = Post.objects.filter(author=request.user, status="draft")
        data = PostSerializer(drafts, many=True).data
        cache.set(cache_key, data, timeout=120)
        return Response(data)
```

### Why it leaks private data — step by step

1. **Alice** (`user.id = 1`) calls `GET /api/my-drafts/`.
   The cache is cold, so the DB returns **Alice's private drafts**, and the
   serializer output is stored under the shared key `"my_drafts"`.
2. **Bob** (`user.id = 2`) calls `GET /api/my-drafts/` within the 120-second
   TTL. `cache.get("my_drafts")` **hits**. Bob never reaches the database, so
   he is served **Alice's drafts**.
3. **Carol** (`user.id = 3`) calls the endpoint too. She also receives Alice's
   drafts.

In other words: **without `request.user.id` in the key, one user's private
drafts are returned to every other user who requests the endpoint.** This is a
horizontal privilege escalation / data leak — Alice's unpublished work is
exposed to Bob and Carol with no authentication check able to stop it, because
the response never touches the database on a cache hit.

### The fix

```python
cache_key = f"my_drafts_user_{request.user.id}"   # ✅ per-user slot
```

Alice's cache entry is `my_drafts_user_1`, Bob's is `my_drafts_user_2`, and
Carol's is `my_drafts_user_3`. They can never collide, so no user can ever be
served another user's cached drafts.

### Defense in depth

- Invalidate `f"my_drafts_user_{request.user.id}"` whenever the user creates,
  edits, or deletes a draft.
- Never cache sensitive, user-specific data under a key that does not include
  the requesting user's identity.
- In multi-tenant systems, prefix keys with the tenant/org ID as well.

## Authors

- Kelly Nshuti Dushimimana — Cache layer (public caches + invalidation)
- Grace Umuwari — Security & user-isolation (MyDraftsView + analysis)