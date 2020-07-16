"""Classes and utilities to use a Monitor for log events."""

import asyncio
from datetime import datetime
from enum import Enum
import logging
import re
import time
from typing import Iterator, Optional

from goth.assertions.monitor import EventMonitor
from goth.runner.log import LogConfig

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Enum representing the rust log levels."""

    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4
    TRACE = 5


# Pattern to match log lines from the `yagna` binary
pattern = re.compile(
    r"^\[(?P<datetime>[^ ]+) (?P<level>[^ ]+) (?P<module>[^\]]+)\] (?P<message>.*)"
)


class LogEvent:
    """An event representing a log line, used for asserting messages."""

    def __init__(self, log_message: str):
        self._timestamp = None
        self._level = None
        self._module = None
        self._message = log_message
        match = pattern.match(log_message)
        if match:
            result = match.groupdict()

            try:
                formatted_time = datetime.strptime(
                    result["datetime"], "%Y-%m-%dT%H:%M:%SZ"
                )
            except Exception:
                pass
            else:
                self._timestamp = formatted_time.timestamp()
                self._level = LogLevel[result["level"]]
                self._module = result["module"]
                self._message = result["message"]
        if not self._timestamp:
            self._timestamp = time.time()

    @property
    def timestamp(self) -> float:
        """Time of the log message.

        (or time of receiving the event when _module is None)
        """
        return self._timestamp

    @property
    def level(self) -> Optional[LogLevel]:
        """Level reported on the log message.

        Will be empty for multi line logs.
        """
        return self._level

    @property
    def module(self) -> Optional[str]:
        """Source module of this log message.

        Will be empty for multi line logs.
        """
        return self._module

    @property
    def message(self) -> str:
        """Text of the log message."""
        return self._message

    def __repr__(self):
        return (
            f"<LogEvent time={self.timestamp:0.0f}, level={self.level},"
            f" module={self.module}, message={self.message},  >"
        )


def _create_file_logger(config: LogConfig) -> logging.Logger:
    """Create a new file logger configured using the `LogConfig` object provided.

    The target log file will have a .log extension.
    """

    handler = logging.FileHandler(
        (config.base_dir / config.file_name).with_suffix(".log"), encoding="utf-8"
    )
    handler.setFormatter(config.formatter)
    logger_ = logging.getLogger(str(config.file_name))
    logger_.setLevel(config.level)
    logger_.addHandler(handler)
    logger_.propagate = False
    return logger_


class LogEventMonitor(EventMonitor[LogEvent]):
    """Buffers logs coming from `in_stream`.

    `log_config` holds the configuration of the file logger.
    Consecutive values are interpreted as lines by splitting them on the new line
    character. Internally, it uses a asyncio task to read the stream and add lines to
    the buffer.
    """

    in_stream: Iterator[bytes]
    logger: logging.Logger

    def __init__(self, log_config: LogConfig):
        super().__init__()
        self.logger = _create_file_logger(log_config)

    def start(self, in_stream: Iterator[bytes]):
        """Start reading the logs."""
        super().start()
        self.in_stream = in_stream
        loop = asyncio.get_event_loop()
        self._buffer_task = loop.run_in_executor(None, self._buffer_input)

        logger.debug(
            "Started LogEventMonitor. stream=%r, logger=%r",
            self.in_stream,
            self.logger,
        )

    def _buffer_input(self):
        logger.debug("Start reading input. name=%s", self.logger.name)

        for chunk in self.in_stream:
            chunk = chunk.decode()
            for line in chunk.splitlines():
                self.logger.info(line)

                event = LogEvent(line)
                logger.debug("[%s] event=%s", self.logger.name, event)
                self.add_event(event)
