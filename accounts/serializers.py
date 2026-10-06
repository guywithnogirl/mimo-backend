from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class TwoUserTokenSerializer(TokenObtainPairSerializer):
    """Issue credentials only to the two explicitly configured account names."""

    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.get_username() not in settings.AUTHORIZED_USERNAMES:
            raise AuthenticationFailed("Invalid credentials")
        return data
