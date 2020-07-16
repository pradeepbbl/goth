"""Tests for the `runner.cli.yagna_payment_cmd` module."""

import time

import pytest

from goth.runner.cli import Cli


def test_payment_init(yagna_container):
    """Test basic usage of `payment init` command."""

    yagna = Cli(yagna_container).yagna

    # The test fails if we call `payment init` too fast
    time.sleep(3.0)
    yagna.payment_init()


@pytest.mark.skip(reason="Not sure what is the expected behaviour")
def test_payment_init_provider_mode(yagna_container):
    """Test `payment init -p`."""

    yagna = Cli(yagna_container).yagna

    yagna.payment_init(provider_mode=True)


@pytest.mark.skip(reason="Not sure what is the expected behaviour")
def test_payment_init_requestor_mode(yagna_container):
    """Test `payment init -r`."""

    yagna = Cli(yagna_container).yagna

    yagna.payment_init(requestor_mode=True)


def test_payment_status(yagna_container):
    """Test `payment status` subcommand."""

    yagna = Cli(yagna_container).yagna

    # The test fails if we call `payment init` too fast
    time.sleep(3.0)
    status = yagna.payment_status()
    assert status


def test_payment_status_with_address(yagna_container):
    """Test `payment status` with explicit node address."""

    yagna = Cli(yagna_container).yagna

    status = yagna.payment_status()
    assert status
