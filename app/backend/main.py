"""
Employer Compliance Radar - API
=================================
Jalankan lokal: uvicorn main:app --reload --port 8000
Lihat README.md di root project untuk instruksi lengkap.

CATATAN JUJUR: ini API lokal untuk keperluan demo prototype, BUKAN
di-deploy ke server publik. Untuk demo hackathon, jalankan ini di
laptop presenter bersamaan dengan frontend React (npm run dev).
"""

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import scoring_engine as engine

DATA_DIR = Path(__file__).parent / "data"

app = FastAPI(title="Employer Compliance Radar API", version="0.1.0")

# CORS dibuka untuk dev lokal (React biasanya di port 5173/3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_employers = pd.read_csv(DATA_DIR / "sim_employers.csv")
_monthly = pd.read_csv(DATA_DIR / "sim_monthly_records.csv")
_features = engine.compute_features(_employers, _monthly)


class WeightOverride(BaseModel):
    score_iuran: Optional[float] = None
    score_upah: Optional[float] = None
    score_pduk: Optional[float] = None


def _current_weights(w: WeightOverride) -> dict:
    base = dict(engine.WEIGHTS)
    if w.score_iuran is not None:
        base["score_iuran"] = w.score_iuran
    if w.score_upah is not None:
        base["score_upah"] = w.score_upah
    if w.score_pduk is not None:
        base["score_pduk"] = w.score_pduk
    return base


@app.get("/api/health")
def health():
    return {"status": "ok", "n_perusahaan": len(_employers)}


@app.get("/api/sektor")
def list_sektor():
    return sorted(_features["sektor"].unique().tolist())


@app.get("/api/employers")
def get_employers(
    sektor: Optional[str] = None,
    status: Optional[str] = Query(None, description="'fraud' atau 'clean'"),
    search: Optional[str] = None,
    limit: int = 100,
):
    """Model dihitung ULANG di sini setiap request (bukan cache statis) -
    supaya benar-benar 'model via API', bukan sekadar serve CSV."""
    scored = engine.compute_scores(_features)

    if sektor:
        scored = scored[scored["sektor"] == sektor]
    if status == "fraud":
        scored = scored[scored["is_fraud"]]
    elif status == "clean":
        scored = scored[~scored["is_fraud"]]
    if search:
        scored = scored[scored["employer_id"].str.contains(search, case=False)]

    cols = ["rank", "employer_id", "sektor", "provinsi", "score_total", "score_iuran",
            "score_upah", "score_pduk", "late_payment_rate", "payment_gap_ratio",
            "wage_ratio", "avg_reported_workers", "alasan", "fraud_type", "is_fraud"]
    return scored[cols].head(limit).to_dict(orient="records")


@app.get("/api/employers/{employer_id}")
def get_employer_detail(employer_id: str):
    scored = engine.compute_scores(_features)
    row = scored[scored["employer_id"] == employer_id]
    if row.empty:
        return {"error": "not found"}
    return row.iloc[0].to_dict()


@app.get("/api/metrics")
def get_metrics():
    scored = engine.compute_scores(_features)
    return engine.compute_metrics(scored)


@app.post("/api/rescoring")
def rescoring(weights: WeightOverride):
    """Uji sensitivitas bobot secara interaktif - kirim bobot custom,
    dapatkan skor & metrik baru. Berguna untuk eksplorasi tim sebelum
    mengunci bobot final di proposal."""
    w = _current_weights(weights)
    scored = engine.compute_scores(_features, weights=w)
    metrics = engine.compute_metrics(scored)
    cols = ["rank", "employer_id", "sektor", "score_total", "score_iuran", "score_upah", "score_pduk", "alasan"]
    return {"weights_dipakai": w, "top_10": scored[cols].head(10).to_dict(orient="records"), "metrics": metrics}
