from pydantic import BaseModel, ConfigDict, Field


class ClinicSettingsData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    owner_name: str | None
    clinic_type: str | None
    whatsapp_number: str
    owner_whatsapp: str
    address: str | None
    city: str | None
    pincode: str | None
    timezone: str
    plan: str
    plan_active: bool
    settings: dict[str, object]


class ClinicSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ClinicSettingsData


class ClinicSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    owner_name: str | None = None
    address: str | None = None
    city: str | None = None
    pincode: str | None = None
    google_place_id: str | None = None
    gbp_review_link: str | None = None
    timezone: str | None = None
    settings: dict[str, object] | None = None
