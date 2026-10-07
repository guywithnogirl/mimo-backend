from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .pagination import MessagePagination
from .serializers import ConversationSerializer, MessageCreateSerializer, MessageSerializer
from .services import get_authorized_conversation_for


class ConversationListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        conversation = get_authorized_conversation_for(request.user)
        return Response([ConversationSerializer(conversation).data])


class ConversationDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, conversation_id):
        if request.user.get_username() not in settings.AUTHORIZED_USERNAMES:
            raise NotFound("Conversation not found.")
        conversation = get_object_or_404(
            Conversation.objects.filter(
                Q(first_member=request.user) | Q(second_member=request.user)
            ),
            pk=conversation_id,
        )
        return Response(ConversationSerializer(conversation).data)


class ConversationMessagesView(APIView):
    permission_classes = (IsAuthenticated,)
    pagination_class = MessagePagination

    def get_conversation(self, request, conversation_id):
        if request.user.get_username() not in settings.AUTHORIZED_USERNAMES:
            raise NotFound("Conversation not found.")
        return get_object_or_404(
            Conversation.objects.filter(
                Q(first_member=request.user) | Q(second_member=request.user)
            ),
            pk=conversation_id,
        )

    def get(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)
        messages = conversation.messages.select_related("sender").order_by("created_at", "id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(messages, request, view=self)
        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(conversation=conversation, sender=request.user)
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
