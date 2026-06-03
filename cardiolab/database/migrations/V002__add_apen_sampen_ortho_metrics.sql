-- V002 — Add ApEn/SampEn columns + orthostatic enrichment (cardiolab v0.1.x → v0.2.0)
-- All ALTER TABLE statements use ADD COLUMN IF NOT EXISTS — safe to re-run.

-- ── hrv_features : approximate entropy and sample entropy ────────────────────
ALTER TABLE hrv_features ADD COLUMN IF NOT EXISTS apen   FLOAT;
ALTER TABLE hrv_features ADD COLUMN IF NOT EXISTS sampen FLOAT;

-- ── hrv_orthostatic : apen/sampen per phase ───────────────────────────────────
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS supine_apen       FLOAT;
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS supine_sampen     FLOAT;
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS transition_apen   FLOAT;
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS transition_sampen FLOAT;
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS standing_apen     FLOAT;
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS standing_sampen   FLOAT;

-- ── hrv_orthostatic : new autonomic response metrics ─────────────────────────
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS lf_hr_pct_change FLOAT;
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS delta_rmssd      FLOAT;
