"""Pydantic models for JForex4 integration configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class JForexCredentials(BaseModel):
    """Connection credentials for a local JForex4 instance.

    Attributes:
        username: JForex4 platform username.
        password: JForex4 platform password (stored as secret).
        host: JForex4 server host (default: localhost).
        port: JForex4 server port (default: 11111).
        account_id: Optional trading account identifier.
    """

    model_config = ConfigDict(
        json_encoders={SecretStr: lambda v: v.get_secret_value() if v else None}
    )

    username: str = Field(..., description="JForex4 platform username")
    password: SecretStr = Field(..., description="JForex4 platform password")
    host: str = Field(default="127.0.0.1", description="JForex4 server host")
    port: int = Field(default=11111, ge=1, le=65535, description="JForex4 server port")
    account_id: str | None = Field(default=None, description="Optional trading account identifier")
