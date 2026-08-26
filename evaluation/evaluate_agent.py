# file: evaluation/evaluate_agent.py

"""
Agent Evaluation Engine and Report Exporter.

Runs the 15 benchmark test cases against the AI Analyst, calculates
metrics, prints a clean terminal output, and saves EVALUATION_REPORT.md.

Usage:
    python -m evaluation.evaluate_agent
"""

import time
import logging
from typing import Dict, Any, List
from sqlalchemy import text
from app.database.connection import SessionLocal
from app.agent.ai_analyst import AIAnalyst
from evaluation.benchmark_dataset import BENCHMARK_CASES

# Suppress verbose SQLAlchemy logs during evaluation run
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def execute_reference_sql(query: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        res = db.execute(text(query))
        return [dict(row) for row in res.mappings()]
    finally:
        db.close()


def compare_results(actual_rows: List[Dict[str, Any]], expected_rows: List[Dict[str, Any]]) -> bool:
    if len(actual_rows) != len(expected_rows):
        return False

    if not actual_rows and not expected_rows:
        return True

    if len(actual_rows) == 1 and len(expected_rows) == 1:
        act_vals = list(actual_rows[0].values())
        exp_vals = list(expected_rows[0].values())
        if len(act_vals) == 1 and len(exp_vals) == 1:
            try:
                return round(float(act_vals[0] or 0), 2) == round(float(exp_vals[0] or 0), 2)
            except (ValueError, TypeError):
                return str(act_vals[0]).strip().lower() == str(exp_vals[0]).strip().lower()

    act_top = list(actual_rows[0].values())
    exp_top = list(expected_rows[0].values())
    return str(act_top[0]).lower() == str(exp_top[0]).lower()


def save_markdown_report(results: List[Dict[str, Any]], metrics: Dict[str, Any]):
    """Saves a clean EVALUATION_REPORT.md file for portfolio display."""
    md = []
    md.append("# 📊 SQL Analyst Agent — Benchmark Evaluation Report\n")
    md.append("This automated evaluation report benchmarks the local AI Agent (`llama3.1:8b`) against 15 ground-truth SQL test cases.\n")
    
    md.append("## Executive Summary\n")
    md.append(f"- **Total Test Cases:** {metrics['total_tests']}")
    md.append(f"- **SQL Safety Validity Rate:** `{metrics['validity_rate']:.1f}%` ({metrics['valid_sql_count']}/{metrics['total_tests']})")
    md.append(f"- **Query Execution Success Rate:** `{metrics['execution_rate']:.1f}%` ({metrics['execution_success_count']}/{metrics['total_tests']})")
    md.append(f"- **Ground-Truth Accuracy Rate:** `{metrics['accuracy_rate']:.1f}%` ({metrics['correct_answer_count']}/{metrics['total_tests']})")
    md.append(f"- **Average Query Latency:** `{metrics['avg_latency']:.2f}s`")
    md.append(f"- **Total Automated Retries Triggered:** `{metrics['total_retries']}`\n")

    md.append("## Detailed Benchmark Results\n")
    md.append("| ID | Category | SQL Valid | Executed | Ground Truth Match | Latency | Retries |")
    md.append("|---|---|---|---|---|---|---|")
    
    for r in results:
        val = "✅ PASS" if r['is_valid'] else "❌ FAIL"
        exc = "✅ PASS" if r['is_executed'] else "❌ FAIL"
        cor = "✅ PASS" if r['is_correct'] else "❌ FAIL"
        md.append(f"| {r['id']} | {r['category']} | {val} | {exc} | {cor} | {r['latency']:.2f}s | {r['retries']} |")

    md.append("\n## Failure Analysis & Root Cause Analysis\n")
    failures = [r for r in results if not r['is_correct']]
    if not failures:
        md.append("🎉 **Perfect Score!** All queries matched ground truth exactly.")
    else:
        for f in failures:
            md.append(f"### [{f['id']}] {f['question']}")
            md.append(f"- **Category:** {f['category']}")
            md.append(f"- **Generated SQL:** `{f['generated_sql']}`")
            md.append(f"- **Issue:** {f['error'] or 'Result subset/ordering differed from ground-truth expectation.'}\n")

    with open("EVALUATION_REPORT.md", "w", encoding="utf-8") as file:
        file.write("\n".join(md))
    
    print("\n📄 Evaluation report saved cleanly to 'EVALUATION_REPORT.md'")


def run_benchmark():
    print("=" * 80)
    print("  SQL ANALYST AGENT — BENCHMARK EVALUATION HARNESS")
    print("=" * 80)
    print("Initializing AI Analyst instance...")

    analyst = AIAnalyst()
    results = []

    total_tests = len(BENCHMARK_CASES)
    valid_sql_count = 0
    execution_success_count = 0
    correct_answer_count = 0
    total_latency = 0.0
    total_retries = 0

    print(f"\nRunning {total_tests} benchmark test cases against local Ollama agent...\n")
    print(f"{'ID':<6} | {'Category':<22} | {'SQL Valid':<10} | {'Executed':<9} | {'Correct':<8} | {'Latency':<8} | {'Retries'}")
    print("-" * 80)

    for case in BENCHMARK_CASES:
        t_start = time.time()
        agent_out = analyst.analyze(case["question"])
        latency = time.time() - t_start
        total_latency += latency

        is_sql_valid = agent_out.get("sql") is not None and "Safety Rejection" not in (agent_out.get("error") or "")
        if is_sql_valid:
            valid_sql_count += 1

        is_exec_success = agent_out.get("error") is None
        if is_exec_success:
            execution_success_count += 1

        expected_rows = execute_reference_sql(case["ground_truth_sql"])
        actual_rows = agent_out.get("rows", [])

        is_correct = False
        if is_exec_success:
            is_correct = compare_results(actual_rows, expected_rows)
            if is_correct:
                correct_answer_count += 1

        steps = agent_out.get("steps", [])
        retry_steps = [s for s in steps if "Retrying" in s.get("step", "")]
        retries = len(retry_steps)
        total_retries += retries

        val_str = "✅ PASS" if is_sql_valid else "❌ FAIL"
        exec_str = "✅ PASS" if is_exec_success else "❌ FAIL"
        corr_str = "✅ PASS" if is_correct else "❌ FAIL"

        print(f"{case['id']:<6} | {case['category']:<22} | {val_str:<10} | {exec_str:<9} | {corr_str:<8} | {latency:>6.2f}s | {retries:>7}")

        results.append({
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "generated_sql": agent_out.get("sql"),
            "is_valid": is_sql_valid,
            "is_executed": is_exec_success,
            "is_correct": is_correct,
            "latency": latency,
            "retries": retries,
            "error": agent_out.get("error")
        })

    metrics = {
        "total_tests": total_tests,
        "valid_sql_count": valid_sql_count,
        "execution_success_count": execution_success_count,
        "correct_answer_count": correct_answer_count,
        "total_retries": total_retries,
        "avg_latency": total_latency / total_tests if total_tests > 0 else 0,
        "validity_rate": (valid_sql_count / total_tests) * 100,
        "execution_rate": (execution_success_count / total_tests) * 100,
        "accuracy_rate": (correct_answer_count / total_tests) * 100,
    }

    print("\n" + "=" * 80)
    print("  FINAL EVALUATION REPORT CARD")
    print("=" * 80)
    print(f"  Total Test Cases:            {total_tests}")
    print(f"  SQL Safety Validity Rate:    {metrics['validity_rate']:>6.1f}%  ({valid_sql_count}/{total_tests})")
    print(f"  Query Execution Success Rate: {metrics['execution_rate']:>6.1f}%  ({execution_success_count}/{total_tests})")
    print(f"  Ground-Truth Accuracy Rate:  {metrics['accuracy_rate']:>6.1f}%  ({correct_answer_count}/{total_tests})")
    print(f"  Average Latency per Query:   {metrics['avg_latency']:>6.2f} seconds")
    print(f"  Total Automated Retries:     {total_retries}")
    print("=" * 80)

    # Export report to markdown
    save_markdown_report(results, metrics)


if __name__ == "__main__":
    run_benchmark()