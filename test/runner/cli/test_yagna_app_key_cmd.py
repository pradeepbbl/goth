"""Tests for the `runner.cli.yagna_app_key_cmd` module"""

from src.runner.cli import Cli
from src.runner.exceptions import CommandError

from conftest import yagna_daemon_running


def test_app_key_create(yagna_container):
    """Test `app-key create <name>` subcommand."""

    yagna = Cli(yagna_container).yagna

    with yagna_daemon_running(yagna_container):

        test_key = yagna.app_key_create("test key")
        assert test_key

        test_key_2 = yagna.app_key_create("test key 2")
        assert test_key_2

        assert test_key != test_key_2


def test_app_key_create_with_address(yagna_container):
    """Test `app-key create <name>` with explicit address."""

    yagna = Cli(yagna_container).yagna

    with yagna_daemon_running(yagna_container):

        default_id = yagna.id_show()

        test_key = yagna.app_key_create("test key", alias_or_addr=default_id.address)
        assert test_key


def test_app_key_create_with_alias(yagna_container):
    """Test `app-key create <name>` with explicit node alias."""

    yagna = Cli(yagna_container).yagna

    with yagna_daemon_running(yagna_container):

        yagna.id_create(alias="alias-id")
        test_key = yagna.app_key_create("test key", alias_or_addr="alias-id")
        assert test_key


def test_app_key_create_duplicate_name_fails(yagna_container):
    """Test if `app-key create <name>` fails when app key `<name>` already exists."""

    yagna = Cli(yagna_container).yagna

    with yagna_daemon_running(yagna_container):

        yagna.app_key_create("test key")

        try:
            yagna.app_key_create("test key")
            assert False
        except CommandError:
            pass


def test_app_key_create_duplicate_name_fails_2(yagna_container):
    """Test if `app-key create <name>` fails when app key `<name>` already exists.

    Even if both keys are created using different node aliases.
    """

    yagna = Cli(yagna_container).yagna

    with yagna_daemon_running(yagna_container):

        yagna.id_create(alias="alias-1")
        yagna.id_create(alias="alias-2")
        yagna.app_key_create("test key", alias_or_addr="alias-1")

        try:
            yagna.app_key_create("test key", alias_or_addr="alias-2")
            assert False
        except CommandError:
            pass


def test_app_key_create_unknown_address_fails(yagna_container):
    """Test if `app-key create --id <address>` fails if `<address>` is unknown."""

    yagna = Cli(yagna_container).yagna

    with yagna_daemon_running(yagna_container):

        try:
            yagna.app_key_create("test key", alias_or_addr="unknown-alias")
            assert False
        except CommandError:
            pass


def test_app_key_list(yagna_container):
    """Test `app-key list` subcommand."""

    yagna = Cli(yagna_container).yagna

    with yagna_daemon_running(yagna_container):

        key_1 = yagna.app_key_create("test key 1")
        key_2 = yagna.app_key_create("test key 2")
        keys = yagna.app_key_list()
        assert {info.key for info in keys} == {key_1, key_2}


def test_app_key_list_with_address(yagna_container):
    """Test `app-key list` subcommand with explicit node address."""

    yagna = Cli(yagna_container).yagna

    with yagna_daemon_running(yagna_container):

        key_1 = yagna.app_key_create("test key 1")

        identity = yagna.id_create(alias="id-alias")
        key_2 = yagna.app_key_create("test key 2", alias_or_addr="id-alias")

        keys_1 = yagna.app_key_list()
        assert {info.key for info in keys_1} == {key_1, key_2}

        keys_2 = yagna.app_key_list(address=identity.address)
        assert {info.key for info in keys_2} == {key_2}

        new_identity = yagna.id_create()
        keys_3 = yagna.app_key_list(address=new_identity.address)
        assert keys_3 == []
