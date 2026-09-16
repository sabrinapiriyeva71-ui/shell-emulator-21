"""Проверки кавычек, переменных, экранирования и ошибочного ввода."""

import unittest
from unittest.mock import patch

from src.parser import ParseError, parse_line


class ParserTests(unittest.TestCase):
    """Проверить результат разбора независимо от команд оболочки."""

    def test_words_and_quotes(self):
        """Пробелы разделяют слова, кавычки склеивают фрагменты."""
        cases = [
            ("", []),
            (" \t ", []),
            (" ls   -la /tmp ", ["ls", "-la", "/tmp"]),
            ('cd "my folder"', ["cd", "my folder"]),
            ("ls 'my folder'", ["ls", "my folder"]),
            ('ls ""', ["ls", ""]),
            ("ls ''", ["ls", ""]),
            ('ls ab"cd"\'ef\'', ["ls", "abcdef"]),
            (r"ls my\ folder", ["ls", "my folder"]),
            (r'ls "C:\Users\student"',
             ["ls", r"C:\Users\student"]),
            (r'ls "a\"b"', ["ls", 'a"b']),
            ('ls "a;b|c"', ["ls", "a;b|c"]),
        ]
        for line, expected in cases:
            with self.subTest(line=line):
                self.assertEqual(parse_line(line, {}), expected)

    def test_variables(self):
        """Раскрытие не разбивает значение и не выполняет его повторно."""
        environment = {"HOME": "/home/test", "NAME": "two words"}
        cases = [
            ("cd $HOME", ["cd", "/home/test"]),
            ('ls "${HOME}/docs"', ["ls", "/home/test/docs"]),
            ("ls '$HOME'", ["ls", "$HOME"]),
            (r"ls \$HOME", ["ls", "$HOME"]),
            (r'ls "\$HOME"', ["ls", "$HOME"]),
            ("ls $UNKNOWN", ["ls", ""]),
            ("ls $NAME", ["ls", "two words"]),
            ("ls $HOME$HOME", ["ls", "/home/test/home/test"]),
            ("ls $", ["ls", "$"]),
            ("ls $1", ["ls", "$1"]),
        ]
        for line, expected in cases:
            with self.subTest(line=line):
                self.assertEqual(parse_line(line, environment), expected)

    def test_real_environment(self):
        """По умолчанию использовать os.environ, а не тестовый словарь."""
        with patch.dict("os.environ", {"DEMO_VALUE": "actual"}):
            self.assertEqual(parse_line("ls $DEMO_VALUE"), ["ls", "actual"])

    def test_expansion_is_not_code(self):
        """Содержимое переменной остаётся текстом без рекурсивного разбора."""
        value = "$HOME; $(exit)"
        self.assertEqual(parse_line("ls $X", {"X": value}), ["ls", value])

    def test_invalid_syntax(self):
        """Незакрытые конструкции и неподдерживаемые операторы отвергать."""
        cases = [
            "ls '", 'ls "', "ls \\", "ls ${HOME", "ls ${}",
            "ls ${1X}", "ls ${HOME:-x}", "ls | cd", "ls > out",
            "ls; exit", "ls &", "ls `pwd`", "ls $(pwd)",
            'ls "$(pwd)"', 'ls "`pwd`"', 'ls "abc\\',
        ]
        for line in cases:
            with self.subTest(line=line):
                with self.assertRaises(ParseError):
                    parse_line(line, {})


if __name__ == "__main__":
    unittest.main()
