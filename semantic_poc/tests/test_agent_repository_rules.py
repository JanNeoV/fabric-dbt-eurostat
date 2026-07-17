from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "semantic-metric-change"


def test_repository_agent_rules_cover_required_boundaries() -> None:
    rules = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for required in (
        "models/semantic/triathlon_semantic.yml",
        "semantic/triathlon_metric_contract.yml",
        "Proposal mode is the default",
        "explicit approval",
        "Never modify the source Power BI definition in place",
        "MANUAL_REVIEW_REQUIRED",
        "traceable change ID",
        "dbt --no-version-check parse",
        "python semantic_poc/run_quality_checks.py",
        "python semantic_poc/run_poc.py --strict",
    ):
        assert required in rules


def test_local_changes_are_ignored_but_placeholder_is_trackable() -> None:
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "semantic_poc/changes/*" in ignore
    assert "!semantic_poc/changes/.gitkeep" in ignore
    assert (REPO_ROOT / "semantic_poc" / "changes" / ".gitkeep").is_file()


def test_skill_structure_has_no_scaffold_placeholders() -> None:
    required = [
        "SKILL.md",
        "agents/openai.yaml",
        "references/architecture.md",
        "references/supported-patterns.md",
        "references/safety-boundaries.md",
        "references/examples.md",
        "scripts/inspect_metric.py",
    ]
    for relative in required:
        assert (SKILL_ROOT / relative).is_file(), relative

    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "[TODO" not in skill_text
    assert "MANUAL_REVIEW_REQUIRED" in skill_text
    assert "Milestone 1 implements inspection" in skill_text


def test_skill_script_emits_json_without_writing_change_requests() -> None:
    change_dir = REPO_ROOT / "semantic_poc" / "changes"
    before = sorted(path.name for path in change_dir.iterdir())
    completed = subprocess.run(
        [
            sys.executable,
            str(SKILL_ROOT / "scripts" / "inspect_metric.py"),
            "Valid SBR Finishers",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    after = sorted(path.name for path in change_dir.iterdir())

    assert completed.returncode == 0
    assert '"canonical"' in completed.stdout
    assert before == after == [".gitkeep"]
