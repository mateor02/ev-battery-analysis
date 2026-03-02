-- Create a table for raw battery readings
USE ev_project_db;

CREATE TABLE IF NOT EXISTS battery_readings_raw (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vah_code VARCHAR(5),
    file_name VARCHAR(10),
    time_s DOUBLE,
    ecell_v DOUBLE,
    i_ma DOUBLE,
    energy_charge_w_h DOUBLE,
    q_charge_ma_h DOUBLE,
    q_discharge_ma_h DOUBLE,
    temperature_c DOUBLE,
    cycle_number INT,
    ns INT,
    test_type VARCHAR(50)
);

CREATE INDEX idx_cycle_number ON battery_readings_raw (cycle_number);
CREATE INDEX idx_vah ON battery_readings_raw (vah_code);
CREATE INDEX idx_file_name ON battery_readings_raw (file_name);
CREATE INDEX idx_vah_cycle ON battery_readings_raw (vah_code, cycle_number);
CREATE INDEX idx_cycle_time ON battery_readings_raw (cycle_number, time_s);


CREATE TABLE IF NOT EXISTS battery_impedance_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vah_code VARCHAR(5),
    file_name VARCHAR(20),
    twenty_pct_one_s DOUBLE,
    twenty_pct_thirty_s DOUBLE,
    sixty_pct_one_s DOUBLE,
    sixty_pct_thirty_s DOUBLE,
    cycle_number INT,
    test_type VARCHAR(50)
);

CREATE INDEX idx_imp_cycle ON battery_impedance_readings (cycle_number);
CREATE INDEX idx_imp_vah ON battery_impedance_readings (vah_code);
CREATE INDEX idx_imp_file_name ON battery_impedance_readings (file_name);
CREATE INDEX idx_imp_vah_cycle ON battery_impedance_readings (vah_code, cycle_number);


CREATE TABLE IF NOT EXISTS battery_anomalies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vah_code VARCHAR(5),
    file_name VARCHAR(10),
    cycle_number INT,
    anomaly_type VARCHAR(50),
    severity TINYINT,
    notes TEXT,
    metrics JSON,
    rule_version INT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_anomaly_vah_cycle ON battery_anomalies (vah_code, cycle_number);
CREATE INDEX idx_anomaly_type on battery_anomalies (anomaly_type);


CREATE TABLE IF NOT EXISTS cycle_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vah_code VARCHAR(5),
    file_name VARCHAR(50),
    cycle_number INT,
    first_time_s DOUBLE,
    last_time_s DOUBLE,
    duration_s DOUBLE,
    max_v DOUBLE,
    min_v DOUBLE,
    max_i DOUBLE,
    min_i DOUBLE,
    total_q DOUBLE,
    total_e DOUBLE,
    test_type VARCHAR(50)
);

CREATE INDEX idx_summary_cycle ON cycle_summary (cycle_number);
CREATE INDEX idx_summary_vah ON cycle_summary (vah_code);
CREATE INDEX idx_summary_file_name ON cycle_summary (file_name);
CREATE INDEX idx_summary_vah_cycle ON cycle_summary (vah_code, cycle_number);
