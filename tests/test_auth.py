from __future__ import annotations

from erp.modules.iam.domain.auth import hash_password, verify_password


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "Test@123456"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("Correct@123")
        assert verify_password("Wrong@123", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("Same@123")
        h2 = hash_password("Same@123")
        assert h1 != h2
