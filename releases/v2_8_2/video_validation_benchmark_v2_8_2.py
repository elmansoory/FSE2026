#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sqlite3
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
import runpy

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fse_owner_v1_2.db"
OUT_DIR = BASE_DIR / "video_validation_exports"

APP_BG = "#0b1220"
SIDEBAR_BG = "#111827"
PANEL_BG = "#172235"
CARD_BG = "#1d2b42"
TEXT = "#eef4ff"
MUTED = "#9eb0ca"
ACCENT = "#3b82f6"
SUCCESS = "#10b981"
WARN = "#f59e0b"
DANGER = "#ef4444"
BORDER = "#263750"

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

def db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn

def open_path(path: Path):
    path = Path(path)
    if not path.exists():
        messagebox.showwarning("Missing", f"Path not found:\n{path}")
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        messagebox.showinfo("Path", str(path))

class KPI(tk.Frame):
    def __init__(self, master, title, value, note="", color=ACCENT):
        super().__init__(master, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        self.configure(width=205, height=88)
        self.grid_propagate(False)
        tk.Label(self, text=title, bg=CARD_BG, fg=MUTED, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        tk.Label(self, text=value, bg=CARD_BG, fg="white", font=("Segoe UI", 20, "bold")).grid(row=1, column=0, sticky="w", padx=12)
        tk.Label(self, text=note, bg=CARD_BG, fg=color, font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", padx=12)

class App:
    def __init__(self, root):
        self.root = root
        self.conn = db()
        self.status = tk.StringVar(value="Ready")
        self.selected_run_id = tk.StringVar(value="")
        self.benchmark_name = tk.StringVar(value="Academy Benchmark 01")
        self.source_reference = tk.StringVar(value="manual_labeled_clips")
        self.model_version = tk.StringVar(value="owner_build")
        self.gt_clip_name = tk.StringVar(value="")
        self.gt_source_video = tk.StringVar(value="")
        self.gt_athlete_name = tk.StringVar(value="")
        self.gt_element = tk.StringVar(value="")
        self.gt_error = tk.StringVar(value="")
        self.gt_goe = tk.StringVar(value="")
        self.gt_reviewer = tk.StringVar(value="Head Reviewer")
        self.pred_clip_name = tk.StringVar(value="")
        self.pred_source_video = tk.StringVar(value="")
        self.pred_element = tk.StringVar(value="")
        self.pred_error = tk.StringVar(value="")
        self.pred_goe = tk.StringVar(value="")
        self.pred_confidence = tk.StringVar(value="0.80")
        root.title("FSE v2.8.2 — Video Validation Benchmark")
        root.geometry("1780x1120")
        root.configure(bg=APP_BG)
        self._build_shell()
        self.show_page("Validation Dashboard")

    def _build_shell(self):
        header = tk.Frame(self.root, bg=APP_BG)
        header.pack(fill="x", padx=16, pady=(12,8))
        tk.Label(header, text="FSE Video Validation Benchmark", bg=APP_BG, fg="white", font=("Segoe UI",24,"bold")).pack(anchor="w")
        tk.Label(header, text="v2.8.2 — benchmark real labeled clips against model predictions and measure actual agreement", bg=APP_BG, fg=MUTED, font=("Segoe UI",11)).pack(anchor="w")
        body = tk.Frame(self.root, bg=APP_BG)
        body.pack(fill="both", expand=True, padx=16, pady=(0,12))
        self.sidebar = tk.Frame(body, bg=SIDEBAR_BG, width=260)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.nav = {}
        for name in ["Validation Dashboard", "Ground Truth Entry", "Prediction Entry", "Benchmark Export", "Diagnostics"]:
            btn = tk.Button(self.sidebar, text=name, anchor="w", relief="flat", bd=0, bg=SIDEBAR_BG, fg=TEXT,
                            activebackground="#20304a", activeforeground="white", font=("Segoe UI",11),
                            command=lambda n=name: self.show_page(n))
            btn.pack(fill="x", padx=10, pady=3, ipady=9)
            self.nav[name] = btn
        foot = tk.Frame(self.sidebar, bg=SIDEBAR_BG)
        foot.pack(side="bottom", fill="x", padx=12, pady=14)
        tk.Label(foot, text="Status", bg=SIDEBAR_BG, fg=MUTED, font=("Segoe UI",9,"bold")).pack(anchor="w")
        tk.Label(foot, textvariable=self.status, bg=SIDEBAR_BG, fg="white", wraplength=230, justify="left").pack(anchor="w", pady=(3,0))
        self.content = tk.Frame(body, bg=APP_BG)
        self.content.pack(side="left", fill="both", expand=True, padx=(16,0))

    def _clear(self):
        for c in self.content.winfo_children():
            c.destroy()

    def _set_active(self, page):
        for n,b in self.nav.items():
            b.configure(bg="#1e2c45" if n == page else SIDEBAR_BG)

    def _header(self, title, subtitle):
        top = tk.Frame(self.content, bg=APP_BG)
        top.pack(fill="x", pady=(2,10))
        tk.Label(top, text=title, bg=APP_BG, fg="white", font=("Segoe UI",20,"bold")).pack(anchor="w")
        tk.Label(top, text=subtitle, bg=APP_BG, fg=MUTED, font=("Segoe UI",10)).pack(anchor="w", pady=(2,0))

    def _tree(self, master, cols, widths, height=12):
        wrap = tk.Frame(master, bg=PANEL_BG)
        tree = ttk.Treeview(wrap, columns=cols, show="headings", height=height)
        ys = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        xs = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        for c,w in zip(cols,widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="w")
        tree.grid(row=0,column=0,sticky="nsew")
        ys.grid(row=0,column=1,sticky="ns")
        xs.grid(row=1,column=0,sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        return wrap, tree

    def ensure_run(self):
        rid = self.selected_run_id.get().strip()
        if rid:
            return int(rid)
        self.conn.execute(
            "INSERT INTO video_validation_runs (benchmark_name, source_reference, model_version, notes) VALUES (?, ?, ?, ?)",
            (self.benchmark_name.get().strip() or "Academy Benchmark 01",
             self.source_reference.get().strip() or "manual_labeled_clips",
             self.model_version.get().strip() or "owner_build",
             "Created from validation benchmark UI"),
        )
        self.conn.commit()
        new_id = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.selected_run_id.set(str(new_id))
        return new_id

    def summary(self):
        gt = self.conn.execute("SELECT clip_name, element_label, error_label, goe_label FROM video_ground_truth").fetchall()
        pred = self.conn.execute("SELECT clip_name, predicted_element, predicted_error, predicted_goe_band FROM video_model_predictions").fetchall()
        gt_map = {r["clip_name"]: dict(r) for r in gt}
        pred_map = {r["clip_name"]: dict(r) for r in pred}
        total_gt = len(gt_map)
        total_pred = len(pred_map)
        matched = 0
        em = 0
        erm = 0
        gm = 0
        for clip, g in gt_map.items():
            p = pred_map.get(clip)
            if not p:
                continue
            matched += 1
            if (g["element_label"] or "").strip().lower() == (p["predicted_element"] or "").strip().lower():
                em += 1
            if (g["error_label"] or "").strip().lower() == (p["predicted_error"] or "").strip().lower():
                erm += 1
            if (g["goe_label"] or "").strip().lower() == (p["predicted_goe_band"] or "").strip().lower():
                gm += 1
        return {
            "validation_runs_total": self.conn.execute("SELECT COUNT(*) FROM video_validation_runs").fetchone()[0],
            "ground_truth_rows": total_gt,
            "prediction_rows": total_pred,
            "matched_prediction_rows": matched,
            "pending_prediction_rows": max(total_gt - matched, 0),
            "element_match_rate_percent": round((em / total_gt) * 100, 2) if total_gt else 0.0,
            "error_match_rate_percent": round((erm / total_gt) * 100, 2) if total_gt else 0.0,
            "goe_match_rate_percent": round((gm / total_gt) * 100, 2) if total_gt else 0.0,
            "benchmark_ready": total_gt > 0 and total_pred > 0,
        }

    def show_page(self, page):
        self._set_active(page)
        self._clear()
        {"Validation Dashboard": self.build_dashboard, "Ground Truth Entry": self.build_gt, "Prediction Entry": self.build_pred, "Benchmark Export": self.build_export, "Diagnostics": self.build_diagnostics}[page]()

    def build_dashboard(self):
        self._header("Validation Dashboard", "Real accuracy starts here, not from attendance or membership spreadsheets.")
        s = self.summary()
        row = tk.Frame(self.content, bg=APP_BG)
        row.pack(fill="x", pady=(0,12))
        items = [
            ("GT Rows", s["ground_truth_rows"], "trusted labels", ACCENT),
            ("Pred Rows", s["prediction_rows"], "model outputs", SUCCESS),
            ("Matched", s["matched_prediction_rows"], "same clip ids", WARN),
            ("Element Match", f"{s['element_match_rate_percent']}%", "core metric", SUCCESS),
            ("Error Match", f"{s['error_match_rate_percent']}%", "error metric", WARN),
            ("GOE Match", f"{s['goe_match_rate_percent']}%", "goe metric", ACCENT),
        ]
        for i,it in enumerate(items):
            KPI(row, *it).grid(row=0, column=i, padx=(0,10), sticky="w")
        txt = tk.Text(self.content, bg="#0f172a", fg=TEXT, relief="flat", font=("Consolas",10))
        txt.pack(fill="both", expand=True)
        txt.insert("end", json.dumps({
            "owner_truth": "I still cannot claim production accuracy until real labeled clips are entered here.",
            "summary": s
        }, indent=2))

    def build_gt(self):
        self._header("Ground Truth Entry", "Enter trusted human labels for each benchmark clip.")
        form = tk.Frame(self.content, bg=PANEL_BG, highlightthickness=1, highlightbackground=BORDER)
        form.pack(fill="x", pady=(0,12))
        inner = tk.Frame(form, bg=PANEL_BG)
        inner.pack(fill="x", padx=16, pady=16)
        fields = [
            ("Benchmark Name", self.benchmark_name),
            ("Source Reference", self.source_reference),
            ("Model Version", self.model_version),
            ("Clip Name", self.gt_clip_name),
            ("Source Video", self.gt_source_video),
            ("Athlete Name", self.gt_athlete_name),
            ("Element Label", self.gt_element),
            ("Error Label", self.gt_error),
            ("GOE Label", self.gt_goe),
            ("Reviewer", self.gt_reviewer),
        ]
        for i,(label,var) in enumerate(fields):
            tk.Label(inner, text=label, bg=PANEL_BG, fg=MUTED).grid(row=i, column=0, sticky="w", pady=5)
            ttk.Entry(inner, textvariable=var, width=36).grid(row=i, column=1, sticky="we", pady=5)
        inner.columnconfigure(1, weight=1)
        ttk.Button(inner, text="Save Ground Truth Row", command=self.save_gt).grid(row=len(fields), column=1, sticky="w", pady=(10,0))

    def save_gt(self):
        run_id = self.ensure_run()
        clip = self.gt_clip_name.get().strip()
        if not clip:
            messagebox.showinfo("Ground Truth", "Clip name is required.")
            return
        self.conn.execute(
            "INSERT INTO video_ground_truth (validation_run_id, clip_name, source_video, athlete_name, element_label, error_label, goe_label, reviewer_name, review_status, start_time, end_time, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'approved', NULL, NULL, ?)",
            (run_id, clip, self.gt_source_video.get().strip(), self.gt_athlete_name.get().strip(),
             self.gt_element.get().strip(), self.gt_error.get().strip(), self.gt_goe.get().strip(),
             self.gt_reviewer.get().strip() or "Head Reviewer", "manual ground truth entry"),
        )
        self.conn.commit()
        self.status.set(f"Ground truth saved for {clip}.")
        messagebox.showinfo("Saved", "Ground truth row saved.")

    def build_pred(self):
        self._header("Prediction Entry", "Enter or import the model prediction for the same benchmark clip.")
        form = tk.Frame(self.content, bg=PANEL_BG, highlightthickness=1, highlightbackground=BORDER)
        form.pack(fill="x", pady=(0,12))
        inner = tk.Frame(form, bg=PANEL_BG)
        inner.pack(fill="x", padx=16, pady=16)
        fields = [
            ("Clip Name", self.pred_clip_name),
            ("Source Video", self.pred_source_video),
            ("Predicted Element", self.pred_element),
            ("Predicted Error", self.pred_error),
            ("Predicted GOE", self.pred_goe),
            ("Confidence", self.pred_confidence),
        ]
        for i,(label,var) in enumerate(fields):
            tk.Label(inner, text=label, bg=PANEL_BG, fg=MUTED).grid(row=i, column=0, sticky="w", pady=5)
            ttk.Entry(inner, textvariable=var, width=36).grid(row=i, column=1, sticky="we", pady=5)
        inner.columnconfigure(1, weight=1)
        ttk.Button(inner, text="Save Prediction Row", command=self.save_pred).grid(row=len(fields), column=1, sticky="w", pady=(10,0))
        frame, tree = self._tree(self.content, ["Clip", "Element", "Error", "GOE", "Conf"], [220,180,180,140,90], height=10)
        frame.pack(fill="both", expand=True)
        for r in self.conn.execute("SELECT clip_name, predicted_element, predicted_error, predicted_goe_band, confidence FROM video_model_predictions ORDER BY id DESC LIMIT 20"):
            tree.insert("", "end", values=r)

    def save_pred(self):
        run_id = self.ensure_run()
        clip = self.pred_clip_name.get().strip()
        if not clip:
            messagebox.showinfo("Prediction", "Clip name is required.")
            return
        try:
            conf = float(self.pred_confidence.get().strip() or 0)
        except Exception:
            conf = 0.0
        self.conn.execute(
            "INSERT INTO video_model_predictions (validation_run_id, clip_name, source_video, predicted_element, predicted_error, predicted_goe_band, confidence, start_time, end_time, notes) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)",
            (run_id, clip, self.pred_source_video.get().strip(), self.pred_element.get().strip(),
             self.pred_error.get().strip(), self.pred_goe.get().strip(), conf, "manual prediction entry"),
        )
        self.conn.commit()
        self.status.set(f"Prediction saved for {clip}.")
        messagebox.showinfo("Saved", "Prediction row saved.")
        self.show_page("Prediction Entry")

    def build_export(self):
        self._header("Benchmark Export", "Generate the benchmark report and open the export folder.")
        box = tk.Frame(self.content, bg=PANEL_BG, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="x", pady=(0,12))
        controls = tk.Frame(box, bg=PANEL_BG)
        controls.pack(fill="x", padx=16, pady=16)
        ttk.Button(controls, text="Build Video Validation Export", command=self.run_export).pack(side="left")
        ttk.Button(controls, text="Open Export Folder", command=lambda: open_path(OUT_DIR)).pack(side="left", padx=8)
        self.report_text = tk.Text(self.content, bg="#0f172a", fg=TEXT, relief="flat", font=("Consolas",10))
        self.report_text.pack(fill="both", expand=True)
        self.report_text.insert("end", "No benchmark export generated yet.")

    def run_export(self):
        out = runpy.run_path(str(BASE_DIR / "export_video_validation_benchmark_v2_8_2.py"))["build_video_validation_export"]()
        self.report_text.delete("1.0", "end")
        self.report_text.insert("end", json.dumps(out, indent=2, ensure_ascii=False))
        self.status.set("Video validation export generated.")
        messagebox.showinfo("Export Complete", "Video validation export generated.")

    def build_diagnostics(self):
        self._header("Diagnostics", "Quick diagnostics for video validation readiness.")
        txt = tk.Text(self.content, bg="#0f172a", fg=TEXT, relief="flat", font=("Consolas",10))
        txt.pack(fill="both", expand=True)
        txt.insert("end", json.dumps({
            "db_exists": DB_PATH.exists(),
            "export_dir_exists": OUT_DIR.exists(),
            "summary": self.summary(),
        }, indent=2))

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
