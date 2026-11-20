import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_no_sample_answers.py"


def run(tests_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(tests_dir)], capture_output=True, text=True, check=False
    )


def test_reference_outside_e2e_fails(tmp_path: Path) -> None:
    (tmp_path / "test_x.py").write_text('open("../samples/output/a.json")\n')
    result = run(tmp_path)
    assert result.returncode == 1
    assert "test_x.py" in result.stdout


def test_sample_pdf_reference_outside_e2e_fails(tmp_path: Path) -> None:
    (tmp_path / "test_y.py").write_text('P = "sample-policies/pvt-car-satp-go-digit.pdf"\n')
    assert run(tmp_path).returncode == 1


def test_reference_inside_e2e_allowed(tmp_path: Path) -> None:
    (tmp_path / "e2e").mkdir()
    (tmp_path / "e2e" / "test_samples.py").write_text('P = "sample-policies/x.pdf"\n')
    (tmp_path / "test_clean.py").write_text("def test_a():\n    assert True\n")
    assert run(tmp_path).returncode == 0
