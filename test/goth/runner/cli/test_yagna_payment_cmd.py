"""Tests for the `runner.cli.yagna_payment_cmd` module."""

import time

import pytest

from goth.runner.cli import Cli
from goth.runner.cli.yagna_payment_cmd import PaymentDriver, PaymentMode, PaymentStatus


def test_payment_init(yagna_container):
    """Test basic usage of `payment init` command."""

    yagna = Cli(yagna_container).yagna

    status: PaymentStatus = yagna.payment_init()
    assert status


def test_payment_init_provider_mode(yagna_container):
    """Test `payment init --receiver`."""

    yagna = Cli(yagna_container).yagna

    status: PaymentStatus = yagna.payment_init(payment_mode=PaymentMode.receiver)
    assert status


def test_payment_init_requestor_mode(yagna_container):
    """Test `payment init --sender`."""

    yagna = Cli(yagna_container).yagna

    status: PaymentStatus = yagna.payment_init(payment_mode=PaymentMode.sender)
    assert status


def test_payment_status(yagna_container):
    """Test `payment status` subcommand."""

    yagna = Cli(yagna_container).yagna

    status = yagna.payment_status()
    assert status


def test_payment_status_with_address(yagna_container):
    """Test `payment status` with explicit node address."""

    yagna = Cli(yagna_container).yagna

    status = yagna.payment_status()
    assert status
