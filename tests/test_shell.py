"""Проверки команд, реального приглашения и устойчивости REPL."""

import io
import os
import unittest
from unittest.mock import patch

from src.shell import display_directory, execute, make_prompt, run_repl


class ShellTests(unittest.TestCase):
    """Проверить наблюдаемое поведение консольного интерфейса."""

    def setUp(self):
        """Создать отдельные потоки для результата и ошибок."""
        self.output = io.StringIO()
        self.errors = io.StringIO()

    def test_stubs(self):
        """Заглушки печатают аргументы и не меняют рабочий каталог."""
        before = os.getcwd()
        for command in ("ls", "cd"):
            with self.subTest(command=command):
                self.output.seek(0)
                self.output.truncate()
                active = execute(
                    [command, "a b", ""], self.output, self.errors
                )
                self.assertTrue(active)
                self.assertEqual(
                    self.output.getvalue(),
                    f'{command}: аргументы = ["a b", ""]\n',
                )
        self.assertEqual(os.getcwd(), before)
        self.assertEqual(self.errors.getvalue(), "")

    def test_empty_command(self):
        """Пустая строка не выводит ошибку и не завершает цикл."""
        self.assertTrue(execute([], self.output, self.errors))
        self.assertEqual(self.output.getvalue(), "")
        self.assertEqual(self.errors.getvalue(), "")

    def test_unknown_command(self):
        """Неизвестная команда выводит ошибку в stderr."""
        self.assertTrue(execute(["whoami"], self.output, self.errors))
        self.assertIn("команда не найдена", self.errors.getvalue())

    def test_exit(self):
        """exit без аргументов завершает цикл."""
        self.assertFalse(execute(["exit"], self.output, self.errors))
        self.assertIn("Выход", self.output.getvalue())

    def test_exit_with_argument(self):
        """Неподдерживаемый аргумент exit не завершает программу."""
        self.assertTrue(execute(["exit", "1"], self.output, self.errors))
        self.assertIn("аргументы не поддерживаются", self.errors.getvalue())

    def test_directory_abbreviation(self):
        """~ заменяет только домашний каталог и его подкаталоги."""
        home = os.path.abspath("student")
        cases = [
            (home, "~"),
            (os.path.join(home, "docs"), "~" + os.sep + "docs"),
            (home + "2", home + "2"),
        ]
        for current, expected in cases:
            with self.subTest(current=current):
                with patch("os.getcwd", return_value=current):
                    with patch("os.path.expanduser", return_value=home):
                        self.assertEqual(display_directory(), expected)

    def test_prompt(self):
        """Собирать приглашение из данных стандартных функций ОС."""
        with patch("getpass.getuser", return_value="student"):
            with patch("socket.gethostname", return_value="laptop"):
                with patch("src.shell.display_directory", return_value="~"):
                    self.assertEqual(make_prompt(), "student@laptop:~$ ")

    def test_repl_recovers_after_errors(self):
        """После ошибок разбора и команды следующий ввод обрабатывается."""
        lines = iter(['ls "', "unknown", "exit 1", "ls", "exit"])
        run_repl(lambda prompt: next(lines), self.output, self.errors)
        self.assertIn("Ошибка синтаксиса", self.errors.getvalue())
        self.assertIn("команда не найдена", self.errors.getvalue())
        self.assertIn("ls: аргументы = []", self.output.getvalue())
        self.assertIn("Выход из эмулятора.", self.output.getvalue())

    def test_eof(self):
        """Конец потока завершает цикл без traceback."""
        with patch("builtins.input", side_effect=EOFError):
            run_repl(output=self.output, errors=self.errors)
        self.assertIn("Конец ввода", self.output.getvalue())

    def test_interrupt(self):
        """Ctrl+C отменяет ввод, затем можно выполнить exit."""
        with patch("builtins.input", side_effect=[KeyboardInterrupt, "exit"]):
            run_repl(output=self.output, errors=self.errors)
        self.assertIn("Ввод отменён", self.output.getvalue())
        self.assertIn("Выход из эмулятора.", self.output.getvalue())

    def test_os_error(self):
        """Ошибка получения каталога завершается понятным сообщением."""
        with patch("os.getcwd", side_effect=OSError("directory missing")):
            run_repl(output=self.output, errors=self.errors)
        self.assertIn("Ошибка ОС", self.errors.getvalue())


if __name__ == "__main__":
    unittest.main()
