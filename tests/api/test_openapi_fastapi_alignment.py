from scripts.validate_openapi_fastapi import main as validate_fastapi_alignment


def test_openapi_fastapi_path_alignment():
    assert validate_fastapi_alignment() == 0
