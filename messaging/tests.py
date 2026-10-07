from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Conversation, Message


@override_settings(AUTHORIZED_USERNAMES=("alice", "bob"))
class ConversationAndMessageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.alice = user_model.objects.create_user(username="alice", password="alice-test-password")
        cls.bob = user_model.objects.create_user(username="bob", password="bob-test-password")
        cls.outsider = user_model.objects.create_user(
            username="outsider", password="outsider-test-password"
        )

    def setUp(self):
        self.client = APIClient()

    def get_conversation(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get("/api/conversations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        return response.json()[0]

    def test_authorized_users_share_the_same_conversation(self):
        conversation = self.get_conversation()
        self.assertEqual(
            conversation["members"], [{"username": "alice"}, {"username": "bob"}]
        )

        self.client.force_authenticate(self.bob)
        list_response = self.client.get("/api/conversations/")
        detail_response = self.client.get(f"/api/conversations/{conversation['id']}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["id"], conversation["id"])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["id"], conversation["id"])

    def test_conversation_pair_is_unique_and_has_two_distinct_members(self):
        self.get_conversation()
        conversation = Conversation.objects.get()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Conversation.objects.create(
                first_member=conversation.first_member,
                second_member=conversation.second_member,
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Conversation.objects.create(
                first_member=self.alice,
                second_member=self.alice,
            )

    def test_outsider_cannot_list_open_or_read_or_send_to_conversation(self):
        conversation = self.get_conversation()
        self.client.force_authenticate(self.outsider)

        responses = (
            self.client.get("/api/conversations/"),
            self.client.get(f"/api/conversations/{conversation['id']}/"),
            self.client.get(f"/api/conversations/{conversation['id']}/messages/"),
            self.client.post(
                f"/api/conversations/{conversation['id']}/messages/",
                {"content": "intrusion"},
                format="json",
            ),
        )
        self.assertEqual([response.status_code for response in responses], [404, 404, 404, 404])
        self.assertEqual(Message.objects.count(), 0)

    def test_unauthenticated_requests_cannot_access_conversation_or_messages(self):
        conversation = self.get_conversation()
        self.client.force_authenticate(user=None)

        responses = (
            self.client.get("/api/conversations/"),
            self.client.get(f"/api/conversations/{conversation['id']}/"),
            self.client.get(f"/api/conversations/{conversation['id']}/messages/"),
            self.client.post(
                f"/api/conversations/{conversation['id']}/messages/",
                {"content": "anonymous"},
                format="json",
            ),
        )
        self.assertEqual([response.status_code for response in responses], [401, 401, 401, 401])

    def test_both_members_can_send_and_read_and_sender_comes_from_authentication(self):
        conversation = self.get_conversation()
        url = f"/api/conversations/{conversation['id']}/messages/"

        self.client.force_authenticate(self.alice)
        spoofed_response = self.client.post(
            url,
            {"content": " Hello Alice ", "sender": self.bob.pk},
            format="json",
        )
        self.assertEqual(spoofed_response.status_code, 400)

        alice_response = self.client.post(url, {"content": " Hello Alice "}, format="json")
        self.assertEqual(alice_response.status_code, 201)
        self.assertEqual(alice_response.json()["content"], "Hello Alice")
        self.assertEqual(alice_response.json()["sender"], {"username": "alice"})
        alice_message_id = alice_response.json()["id"]
        alice_read_response = self.client.get(url)
        self.assertEqual(alice_read_response.status_code, 200)
        self.assertEqual(alice_read_response.json()["results"][0]["id"], alice_message_id)

        self.client.force_authenticate(self.bob)
        bob_response = self.client.post(url, {"content": "Hello Bob"}, format="json")
        self.assertEqual(bob_response.status_code, 201)
        self.assertEqual(bob_response.json()["sender"], {"username": "bob"})

        list_response = self.client.get(url)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["count"], 2)
        self.assertEqual(
            {item["id"] for item in list_response.json()["results"]},
            {alice_message_id, bob_response.json()["id"]},
        )

    def test_messages_are_ordered_chronologically_and_paginated(self):
        conversation = self.get_conversation()
        first = Message.objects.create(
            conversation_id=conversation["id"], sender=self.alice, content="first"
        )
        second = Message.objects.create(
            conversation_id=conversation["id"], sender=self.bob, content="second"
        )
        now = timezone.now()
        Message.objects.filter(pk=first.pk).update(created_at=now)
        Message.objects.filter(pk=second.pk).update(created_at=now + timedelta(seconds=1))

        self.client.force_authenticate(self.alice)
        url = f"/api/conversations/{conversation['id']}/messages/?page_size=1"
        page_one = self.client.get(url)
        page_two = self.client.get(f"{url}&page=2")

        self.assertEqual(page_one.status_code, 200)
        self.assertEqual(page_one.json()["count"], 2)
        self.assertIsNotNone(page_one.json()["next"])
        self.assertEqual(page_one.json()["results"][0]["id"], str(first.pk))
        self.assertEqual(page_two.json()["results"][0]["id"], str(second.pk))

    def test_empty_and_overlong_messages_are_rejected(self):
        conversation = self.get_conversation()
        self.client.force_authenticate(self.alice)
        url = f"/api/conversations/{conversation['id']}/messages/"

        empty = self.client.post(url, {"content": "  \n "}, format="json")
        long = self.client.post(url, {"content": "x" * 4001}, format="json")

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(long.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)
