-- V006 — Session RPE + orthostatic score de forme (cardiolab v0.5.0)
-- All ALTER TABLE statements use ADD COLUMN IF NOT EXISTS — safe to re-run.

-- ── hrv_training_sessions : perceived effort of the session (0–10, Foster 2001) ──
-- Used by trimp_session_rpe(): load = duration (min) × RPE. NULL = not entered.
ALTER TABLE hrv_training_sessions ADD COLUMN IF NOT EXISTS rpe SMALLINT
    CHECK (rpe IS NULL OR rpe BETWEEN 0 AND 10);

-- ── hrv_orthostatic : score de forme of the supine phase ──────────────────────
-- Score de forme when the orthostatic test is the main daily measurement
-- (supine phase vs previous supine phases). Distinct from `score` (autonomic
-- response to standing). NULL for rows stored before v0.5.0 until reprocessed.
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS readiness_score FLOAT;
