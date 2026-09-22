"""The administrator command must not leave the previous login working."""

import sys
from unittest.mock import patch

import pytest
from django.contrib.auth import authenticate, get_user_model

from app.core.cli import main

PASSWORD = "harbor-thistle-quartz-reef-pepper-2417"


@pytest.mark.django_db
def test_admin_rename_retires_the_previous_account(tmp_path):
    User = get_user_model()
    User.objects.create_superuser("admin", password="starting-password-long-enough")
    secret = tmp_path / "password"
    secret.write_text(PASSWORD, encoding="utf-8")

    with patch.object(
        sys,
        "argv",
        ["radar", "admin", "--username", "blian", "--retire", "admin", "--password-file", str(secret)],
    ):
        main()

    assert authenticate(username="blian", password=PASSWORD) is not None
    old = User.objects.get(username="admin")
    assert authenticate(username="admin", password="starting-password-long-enough") is None
    assert not old.is_active and not old.is_staff and not old.is_superuser
    assert not old.has_usable_password()


@pytest.mark.django_db
def test_admin_rejects_password_below_the_configured_floor(tmp_path):
    secret = tmp_path / "password"
    secret.write_text("elevenchars", encoding="utf-8")
    with patch.object(sys, "argv", ["radar", "admin", "--password-file", str(secret)]):
        with pytest.raises(ValueError):
            main()
