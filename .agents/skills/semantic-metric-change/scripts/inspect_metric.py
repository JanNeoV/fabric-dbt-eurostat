from __future__ import annotations

import sys
from pathlib import Path


def find_repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "dbt_project.yml").is_file() and (candidate / "semantic_poc").is_dir():
            return candidate
    raise SystemExit("Repository root could not be found from the skill script path.")


def main() -> int:
    repo_root = find_repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from semantic_poc.agent.cli import main as cli_main

    return cli_main(["inspect", *sys.argv[1:], "--json"])


if __name__ == "__main__":
    raise SystemExit(main())
