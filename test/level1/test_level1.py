"""Level 1 test to be ran from pytest."""

import logging
from pathlib import Path
from string import Template
from typing import Dict, Optional

import pytest

from goth.address import (
    ACTIVITY_API_URL,
    MARKET_API_URL,
    MARKET_BASE_URL,
    PAYMENT_API_URL,
    PROXY_HOST,
    ROUTER_HOST,
    ROUTER_PORT,
    YAGNA_BUS_URL,
    YAGNA_REST_URL,
)
from goth.runner import Runner

from goth.runner.container.yagna import YagnaContainerConfig
from goth.runner.probe import Provider, Requestor

logger = logging.getLogger(__name__)


def node_environment(
    market_url_base: str = "", rest_api_url_base: str = ""
) -> Dict[str, str]:
    """Construct an environment for executing commands in a yagna docker container."""
    # Use custom base if given, default otherwise
    market_template_params = {"base": market_url_base} if market_url_base else {}

    daemon_env = {
        "CENTRAL_MARKET_URL": MARKET_API_URL.substitute(market_template_params),
        "CENTRAL_NET_HOST": f"{ROUTER_HOST}:{ROUTER_PORT}",
        "ETH_FAUCET_ADDRESS": "http://faucet.testnet.golem.network:4000/donate",
        "GSB_URL": YAGNA_BUS_URL.substitute(host="0.0.0.0"),
        "RUST_LOG": "debug,trust_dns_proto=info",
        "YAGNA_API_URL": YAGNA_REST_URL.substitute(host="0.0.0.0"),
    }
    node_env = daemon_env

    if rest_api_url_base:
        agent_env = {
            "YAGNA_MARKET_URL": MARKET_API_URL.substitute(base=rest_api_url_base),
            "YAGNA_ACTIVITY_URL": ACTIVITY_API_URL.substitute(base=rest_api_url_base),
            "YAGNA_PAYMENT_URL": PAYMENT_API_URL.substitute(base=rest_api_url_base),
        }
        node_env.update(agent_env)

    return node_env


VOLUMES = {
    Template("$assets_path"): "/asset",
    Template("$assets_path/presets.json"): "/presets.json",
}


LEVEL1_TOPOLOGY = [
    YagnaContainerConfig(
        name="requestor",
        role=Requestor,
        environment=node_environment(),
        volumes=VOLUMES,
    ),
    YagnaContainerConfig(
        name="provider_1",
        role=Provider,
        # Configure this provider node to communicate via proxy
        environment=node_environment(
            market_url_base=MARKET_BASE_URL.substitute(host=PROXY_HOST),
            rest_api_url_base=YAGNA_REST_URL.substitute(host=PROXY_HOST),
        ),
        volumes=VOLUMES,
    ),
    # YagnaContainerConfig(
    #     name="provider_2",
    #     role=Provider,
    #     # Configure the second provider node to communicate via proxy
    #     environment=node_environment(
    #         market_url_base=MARKET_BASE_URL.substitute(host=PROXY_HOST),
    #         rest_api_url_base=YAGNA_REST_URL.substitute(host=PROXY_HOST),
    #     ),
    #     volumes=VOLUMES,
    # ),
]


class _TestLevel1:
    """TestCase running Level1Scenario."""

    @pytest.mark.asyncio
    async def _test_level1(self, logs_path: Path, assets_path: Optional[Path]):
        """Test running Level1Scenario."""
        runner = Runner(
            LEVEL1_TOPOLOGY, "assertions.level1_assertions", logs_path, assets_path
        )

        provider = runner.get_probes(role=Provider)
        requestor = runner.get_probes(role=Requestor)

        requestor.init_payment()

        # Market
        provider.wait_for_offer_subscribed()
        subscription_id = requestor.subscribe_demand()
        proposal = requestor.wait_for_proposal(subscription_id)
        requestor.counter_proposal(subscription_id, proposal)
        provider.wait_for_proposal_accepted()
        requestor.wait_for_proposal(subscription_id)
        agreement_id = requestor.create_agreement(proposal)
        requestor.confirm_agreement(agreement_id)
        provider.wait_for_agreement_approved()
        # requestor.wait_for_approval() ???
        requestor.unsubscribe_demand(subscription_id)

        # Activity
        activity_id = requestor.create_activity(agreement_id)
        provider.wait_for_activity_created()
        batch_id = requestor.call_exec(activity_id)
        provider.wait_for_exeunit_started()
        requestor.collect_results(activity_id, batch_id)
        requestor.destroy_activity(activity_id)
        provider.wait_for_exeunit_finished()

        # Payment
        provider.wait_for_invoice_sent()
        invoice = requestor.gather_invoice(agreement_id)
        requestor.pay_invoice(invoice)
        provider.wait_for_invoice_paid()

        await runner.run_scenario()


from goth.runner.immediate import ImmediateRunner, ProviderProbeOperations, RequestorProbeOperations


class TestLevel1Immediate:

    @pytest.mark.asyncio
    async def test_level_1(self, logs_path: Path, assets_path: Optional[Path]):
        """Test running Level1Scenario."""

        runner = ImmediateRunner(
            LEVEL1_TOPOLOGY, "assertions.level1_assertions", logs_path, assets_path
        )

        async with runner:

            requestor = runner.get_probe("requestor")
            assert isinstance(requestor, RequestorProbeOperations)

            provider = runner.get_probe("provider_1")
            assert isinstance(provider, ProviderProbeOperations)

            # await requestor.init_payment()

            # Market
            await provider.wait_for_offer_subscribed()
            subscription_id, demand = await requestor.subscribe_demand()
            provider_proposal = await requestor.wait_for_proposal(subscription_id)
            counterproposal_id = await requestor.counter_proposal(subscription_id, demand, provider_proposal)
            await provider.wait_for_proposal_accepted() # timeout=10000)
            new_proposal = await requestor.wait_for_proposal(subscription_id)
            assert new_proposal.prev_proposal_id == counterproposal_id
            print(new_proposal)

            # agreement_id = requestor.create_agreement(proposal)

        logger.info("Test finished")


