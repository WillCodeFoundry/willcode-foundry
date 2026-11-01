"""The routing table in agent-kit/AGENTS.md's "Taking turns" agrees with the outcomes each ROLE.md defines.

A role ends its turn with an outcome from its own "Outcomes" section, then writes in TURN the role the table
gives for it. A renamed or dropped outcome would otherwise leave the table routing one no role reports, or a
role reporting one the table can't route.
"""

import re
from collections import deque
from pathlib import Path

from foundry import yaml_io

REPO_ROOT = Path(__file__).parents[2]
AGENT_KIT = REPO_ROOT / "agent-kit"
HUMAN, ANY_ROLE, STUCK = "human", "any role", "stuck"


def routing_table() -> dict[tuple[str, str], str]:
    """(role, outcome) → next role, from the table under "### Taking turns"."""
    section = re.search(r"### Taking turns\n(.*?)\n### ", (AGENT_KIT / "AGENTS.md").read_text(), re.DOTALL)
    assert section, 'AGENTS.md no longer has a "### Taking turns" section'
    rows = re.findall(r"^\| ([a-z ]+) \| `([a-z-]+)` \| ([a-z]+) \|$", section[1], re.MULTILINE)
    assert rows, "no routing rows found under Taking turns"
    return {(role, outcome): next_role for role, outcome, next_role in rows}


def outcomes_by_role() -> dict[str, set[str]]:
    """Each role's outcomes, from the bullets of its ROLE.md's "## Outcomes"; roles without one are left out."""
    outcomes = {}
    for role_md in sorted(AGENT_KIT.glob("roles/*/ROLE.md")):
        section = re.search(r"^## Outcomes\n(.*?)(?=^## |\Z)", role_md.read_text(), re.DOTALL | re.MULTILINE)
        if section:
            outcomes[role_md.parent.name] = set(re.findall(r"^- `([a-z-]+)`:", section[1], re.MULTILINE))
    return outcomes


def test_every_routed_outcome_is_one_its_role_defines() -> None:
    defined = outcomes_by_role()
    undefined = [
        (role, outcome)
        for role, outcome in routing_table()
        if role != ANY_ROLE and outcome not in defined.get(role, set())
    ]
    assert undefined == []


def test_every_outcome_a_role_defines_is_routed() -> None:
    table = routing_table()
    unrouted = [
        (role, outcome)
        for role, outcomes in outcomes_by_role().items()
        for outcome in outcomes
        if (role, outcome) not in table and (ANY_ROLE, outcome) not in table
    ]
    assert unrouted == []


def test_every_role_can_be_stuck_and_stuck_goes_to_the_human() -> None:
    assert routing_table()[(ANY_ROLE, STUCK)] == HUMAN
    assert all(STUCK in outcomes for outcomes in outcomes_by_role().values())


def test_every_next_role_is_a_configured_role_or_the_human() -> None:
    roles = set(yaml_io.load(REPO_ROOT / "config" / "foundry.yaml")["roles"])
    assert {next_role for next_role in routing_table().values()} <= roles | {HUMAN}


def test_from_the_planner_every_role_is_reached_and_each_can_reach_the_human_without_being_stuck() -> None:
    """A feature starts at the planner and ends with the human; stuck is left out, since it reaches the human
    from anywhere and would hide a role with no way forward."""
    moves: dict[str, set[str]] = {}
    for (role, outcome), next_role in routing_table().items():
        if outcome != STUCK:
            moves.setdefault(role, set()).add(next_role)

    def reached_from(start: str) -> set[str]:
        seen, queue = {start}, deque([start])
        while queue:
            for next_role in moves.get(queue.popleft(), set()):
                if next_role not in seen:
                    seen.add(next_role)
                    queue.append(next_role)
        return seen

    assert reached_from("planner") >= set(outcomes_by_role())
    assert [role for role in outcomes_by_role() if HUMAN not in reached_from(role)] == []
