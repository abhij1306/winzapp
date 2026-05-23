from app.schemas.common import ErrorDetail, ErrorEnvelope, PaginationMeta


def test_error_envelope_serializes_expected_shape() -> None:
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code="INVALID_INPUT",
            message="Invalid input",
            details={"field": "name"},
            request_id="req-123",
        ),
    )

    assert envelope.model_dump() == {
        "error": {
            "code": "INVALID_INPUT",
            "message": "Invalid input",
            "details": {"field": "name"},
            "request_id": "req-123",
        },
    }


def test_pagination_meta_serializes_expected_fields() -> None:
    meta = PaginationMeta(page=1, page_size=20, total=100)

    assert meta.model_dump() == {
        "page": 1,
        "page_size": 20,
        "total": 100,
    }
