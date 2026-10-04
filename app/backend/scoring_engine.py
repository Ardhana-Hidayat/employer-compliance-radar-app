"""
Employer Integrity Score - Scoring Engine
==========================================
Refactor dari scoring.py (versi CLI) jadi modul reusable yang dipanggil
API. Logika perhitungan TIDAK berubah dari versi yang sudah divalidasi
sebelumnya - hanya dibungkus jadi fungsi supaya bisa dipanggil ulang
per-request tanpa nulis file setiap kali.

ASUMSI bobot (WEIGHTS) masih sama seperti sebelumnya - lihat catatan
di scoring.py versi asli soal false-positive di sektor Teknologi yang
belum diperbaiki. Ini genuine limitation, bukan disembunyikan di sini.
"""

import numpy as np
import pandas as pd

WEIGHTS = {"score_iuran": 0.45, "score_upah": 0.35, "score_pduk": 0.20}


def compute_features(employers: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    agg = monthly.groupby("employer_id").agg(
        avg_reported_workers=("reported_worker_count", "mean"),
        cv_reported_workers=("reported_worker_count", lambda x: x.std() / x.mean() if x.mean() else 0),
        avg_reported_wage=("reported_avg_wage_rupiah", "mean"),
        late_payment_rate=("telat_bayar", "mean"),
        total_iuran_dilaporkan=("iuran_dilaporkan_rupiah", "sum"),
        total_iuran_dibayar=("iuran_dibayar_rupiah", "sum"),
    ).reset_index()

    agg["payment_gap_ratio"] = 1 - (agg["total_iuran_dibayar"] / agg["total_iuran_dilaporkan"].replace(0, np.nan))
    agg["payment_gap_ratio"] = agg["payment_gap_ratio"].fillna(0).clip(0, 1)

    df = agg.merge(
        employers[["employer_id", "sektor", "provinsi", "ump_wilayah_rupiah", "fraud_type", "is_fraud"]],
        on="employer_id",
    )
    df["wage_ratio"] = df["avg_reported_wage"] / df["ump_wilayah_rupiah"]
    return df


def _risk_from_deficit(value, peer_median, cap=100):
    deficit = (peer_median - value) / peer_median.replace(0, np.nan)
    return (deficit.clip(lower=0) * cap).clip(upper=cap).fillna(0)


def _top_reason(row):
    parts = []
    if row["score_iuran"] > 40:
        parts.append(f"telat bayar {row['late_payment_rate']*100:.0f}% bulan, gap iuran {row['payment_gap_ratio']*100:.0f}%")
    if row["score_upah"] > 40:
        parts.append(f"upah dilaporkan {row['wage_ratio']*100:.0f}% dari UMP wilayah (di bawah median sektor)")
    if row["score_pduk"] > 40:
        parts.append(f"jumlah pekerja terdaftar jauh di bawah median sektor {row['sektor']}")
    return "; ".join(parts) if parts else "tidak ada sinyal risiko signifikan"


def compute_scores(df: pd.DataFrame, weights: dict = None) -> pd.DataFrame:
    """Menghitung skor dari fitur yang sudah diagregasi. weights bisa
    dioverride lewat API supaya tim bisa uji sensitivitas bobot secara
    interaktif tanpa edit kode - berguna karena bobot ini masih asumsi."""
    weights = weights or WEIGHTS
    df = df.copy()
    peer_wage_median = df.groupby("sektor")["wage_ratio"].transform("median")
    peer_worker_median = df.groupby("sektor")["avg_reported_workers"].transform("median")

    df["score_upah"] = _risk_from_deficit(df["wage_ratio"], peer_wage_median)
    df["score_pduk"] = _risk_from_deficit(df["avg_reported_workers"], peer_worker_median)
    df["score_iuran"] = ((0.5 * df["late_payment_rate"] + 0.5 * df["payment_gap_ratio"]) * 100).clip(0, 100)

    df["score_total"] = sum(df[k] * w for k, w in weights.items())
    df["alasan"] = df.apply(_top_reason, axis=1)
    df = df.sort_values("score_total", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


def _eval_at_k(df, score_col, fraud_label, k):
    k = max(1, k)
    top = df.nlargest(k, score_col)
    actual_positive = df[df["fraud_type"] == fraud_label]
    tp = len(top[top["fraud_type"] == fraud_label])
    return {
        "n_diperiksa": k,
        "n_aktual_fraud_jenis_ini": len(actual_positive),
        "true_positive": int(tp),
        "precision": round(tp / k, 3) if k else 0,
        "recall": round(tp / len(actual_positive), 3) if len(actual_positive) else 0,
    }


def compute_metrics(df: pd.DataFrame) -> list:
    labels = {"score_iuran": "gelap_iuran", "score_upah": "underreport_upah", "score_pduk": "pduk"}
    metrics = []
    for score_col, label in labels.items():
        n_actual = len(df[df["fraud_type"] == label])
        n_15pct = max(1, int(len(df) * 0.15))
        metrics.append({
            "jenis_fraud": label,
            "score_dipakai": score_col,
            "precision_at_k_prevalensi": _eval_at_k(df, score_col, label, n_actual),
            "precision_at_top15pct": _eval_at_k(df, score_col, label, n_15pct),
        })

    n_actual_fraud = int(df["is_fraud"].sum())
    n_15pct = max(1, int(len(df) * 0.15))
    top_prev = df.nlargest(n_actual_fraud, "score_total")
    top_15 = df.nlargest(n_15pct, "score_total")
    metrics.append({
        "jenis_fraud": "GABUNGAN (semua jenis, pakai score_total)",
        "score_dipakai": "score_total",
        "precision_at_k_prevalensi": {
            "n_diperiksa": n_actual_fraud, "n_aktual_fraud_jenis_ini": n_actual_fraud,
            "true_positive": int(top_prev["is_fraud"].sum()),
            "precision": round(top_prev["is_fraud"].sum() / n_actual_fraud, 3) if n_actual_fraud else 0,
            "recall": round(top_prev["is_fraud"].sum() / n_actual_fraud, 3) if n_actual_fraud else 0,
        },
        "precision_at_top15pct": {
            "n_diperiksa": n_15pct, "n_aktual_fraud_jenis_ini": n_actual_fraud,
            "true_positive": int(top_15["is_fraud"].sum()),
            "precision": round(top_15["is_fraud"].sum() / n_15pct, 3),
            "recall": round(top_15["is_fraud"].sum() / n_actual_fraud, 3) if n_actual_fraud else 0,
        },
    })
    return metrics
