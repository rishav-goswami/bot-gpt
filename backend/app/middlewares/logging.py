# File: app/middlewares/logging.py
import time
import json
import logging
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings


# Configure Root Logger to output JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        return json.dumps(log_obj)


logger = logging.getLogger("api_logger")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(settings.LOG_LEVEL)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Generate Request ID (for tracing across services)
        request_id = str(uuid.uuid4())

        # 2. Start Timer
        start_time = time.time()

        # 3. Process Request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log Crash
            process_time = time.time() - start_time
            logger.error(f"Request failed: {str(e)}", extra={"request_id": request_id})
            raise e

        # 4. Calculate Duration
        process_time = time.time() - start_time

        # 5. Log structured data
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(process_time * 1000, 2),
            "client_ip": request.client.host if request.client else "unknown",
            "request_id": request_id,
        }

        # Log 4xx/5xx as errors/warnings, 2xx as info
        if response.status_code >= 500:
            logger.error(json.dumps(log_data), extra={"request_id": request_id})
        elif response.status_code >= 400:
            logger.warning(json.dumps(log_data), extra={"request_id": request_id})
        else:
            logger.info(json.dumps(log_data), extra={"request_id": request_id})

        # Add Request ID to Response Headers (for debugging on frontend)
        response.headers["X-Request-ID"] = request_id

        return response
