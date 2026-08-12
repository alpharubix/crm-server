from starlette import status
from starlette.responses import JSONResponse


async def authorize_invoice_route_user(request,call_next):
    try:
        if request.url.path.startswith("/invoice") and request.state.role not in ("super_admin", "admin"):
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "You are not authorized to view this resource"})
        else:
            return await call_next(request)
    except Exception as e:
        print(e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message":"Internal server error"})
