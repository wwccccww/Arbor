from tests.api.test_auth import test_grants_revoke_chat, test_memory_hidden_without_grant


def test_persona_grants():
    test_memory_hidden_without_grant()
    test_grants_revoke_chat()
