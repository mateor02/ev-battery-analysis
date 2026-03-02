from __future__ import annotations
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy import Column, Integer, Float, String, text
from sqlalchemy.engine import URL

# =========================
# ESTABLISH CONNECTION TO
# MYSQL SERVER
# =========================
url = URL.create(
    drivername="mysql+pymysql",
    username="root",
    password="(DB_PASSWORD)",
    host="localhost",
    port=3306,
    database="ev_project_db",
)

engine = create_engine(url, pool_pre_ping=True)

Base = declarative_base()

class BatteryReadingsRaw(Base):
    __tablename__ = 'battery_readings_raw'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vah_code = Column(String(5))
    file_name = Column(String(10))
    time_s = Column(Float)
    ecell_v = Column(Float)
    i_ma = Column(Float)
    energy_charge_w_h = Column(Float)
    q_charge_ma_h = Column(Float)
    energy_discharge_w_h = Column(Float)
    q_discharge_ma_h = Column(Float)
    temperature_c = Column(Float)
    cycle_number = Column(Integer, index=True)
    ns = Column(Integer)
    test_type = Column(String(50))

class BatteryImpedanceReadings(Base):
    __tablename__ = 'battery_impedance_readings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vah_code = Column(String(5))
    file_name = Column(String(20))
    twenty_pct_one_s = Column(Float)
    twenty_pct_thirty_s = Column(Float)
    sixty_pct_one_s = Column(Float)
    sixty_pct_thirty_s = Column(Float)
    cycle_number = Column(Integer)
    test_type = Column(String(50))


def get_test_type(filename: str) -> str:
    mapping = {
        "VAH01": "Baseline",
        "VAH02": "Extended cruise (1000 sec)",
        "VAH05": "10% power reduction during discharge (flight)",
        "VAH06": "CC charge current reduced to C/2",
        "VAH07": "CV charge voltage reduced to 4.0V",
        "VAH09": "Thermal chamber temperature of 20°C",
        "VAH10": "Thermal chamber temperature of 30°C",
        "VAH11": "20% power reduction during discharge (flight)",
        "VAH12": "Short cruise length (400 sec)",
        "VAH13": "Short cruise length (600 sec)",
        "VAH15": "Extended cruise (1000 sec)",
        "VAH16": "CC charge current reduced to 1.5C",
        "VAH17": "Baseline",
        "VAH20": "Charge current reduced to 1.5C",
        "VAH22": "Extended cruise (1000 sec)",
        "VAH23": "CV charge voltage reduced to 4.1V",
        "VAH24": "CC charge current reduced to C/2",
        "VAH25": "Thermal chamber temperature of 20°C",
        "VAH26": "Short cruise length (600 sec)",
        "VAH27": "Baseline",
        "VAH28": "10% power reduction during discharge (flight)",
        "VAH30": "Thermal chamber temperature of 35°C",
    }
    
    if Path(filename).stem.endswith("_impedance"):
        stem1 = Path(filename).stem[:5].strip()
    else:
        stem1 = Path(filename).stem.strip()
                    
    return mapping.get(stem1, "Unknown")


DATA_DIR = Path("/Users/mateomelgoza/2025_Projects/EV_Project/data")
CYCLE_TARGET_COLS = [
    "time_s","Ecell_V","I_mA","EnergyCharge_W_h","QCharge_mA_h","EnergyDischarge_W_h","QDischarge_mA_h","Temperature__C",
    "cycleNumber","Ns"
]

IMP_TARGET_COLS = [
    "20%_1_second","20%_30_second","60%_1_second","60%_30_second","cycle numbers"
]    

def ingest():
    csvs = sorted(DATA_DIR.glob("*.csv"))
    if not csvs:
        print(f"No CSVs in {DATA_DIR}")
        return
    
    with Session(engine) as session:
        for fp in csvs:
            print(f"[READ] {fp.name}")
            df = pd.read_csv(fp, low_memory=False, on_bad_lines="warn") # nrows = 5000 for testing purposes
            df["vah_code"] = fp.name[:5]
            df["file_name"] = fp.name
            df["test_type"] = get_test_type(fp.name)
            
            rename_battery_readings_raw = {
                "Ecell_V": "ecell_v",
                "I_mA": "i_ma",
                "EnergyCharge_W_h": "energy_charge_w_h",
                "QCharge_mA_h": "q_charge_ma_h",
                "EnergyDischarge_W_h": "energy_discharge_w_h",
                "QDischarge_mA_h": "q_discharge_ma_h",
                "Temperature__C": "temperature_c",
                "cycleNumber": "cycle_number",
                "Ns": "ns"
            }
            
            rename_battery_impedance_readings = {
                "20%_1_second": "twenty_pct_one_s",
                "20%_30_second": "twenty_pct_thirty_s",
                "60%_1_second": "sixty_pct_one_s",
                "60%_30_second": "sixty_pct_thirty_s",
                "cycle numbers": "cycle_number"
            }
            
            if fp.stem.endswith("_impedance"):
                df.rename(columns=rename_battery_impedance_readings, inplace=True)
            else:
                df.rename(columns=rename_battery_readings_raw, inplace=True)
            
            # convert dataframe to a list of row dictionaries for SQLALCHEMY bulk inserts
            records = df.to_dict(orient="records")
            
            CHUNK = 10_000
            
            try:
                for i in range(0, len(records), CHUNK):
                    if fp.stem.endswith("_impedance"):
                        session.execute(insert(BatteryImpedanceReadings.__table__), records[i:i+CHUNK])
                    else:
                        session.execute(insert(BatteryReadingsRaw.__table__), records[i:i+CHUNK])
                session.commit()
                print(f"[OK] Inserted {len(records):,} rows from {fp.name}")
            except Exception as e:
                session.rollback()
                print(f"[ERROR] {fp.name}: {e}")
                        
def clear_table():
    with Session(engine) as session:
        session.execute(text("TRUNCATE TABLE battery_readings_raw;"))
        session.execute(text("TRUNCATE TABLE battery_impedance_readings;"))
        session.commit()
        print("[INFO] Cleared battery_readings_raw")
        print("[INFO] Cleared battery_impedance_readings")

if __name__ == "__main__":
    clear_table() # <- function only used for testing purposes
    ingest()
    
    