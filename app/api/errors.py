from uuid import uuid4

from fastapi.responses import JSONResponse

from app.schemas.common import ErrorDetail, ErrorEnvelope


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or {},
            request_id=str(uuid4()),
        ),
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())
