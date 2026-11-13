-- V010 — Highest heart rate held 5 s per training session (cardiolab v0.10.0)
-- Two new columns in hrv_training_sessions, nothing else changed. Safe to re-run.
-- They let the HRmax observed in sessions be read from the database
-- (HRVRepository.observed_hr_max) without the original .fit files.

-- hr_peak: highest heart rate held for a whole 5-s window (3-sample median, then
--          5-s minimum — cardiolab.analytics.hr_max.sustained_peak); NULL = unknown
--          (manual entry, file without heart rate, sessions imported before v0.10.0).
-- hr_peak_optical: TRUE when recorded with an optical (wrist) sensor — less reliable.
ALTER TABLE hrv_training_sessions ADD COLUMN IF NOT EXISTS hr_peak FLOAT;
ALTER TABLE hrv_training_sessions ADD COLUMN IF NOT EXISTS hr_peak_optical BOOLEAN;
