"""End to end tests for requesting WASM tasks using ya-requestor agent."""

import logging
from pathlib import Path
from typing import List

import pytest

from goth.address import (
    MARKET_BASE_URL,
    PROXY_HOST,
    YAGNA_REST_URL,
)
from goth.node import node_environment
from goth.runner import Runner
from goth.runner.container.compose import ComposeConfig
from goth.runner.container.yagna import YagnaContainerConfig
from goth.runner.probe import ProviderProbe, RequestorProbeWithAgent
from goth.runner.provider import ProviderProbeWithLogSteps


logger = logging.getLogger(__name__)


def topology(assets_path: Path, agent_task_package: str) -> List[YagnaContainerConfig]:
    """Define the topology of the test network."""

    # Nodes are configured to communicate via proxy
    provider_env = node_environment(
        market_url_base=MARKET_BASE_URL.substitute(host=PROXY_HOST),
        rest_api_url_base=YAGNA_REST_URL.substitute(host=PROXY_HOST),
    )
    provider_1_env = provider_env.copy()
    provider_1_env.update(ACCOUNT_LIST="/asset/key/002-accounts.json")
    provider_2_env = provider_env.copy()
    provider_2_env.update(ACCOUNT_LIST="/asset/key/003-accounts-zk.json")
    requestor_env = node_environment(
        market_url_base=MARKET_BASE_URL.substitute(host=PROXY_HOST),
        rest_api_url_base=YAGNA_REST_URL.substitute(host=PROXY_HOST),
        account_list="/asset/key/001-multi.json",
    )

    provider_volumes = {
        assets_path / "provider" / "presets.json": "/presets.json",
        assets_path / "provider": "/asset",
    }

    return [
        YagnaContainerConfig(
            "requestor",
            probe_type=RequestorProbeWithAgent,
            probe_properties={"task_package": agent_task_package},
            volumes={assets_path / "requestor": "/asset"},
            environment=requestor_env,
            key_file="/asset/key/001.json",
        ),
        YagnaContainerConfig(
            "provider_1",
            probe_type=ProviderProbe,
            environment=provider_1_env,
            volumes=provider_volumes,
            key_file="/asset/key/002.json",
        ),
        YagnaContainerConfig(
            "provider_2",
            probe_type=ProviderProbe,
            environment=provider_2_env,
            volumes=provider_volumes,
            key_file="/asset/key/003.json",
        ),
    ]


@pytest.mark.asyncio
async def test_multi_driver_success(
    logs_path: Path,
    assets_path: Path,
    compose_config: ComposeConfig,
    task_package_template: str,
):
    """Test succesful flow requesting WASM tasks with requestor agent."""

    async with Runner(
        api_assertions_module="test.yagna.assertions.e2e_wasm_assertions",
        assets_path=assets_path,
        compose_config=compose_config,
        logs_path=logs_path,
        topology=topology(assets_path, task_package_template),
    ) as runner:

        providers = runner.get_probes(probe_type=ProviderProbe)

        steps = [
            ProviderProbeWithLogSteps.wait_for_offer_subscribed,
            ProviderProbeWithLogSteps.wait_for_proposal_accepted,
            ProviderProbeWithLogSteps.wait_for_agreement_approved,
            ProviderProbeWithLogSteps.wait_for_exeunit_started,
            ProviderProbeWithLogSteps.wait_for_exeunit_finished,
            ProviderProbeWithLogSteps.wait_for_invoice_sent,
            ProviderProbeWithLogSteps.wait_for_invoice_paid,
        ]

        for step in steps:
            for provider in providers:
                await step(provider)
