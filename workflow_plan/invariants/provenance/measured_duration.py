"""`duration_secs` must be MEASURED, not reconstructed from the timestamps beside it.

    started_at / ended_at    PROVENANCE — when it happened, for correlating against logs
    duration_secs            MEASUREMENT — how long it took, from a monotonic clock

Two fields, two purposes, and deliberately two failure modes. A wall clock is corrected by NTP; a
monotonic clock is not. Deriving the measurement from the provenance couples them, so a clock
correction during a step silently corrupts a performance number.

## Why the corruption is worse than being wrong

It is asymmetric. A backwards correction makes `ended_at - started_at` NEGATIVE. Nothing downstream
expects a negative duration, so something clamps it to zero, and a forty-second step reports as
instant. That is not a visibly wrong number a reader would question — it is a plausible one, in the
direction of "fast", on a metric someone is watching for regressions.

`Activity` refuses a negative `duration_secs` outright. This rule catches the quieter half.

## What it looks for, and why both directions are findings

    duration_secs == (ended_at - started_at).total_seconds()   EXACTLY
        -> reconstructed. Two clocks started at different instants and drift apart; a real
           measurement matching a wall-clock delta to full float precision does not happen.

    |duration_secs - wall_delta| > TOLERANCE
        -> the wall clock moved during the step. The measurement is fine and the timestamps are
           suspect, which is the opposite conclusion and equally worth having.

⚠️ The gap IS the finding, in both directions. This rule does not decide which clock to believe —
it reports that they disagree, and by how much, because a reader who knows the deploy history can
tell an NTP step from a bug and this module cannot.

## What it deliberately does not do

It does not require `duration_secs` to be present. `None` means NOT MEASURED, and a runner that does
not measure is a legitimate runner — demanding a number would produce fabricated ones. Absence is
reported by nothing here; it is visible as `None` and must never render as `0.0`.
"""
from __future__ import annotations

from typing import Sequence

from workflow_plan.invariants.invariant import InvariantCategory, Invariant
from workflow_plan.ontology.prov import Activity

#: Seconds of disagreement tolerated before the clocks are reported as having diverged. Generous on
#: purpose: process scheduling alone puts tens of milliseconds between the two readings, and a rule
#: that fires on ordinary jitter is one nobody keeps.
TOLERANCE_SECS = 1.0


def _measured_not_reconstructed(activities: Sequence[Activity]) -> None:
    reconstructed: list[str] = []
    diverged: list[str] = []

    for a in activities:
        if a.duration_secs is None or a.ended_at is None:
            continue                      # not measured, or not finished — neither is a violation
        wall = (a.ended_at - a.started_at).total_seconds()
        if a.duration_secs == wall:
            reconstructed.append(f"{a.id} ({a.step_name}) = {wall}s exactly")
        elif abs(a.duration_secs - wall) > TOLERANCE_SECS:
            diverged.append(
                f"{a.id} ({a.step_name}) measured {a.duration_secs}s, wall clock says {wall}s")

    if reconstructed:
        raise MEASURED_DURATION.violated(
            "duration_secs equals ended_at - started_at to full float precision for: "
            + "; ".join(reconstructed)
            + ". A monotonic measurement and a wall-clock delta start at different instants and "
              "drift; an exact match means the duration was reconstructed from the timestamps "
              "rather than measured. Use time.monotonic().")
    if diverged:
        raise MEASURED_DURATION.violated(
            "the two clocks disagree by more than "
            f"{TOLERANCE_SECS}s for: " + "; ".join(diverged)
            + ". The measurement is probably right and the timestamps moved under it — check "
              "whether NTP corrected during the run. Reported rather than resolved: which clock to "
              "believe depends on deploy history this rule cannot see.")


MEASURED_DURATION: Invariant[Sequence[Activity]] = Invariant(
    id="provenance.measured_duration",
    category=InvariantCategory.PROVENANCE,
    statement="Activity.duration_secs is measured from a monotonic clock, never reconstructed "
              "from started_at and ended_at.",
    why=("Timestamps are provenance and duration is measurement; they have no reason to share a "
         "failure mode. Derived from a wall clock, an NTP step backwards yields a negative "
         "duration, something downstream clamps it, and a 40-second step reports as instant — a "
         "plausible number, in the flattering direction, on a metric watched for regressions."),
    check=_measured_not_reconstructed,
)

ALL: tuple[Invariant[Sequence[Activity]], ...] = (MEASURED_DURATION,)
