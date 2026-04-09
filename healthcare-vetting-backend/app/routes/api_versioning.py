"""
API Versioning — mount all existing route modules under /api/v1/ prefix.

Existing /api/ routes continue to work for backward compatibility.
New clients should prefer /api/v1/ so we can evolve /api/v2/ independently later.
"""
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1", tags=["API v1"])


def register_v1_routes(app) -> None:  # noqa: ANN001
    """Clone every existing /api/* route into /api/v1/*.

    Iterates over already-registered routes, and for each that starts with
    ``/api/`` it adds a mirror under ``/api/v1/``.  This avoids duplicating
    the include_router() calls in main.py — any new router added there is
    automatically available under both prefixes.
    """
    from fastapi.routing import APIRoute

    for route in list(app.routes):
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/"):
            continue
        # Build the v1 path by inserting /v1 after /api
        v1_path = "/api/v1" + route.path[4:]  # strip "/api" prefix, prepend "/api/v1"

        # Create a new route with the v1 path
        new_route = APIRoute(
            path=v1_path,
            endpoint=route.endpoint,
            methods=route.methods,
            name=f"v1_{route.name}" if route.name else None,
            response_model=route.response_model,
            status_code=route.status_code,
            tags=route.tags,
            dependencies=route.dependencies,
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            deprecated=route.deprecated,
            operation_id=f"v1_{route.operation_id}" if route.operation_id else None,
            include_in_schema=route.include_in_schema,
        )
        app.routes.append(new_route)
