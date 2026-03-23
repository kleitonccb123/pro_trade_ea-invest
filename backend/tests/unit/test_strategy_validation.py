"""
Unit Tests — Strategy Validation
==================================

Tests for StrategySubmissionService.validate_python_code().
"""

import pytest

from app.strategies.service import StrategySubmissionService


class TestValidatePythonCode:
    svc = StrategySubmissionService

    def test_valid_function(self):
        code = "def my_strategy():\n    return True"
        ok, msg = self.svc.validate_python_code(code)
        assert ok is True
        assert msg is None

    def test_valid_class(self):
        code = "class MyStrategy:\n    pass"
        ok, msg = self.svc.validate_python_code(code)
        assert ok is True

    def test_valid_async_function(self):
        code = "async def my_strategy():\n    return True"
        ok, msg = self.svc.validate_python_code(code)
        assert ok is True

    def test_syntax_error(self):
        code = "def broken(\n"
        ok, msg = self.svc.validate_python_code(code)
        assert ok is False
        assert "sintaxe" in msg.lower() or "syntax" in msg.lower()

    def test_no_definitions(self):
        code = "x = 42\nprint(x)"
        ok, msg = self.svc.validate_python_code(code)
        assert ok is False
        assert "função" in msg.lower() or "classe" in msg.lower() or "class" in msg.lower()

    def test_empty_string(self):
        ok, msg = self.svc.validate_python_code("")
        assert ok is False

    def test_multiple_functions(self):
        code = "def a():\n    pass\ndef b():\n    pass"
        ok, msg = self.svc.validate_python_code(code)
        assert ok is True
