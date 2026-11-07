from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: SecretStr = Field(min_length=12, max_length=128)


class PlayerLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: SecretStr = Field(max_length=128)


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: SecretStr = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
