-- V009 — HRmax field test and HRmax source of the profile (cardiolab v0.10.0)
-- One new table, one new column in user_profiles. Safe to re-run (IF NOT EXISTS).
-- hrv_hr_max_tests holds user data: listed in USER_DATA_TABLE_ATTRS (delete_user_data).

-- ── HRmax field test (Olympiatoppen) ──────────────────────────────────────────
-- One row per test: highest heart rate held 5 s, sport (HRmax depends on it),
-- final effort (s at ≥ 90 % of the peak before it), plateau before the peak,
-- sensor (chest_strap · optical), status valid · doubtful · invalid.
-- raw_max: highest single sample (a higher isolated spike is an artefact).
CREATE TABLE IF NOT EXISTS hrv_hr_max_tests (
    id                SERIAL PRIMARY KEY,
    user_id           TEXT    NOT NULL,
    date              DATE    NOT NULL,
    sport             TEXT,
    hr_max            FLOAT,
    peak_time_sec     FLOAT,
    raw_max           FLOAT,
    final_effort_sec  FLOAT,
    plateau_reached   BOOLEAN,
    sensor            TEXT CHECK (sensor IS NULL OR sensor IN ('chest_strap', 'optical')),
    status            TEXT CHECK (status IN ('valid', 'doubtful', 'invalid')),
    UNIQUE(user_id, date)
);

-- ── Where the profile HRmax comes from ────────────────────────────────────────
-- provided (entered) · tanaka (predicted from the age) · field_test (HRmax test)
-- · observed (highest heart rate held 5 s in the sessions). NULL = unknown
-- (profiles created before v0.10.0). Changed only when the athlete accepts.
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS hr_max_source TEXT
    CHECK (hr_max_source IS NULL
           OR hr_max_source IN ('provided', 'tanaka', 'field_test', 'observed'));
