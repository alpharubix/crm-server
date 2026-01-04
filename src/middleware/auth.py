from starlette.requests import Request
from starlette.responses import RedirectResponse
from src.utility.utils import get_decoded_jwt_token

SCOPE = {'super_admin':['Read.ALL','Write.ALL'],'executive':['Read.OWN']} #pre-defined scope for authentication

async def authorization(request: Request, call_next):
    print('Im exceuting')
    print(request.url.path)
    if request.url.path.rstrip('/') == '/login':
        response =  await call_next(request)
        return response
    token = request.cookies.get('token')
    if not token:
        return RedirectResponse('/login')
    else:
        decoded_jwt_token = get_decoded_jwt_token(token)
        user_id = decoded_jwt_token['user_id']
        role = decoded_jwt_token['role']
        scope = SCOPE[role]
        request.state.scope = scope
        request.state.user_id = user_id
        request.state.role = role
    response = await call_next(request)
    return response


