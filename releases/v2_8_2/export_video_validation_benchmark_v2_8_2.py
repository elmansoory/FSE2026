from pathlib import Path
import json
import sqlite3
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fse_owner_v1_2.db"
OUT_DIR = BASE_DIR / "video_validation_exports"
OUT_DIR.mkdir(exist_ok=True)

SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS video_validation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_name TEXT NOT NULL,
    source_reference TEXT,
    model_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS video_ground_truth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validation_run_id INTEGER,
    clip_name TEXT NOT NULL,
    source_video TEXT,
    athlete_name TEXT,
    element_label TEXT,
    error_label TEXT,
    goe_label TEXT,
    reviewer_name TEXT,
    review_status TEXT DEFAULT 'approved',
    start_time REAL,
    end_time REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_model_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validation_run_id INTEGER,
    clip_name TEXT NOT NULL,
    source_video TEXT,
    predicted_element TEXT,
    predicted_error TEXT,
    predicted_goe_band TEXT,
    confidence REAL,
    start_time REAL,
    end_time REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
'''

def ensure_schema(conn):
    conn.executescript(SCHEMA_SQL)
    conn.commit()

def build_video_validation_export():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)

    gt_rows = [dict(r) for r in conn.execute("SELECT * FROM video_ground_truth ORDER BY id").fetchall()]
    pred_rows = [dict(r) for r in conn.execute("SELECT * FROM video_model_predictions ORDER BY id").fetchall()]
    run_rows = [dict(r) for r in conn.execute("SELECT * FROM video_validation_runs ORDER BY id DESC").fetchall()]
    conn.close()

    gt_df = pd.DataFrame(gt_rows)
    pred_df = pd.DataFrame(pred_rows)

    merged = pd.DataFrame()
    if not gt_df.empty:
        if pred_df.empty:
            merged = gt_df.copy()
            merged["predicted_element"] = ""
            merged["predicted_error"] = ""
            merged["predicted_goe_band"] = ""
            merged["confidence"] = None
        else:
            merged = gt_df.merge(
                pred_df[["clip_name", "predicted_element", "predicted_error", "predicted_goe_band", "confidence"]],
                on="clip_name",
                how="left",
            )

    total_gt = int(len(gt_df))
    total_pred = int(len(pred_df))
    matched = int(merged["predicted_element"].fillna("").astype(str).str.strip().ne("").sum()) if not merged.empty else 0
    pending_prediction = int(merged["predicted_element"].fillna("").astype(str).str.strip().eq("").sum()) if not merged.empty else total_gt
    element_matches = int((merged["element_label"].fillna("").astype(str).str.strip().str.lower() == merged["predicted_element"].fillna("").astype(str).str.strip().str.lower()).sum()) if not merged.empty else 0
    error_matches = int((merged["error_label"].fillna("").astype(str).str.strip().str.lower() == merged["predicted_error"].fillna("").astype(str).str.strip().str.lower()).sum()) if not merged.empty else 0
    goe_matches = int((merged["goe_label"].fillna("").astype(str).str.strip().str.lower() == merged["predicted_goe_band"].fillna("").astype(str).str.strip().str.lower()).sum()) if not merged.empty else 0

    element_match_rate = round((element_matches / total_gt) * 100, 2) if total_gt else 0.0
    error_match_rate = round((error_matches / total_gt) * 100, 2) if total_gt else 0.0
    goe_match_rate = round((goe_matches / total_gt) * 100, 2) if total_gt else 0.0
    benchmark_ready = total_gt > 0 and total_pred > 0

    summary = {
        "validation_runs_total": len(run_rows),
        "ground_truth_rows": total_gt,
        "prediction_rows": total_pred,
        "matched_prediction_rows": matched,
        "pending_prediction_rows": pending_prediction,
        "element_match_rate_percent": element_match_rate,
        "error_match_rate_percent": error_match_rate,
        "goe_match_rate_percent": goe_match_rate,
        "benchmark_ready": benchmark_ready,
        "owner_note": (
            "Benchmark shell is ready, but there is no validated clip set yet."
            if not benchmark_ready else
            "Benchmark contains both ground truth and predictions. Review rates before trusting production accuracy."
        ),
    }

    summary_json = OUT_DIR / "video_validation_summary.json"
    gt_json = OUT_DIR / "video_ground_truth.json"
    pred_json = OUT_DIR / "video_model_predictions.json"
    merged_csv = OUT_DIR / "video_validation_merged.csv"
    merged_xlsx = OUT_DIR / "video_validation_merged.xlsx"
    report_md = OUT_DIR / "video_validation_report.md"

    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    gt_json.write_text(json.dumps(gt_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    pred_json.write_text(json.dumps(pred_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if merged.empty:
        empty_df = pd.DataFrame(columns=[
            "clip_name", "source_video", "athlete_name", "element_label", "error_label", "goe_label",
            "predicted_element", "predicted_error", "predicted_goe_band", "confidence"
        ])
        empty_df.to_csv(merged_csv, index=False, encoding="utf-8-sig")
        with pd.ExcelWriter(merged_xlsx, engine="openpyxl") as writer:
            empty_df.to_excel(writer, sheet_name="validation", index=False)
            pd.DataFrame([summary]).to_excel(writer, sheet_name="summary", index=False)
    else:
        merged.to_csv(merged_csv, index=False, encoding="utf-8-sig")
        with pd.ExcelWriter(merged_xlsx, engine="openpyxl") as writer:
            merged.to_excel(writer, sheet_name="validation", index=False)
            pd.DataFrame([summary]).to_excel(writer, sheet_name="summary", index=False)

    lines = [
        "# FSE Video Validation Report",
        "",
        f"- Validation Runs: {summary['validation_runs_total']}",
        f"- Ground Truth Rows: {summary['ground_truth_rows']}",
        f"- Prediction Rows: {summary['prediction_rows']}",
        f"- Matched Prediction Rows: {summary['matched_prediction_rows']}",
        f"- Pending Prediction Rows: {summary['pending_prediction_rows']}",
        f"- Element Match Rate: {summary['element_match_rate_percent']}%",
        f"- Error Match Rate: {summary['error_match_rate_percent']}%",
        f"- GOE Match Rate: {summary['goe_match_rate_percent']}%",
        "",
        "## Owner Truth",
        f"- {summary['owner_note']}",
        "- Real accuracy cannot be claimed until trusted labeled clips are entered.",
    ]
    report_md.write_text("\n".join(lines), encoding="utf-8")

    return {
        "summary_json": str(summary_json),
        "ground_truth_json": str(gt_json),
        "predictions_json": str(pred_json),
        "merged_csv": str(merged_csv),
        "merged_xlsx": str(merged_xlsx),
        "report_md": str(report_md),
        "summary": summary,
    }

if __name__ == "__main__":
    out = build_video_validation_export()
    print(json.dumps(out, indent=2, ensure_ascii=False))
