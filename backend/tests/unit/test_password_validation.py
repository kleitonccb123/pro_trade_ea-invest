"""
Unit Tests — Password Strength Validation
==========================================

Tests the validate_password_strength function from auth/router.py.
"""

import pytest

from app.auth.router import validate_password_strength


class TestPasswordStrength:
    """All rules: 8-128 chars, 1 upper, 1 lower, 1 digit, 1 special."""

    # ── Valid passwords ─────────────────────────────────────────────

    @pytest.mark.parametrize("pwd", [
        "Abcdef1!",          # exact minimum (8 chars)
        "MyStr0ng@Pass",
        "Super$ecure99",
        "C0mpl3x!Passw0rd",
        "A" * 120 + "a1!abcd",  # near max length
    ])
    def test_valid_passwords(self, pwd):
        ok, msg = validate_password_strength(pwd)
        assert ok is True, f"Expected valid but got: {msg}"
        assert msg == ""

    # ── Too short ───────────────────────────────────────────────────

    def test_too_short(self):
        ok, msg = validate_password_strength("Ab1!xyz")
        assert ok is False
        assert "mínimo" in msg.lower() or "8" in msg

    def test_empty_password(self):
        ok, msg = validate_password_strength("")
        assert ok is False

    # ── Too long ────────────────────────────────────────────────────

    def test_too_long(self):
        pwd = "Aa1!" + "x" * 125  # 129 chars
        ok, msg = validate_password_strength(pwd)
        assert ok is False
        assert "máximo" in msg.lower() or "128" in msg

    # ── Missing uppercase ───────────────────────────────────────────

    def test_no_uppercase(self):
        ok, msg = validate_password_strength("abcdef1!")
        assert ok is False
        assert "maiúscula" in msg.lower() or "uppercase" in msg.lower()

    # ── Missing lowercase ───────────────────────────────────────────

    def test_no_lowercase(self):
        ok, msg = validate_password_strength("ABCDEF1!")
        assert ok is False
        assert "minúscula" in msg.lower() or "lowercase" in msg.lower()

    # ── Missing digit ───────────────────────────────────────────────

    def test_no_digit(self):
        ok, msg = validate_password_strength("Abcdefg!")
        assert ok is False
        assert "número" in msg.lower() or "digit" in msg.lower()

    # ── Missing special char ────────────────────────────────────────

    def test_no_special_char(self):
        ok, msg = validate_password_strength("Abcdefg1")
        assert ok is False
        assert "especial" in msg.lower() or "special" in msg.lower()

    # ── Edge cases ──────────────────────────────────────────────────

    def test_only_special_chars(self):
        ok, _ = validate_password_strength("!@#$%^&*")
        assert ok is False

    def test_only_digits(self):
        ok, _ = validate_password_strength("12345678")
        assert ok is False

    def test_spaces_in_password(self):
        # Spaces should not count as special char but password can contain them
        ok, _ = validate_password_strength("Ab1 defgh")
        assert ok is False  # space is not in the special char regex

    @pytest.mark.parametrize("special", list("!@#$%^&*()_+-=[]{}|;':\"\\,.<>/?`~"))
    def test_various_special_characters(self, special):
        pwd = f"Abcdef1{special}"
        ok, msg = validate_password_strength(pwd)
        assert ok is True, f"Special char '{special}' rejected: {msg}"
