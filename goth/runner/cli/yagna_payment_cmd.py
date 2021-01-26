"""Implementation of `yagna payment` subcommands."""

from dataclasses import dataclass
from enum import auto, Enum
from typing import Dict, Optional

from goth.runner.cli.base import make_args
from goth.runner.cli.typing import CommandRunner


class PaymentDriver(Enum):
    """Available payment drivers for yagna."""

    erc20 = auto()
    zksync = auto()


DEFAULT_PAYMENT_DRIVER = PaymentDriver.erc20


@dataclass(frozen=True)
class Payments:
    """Information about payment amounts."""

    accepted: float
    confirmed: float
    rejected: float
    requested: float


@dataclass(frozen=True)
class PaymentStatus:
    """Information about payment status."""

    amount: float
    incoming: Payments
    outgoing: Payments
    reserved: float

    @staticmethod
    def from_dict(source: dict) -> "PaymentStatus":
        """Parse a dict into an instance of `PaymentStatus`."""
        return PaymentStatus(
            amount=float(source["amount"]),
            incoming=Payments(
                **{key: float(value) for key, value in source["incoming"].items()}
            ),
            outgoing=Payments(
                **{key: float(value) for key, value in source["outgoing"].items()}
            ),
            reserved=float(source["reserved"]),
        )


class PaymentMode(Enum):
    """Possible modes for payment init CLI subcommand."""

    receiver = auto()
    sender = auto()


class YagnaPaymentMixin:
    """A mixin class that adds support for `<yagna-cmd> payment` commands."""

    def payment_init(
        self: CommandRunner,
        payment_mode: PaymentMode = PaymentMode.receiver,
        data_dir: str = "",
        payment_driver: PaymentDriver = DEFAULT_PAYMENT_DRIVER,
        address: Optional[str] = None,
        network: Optional[str] = None,
    ) -> PaymentStatus:
        """Run `<cmd> payment init` with optional extra args.

        Return the command's output.
        """

        args = make_args(
            "payment",
            "init",
            data_dir=data_dir,
            payment_driver=payment_driver.name,
            address=address,
            network=network,
        )
        args.append(f"--{payment_mode.name}")

        output = self.run_json_command(Dict, *args)
        return PaymentStatus.from_dict(output)

    def payment_status(
        self: CommandRunner,
        data_dir: str = "",
        driver: PaymentDriver = DEFAULT_PAYMENT_DRIVER,
    ) -> PaymentStatus:
        """Run `<cmd> payment status` with optional extra args.

        Parse the command's output as a `PaymentStatus` and return it.
        """

        args = make_args("payment", "status", driver.name, data_dir=data_dir)
        output = self.run_json_command(Dict, *args)
        return PaymentStatus.from_dict(output)
