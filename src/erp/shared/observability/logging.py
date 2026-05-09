import logging
import sys

import structlog

from erp.shared.context import actor_id_var, tenant_id_var, trace_id_var

_shared_logger = None


def _add_context_vars(logger, method_name, event_dict):
    tid = tenant_id_var.get("")
    trid = trace_id_var.get("")
    aid = actor_id_var.get("")
    if tid:
        event_dict["tenant_id"] = tid
    if trid:
        event_dict["trace_id"] = trid
    if aid:
        event_dict["actor_id"] = aid
    return event_dict


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    global _shared_logger

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        _add_context_vars,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    _shared_logger = structlog.get_logger("erp")


def get_logger(name: str = "erp") -> structlog.stdlib.BoundLogger:
    if _shared_logger is None:
        setup_logging()
    return structlog.get_logger(name)
