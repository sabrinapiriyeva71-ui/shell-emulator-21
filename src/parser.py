"""Разбор слов, кавычек и переменных без запуска системной оболочки."""

import os
import re

VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
OPERATORS = "|&;<>"
DOUBLE_ESCAPES = '$"\\'
NOT_FOUND = -1


class ParseError(ValueError):
    """Ошибка синтаксиса введённой команды."""


class Parser:
    """Хранит строку, текущую позицию и окружение одного разбора."""

    def __init__(self, line, environment):
        """Подготовить независимое состояние разбора."""
        self.line = line
        self.environment = environment
        self.position = 0

    def parse(self):
        """Собрать список слов, сохраняя явно пустые аргументы."""
        words = []
        parts = []
        started = False
        while self.position < len(self.line):
            char = self.line[self.position]
            if char.isspace():
                if started:
                    words.append("".join(parts))
                parts = []
                started = False
                self.position += 1
            else:
                parts.append(self.read_part())
                started = True
        if started:
            words.append("".join(parts))
        return words

    def read_part(self):
        """Прочитать фрагмент вне кавычек либо сообщить об операторе."""
        char = self.line[self.position]
        if char in OPERATORS or char == "`":
            raise ParseError(f"Оператор {char!r} пока не поддерживается")
        readers = {
            "'": self.read_single,
            '"': self.read_double,
            "$": self.read_variable,
            "\\": self.read_escape,
        }
        if char in readers:
            return readers[char]()
        self.position += 1
        return char

    def read_single(self):
        """Прочитать одинарные кавычки без раскрытия переменных."""
        self.position += 1
        end = self.line.find("'", self.position)
        if end == NOT_FOUND:
            raise ParseError("Не закрыта одинарная кавычка")
        result = self.line[self.position:end]
        self.position = end + 1
        return result

    def read_double(self):
        """Прочитать двойные кавычки, раскрывая переменные внутри."""
        self.position += 1
        parts = []
        while self.position < len(self.line):
            char = self.line[self.position]
            if char == '"':
                self.position += 1
                return "".join(parts)
            if char == "$":
                parts.append(self.read_variable())
            elif char == "\\":
                parts.append(self.read_double_escape())
            elif char == "`":
                raise ParseError("Подстановка команд не поддерживается")
            else:
                parts.append(char)
                self.position += 1
        raise ParseError("Не закрыта двойная кавычка")

    def read_escape(self):
        """Вернуть следующий символ буквально вне кавычек."""
        self.position += 1
        if self.position == len(self.line):
            raise ParseError("После обратной косой черты нужен символ")
        char = self.line[self.position]
        self.position += 1
        return char

    def read_double_escape(self):
        """В двойных кавычках экранировать доллар, кавычку и слеш."""
        self.position += 1
        if self.position == len(self.line):
            raise ParseError("Не закрыта двойная кавычка")
        char = self.line[self.position]
        if char in DOUBLE_ESCAPES:
            self.position += 1
            return char
        return "\\"

    def read_variable(self):
        """Раскрыть $NAME или ${NAME}; отсутствующее имя даёт пустоту."""
        self.position += 1
        if self.position == len(self.line):
            return "$"
        char = self.line[self.position]
        if char == "(":
            raise ParseError("Подстановка команд не поддерживается")
        if char == "{":
            return self.read_braced_variable()
        match = VARIABLE_NAME.match(self.line, self.position)
        if match is None:
            return "$"
        self.position = match.end()
        return self.environment.get(match.group(), "")

    def read_braced_variable(self):
        """Проверить закрывающую скобку и имя переменной ${NAME}."""
        self.position += 1
        end = self.line.find("}", self.position)
        if end == NOT_FOUND:
            raise ParseError("Не закрыта фигурная скобка переменной")
        name = self.line[self.position:end]
        if VARIABLE_NAME.fullmatch(name) is None:
            raise ParseError("Некорректное имя переменной")
        self.position = end + 1
        return self.environment.get(name, "")


def parse_line(line, environment=None):
    """Разобрать строку; по умолчанию читать реальное окружение ОС."""
    if environment is None:
        environment = os.environ
    return Parser(line, environment).parse()
