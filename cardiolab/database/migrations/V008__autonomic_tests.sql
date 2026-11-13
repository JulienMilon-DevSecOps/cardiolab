-- V008 — Autonomic reflex tests: Ewing battery heart rate tests (cardiolab v0.8.0)
-- One new table, nothing changed in the existing ones. Safe to re-run (IF NOT EXISTS).
-- It holds user data: listed in USER_DATA_TABLE_ATTRS (delete_user_data).

-- One row per day; each test may be missing (NULL columns).
-- db_*      deep breathing (6 breaths/min): mean heart rate difference (bpm) and
--           E/I ratio over the complete cycles, breathing rate; reference
--           ewing_1985 (adult values) or may_1999 (age-corrected 5th percentile,
--           age stored in "age"); status ok · unreliable (< 3 cycles).
-- valsalva_ strain at 40 mmHg: longest RR after / shortest RR during the strain.
-- ratio_30_15 longest RR (beats 20–40) / shortest RR (beats 5–25) after standing;
--           stand_estimated = moment of standing estimated from the heart rate rise.
-- *_interpretation: normal · borderline · abnormal (reference values, not a diagnosis).
CREATE TABLE IF NOT EXISTS hrv_autonomic_tests (
    id                           SERIAL PRIMARY KEY,
    user_id                      TEXT    NOT NULL,
    date                         DATE    NOT NULL,
    age                          FLOAT,
    db_hr_difference             FLOAT,
    db_ei_ratio                  FLOAT,
    db_n_cycles                  INTEGER,
    db_breathing_rate            FLOAT,
    db_interpretation            TEXT CHECK (db_interpretation IN ('normal', 'borderline', 'abnormal', '')),
    db_reference                 TEXT CHECK (db_reference IN ('ewing_1985', 'may_1999')),
    db_status                    TEXT CHECK (db_status IN ('ok', 'unreliable')),
    valsalva_ratio               FLOAT,
    valsalva_max_hr              FLOAT,
    valsalva_min_hr              FLOAT,
    valsalva_strain_sec          FLOAT,
    valsalva_interpretation      TEXT CHECK (valsalva_interpretation IN ('normal', 'borderline', 'abnormal', '')),
    valsalva_status              TEXT CHECK (valsalva_status IN ('ok', 'unreliable')),
    ratio_30_15                  FLOAT,
    ratio_30_15_stand_sec        FLOAT,
    ratio_30_15_stand_estimated  BOOLEAN,
    ratio_30_15_interpretation   TEXT CHECK (ratio_30_15_interpretation IN ('normal', 'borderline', 'abnormal', '')),
    UNIQUE(user_id, date)
);
