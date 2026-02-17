"""PyInstaller runtime hook for FastAPI dependency injection."""

# Force import of all FastAPI dependency modules
import fastapi
import fastapi.dependencies
import fastapi.dependencies.utils
import fastapi.routing
import fastapi.params
import fastapi.utils

# Ensure starlette Request is properly collected
import starlette.requests
import starlette.responses
import starlette.routing
import starlette.middleware
import starlette.exceptions
import starlette.concurrency

# Force collection of all fastapi submodules
import fastapi.encoders
import fastapi.exception_handlers
import fastapi.openapi
import fastapi.openapi.constants
import fastapi.openapi.docs
import fastapi.openapi.utils
import fastapi.security
