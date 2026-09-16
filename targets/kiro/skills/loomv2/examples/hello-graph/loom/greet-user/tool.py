"""greet_user — entry tool task."""
from io_types import GreetUserInput, GreetUserOutput


def greet_user(inp: GreetUserInput) -> GreetUserOutput:
    return GreetUserOutput(greeting=f"Hello, {inp.name}!")
