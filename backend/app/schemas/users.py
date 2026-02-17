from pydantic import BaseModel, EmailStr


class PrivilegedUserCreate(BaseModel):
    email: EmailStr


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str

    class Config:
        from_attributes = True
