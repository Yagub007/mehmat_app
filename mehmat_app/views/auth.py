"""Authentication views (Telegram Mini App)."""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from mehmat_app.serializers.auth import TelegramAuthSerializer, TokenPairSerializer
from mehmat_app.serializers.user import UserSerializer
from mehmat_app.services.telegram import authenticate_telegram_user
from mehmat_app.throttles import TelegramAuthThrottle


class TelegramAuthView(APIView):
    """Authenticate a Telegram Mini App user from ``initData``.

    Verifies the Telegram signature server-side, provisions the user on first
    login, and returns a JWT access/refresh pair.
    """

    # A JWT authenticator is declared (though the endpoint is open) so that a
    # failed Telegram verification yields a proper 401 with a WWW-Authenticate
    # header rather than a 403.
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [TelegramAuthThrottle]

    @extend_schema(
        request=TelegramAuthSerializer,
        responses={200: TokenPairSerializer},
        summary="Authenticate via Telegram initData",
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        serializer = TelegramAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, created = authenticate_telegram_user(
            serializer.validated_data["init_data"]
        )
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        refresh = RefreshToken.for_user(user)
        payload = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            "created": created,
        }
        return Response(payload, status=status.HTTP_200_OK)
