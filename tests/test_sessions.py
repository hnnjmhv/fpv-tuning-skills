import json
from pathlib import Path
import importlib.util

from fpv_tune.cli import main


def test_three_unique_flights_and_complete_plan(tmp_path):
    location = Path(__file__).resolve().parents[1] / "examples" / "generate_demo.py"
    spec = importlib.util.spec_from_file_location("generate_demo", location)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    data = tmp_path / "data"
    demo.generate(data)
    session = tmp_path / "session"
    assert main(["start", "--session", str(session)]) == 0
    for check in (1, 2, 3):
        args = ["analyze", "--csv", str(data / f"flight-{check}.csv"), "--config", str(data / "dump.txt"),
                "--profile", "0", "--metadata", str(data / "metadata.json"), "--session", str(session)]
        assert main(args) == 0
        if check == 1:
            assert main(args) == 2
        assert (session / f"check-{check}" / "report.zh-CN.md").is_file()
        assert (session / f"check-{check}" / "report.en.md").is_file()
    journal = json.loads((session / "session.json").read_text(encoding="utf-8"))
    assert len(journal["checks"]) == 3
    assert journal["status"] == "checks_analyzed_review_required"
    assert journal["validated"] is False
    assert main(["plan", "--analysis", str(session / "check-1" / "analysis.json"), "--config", str(data / "dump.txt"),
                 "--profile", "0", "--changes", str(data / "changes.json"), "--out", str(tmp_path / "plan")]) == 0
    assert "set p_pitch = 42" in (tmp_path / "plan" / "candidate-cli.txt").read_text(encoding="utf-8")
    assert (session / "check-2" / "comparison.json").is_file()
    assert (session / "check-3" / "baseline-comparison.json").is_file()
    evaluation = json.loads((session / "check-3" / "validation.json").read_text(encoding="utf-8"))
    assert evaluation["validated"] is False
    assert evaluation["criteria"]["motor_temperature"]["status"] == "not_evaluated"
    assert main(["analyze", "--csv", str(data / "flight-3.csv"), "--out", str(session / "check-3")]) == 2
