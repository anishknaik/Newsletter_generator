"""Shared rate limiter (slowapi), keyed by client IP.

Defined in its own module so both main.py and the route modules can import the
same instance. In-memory storage is fine for a single-process dev/portfolio app;
swap to Redis storage for a multi-worker deployment.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
