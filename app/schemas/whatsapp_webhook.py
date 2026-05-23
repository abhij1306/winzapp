from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_MESSAGE_TYPES = {
    "text",
    "interactive",
    "button",
    "location",
    "image",
    "document",
}


class WAText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str


class WALocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float
    name: str | None = None
    address: str | None = None


class WAMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str
    text: WAText | None = None
    location: WALocation | None = None
    interactive: dict[str, object] | None = None
    button: dict[str, object] | None = None
    image: dict[str, object] | None = None
    document: dict[str, object] | None = None

    @field_validator("type")
    @classmethod
    def validate_supported_type(cls, value: str) -> str:
        if value not in SUPPORTED_MESSAGE_TYPES:
            raise ValueError(f"Unsupported WhatsApp message type: {value}")
        return value


class WAContactProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None


class WAContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wa_id: str
    profile: WAContactProfile | None = None


class WAValueMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_phone_number: str | None = None
    phone_number_id: str


class WAChangeValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messaging_product: str | None = None
    metadata: WAValueMetadata | None = None
    contacts: list[WAContact] = Field(default_factory=list)
    messages: list[WAMessage] = Field(default_factory=list)


class WAChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    value: WAChangeValue


class WAEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    changes: list[WAChange] = Field(default_factory=list)


class WAWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object: str
    entry: list[WAEntry]

    @field_validator("object")
    @classmethod
    def validate_whatsapp_object(cls, value: str) -> str:
        if value != "whatsapp_business_account":
            raise ValueError("Webhook payload is not a WhatsApp business account event")
        return value
