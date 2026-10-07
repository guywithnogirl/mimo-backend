import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Conversation(models.Model):
    """The one private conversation shared by the two configured users."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="first_private_conversations",
    )
    second_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="second_private_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(first_member__lt=F("second_member")),
                name="conversation_members_canonical",
            ),
            models.UniqueConstraint(
                fields=("first_member", "second_member"),
                name="unique_private_conversation_pair",
            ),
        ]

    def __str__(self):
        return f"Private conversation {self.pk}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_private_messages",
    )
    content = models.CharField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=("conversation", "created_at", "id"),
                name="message_conversation_order_idx",
            ),
        ]

    def __str__(self):
        return f"Message {self.pk}"
