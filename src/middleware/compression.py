"""
Compression middleware using zstandard for FastAPI.
Provides better compression ratios and speed compared to gzip.
"""
from typing import Callable
import zstandard as zstd
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.lib.logger import get_logger

logger = get_logger(__name__)


class ZstdMiddleware:
    """
    ZSTD (Zstandard) compression middleware for FastAPI/Starlette.
    
    Features:
    - Better compression ratio than gzip (20-30% smaller)
    - Faster compression/decompression
    - Modern browsers support (Chrome, Firefox, Safari, Edge)
    
    Args:
        minimum_size: Minimum response size in bytes to compress (default 1000)
        compression_level: Compression level 1-22 (default 3, balanced speed/ratio)
    """
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 1000,
        compression_level: int = 3,
    ) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.compressor = zstd.ZstdCompressor(level=compression_level)
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Check if client accepts zstd
        headers = Headers(scope=scope)
        accept_encoding = headers.get("accept-encoding", "")
        
        if "zstd" not in accept_encoding.lower():
            # Client doesn't support zstd, pass through
            await self.app(scope, receive, send)
            return
        
        # Intercept response
        responder = ZstdResponder(
            self.app, self.compressor, self.minimum_size
        )
        await responder(scope, receive, send)


class ZstdResponder:
    """Handles the actual compression of responses."""
    
    def __init__(
        self,
        app: ASGIApp,
        compressor: zstd.ZstdCompressor,
        minimum_size: int,
    ) -> None:
        self.app = app
        self.compressor = compressor
        self.minimum_size = minimum_size
        self.send: Send = None  # type: ignore
        self.initial_message: Message = {}
        self.started = False
        self.content_length = 0
        self.buffer = bytearray()
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.app(scope, receive, self.send_with_compression)
    
    async def send_with_compression(self, message: Message) -> None:
        message_type = message["type"]
        
        if message_type == "http.response.start":
            # Store the initial message, don't send yet
            self.initial_message = message
            headers = MutableHeaders(raw=list(message["headers"]))
            
            # Get content length if available
            if "content-length" in headers:
                self.content_length = int(headers["content-length"])
            
        elif message_type == "http.response.body":
            # Accumulate body
            body = message.get("body", b"")
            if body:
                self.buffer.extend(body)
            
            # Check if this is the last chunk
            if not message.get("more_body", False):
                # All body received, decide whether to compress
                headers = MutableHeaders(raw=list(self.initial_message["headers"]))
                
                # Don't compress if already compressed or too small
                if (
                    "content-encoding" in headers
                    or len(self.buffer) < self.minimum_size
                ):
                    # Send original response
                    await self.send(self.initial_message)
                    await self.send({"type": "http.response.body", "body": bytes(self.buffer)})
                else:
                    # Compress and send
                    original_size = len(self.buffer)
                    compressed = self.compressor.compress(bytes(self.buffer))
                    compressed_size = len(compressed)
                    compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
                    
                    # Log compression metrics
                    logger.debug("response_compressed",
                               original_size=original_size,
                               compressed_size=compressed_size,
                               compression_ratio_percent=round(compression_ratio, 2))
                    
                    # Update headers
                    headers["content-encoding"] = "zstd"
                    headers["content-length"] = str(compressed_size)
                    if "vary" in headers:
                        headers["vary"] = headers["vary"] + ", Accept-Encoding"
                    else:
                        headers["vary"] = "Accept-Encoding"
                    
                    # Remove any existing content-length
                    self.initial_message["headers"] = headers.raw
                    
                    # Send compressed response
                    await self.send(self.initial_message)
                    await self.send({"type": "http.response.body", "body": compressed})
                    await self.send(self.initial_message)
                    await self.send({"type": "http.response.body", "body": compressed})
