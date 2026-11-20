"""Fail if any backend test outside tests/e2e/ reads the sample policies or their committed outputs.

Guards intent NN5: no test, fixture or code branch may be keyed to a sample's expected answer.
Only tests/e2e/ may open sample PDFs, and it asserts structure only.
"""

import sys
from pathlib import Path

FORBIDDEN = ("sample-policies", "samples/output")
# This guard's own test necessarily contains the forbidden strings.
SELF_TEST = "test_check_no_sample_answers.py"


def offenders(tests_dir: Path) -> list[str]:
    found = []
    for path in sorted(tests_dir.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".json", ".txt", ".md"}:
            continue
        rel = path.relative_to(tests_dir)
        if rel.parts[0] == "e2e" or path.name == SELF_TEST:
            continue
        text = path.read_text(errors="ignore")
        if any(token in text for token in FORBIDDEN):
            found.append(str(rel))
    return found


def main() -> int:
    tests_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("backend/tests")
    bad = offenders(tests_dir)
    for rel in bad:
        print(f"{rel}: references sample policies or sample outputs outside tests/e2e/")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
