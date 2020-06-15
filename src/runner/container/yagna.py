from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Dict, Optional, TYPE_CHECKING

from docker import DockerClient

from src.runner.container import DockerContainer
from src.runner.log import LogConfig

if TYPE_CHECKING:
    from src.runner.probe import Role


@dataclass
class YagnaContainerConfig:
    """ Configuration to be used for creating a new `YagnaContainer`. """

    name: str
    """ Name to be used for this container, must be unique """

    role: "Role"

    assets_path: Optional[Path] = None
    """ Path to the assets directory. This will be used in templates from `volumes` """

    log_config: Optional[LogConfig] = None
    """ Optional custom logging config to be used for this container """

    environment: Dict[str, str] = field(default_factory=dict)
    """ Environment variables to be set for this container """

    volumes: Dict[Template, str] = field(default_factory=dict)
    """ Volumes to be mounted in the container. Keys are paths on the host machine,
        represented by `Template`s. These templates may include `assets_path`
        as a placeholder to be used for substitution.  The values are container
        paths to be used as mount points. """


class YagnaContainer(DockerContainer):
    BUS_PORT = 6010
    HTTP_PORT = 6000
    COMMAND = ["service", "run", "-d", "/"]
    ENTRYPOINT = "/usr/bin/yagna"
    IMAGE = "yagna"

    # Keeps track of assigned ports on the Docker host
    _port_offset = 0

    def __init__(
        self,
        client: DockerClient,
        config: YagnaContainerConfig,
        log_config: Optional[LogConfig] = None,
        **kwargs,
    ):
        self.environment = config.environment
        self.ports = {
            YagnaContainer.HTTP_PORT: YagnaContainer.host_http_port(),
            YagnaContainer.BUS_PORT: YagnaContainer.host_bus_port(),
        }
        self.volumes: Dict[str, dict] = {}
        if config.assets_path:
            for host_template, mount_path in config.volumes.items():
                host_path = host_template.substitute(
                    assets_path=str(config.assets_path)
                )
                self.volumes[host_path] = {"bind": mount_path, "mode": "ro"}

        YagnaContainer._port_offset += 1

        super().__init__(
            client=client,
            command=self.COMMAND,
            entrypoint=self.ENTRYPOINT,
            environment=self.environment,
            image=self.IMAGE,
            log_config=log_config,
            name=config.name,
            ports=self.ports,
            volumes=self.volumes,
            **kwargs,
        )

    @classmethod
    def host_http_port(cls):
        return cls.HTTP_PORT + cls._port_offset

    @classmethod
    def host_bus_port(cls):
        return cls.BUS_PORT + cls._port_offset
