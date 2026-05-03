"""
Request tracing support for service-to-service calls.
"""
import uuid
from contextvars import ContextVar


REQUEST_ID_HEADER = "X-Request-Id"
REQUEST_ID_META_KEY = "HTTP_X_REQUEST_ID"
REQUEST_ID_MAX_LENGTH = 64

_current_request_id = ContextVar("current_request_id", default=None)


def normalize_request_id(value):
    """Return a usable request id, or an empty string when the header is invalid."""
    if value is None:
        return ""
    request_id = str(value).strip()
    if not request_id or len(request_id) > REQUEST_ID_MAX_LENGTH:
        return ""
    if "\n" in request_id or "\r" in request_id:
        return ""
    return request_id


def get_current_request_id(default=None):
    return _current_request_id.get() or default


class RequestTracingMiddleware:
    """
    Attach a request id to each request and response.

    Incoming X-Request-Id is reused when valid. Otherwise a UUID is generated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = normalize_request_id(request.META.get(REQUEST_ID_META_KEY))
        if not request_id:
            request_id = str(uuid.uuid4())

        request.request_id = request_id
        token = _current_request_id.set(request_id)
        try:
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            _current_request_id.reset(token)


class RequestIdLogFilter:
    """Add request_id to log records so formatters can include it."""

    def filter(self, record):
        record.request_id = get_current_request_id("-")
        return True
