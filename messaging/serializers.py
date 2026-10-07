from rest_framework import serializers

from .models import Conversation, Message


class ConversationMemberSerializer(serializers.Serializer):
    username = serializers.CharField(read_only=True)


class ConversationSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "members", "created_at")
        read_only_fields = fields

    def get_members(self, conversation):
        return ConversationMemberSerializer(
            (conversation.first_member, conversation.second_member), many=True
        ).data


class MessageSenderSerializer(serializers.Serializer):
    username = serializers.CharField(read_only=True)


class MessageSerializer(serializers.ModelSerializer):
    sender = MessageSenderSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ("id", "sender", "content", "created_at")
        read_only_fields = ("id", "sender", "created_at")


class MessageCreateSerializer(serializers.ModelSerializer):
    content = serializers.CharField(max_length=4000, allow_blank=False, trim_whitespace=True)

    class Meta:
        model = Message
        fields = ("content",)

    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            extra_fields = set(data.keys()) - {"content"}
            if extra_fields:
                raise serializers.ValidationError(
                    {field: "This field is not accepted." for field in sorted(extra_fields)}
                )
        return super().to_internal_value(data)
