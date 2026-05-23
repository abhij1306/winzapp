from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportReadyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: str
    patient_phone: str = Field(min_length=8)
    test_name: str = Field(min_length=1)
    report_pdf_url: str | None = None
    report_pdf_base64: str | None = None

    @model_validator(mode="after")
    def require_one_pdf_source(self) -> "ReportReadyRequest":
        has_url = bool(self.report_pdf_url)
        has_base64 = bool(self.report_pdf_base64)
        if has_url == has_base64:
            raise ValueError("Provide exactly one of report_pdf_url or report_pdf_base64")
        return self


class ReportReadyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: str
    status: str
    report_file_path: str


class ReportReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ReportReadyData
