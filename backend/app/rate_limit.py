"""Rate limiting configuration using slowapi.

Provides a shared Limiter instance that can be imported by routers.
The limiter must also be attached to app.state in main.py for the
exception handler to work.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
