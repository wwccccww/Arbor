from tests.api.test_auth import test_auth_missing_bearer, test_error_shape, test_tenant_mismatch_not_found


def test_forbidden_codes():
    test_auth_missing_bearer()
    test_tenant_mismatch_not_found()
    test_error_shape()
