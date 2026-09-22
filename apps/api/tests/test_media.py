from app import media


def test_save_and_read_bytes_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    org_id = "11111111-1111-1111-1111-111111111111"

    storage_path = media.save_bytes(org_id, b"fake-jpeg-bytes", ".jpg")

    assert storage_path.startswith(f"{org_id}/")
    assert storage_path.endswith(".jpg")
    assert media.read_bytes(storage_path) == b"fake-jpeg-bytes"


def test_save_bytes_creates_org_subdirectory(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    org_id = "22222222-2222-2222-2222-222222222222"

    media.save_bytes(org_id, b"x", ".jpg")

    assert (tmp_path / org_id).is_dir()


def test_download_telegram_photo_returns_none_on_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(media.httpx, "get", boom)
    assert media.download_telegram_photo("token", "file123") is None
