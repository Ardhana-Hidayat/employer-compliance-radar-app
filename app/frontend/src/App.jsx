import { useEffect, useMemo, useState } from "react";
import { api } from "./api";

function ScoreBar({ value, tone = "navy" }) {
  const w = Math.max(2, Math.min(100, value));

  return (
    <div className="scorebar">
      <div
        className={`scorebar-fill tone-${tone}`}
        style={{ width: `${w}%` }}
      />
      <span className="scorebar-label">{value.toFixed(0)}</span>
    </div>
  );
}

function MetricCard({ label, m }) {
  const p = m.precision_at_k_prevalensi;
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-num">
        P {p.precision.toFixed(2)} <span className="metric-sep">/</span> R {p.recall.toFixed(2)}
      </div>
      <div className="metric-sub">
        k = {p.n_diperiksa} (prevalensi asli), {p.n_aktual_fraud_jenis_ini} kasus aktual
      </div>
    </div>
  );
}

const LABELS = {
  gelap_iuran: "Penggelapan Iuran",
  underreport_upah: "Under-reporting Upah",
  pduk: "PDUK",
  "GABUNGAN (semua jenis, pakai score_total)": "Gabungan (score total)",
};

export default function App() {
  const [connected, setConnected] = useState(null);
  const [sektorList, setSektorList] = useState([]);
  const [rows, setRows] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState("");
  const [sektor, setSektor] = useState("");
  const [status, setStatus] = useState("");
  const [sortKey, setSortKey] = useState("rank");
  const [sortAsc, setSortAsc] = useState(true);

  const [weightIuran, setWeightIuran] = useState(0.45);
  const [weightUpah, setWeightUpah] = useState(0.35);
  const [weightPduk, setWeightPduk] = useState(0.20);
  const [weightPreview, setWeightPreview] = useState(null);
  const [weightBusy, setWeightBusy] = useState(false);

  useEffect(() => {
    api.health().then(() => setConnected(true)).catch(() => setConnected(false));
    api.sektorList().then(setSektorList).catch(() => {});
    api.metrics().then(setMetrics).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .employers({ sektor, status, search, limit: 200 })
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sektor, status, search]);

  const sortedRows = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (typeof x === "string") return sortAsc ? x.localeCompare(y) : y.localeCompare(x);
      return sortAsc ? x - y : y - x;
    });
    return copy;
  }, [rows, sortKey, sortAsc]);

  function toggleSort(key) {
    if (key === sortKey) setSortAsc(!sortAsc);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  async function previewWeights() {
    setWeightBusy(true);
    try {
      const res = await api.rescoring({
        score_iuran: weightIuran,
        score_upah: weightUpah,
        score_pduk: weightPduk,
      });
      setWeightPreview(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setWeightBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="topbar-title">
          <span className="topbar-mark">ECR</span>
          <div>
            <h1>Employer Compliance Radar</h1>
            <p>Ranking risiko kepatuhan pemberi kerja — model dihitung ulang tiap request via API lokal</p>
          </div>
        </div>
        <div className={`conn-badge ${connected ? "ok" : "down"}`}>
          {connected === null ? "Menghubungkan…" : connected ? "API tersambung" : "API tidak tersambung"}
        </div>
      </header>

      {!connected && connected !== null && (
        <div className="banner-warn">
          Tidak bisa menghubungi backend di <code>http://127.0.0.1:8000</code>. Jalankan{" "}
          <code>uvicorn main:app --port 8000</code> di folder <code>backend/</code> dulu — lihat README.
        </div>
      )}

      <main className="content">
        <div className="banner-note">
          Kolom "Ground Truth" hanya ada di data simulasi untuk validasi internal — di dunia nyata status ini
          tidak diketahui sistem. Skor adalah alat prioritisasi, bukan vonis fraud.
        </div>

        <section className="metrics-row">
          {metrics.map((m) => (
            <MetricCard key={m.jenis_fraud} label={LABELS[m.jenis_fraud] || m.jenis_fraud} m={m} />
          ))}
        </section>

        <section className="weight-panel">
          <h2>Uji sensitivitas bobot</h2>
          <p className="weight-desc">
            Bobot saat ini di proposal adalah asumsi (iuran 0.45 / upah 0.35 / PDUK 0.20). Geser untuk melihat
            dampaknya ke ranking &amp; presisi sebelum dikunci sebagai final.
          </p>
          <div className="weight-sliders">
            <label>
              Iuran ({weightIuran.toFixed(2)})
              <input type="range" min="0" max="1" step="0.05" value={weightIuran}
                onChange={(e) => setWeightIuran(parseFloat(e.target.value))} />
            </label>
            <label>
              Upah ({weightUpah.toFixed(2)})
              <input type="range" min="0" max="1" step="0.05" value={weightUpah}
                onChange={(e) => setWeightUpah(parseFloat(e.target.value))} />
            </label>
            <label>
              PDUK ({weightPduk.toFixed(2)})
              <input type="range" min="0" max="1" step="0.05" value={weightPduk}
                onChange={(e) => setWeightPduk(parseFloat(e.target.value))} />
            </label>
            <button onClick={previewWeights} disabled={weightBusy}>
              {weightBusy ? "Menghitung…" : "Hitung ulang via API"}
            </button>
          </div>
          {weightPreview && (
            <div className="weight-preview">
              <span>Top 3 dengan bobot ini: </span>
              {weightPreview.top_10.slice(0, 3).map((r) => (
                <span key={r.employer_id} className="weight-chip">
                  {r.employer_id} ({r.score_total.toFixed(0)})
                </span>
              ))}
            </div>
          )}
        </section>

        <section className="controls">
          <input
            type="text"
            placeholder="Cari employer_id…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select value={sektor} onChange={(e) => setSektor(e.target.value)}>
            <option value="">Semua Sektor</option>
            {sektorList.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Semua Status</option>
            <option value="fraud">Ditandai Fraud (Ground Truth)</option>
            <option value="clean">Bersih (Ground Truth)</option>
          </select>
        </section>

        {error && <div className="banner-warn">Error: {error}</div>}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  ["rank", "Rank"], ["employer_id", "ID"], ["sektor", "Sektor"], ["provinsi", "Provinsi"],
                  ["score_total", "Skor Total"], ["score_iuran", "Iuran"], ["score_upah", "Upah"],
                  ["score_pduk", "PDUK"], [null, "Alasan"], ["fraud_type", "Ground Truth"],
                ].map(([key, label]) => (
                  <th key={label} onClick={() => key && toggleSort(key)} className={key ? "sortable" : ""}>
                    {label}{sortKey === key ? (sortAsc ? " ▲" : " ▼") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="empty">Memuat…</td></tr>
              ) : sortedRows.length === 0 ? (
                <tr><td colSpan={10} className="empty">Tidak ada perusahaan yang cocok filter ini.</td></tr>
              ) : (
                sortedRows.map((r) => (
                  <tr key={r.employer_id}>
                    <td>{r.rank}</td>
                    <td className="mono">{r.employer_id}</td>
                    <td>{r.sektor}</td>
                    <td>{r.provinsi}</td>
                    <td><ScoreBar value={r.score_total} tone="navy" /></td>
                    <td><ScoreBar value={r.score_iuran} tone="warn" /></td>
                    <td><ScoreBar value={r.score_upah} tone="navy" /></td>
                    <td><ScoreBar value={r.score_pduk} tone="muted" /></td>
                    <td className="reason">{r.alasan}</td>
                    <td>
                      {r.is_fraud
                        ? <span className="badge fraud">{r.fraud_type}</span>
                        : <span className="badge clean">bersih</span>}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>

      <footer className="footer">Prototype internal — Healthkathon 2026 — data sepenuhnya sintetis</footer>
    </div>
  );
}
