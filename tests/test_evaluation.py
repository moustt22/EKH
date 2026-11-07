from app.evaluation.run import run_evaluation, write_report


def test_evaluation_writes_the_three_scores(tmp_path):
    report = write_report(tmp_path / "latest.json")
    assert set(report) >= {"faithfulness", "answer_relevance", "citation_accuracy", "cases"}
    saved = (tmp_path / "latest.json").read_text(encoding="utf-8")
    assert "faithfulness" in saved
    by_id = {case["id"]: case for case in report["cases"]}
    assert by_id["leave-vacation-accrual"]["faithfulness"] == 1.0
    assert by_id["salary-bands-hr"]["faithfulness"] == 1.0
    assert by_id["planted-instruction"]["faithfulness"] == 1.0
    assert "swordfish" not in by_id["planted-instruction"]["answer"]
    assert run_evaluation()["citation_accuracy"] == 1.0
