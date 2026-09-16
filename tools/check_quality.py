"""Локальная проверка перечисленных требований к репозиторию."""

import ast
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 1000
MAX_PYTHON_WIDTH = 80
MAX_TEXT_WIDTH = 120
MAX_FUNCTION_LINES = 40
MAX_ARGUMENTS = 7
MAX_COMPLEXITY = 10
NO_ERRORS = 0
SNAKE_CASE = re.compile(r"_?[a-z][a-z0-9_]*\Z")
CONSTANT_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")
CLASS_NAME = re.compile(r"[A-Z][A-Za-z0-9]*\Z")
COMMIT = re.compile(r"[a-z]+\([a-z0-9_-]+\): .+\Z")
SPECIAL_NAMES = {"__init__", "__name__", "__file__", "setUp"}
BANNED_PARTS = {
    "__pycache__", ".venv", "venv", ".idea", ".vscode", "build", "dist",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov",
}
BANNED_SUFFIXES = {
    ".zip", ".gz", ".tar", ".7z", ".rar", ".pyc", ".pyo", ".exe",
    ".dll", ".so", ".o", ".class", ".pdf", ".png", ".jpg", ".bundle",
}
FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
DOCUMENTED_TYPES = (ast.Module, ast.ClassDef) + FUNCTION_TYPES
BRANCH_TYPES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp,
    ast.ExceptHandler, ast.Assert,
)


def git_output(*arguments):
    """Получить текст Git; ошибка команды означает провал проверки."""
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, encoding="utf-8"
    )


def complexity(node):
    """Посчитать консервативную оценку ветвлений AST, включая assert."""
    score = 1
    for item in ast.walk(node):
        if isinstance(item, BRANCH_TYPES):
            score += 1
        if isinstance(item, ast.BoolOp):
            score += len(item.values) - 1
        if isinstance(item, ast.comprehension):
            score += 1 + len(item.ifs)
        if isinstance(item, (ast.For, ast.While, ast.Try)) and item.orelse:
            score += 1
    return score


def function_errors(node):
    """Проверить длину, число аргументов и сложность функции."""
    errors = []
    length = node.end_lineno - node.lineno + 1
    arguments = node.args
    count = len(arguments.posonlyargs + arguments.args)
    count += len(arguments.kwonlyargs)
    count += bool(arguments.vararg) + bool(arguments.kwarg)
    if length > MAX_FUNCTION_LINES:
        errors.append(f"{node.name}: длина функции {length}")
    if count > MAX_ARGUMENTS:
        errors.append(f"{node.name}: аргументов {count}")
    score = complexity(node)
    if score > MAX_COMPLEXITY:
        errors.append(f"{node.name}: сложность {score}")
    return errors


def identifier_errors(node):
    """Проверить базовые соглашения имён, разрешая API unittest."""
    name = None
    if isinstance(node, (ast.ClassDef,) + FUNCTION_TYPES):
        name = node.name
    elif isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.arg):
        name = node.arg
    if name is None or name in SPECIAL_NAMES:
        return []
    if isinstance(node, ast.ClassDef):
        valid = CLASS_NAME.fullmatch(name)
    else:
        valid = any(pattern.fullmatch(name) for pattern in (
            SNAKE_CASE, CONSTANT_NAME, CLASS_NAME
        ))
    return [] if valid else [f"имя не соответствует соглашениям: {name}"]


def is_number(node):
    """Распознать числовой литерал, включая отрицательное число."""
    if isinstance(node, ast.UnaryOp):
        return is_number(node.operand)
    if isinstance(node, ast.Constant):
        return type(node.value) in (int, float, complex)
    return False


def python_errors(text):
    """Проверить документацию, функции, имена и числа в сравнениях."""
    tree = ast.parse(text)
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, DOCUMENTED_TYPES) and not ast.get_docstring(node):
            errors.append(f"нет docstring: строка {getattr(node, 'lineno', 1)}")
        if isinstance(node, FUNCTION_TYPES):
            errors.extend(function_errors(node))
        errors.extend(identifier_errors(node))
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(is_number(operand) for operand in operands):
                errors.append(f"число в сравнении: строка {node.lineno}")
    return errors


def text_errors(text, suffix):
    """Проверить число и длину строк текстового файла."""
    errors = []
    lines = text.splitlines()
    limit = MAX_PYTHON_WIDTH if suffix == ".py" else MAX_TEXT_WIDTH
    if len(lines) > MAX_LINES:
        errors.append(f"слишком много строк: {len(lines)}")
    for number, line in enumerate(lines, start=1):
        if len(line) > limit:
            errors.append(f"строка {number}: длина {len(line)} > {limit}")
    if suffix == ".py":
        errors.extend(python_errors(text))
    return errors


def file_errors(relative):
    """Проверить один отслеживаемый файл, его тип и размер строк."""
    path = ROOT / relative
    errors = []
    if set(path.parts) & BANNED_PARTS or path.suffix in BANNED_SUFFIXES:
        errors.append("запрещённый сгенерированный файл")
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeError, OSError):
        return [f"{relative}: бинарный или недоступный файл"]
    if "\0" in text:
        errors.append("бинарное содержимое")
    errors.extend(text_errors(text, path.suffix))
    return [f"{relative}: {error}" for error in errors]


def structure_errors(files):
    """Проверить обязательные элементы именно в индексе Git."""
    errors = []
    for required in ("README.md", ".gitignore"):
        if required not in files:
            errors.append(f"Отсутствует {required}")
    for directory in ("src/", "tests/"):
        if not any(name.startswith(directory) for name in files):
            errors.append(f"Отсутствует {directory}")
    if not set(files) & {"run.sh", "run.bat", "Makefile"}:
        errors.append("Отсутствует скрипт запуска")
    return errors


def main():
    """Проверить индекс, содержимое файлов и заголовки всех коммитов."""
    files = git_output("ls-files", "-z").split("\0")
    files = [name for name in files if name]
    errors = structure_errors(files)
    for relative in files:
        errors.extend(file_errors(relative))
    for subject in git_output("log", "--format=%s").splitlines():
        if COMMIT.fullmatch(subject) is None:
            errors.append(f"Неверный формат коммита: {subject}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: локальная проверка {len(files)} файлов пройдена.")
    print("Методика и границы проверки: docs/quality.md")
    return NO_ERRORS


if __name__ == "__main__":
    sys.exit(main())
