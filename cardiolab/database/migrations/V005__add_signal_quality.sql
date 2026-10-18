-- V005 — Add signal quality index (cardiolab v0.4.0)
-- One JSONB column per protocol table whose results depend on beat-to-beat
-- variability: {"grade", "artifact_pct", "corrected", "n_beats",
-- "effective_duration"}. hrv_orthostatic stores one object per phase:
-- {"overall": …, "supine": …, "transition": …, "standing": …}.
-- Rows stored before v0.4.0 keep NULL = quality unknown (never excluded).
-- HRR and cardiac drift are heart-rate based and not graded.
-- All ALTER TABLE statements use ADD COLUMN IF NOT EXISTS — safe to re-run.

ALTER TABLE hrv_features    ADD COLUMN IF NOT EXISTS quality JSONB;
ALTER TABLE hrv_orthostatic ADD COLUMN IF NOT EXISTS quality JSONB;
ALTER TABLE hrv_coherence   ADD COLUMN IF NOT EXISTS quality JSONB;
ALTER TABLE hrv_vo2max      ADD COLUMN IF NOT EXISTS quality JSONB;
