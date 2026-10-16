import pytest
from app.animation.strict_json import parse_strict_document
from app.animation.service import DomainError
from app.animation.process.host_owned_process import HostOwnedProcess

def test_strict_json_duplicate_keys_and_nonfinite():
    assert parse_strict_document('{"valid":true}')=={"valid":True}
    for text in ('{"a":1,"a":2}', '{"value":NaN}', '[1]', 'not JSON'):
        with pytest.raises(DomainError):
            parse_strict_document(text)

def test_strict_json_bounded_size():
    with pytest.raises(DomainError) as got:
        parse_strict_document('{"x":"12345"}', max_bytes=6)
    assert got.value.code=="IMPORT_TOO_LARGE"

def test_process_owner_importable_without_legacy():
    assert HostOwnedProcess.__module__.startswith("app.animation.process.")
