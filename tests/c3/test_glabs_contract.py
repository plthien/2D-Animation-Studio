"""G-Labs donor wire-contract tests: no live provider or paid network requests."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.animation.provider.glabs_webhook_client import GLabsWebhookClient
from app.animation.provider import AppError

class FakeHttpTransport:
    calls=[]
    def request_json(self,*,method,url,headers,body,expected_status,**kwargs):
        self.calls.append((method,url,headers.get("X-API-Key"),body,expected_status))
        if url.endswith("api/image/generate"):
            assert method=="POST" and expected_status==202
            return {"task_id":"ABCDEF12","status":"pending"}
        if url.endswith("api/status/abcdef12"):
            return {"task_id":"abcdef12","status":"completed"}
        if url.endswith("api/result/abcdef12"):
            return {"task_id":"abcdef12","status":"completed",
                    "results":["http://127.0.0.1:8765/files/result.png"]}
        raise AssertionError("Unexpected donor wire endpoint: "+url)

    def download_to_file(self,*,url,destination,max_bytes,**kwargs):
        raw=(b"\x89PNG\r\n\x1a\n"+b"\x00"*128)
        assert max_bytes>=len(raw)
        destination.write_bytes(raw)
        return SimpleNamespace(content_type="image/png",size_bytes=len(raw),
                               sha256=hashlib.sha256(raw).hexdigest())

def test_glabs_real_donor_endpoint_and_task_protocol(tmp_path):
    wire=FakeHttpTransport()
    client=GLabsWebhookClient({"base_url":"http://127.0.0.1:8765","api_key":"fake-only"},
                              transport=wire)
    sent=client.submit_image({"prompt":"Cartoon hero","model":"nano_banana_2"})
    assert sent["task_id"]=="abcdef12"
    status=client.get_status(sent["task_id"])
    assert status["status"]=="completed"
    result=client.get_result(sent["task_id"])
    image=tmp_path/"image.png"
    info=client.download_file(result["results"][0],image,1024)
    assert info.mime_type=="image/png" and info.sha256==hashlib.sha256(image.read_bytes()).hexdigest()
    assert wire.calls[0][0:3]==("POST","http://127.0.0.1:8765/api/image/generate","fake-only")

def test_donor_rejects_invalid_task_and_remote_download_url():
    client=GLabsWebhookClient({"base_url":"http://127.0.0.1:8765","api_key":"fake-only"},
                              transport=FakeHttpTransport())
    with pytest.raises(AppError):
        client.normalize_task_id("INVALID-TASK-IDENTITY")
    with pytest.raises(AppError):
        client.validate_result_url("https://malicious.example/file.png")


def test_provider_error_diagnostics_redact_keys():
    from app.animation.provider.redaction import sanitize_diagnostic_value
    safe=sanitize_diagnostic_value({"Authorization":"Bearer secret",
                                   "error":"authorization: private-token"})
    assert safe["Authorization"]=="[REDACTED]"
    assert "private-token" not in safe["error"]
    assert "[REDACTED]" in safe["error"]
