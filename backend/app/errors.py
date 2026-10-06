"""Shared error type: the client sent data or parameters we cannot use.

Raised anywhere in the pipeline (parsers, transforms, filters) and turned into
an HTTP 422 response by a single handler in main.py, so bad input can never
surface as a 500.
"""


class BadRequest(ValueError):
    pass
