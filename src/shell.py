"""Приглашение, команды-заглушки и интерактивный цикл REPL."""

import getpass
import json
import os
import socket
import sys

from src.parser import ParseError, parse_line


def display_directory():
    """Сократить домашний каталог до ~ с учётом границ пути."""
    current = os.getcwd()
    home = os.path.expanduser("~")
    if current == home:
        return "~"
    prefix = home.rstrip(os.sep) + os.sep
    if current.startswith(prefix):
        return "~" + os.sep + current[len(prefix):]
    return current


def make_prompt():
    """Получить имя пользователя, хост и каталог из реальной ОС."""
    username = getpass.getuser()
    hostname = socket.gethostname()
    return f"{username}@{hostname}:{display_directory()}$ "


def execute(words, output, errors):
    """Обработать команду; False означает успешный запрос выхода."""
    if not words:
        return True
    command, *arguments = words
    if command == "exit":
        if arguments:
            print("exit: аргументы не поддерживаются", file=errors)
            return True
        print("Выход из эмулятора.", file=output)
        return False
    if command in ("ls", "cd"):
        encoded = json.dumps(arguments, ensure_ascii=False)
        print(f"{command}: аргументы = {encoded}", file=output)
    else:
        print(f"{command}: команда не найдена", file=errors)
    return True


def run_repl(reader=None, output=None, errors=None):
    """Читать команды до exit/EOF; после ошибки продолжать диалог."""
    reader = input if reader is None else reader
    output = sys.stdout if output is None else output
    errors = sys.stderr if errors is None else errors
    print("Эмулятор оболочки — вариант 21, этап 1.", file=output)
    while True:
        try:
            line = reader(make_prompt())
            words = parse_line(line)
            if not execute(words, output, errors):
                return
        except EOFError:
            print("\nКонец ввода. Выход из эмулятора.", file=output)
            return
        except KeyboardInterrupt:
            print("\nВвод отменён.", file=output)
        except ParseError as error:
            print(f"Ошибка синтаксиса: {error}", file=errors)
        except OSError as error:
            print(f"Ошибка ОС: {error}", file=errors)
            return


if __name__ == "__main__":
    run_repl()
