"""
Structured logging configuration using structlog.

Provides:
- JSON formatted logs for production (Docker/containers)
- Colored console logs for development (local TTY)
- Automatic OpenTelemetry trace context binding
- Performance-optimized processors
- Stack trace capture for errors
"""
import sys
import logging
import structlog
from structlog.types import EventDict, WrappedLogger
from typing import Any
from opentelemetry import trace


def add_open_telemetry_spans(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add OpenTelemetry trace and span IDs to log records."""
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def add_app_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application-level context to all logs."""
    event_dict["app"] = "performant-python"
    return event_dict


def configure_structlog(json_logs: bool = None) -> None:
    """
    Configure structlog for the application.
    
    Args:
        json_logs: If True, output JSON. If False, colored console.
                   If None, auto-detect (JSON if not a TTY, colored if TTY)
    """
    # Auto-detect if not specified
    if json_logs is None:
        json_logs = not sys.stderr.isatty()
    
    # Configure standard logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )
    
    # Common processors for all configurations
    processors = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add OpenTelemetry trace context
        add_open_telemetry_spans,
        # Add app context
        add_app_context,
        # Stack traces for exceptions
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if json_logs:
        # Production: JSON output
        processors.extend([
            # Render as JSON
            structlog.processors.JSONRenderer(sort_keys=True)
        ])
    else:
        # Development: Colored console output
        processors.extend([
            # Add colors
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__ for the module)
    
    Returns:
        Configured structlog logger
        
    Usage:
        logger = get_logger(__name__)
        logger.info("cache_hit", key="user:123", latency_ms=2.1)
        
        # Development output:
        [2024-12-14 17:14:02] cache_hit    key=user:123 latency_ms=2.1
        
        # Production output (JSON):
        {"event": "cache_hit", "key": "user:123", "latency_ms": 2.1, 
         "timestamp": "2024-12-14T11:44:02.123456Z", "level": "info"}
    """
    return structlog.get_logger(name)


# Initialize on import with auto-detection
configure_structlog()
