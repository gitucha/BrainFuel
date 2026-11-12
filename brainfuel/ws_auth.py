"""
JWT authentication for WebSocket connections.

The frontend logs in with SimpleJWT and keeps the access token in
localStorage, so there is no Django session cookie for Channels'
AuthMiddlewareStack to read. Browsers can't set headers on WebSocket
requests, so the client sends the token as ?token=<access> instead.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_token(raw_token):
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        token = AccessToken(raw_token)
        return get_user_model().objects.get(pk=token["user_id"])
    except (InvalidToken, TokenError, KeyError, get_user_model().DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        if token:
            scope["user"] = await _user_from_token(token)
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    # Fall back to session auth (e.g. Django admin) when no token is sent.
    from channels.auth import AuthMiddlewareStack

    return AuthMiddlewareStack(JWTAuthMiddleware(inner))
