"""End to end tests for requesting WASM tasks using goth REST API clients."""

import json
import logging
import os
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
from goth.runner.container.build import YagnaBuildEnvironment
from goth.runner.container.yagna import YagnaContainerConfig
from goth.runner.provider import ProviderProbeWithLogSteps
from goth.runner.requestor import RequestorProbeWithApiSteps

logger = logging.getLogger(__name__)


def topology(assets_path: Path) -> List[YagnaContainerConfig]:
    """Define the topology of the test network."""

    # Nodes are configured to communicate via proxy
    provider_env = node_environment(
        market_url_base=MARKET_BASE_URL.substitute(host=PROXY_HOST),
        rest_api_url_base=YAGNA_REST_URL.substitute(host=PROXY_HOST),
    )
    requestor_env = node_environment(
        market_url_base=MARKET_BASE_URL.substitute(host=PROXY_HOST),
        rest_api_url_base=YAGNA_REST_URL.substitute(host=PROXY_HOST),
        account_list="/asset/key/001-accounts.json",
    )

    provider_volumes = {
        assets_path
        / "provider"
        / "presets.json": "/root/.local/share/ya-provider/presets.json",
        assets_path
        / "provider"
        / "hardware.json": "/root/.local/share/ya-provider/hardware.json",
        assets_path
        / "provider"
        / "images": "/root/.local/share/ya-provider/exe-unit/cache/tmp",
    }

    return [
        YagnaContainerConfig(
            name="requestor",
            probe_type=RequestorProbeWithApiSteps,
            volumes={assets_path / "requestor": "/asset"},
            environment=requestor_env,
            key_file="/asset/key/001.json",
        ),
        YagnaContainerConfig(
            name="provider_1",
            probe_type=ProviderProbeWithLogSteps,
            environment=provider_env,
            volumes=provider_volumes,
            privileged_mode=True,
        ),
        YagnaContainerConfig(
            name="provider_2",
            probe_type=ProviderProbeWithLogSteps,
            environment=provider_env,
            volumes=provider_volumes,
            privileged_mode=True,
        ),
    ]


def _exe_script(runner: Runner, output_file: str):

    output_path = Path(runner.web_root_path) / output_file
    if output_path.exists():
        os.remove(output_path)

    web_server_addr = f"http://{runner.host_address}:{runner.web_server_port}"

    return [
        {"deploy": {}},
        {"start": {}},
        {
            "transfer": {
                "from": f"{web_server_addr}/scene.blend",
                "to": "container:/golem/resource/scene.blend",
            }
        },
        {
            "transfer": {
                "from": f"{web_server_addr}/params.json",
                "to": "container:/golem/work/params.json",
            }
        },
        {"run": {"entry_point": "/golem/entrypoints/run-blender.sh", "args": []}},
        {
            "transfer": {
                "from": f"container:/golem/output/{output_file}",
                "to": f"{web_server_addr}/upload/{output_file}",
            }
        },
    ]


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Running in GitHub Actions (no nested virtualization)",
)
@pytest.mark.asyncio
async def test_e2e_vm_success(
    logs_path: Path,
    assets_path: Path,
    yagna_build_env: YagnaBuildEnvironment,
    compose_file_path: Path,
    demand_constraints: str,
):
    """Test successful flow requesting a Blender task with goth REST API client."""

    async with Runner(
        topology=topology(assets_path),
        api_assertions_module="test.yagna.assertions.e2e_wasm_assertions",
        logs_path=logs_path,
        assets_path=assets_path,
        compose_file_path=compose_file_path,
        build_environment=yagna_build_env,
    ) as runner:

        task_package = (
            "hash:sha3:9a3b5d67b0b27746283cb5f287c13eab1beaa12d92a9f536b747c7ae:"
            "http://3.249.139.167:8000/local-image-c76719083b.gvmi"
        )

        output_file = "out0000.png"

        output_path = Path(runner.web_root_path) / output_file
        if output_path.exists():
            os.remove(output_path)

        exe_script = _exe_script(runner, output_file)

        requestor = runner.get_probes(probe_type=RequestorProbeWithApiSteps)[0]
        providers = runner.get_probes(probe_type=ProviderProbeWithLogSteps)

        # Market

        for provider in providers:
            await provider.wait_for_offer_subscribed()

        subscription_id, demand = await requestor.subscribe_demand(
            task_package, demand_constraints
        )

        proposals = await requestor.wait_for_proposals(
            subscription_id,
            providers,
            lambda proposal: proposal.properties.get("golem.runtime.name") == "vm",
        )
        logger.info("Collected %s proposals", len(proposals))

        agreement_providers = []

        for proposal in proposals:
            provider = next(p for p in providers if p.address == proposal.issuer_id)
            logger.info("Processing proposal from %s", provider.name)

            counterproposal_id = await requestor.counter_proposal(
                subscription_id, demand, proposal
            )
            await provider.wait_for_proposal_accepted()

            new_proposals = await requestor.wait_for_proposals(
                subscription_id, (provider,)
            )
            new_proposal = new_proposals[0]
            assert new_proposal.prev_proposal_id == counterproposal_id

            agreement_id = await requestor.create_agreement(new_proposal)
            await requestor.confirm_agreement(agreement_id)
            await provider.wait_for_agreement_approved()
            agreement_providers.append((agreement_id, provider))

        await requestor.unsubscribe_demand(subscription_id)
        logger.info("Got %s agreements", len(agreement_providers))

        #  Activity

        num_commands = len(exe_script)

        for agreement_id, provider in agreement_providers:
            logger.info("Running activity on %s", provider.name)
            activity_id = await requestor.create_activity(agreement_id)
            await provider.wait_for_exeunit_started()
            batch_id = await requestor.call_exec(activity_id, json.dumps(exe_script))
            await requestor.collect_results(
                activity_id, batch_id, num_commands, timeout=300
            )
            await requestor.destroy_activity(activity_id)
            await provider.wait_for_exeunit_finished()

        assert output_path.is_file()
        assert output_path.stat().st_size > 0

        # Payment

        for agreement_id, provider in agreement_providers:
            await provider.wait_for_invoice_sent()
            invoices = await requestor.gather_invoices(agreement_id)
            assert all(inv.agreement_id == agreement_id for inv in invoices)
            # TODO:
            await requestor.pay_invoices(invoices)
            await provider.wait_for_invoice_paid()
