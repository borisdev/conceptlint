"""Their `parallel_processing.py`, declared ONCE and used by every stage.

    numbers ──> Square ──> squares ──> Total ──> total

Stage 2 varies the implementation of `Square`; stage 3 shows the same declaration compiling to
their real `.map()` and join. Both import from here.

⚠️ **This module exists because conceptlint reported it.** Stage 2 and stage 3 each declared their
own `Square` and `Total`, and `naming.ambiguous_reference` fired: *"Square is declared twice with
different shapes"*. Two names for what a reader takes to be one operation is exactly what this
package reports, and it had happened inside the examples FOR this package, within an hour of them
being written. One declaration, two demos — which is also the thing the package claims you get.
"""
from __future__ import annotations

from workflow_plan import Plan, Step, Variable

numbers = Variable("numbers", list)
number = Variable("number", int)
squared = Variable("squared", int)
squares = Variable("squares", list)
total = Variable("total", int)


class Square(Step):
    """Theirs, unchanged: one number in, one number out, applied to each item."""

    inputs, outputs = (number,), (squared,)
    map_over = (numbers, squares)


class Total(Step):
    """Their example stops at the joined list; summing gives us something to eval."""

    inputs, outputs = (squares,), (total,)


plan = Plan(name="parallel_processing", steps=(Square(), Total()),
            declared_inputs=(numbers,))


def square_exact(number: int) -> int:
    return number * number


def square_by_addition(number: int) -> int:
    return sum(abs(number) for _ in range(abs(number)))


def square_cheap(number: int) -> int:
    """Wrong above 10 — the arm an eval has to catch."""
    return number * number if abs(number) <= 10 else abs(number) * 10


def total_impl(squares: list) -> int:
    return sum(squares)


#: Three peers. Not SquareV1/V2/V3, which would be three names for one operation.
ARMS = {
    "exact": {Square: square_exact, Total: total_impl},
    "by_addition": {Square: square_by_addition, Total: total_impl},
    "cheap": {Square: square_cheap, Total: total_impl},
}

CORPUS = [[1, 2, 3, 4, 5], [12], [3, 20]]
