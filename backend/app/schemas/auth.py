from pydantic import BaseModel


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthToken(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    role: str
    email: str
    name: str
