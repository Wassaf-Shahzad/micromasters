"""
Tests for serializing Django User objects
"""
from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from django.db.models.signals import post_save
from factory.django import mute_signals
from micromasters.serializers import UserSerializer, serialize_maybe_user
from micromasters.factories import UserFactory
from profiles.factories import ProfileFactory
from search.base import MockedESTestCase


class UserTests(MockedESTestCase):
    """
    Tests for serializing users.
    """
    def test_basic_user(self):
        """
        Test serializing a basic user, no profile
        """
        with mute_signals(post_save):
            user = UserFactory.create(email="fake@example.com")

        data = UserSerializer(user).data
        assert data == {
            "username": user.username,
            "email": "fake@example.com",
            "first_name": None,
            "last_name": None,
            "preferred_name": None,
        }

    def test_logged_in_user_through_maybe_wrapper(self):
        """
        Test serialize_maybe_user
        """
        with mute_signals(post_save):
            user = UserFactory.create(email="fake@example.com")

        data = serialize_maybe_user(user)
        assert data == {
            "username": user.username,
            "email": "fake@example.com",
            "first_name": None,
            "last_name": None,
            "preferred_name": None,
        }

    def test_user_with_profile(self):
        """
        Test a user with a profile
        """
        with mute_signals(post_save):
            user = UserFactory.create(email="fake@example.com")
            ProfileFactory.create(
                user=user,
                first_name="Rando",
                last_name="Cardrizzian",
                preferred_name="Hobo",
            )

        data = UserSerializer(user).data
        assert data == {
            "username": user.username,
            "email": "fake@example.com",
            "first_name": "Rando",
            "last_name": "Cardrizzian",
            "preferred_name": "Hobo",
        }


class AnonymousUserTests(TestCase):
    """
    Tests for serializing anonymous users.
    """
    def test_serialize_anonymous_user(self):
        """
        Test serializing an anonymous user
        """
        anon_user = AnonymousUser()
        data = serialize_maybe_user(anon_user)
        assert data is None
