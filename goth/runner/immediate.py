import abc
import asyncio
from datetime import datetime, timedelta
import functools
import logging
from pathlib import Path
import re
import time
from typing import Generic, List, Optional, Tuple, TypeVar

from goth.assertions import EventStream
from goth.assertions.operators import eventually
from goth.runner import Runner
from goth.runner.container.yagna import YagnaContainerConfig
from goth.runner.log_monitor import LogEvent
from goth.runner.probe import ProviderProbe, RequestorProbe

from openapi_market_client import Demand, Proposal


R = TypeVar("R", ProviderProbe, RequestorProbe)


class ProbeOperations(Generic[R], abc.ABC):

    probe: R

    last_checked_line: int

    def __init__(self, probe: R):
        self.probe = probe
        self.last_checked_line = -1

    async def _wait_for_log(self, pattern: str, timeout: float = 1000):

        regex = re.compile(pattern)

        def predicate(log_event) -> bool:
            return regex.match(log_event.message) is not None

        # First examine log lines already seen
        while self.last_checked_line + 1 < len(self.probe.agent_logs.events):
            self.last_checked_line += 1
            log_event = self.probe.agent_logs.events[self.last_checked_line]
            if predicate(log_event):
                return True

        # Otherwise create an assertion that waits for a matching line
        async def coro(stream):
            try:
                await eventually(stream, predicate, timeout=timeout)
            finally:
                self.last_checked_line = len(stream.past_events) - 1

        assertion = self.probe.agent_logs.add_assertion(coro)

        while not assertion.done:
            await asyncio.sleep(0.1)

        if assertion.failed:
            raise assertion.result
        return assertion.result


logger = logging.getLogger(__name__)


def step(default_timeout: float = 10.0):

    def decorator(func):

        @functools.wraps(func)
        async def wrapper(*args, timeout: Optional[float] = None):
            timeout = timeout if timeout is not None else default_timeout
            start_time = time.time()
            logger.info("Running step '%s', timeout: %s", func.__name__, timeout)
            try:
                result = await asyncio.wait_for(func(*args), timeout=timeout)
                logger.info(
                    "Finished step '%s', result: %s, time: %s",
                    func.__name__, result, time.time() - start_time
                )
            except asyncio.TimeoutError as te:
                logger.exception(te)
                raise
            return result

        return wrapper

    return decorator


class ProviderProbeOperations(ProbeOperations[ProviderProbe]):

    def __init__(self, probe: ProviderProbe):
        super().__init__(probe)

    @step()
    async def wait_for_offer_subscribed(self, timeout: float = 10.0):
        return await self._wait_for_log("Subscribed offer")

    @step()
    async def wait_for_proposal_accepted(self):
        return await self._wait_for_log("Decided to AcceptProposal")


class RequestorProbeOperations(ProbeOperations[RequestorProbe]):

    def __init__(self, probe: RequestorProbe):
        super().__init__(probe)

    @step()
    async def init_payment(self) -> str:
        result = self.probe.cli.payment_init(requestor_mode=True)
        return result

    @step()
    async def subscribe_demand(self) -> Tuple[str, Demand]:

        package = (
            "hash://sha3:d5e31b2eed628572a5898bf8c34447644bfc4b5130cfc1e4f10aeaa1"
            ":http://34.244.4.185:8000/rust-wasi-tutorial.zip"
        )
        constraints = (
            "(&(golem.inf.mem.gib>0.5)(golem.inf.storage.gib>1)"
            "(golem.com.pricing.model=linear))"
        )

        demand = Demand(
            requestor_id=self.probe.address,
            properties={
                "golem.node.id.name": "test1",
                "golem.srv.comp.expiration": int(
                    (datetime.now() + timedelta(days=1)).timestamp() * 1000
                ),
                "golem.srv.comp.task_package": package,
            },
            constraints=constraints,
        )

        subscription_id = self.probe.market.subscribe_demand(demand)
        return subscription_id, demand

    @step()
    async def wait_for_proposal(self, subscription_id: str) -> Proposal:

        proposal = None

        while proposal is None:
            result_offers = self.probe.market.collect_offers(subscription_id)
            logger.debug(
                "collect_offers(%s). proposal=%r", subscription_id, result_offers,
            )
            if result_offers:
                proposal = result_offers[0].proposal
            else:
                logger.debug("Waiting on proposal... %r", result_offers)
                await asyncio.sleep(1.0)

        return proposal

    @step()
    async def counter_proposal(
            self, subscription_id: str, demand: Demand, provider_proposal: Proposal
    ) -> str:

        proposal = Proposal(
            constraints=demand.constraints,
            properties=demand.properties,
            prev_proposal_id=provider_proposal.proposal_id,
        )

        counter_proposal = self.probe.market.counter_proposal_demand(
            subscription_id=subscription_id,
            proposal_id=provider_proposal.proposal_id,
            proposal=proposal,
        )

        return counter_proposal


class ImmediateRunner(Runner):

    def __init__(
            self,
            topology: List[YagnaContainerConfig],
            api_assertions_module: Optional[str],
            logs_path: Path,
            assets_path: Optional[Path],
    ):
        super().__init__(topology, api_assertions_module, logs_path, assets_path)

    def get_probe(self, name: str) -> ProbeOperations:

        for probe in self.probes:
            if probe.name == name:
                if isinstance(probe, ProviderProbe):
                    wrapper_class = ProviderProbeOperations
                elif isinstance(probe, RequestorProbe):
                    wrapper_class = RequestorProbeOperations
                else:
                    assert False
                return wrapper_class(probe)

        raise KeyError(f"No such probe: {name}")

    async def __aenter__(self):
        self._start_nodes()

    async def __aexit__(self, *args):
        await asyncio.sleep(2.0)
        for probe in self.probes:
            self.logger.info("stopping probe. name=%s", probe.name)
            await probe.stop()

        self.proxy.stop()
        # Stopping the proxy triggered evaluation of assertions
        # "at the end of events".
        self.check_assertion_errors()


def assert_message_starts_with(pattern: str):
    """Return the "message.start_with" assertion with pre-compiled re `needle`.

    Prepare an assertion that:
    Assert that a `LogEvent` with message starts with {needle} is found.
    """

    # No need to add ^ in the regexp since .match( searches from the start
    regex = re.compile(pattern)

    async def _assert_starts_with(stream: EventStream[LogEvent]) -> int:

        async for event in stream:
            match = regex.match(event.message)
            if match:
                return len(stream.past_events)

        raise AssertionError(f"No message starts with '{pattern}'")

    return _assert_starts_with
