"""Test harness runner class, creating the nodes and running the scenario."""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from itertools import chain
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import docker

from goth.assertions import TemporalAssertionError
from goth.runner.container.yagna import YagnaContainerConfig
from goth.runner.log import configure_logging, LogConfig
from goth.runner.probe import Probe, ProviderProbe, RequestorProbe, Role
from goth.runner.probe_steps import ProbeStepBuilder, Step
from goth.runner.proxy import Proxy


class Runner:
    """Manages the nodes and runs the scenario on them."""

    api_assertions_module: Optional[str]
    """Name of the module containing assertions to be loaded into the API monitor."""

    assets_path: Optional[Path]
    """Path to directory containing yagna assets to be mounted in containers."""

    base_log_dir: Path
    """Base directory for all log files created during this test run."""

    probes: Dict[Role, List[Probe]]
    """Probes used for the test run, identified by their role names."""

    proxy: Optional[Proxy]
    """An embedded instance of mitmproxy."""

    topology: List[YagnaContainerConfig]
    """A list of configuration objects for the containers to be instantiated."""

    steps: List[Step]
    """The list of steps to be awaited, steps of the scenario to be executed."""

    def __init__(
        self,
        topology: List[YagnaContainerConfig],
        api_assertions_module: Optional[str],
        logs_path: Path,
        assets_path: Optional[Path],
    ):
        self.topology = topology
        self.api_assertions_module = api_assertions_module
        self.assets_path = assets_path
        self.probes = defaultdict(list)
        self.proxy = None
        self.steps = []

        # Create a unique subdirectory for this test run
        date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S%z")
        self.base_log_dir = logs_path / f"yagna_integration_{date_str}"
        self.base_log_dir.mkdir(parents=True)

        configure_logging(self.base_log_dir)
        self.logger = logging.getLogger(__name__)
        self._run_nodes()

    def check_assertion_errors(self) -> None:
        """If any monitor reports an assertion error, raise the first error."""

        probes = chain.from_iterable(self.probes.values())
        monitors = chain.from_iterable(
            (
                (probe.container.logs for probe in probes),
                (probe.agent_logs for probe in probes),
                [self.proxy.monitor],
            )
        )
        failed = chain.from_iterable(
            monitor.failed for monitor in monitors if monitor is not None
        )
        for assertion in failed:
            # We assume all failed assertions were already reported
            # in their corresponding log files. Now we only need to raise
            # one of them to break the execution.
            raise TemporalAssertionError(
                f"Assertion '{assertion.name}' failed, cause: {assertion.result}"
            )

    async def run_scenario(self):
        """Start the nodes, run the scenario, then stop the nodes and clean up."""
        self._start_nodes()
        try:
            for step in self.steps:
                self.logger.info("running step. step=%s", step)
                deadline = datetime.now() + timedelta(seconds=step.timeout)

                while not step.is_done():
                    if deadline < datetime.now():
                        raise TimeoutError
                    await asyncio.sleep(0.1)

        finally:
            # Sleep to let the logs be saved
            await asyncio.sleep(2.0)
            for probe in chain.from_iterable(self.probes.values()):
                self.logger.info("stopping probe. name=%s", probe.name)
                await probe.stop()

            self.proxy.stop()
            # Stopping the proxy triggered evaluation of assertions
            # "at the end of events".
            self.check_assertion_errors()

    def _run_nodes(self) -> None:

        docker_client = docker.from_env()
        scenario_dir = self.base_log_dir / self._get_test_log_dir_name()
        scenario_dir.mkdir(exist_ok=True)

        self.proxy = Proxy(assertions_module=self.api_assertions_module)
        self.proxy.start()

        for config in self.topology:
            log_config = config.log_config or LogConfig(config.name)
            log_config.base_dir = scenario_dir

            if isinstance(config, YagnaContainerConfig):
                if config.role == Role.requestor:
                    probe = RequestorProbe(
                        docker_client, config, log_config, self.assets_path
                    )
                else:
                    probe = ProviderProbe(
                        docker_client, config, log_config, self.assets_path
                    )

                self.probes[config.role].append(probe)

    def _get_test_log_dir_name(self):
        test_name = os.environ.get("PYTEST_CURRENT_TEST")
        self.logger.debug("Raw current pytest test=%s", test_name)
        # Take only the function name of the currently running test
        test_name = test_name.split("::")[-1].split()[0]
        self.logger.debug("Cleaned current test dir name=%s", test_name)
        return test_name

    def _start_nodes(self):
        for probe in chain.from_iterable(self.probes.values()):
            probe.start()

    def get_probes_by_role(self, role):
        """Create a ProbeStepBuilder for the requested role."""
        return ProbeStepBuilder(steps=self.steps, probes=self.probes[role])
