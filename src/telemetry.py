"""
OpenTelemetry initialization for the application.
Only initialized when ENABLE_TRACING=true.
"""
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def init_tracing():
    """Initialize OpenTelemetry tracing if ENABLE_TRACING is true."""
    if os.getenv("ENABLE_TRACING", "false").lower() != "true":
        print("⏭️  Tracing disabled, skipping OpenTelemetry initialization")
        return False
    
    print("🔧 Initializing OpenTelemetry SDK...")
    
    # Create resource with service name
    resource = Resource(attributes={
        "service.name": os.getenv("OTEL_SERVICE_NAME", "performant-python"),
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Add OTLP exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    
    print(f"✅ OpenTelemetry initialized | Endpoint: {otlp_endpoint}")
    return True

def instrument_fastapi(app):
    """Instrument FastAPI app if tracing is enabled."""
    if os.getenv("ENABLE_TRACING", "false").lower() == "true":
        FastAPIInstrumentor.instrument_app(app)
        print("✅ FastAPI instrumented for tracing")
