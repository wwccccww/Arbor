from unittest.mock import MagicMock

from arbor.adapters.outbound.s3 import S3ObjectStorage


def test_s3_put_get_roundtrip():
    client = MagicMock()
    body = MagicMock()
    body.read.return_value = b"payload"
    client.put_object.return_value = {}
    client.get_object.return_value = {"Body": body}
    storage = S3ObjectStorage(bucket="arbor", client=client, prefix="arbor")
    key = storage.put("chat/t1/file.txt", b"payload")
    assert key == "arbor/chat/t1/file.txt"
    assert storage.get(key) == b"payload"
    client.put_object.assert_called_once_with(
        Bucket="arbor",
        Key="arbor/chat/t1/file.txt",
        Body=b"payload",
    )


def test_s3_get_missing_returns_none():
    client = MagicMock()
    err = type("E", (Exception,), {})()
    err.response = {"Error": {"Code": "NoSuchKey"}}
    from botocore.exceptions import ClientError

    client.get_object.side_effect = ClientError(err.response, "GetObject")
    storage = S3ObjectStorage(bucket="arbor", client=client, prefix="")
    assert storage.get("missing.bin") is None
