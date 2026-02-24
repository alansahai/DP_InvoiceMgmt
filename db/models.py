from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserModel(BaseModel):
    id: Optional[int] = None
    email: EmailStr
    password_hash: str
    role: str
    created_at: Optional[datetime] = None
