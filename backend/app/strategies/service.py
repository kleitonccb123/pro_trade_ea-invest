from __future__ import annotations

import ast
import re
from typing import Any, Optional, Dict, Tuple
from datetime import datetime, timedelta
from bson import ObjectId

from app.strategies.model import UserStrategy
from app.strategies.schemas import StrategyValidationResponse


# Valida??o de estrat?gias submetidas
class StrategySubmissionService:
    """Servi?o para validar e gerenciar submiss?es de estrat?gias"""

    @staticmethod
    def validate_python_code(code: str) -> Tuple[bool, Optional[str]]:
        """
        Valida se o c?digo Python ? v?lido
        
        Args:
            code: String contendo o c?digo Python
            
        Returns:
            Tupla (is_valid, error_message)
        """
        try:
            # Tenta fazer parsing do c?digo
            ast.parse(code)
            
            # Verifica se tem fun??es ou classes definidas
            tree = ast.parse(code)
            has_definitions = any(
                isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                for node in ast.walk(tree)
            )
            
            if not has_definitions:
                return False, "C?digo deve conter pelo menos uma fun??o ou classe"
            
            return True, None
            
        except SyntaxError as e:
            return False, f"Erro de sintaxe: {e.msg} (linha {e.lineno})"
        except Exception as e:
            return False, f"Erro ao validar c?digo: {str(e)}"

    @staticmethod
    def create_strategy_document(
        author_name: str,
        email: str,
        whatsapp: str,
        strategy_name: str,
        code: str,
    ) -> Dict[str, Any]:
        """
        Cria um documento de estrat?gia para MongoDB
        
        Args:
            author_name: Nome do autor
            email: Email do autor
            whatsapp: WhatsApp do autor
            strategy_name: Nome da estrat?gia
            code: C?digo Python
            
        Returns:
            Dicion?rio com dados da estrat?gia
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(days=50)
        
        return {
            "_id": ObjectId(),
            "authorName": author_name,
            "email": email,
            "whatsapp": whatsapp,
            "strategyName": strategy_name,
            "code": code,
            "submittedAt": now,
            "expiresAt": expires_at,
            "createdAt": now,
            "updatedAt": now,
            "status": "active",
            "views": 0,
            "likes": 0,
        }

    @staticmethod
    def format_expires_at(expires_at: datetime) -> str:
        """Formata data de expira??o"""
        return expires_at.isoformat()

    @staticmethod
    async def create_ttl_index(collection):
        """
        Cria ?ndice TTL para expirar documentos automaticamente ap?s expiresAt
        
        Args:
            collection: Cole??o MongoDB
        """
        try:
            await collection.create_index(
                "expiresAt",
                expireAfterSeconds=0,
            )
            print("? ?ndice TTL criado com sucesso na cole??o de estrat?gias")
        except Exception as e:
            print(f"??  Erro ao criar ?ndice TTL: {e}")


class StrategyValidationService:

    # Forbidden imports
    FORBIDDEN_MODULES = {
        "os", "sys", "subprocess", "socket", "urllib",
        "requests", "exec", "eval", "compile",
    }

    @staticmethod
    def validate_strategy_code(code: str) -> StrategyValidationResponse:
        """Validate user strategy code"""
        errors = []
        warnings = []

        # Check if code is empty
        if not code or not code.strip():
            errors.append("Strategy code cannot be empty")
            return StrategyValidationResponse(is_valid=False, errors=errors, warnings=warnings)

        # Try to parse the code as valid Python
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error: {str(e)}")
            return StrategyValidationResponse(is_valid=False, errors=errors, warnings=warnings)

        # Validate imports
        imports_errors, imports_warnings = StrategyValidationService._validate_imports(tree)
        errors.extend(imports_errors)
        warnings.extend(imports_warnings)

        # Check for required functions
        required_functions_errors = StrategyValidationService._check_required_functions(tree)
        errors.extend(required_functions_errors)

        # Check for forbidden patterns
        forbidden_errors = StrategyValidationService._check_forbidden_patterns(code)
        errors.extend(forbidden_errors)

        # Check code complexity
        complexity_warnings = StrategyValidationService._check_complexity(code)
        warnings.extend(complexity_warnings)

        is_valid = len(errors) == 0

        return StrategyValidationResponse(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _validate_imports(tree: ast.AST) -> tuple[list[str], list[str]]:
        """Validate imports in the AST"""
        errors = []
        warnings = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    if module_name in StrategyValidationService.FORBIDDEN_MODULES:
                        errors.append(f"Forbidden module: {module_name}")
                    elif module_name not in StrategyValidationService.ALLOWED_MODULES and not StrategyValidationService._is_builtin(module_name):
                        warnings.append(f"Unrecognized module: {module_name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split(".")[0]
                    if module_name in StrategyValidationService.FORBIDDEN_MODULES:
                        errors.append(f"Forbidden module: {module_name}")
                    elif module_name not in StrategyValidationService.ALLOWED_MODULES and not StrategyValidationService._is_builtin(module_name):
                        warnings.append(f"Unrecognized module: {module_name}")

        return errors, warnings

    @staticmethod
    def _check_required_functions(tree: ast.AST) -> list[str]:
        """Check if required functions exist in the code"""
        errors = []
        defined_functions = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                defined_functions.add(node.name)

        for required_func in StrategyValidationService.REQUIRED_FUNCTIONS:
            if required_func not in defined_functions:
                errors.append(f"Missing required function: {required_func}")

        return errors

    @staticmethod
    def _check_forbidden_patterns(code: str) -> list[str]:
        """Check for forbidden patterns in code"""
        errors = []

        # Check for eval, exec, compile
        forbidden_patterns = [
            (r"\beval\s*\(", "eval() is not allowed"),
            (r"\bexec\s*\(", "exec() is not allowed"),
            (r"\bcompile\s*\(", "compile() is not allowed"),
            (r"__import__", "__import__ is not allowed"),
            (r"subprocess", "subprocess module is not allowed"),
        ]

        for pattern, message in forbidden_patterns:
            if re.search(pattern, code):
                errors.append(message)

        return errors

    @staticmethod
    def _check_complexity(code: str) -> list[str]:
        """Check code complexity and give warnings"""
        warnings = []

        # Warn if code is very long
        lines = code.split("\n")
        if len(lines) > 500:
            warnings.append("Strategy code is very long (>500 lines). Consider simplifying it.")

        # Warn if indentation is too deep
        max_indent = 0
        for line in lines:
            indent = len(line) - len(line.lstrip())
            max_indent = max(max_indent, indent)
        
        if max_indent > 24:  # More than 6 levels of indentation
            warnings.append("Code has very deep nesting. Consider refactoring.")

        return warnings

    @staticmethod
    def _is_builtin(module_name: str) -> bool:
        """Check if module is a Python builtin"""
        builtins = {
            "builtins", "collections", "itertools", "functools",
            "operator", "math", "statistics", "random",
            "datetime", "time", "json", "csv",
            "decimal", "fractions", "numbers",
        }
        return module_name in builtins


class StrategyExecutionService:
    """Service for executing strategy logic"""

    @staticmethod
    async def validate_and_prepare_strategy(code: str) -> dict[str, Any]:
        """Validate code and prepare for execution"""
        validation_result = StrategyValidationService.validate_strategy_code(code)

        if not validation_result.is_valid:
            raise ValueError(f"Invalid strategy: {', '.join(validation_result.errors)}")

        # Create a safe execution environment
        safe_globals = {
            "math": __import__("math"),
            "statistics": __import__("statistics"),
            "datetime": __import__("datetime"),
            "decimal": __import__("decimal"),
        }

        # Try to execute the code in safe environment
        try:
            exec(code, safe_globals)
        except Exception as e:
            raise ValueError(f"Error executing strategy code: {str(e)}")

        return {
            "on_buy_signal": safe_globals.get("on_buy_signal"),
            "on_sell_signal": safe_globals.get("on_sell_signal"),
            "warnings": validation_result.warnings,
        }
