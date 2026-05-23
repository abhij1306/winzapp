from pydantic import BaseModel, ConfigDict, Field


class OtpSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_whatsapp: str = Field(min_length=8)


class OtpVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_whatsapp: str = Field(min_length=8)
    otp: str = Field(pattern=r"^\d{6}$")


class OtpSendData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class OtpSendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OtpSendData


class OtpVerifyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str
    expires_in: int


class OtpVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OtpVerifyData
