from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound

from .models import Conversation


class ConversationUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The private conversation is not ready."
    default_code = "conversation_unavailable"


def get_authorized_conversation_for(user):
    """Return the fixed pair's conversation, creating it on first use."""
    if user.get_username() not in settings.AUTHORIZED_USERNAMES:
        raise NotFound("Conversation not found.")

    user_model = get_user_model()
    users = list(
        user_model.objects.filter(username__in=settings.AUTHORIZED_USERNAMES).order_by("pk")
    )
    if len(users) != 2:
        raise ConversationUnavailable()

    first_member, second_member = users
    with transaction.atomic():
        conversation, _created = Conversation.objects.get_or_create(
            first_member=first_member,
            second_member=second_member,
        )
    return conversation
