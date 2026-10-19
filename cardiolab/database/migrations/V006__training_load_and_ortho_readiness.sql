-- V006 — Training load methods + orthostatic score de forme + VO2max HRmax source (cardiolab v0.5.0)
-- All statements use ADD COLUMN IF NOT EXISTS — safe to re-run.

-- ── hrv_training_sessions : data of each load method ──────────────────────────
-- rpe     : perceived effort of the session (0–10, Foster 2001) — "rpe" method
-- hr_mean : mean heart rate of the session (bpm)                — "banister" method
-- NULL = not entered.
ALTER TABLE hrv_training_sessions ADD COLUMN IF NOT EXISTS rpe SMALLINT
    CHECK (rpe IS NULL OR rpe BETWEEN 0 AND 10);
ALTER TABLE hrv_training_sessions ADD COLUMN IF NOT EXISTS hr_mean FLOAT;

-- ── user_profiles : load method applied to every session of the athlete ──────
-- hrv (score de forme of the day) · banister (session HR) · rpe (perceived
-- effort). One method per athlete keeps ATL / CTL / TSB on one scale.
-- Existing profiles get 'hrv' — the method used until v0.5.0.
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS load_method TEXT NOT NULL DEFAULT 'hrv'
    CHECK (load_method IN ('hrv', 'banister', 'rpe'));

-- ── hrv_orthostatic : score de forme of the supine phase ──────────────────────
-- Score de forme when the orthostatic test is the main daily measurement
-- (supine phase vs previous supine phases). Distinct from `score` (autonomic
-- response to standing). NULL for rows stored before v0.5.0 until reprocessed.
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS readiness_score FLOAT;

-- ── hrv_vo2max : origin of the HRmax used by the Uth model ───────────────────
-- provided (given by the user) · tanaka (208 − 0.7 × age, from birth_year)
-- NULL = no HRmax, or rows stored before v0.5.0 (HRmax was always provided).
ALTER TABLE hrv_vo2max ADD COLUMN IF NOT EXISTS hr_max_source TEXT
    CHECK (hr_max_source IS NULL OR hr_max_source IN ('provided', 'tanaka'));
