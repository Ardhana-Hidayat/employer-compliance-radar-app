# Employer Compliance Radar — Prototype (React + FastAPI)

Prototype dashboard untuk Healthkathon 2026. Model skoring dijalankan di backend
Python dan dipanggil frontend React lewat REST API. **Dirancang untuk demo lokal**
(bukan deploy publik) — jalankan keduanya di laptop presenter.

## Struktur
```
backend/    FastAPI + scoring_engine.py (logika skor) + data/ (CSV simulasi)
frontend/   React (Vite) — tabel ranking, metrik, uji sensitivitas bobot
```

## Menjalankan (butuh Python 3.10+ dan Node 18+)

**Terminal 1 — backend**
```
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000
```
Cek: buka http://127.0.0.1:8000/api/health  → harus muncul `{"status":"ok",...}`
Dokumentasi API otomatis: http://127.0.0.1:8000/docs

**Terminal 2 — frontend**
```
cd frontend
npm install
npm run dev
```
Buka http://localhost:5173

> Backend harus jalan DULU. Kalau tidak, frontend menampilkan banner
> "API tidak tersambung".

## Endpoint
| Method | Path | Fungsi |
|---|---|---|
| GET | /api/health | cek koneksi |
| GET | /api/sektor | daftar sektor untuk filter |
| GET | /api/employers?sektor=&status=&search=&limit= | ranking perusahaan (skor dihitung ulang tiap request) |
| GET | /api/employers/{id} | detail satu perusahaan |
| GET | /api/metrics | precision/recall per jenis fraud |
| POST | /api/rescoring | hitung ulang dengan bobot custom (uji sensitivitas) |

## Batasan yang harus diketahui (jangan disembunyikan saat demo)
- Data 100% sintetis; metrik precision/recall dihitung terhadap ground truth
  yang kita sendiri inject, jadi belum membuktikan performa di data riil.
- Deteksi PDUK lemah (precision ~0.09, mendekati tebakan acak) — butuh proxy
  jumlah pekerja sebenarnya (mis. data PPh 21 / BPJS Ketenagakerjaan).
- Skor gabungan (`score_total`) masih memunculkan false positive, terutama
  perusahaan kecil di sektor Teknologi/Jasa. Bobot 0.45/0.35/0.20 adalah asumsi,
  bukan hasil optimasi — panel "Uji sensitivitas bobot" ada untuk mengeksplorasinya.
- Slider bobot tidak dinormalisasi otomatis ke total 1.0.
- CORS dibuka (`*`) hanya untuk pengembangan lokal. Jangan dipakai apa adanya
  di server publik.
- Belum ada autentikasi, logging, atau uji otomatis.
