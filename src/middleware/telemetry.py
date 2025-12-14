"""
OpenTelemetry initialization for the application.
Only initialized when ENABLE_TRACING=true.
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.lib.logger import get_logger

logger = get_logger(__name__)


def init_tracing():
    """Initialize OpenTelemetry tracing if ENABLE_TRACING is true."""
    if os.getenv("ENABLE_TRACING", "false").lower() != "true":
        logger.info("tracing_disabled", message="Skipping OpenTelemetry initialization")
        return False

    logger.info("tracing_initializing", message="Starting OpenTelemetry SDK")

    # Create resource with service name
    resource = Resource(
        attributes={
            "service.name": os.getenv("OTEL_SERVICE_NAME", "performant-python"),
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    logger.info(
        "tracing_initialized",
        endpoint=otlp_endpoint,
        service_name=os.getenv("OTEL_SERVICE_NAME", "performant-python"),
    )
    return True


def instrument_fastapi(app):
    """Instrument FastAPI app if tracing is enabled."""
    if os.getenv("ENABLE_TRACING", "false").lower() == "true":
        FastAPIInstrumentor.instrument_app(app)
        logger.info("fastapi_instrumented", message="FastAPI instrumented for tracing")
