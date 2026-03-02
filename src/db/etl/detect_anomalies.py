import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')
from ingest_csv_to_mysql import engine

class BatteryAnomalyDetector:
    """
    Detects anomalies in eVTOL battery test data.
    """
    
    def __init__(self):
        """Initialize detector using existing engine"""
        self.engine = engine
    
    def get_cycle_summary(self, vah_code: str = None) -> pd.DataFrame:
        """
        Retrieve cycle summary data.
        
        Args:
            vah_code: Optional filter for specific cell, if provided and not None
        """
        query = "SELECT * FROM cycle_summary"
        if vah_code:
            query += f" WHERE vah_code = '{vah_code}'"
        query += " ORDER BY vah_code, cycle_number"
        
        return pd.read_sql(query, self.engine)
    
    def get_all_vah_codes(self) -> List[str]:
        """Get list of all VAH codes."""
        return [
            'VAH01', 'VAH02', 'VAH05', 'VAH06', 'VAH07', 'VAH09', 'VAH10',
            'VAH11', 'VAH12', 'VAH13', 'VAH15', 'VAH16', 'VAH17', 'VAH20',
            'VAH22', 'VAH23', 'VAH24', 'VAH25', 'VAH26', 'VAH27', 'VAH28', 'VAH30'
        ]
    
    def detect_incomplete_charge(self, df: pd.DataFrame, expected_max_voltage: float = 4.2, tolerance: float = 0.05) -> List[int]:
        """
        Detect cycles where max voltage didn't reach expected charge voltage.
        FAST: Uses pre- computed max_v from cycle summary
        Store incomplete cycles in new df
        """
        incomplete = df[df['max_v'] < (expected_max_voltage - tolerance)]
        return sorted(incomplete['cycle_number'].tolist())
    
    def detect_voltage_out_of_range(self, df: pd.DataFrame, min_voltage: float = 2.5,
                                                            max_voltage: float = 4.3) -> List[int]:
    
        """
        Detect vyvles with voltage readings outside typical Li-ion range.
        FAST: Uses pre-computed min_v/max_v
        """
    
        out_of_range = df[
            (df['min_v'] < min_voltage) | (df['max_v'] > max_voltage)
        ]
        return sorted(out_of_range['cycle_number'].tolist())
    
    def detect_missing_cycles(self, df: pd.DataFrame) -> List[int]:
        """
        Detect missing cycle numbers in sequence.
        """
        if len(df) == 0:
            return []
        
        all_cycles = set(range(int(df['cycle_number'].min()),
                            int(df['cycle_number'].max()) + 1))
        present_cycles = set(df['cycle_number'].unique())
        return sorted(list(all_cycles - present_cycles))
    
    def detect_abnormal_duration(self, df: pd.DataFrame) -> List[int]:
        """
        Detect cycles with abnormally short or long durations.
        Uses duration_s from cycle summary.
        """
        if len(df) < 10:
            return []
        
        # Calculate z-scores for duration
        mean_duration = df['duration_s'].mean()
        std_duration = df['duration_s'].std()
        
        if std_duration == 0:
            return []
        
        df_copy = df.copy()
        df_copy['duration_zscore'] = (df_copy['duration_s'] - mean_duration) / std_duration
        
        # Flag cycles with |z-score| > 3 (very unusual duration)
        abnormal = df_copy[df_copy['duration_zscore'].abs() > 3]
        return sorted(abnormal['cycle_number'].tolist())
    
    def detect_data_gaps(self, df: pd.DataFrame, max_time_gap: float = 7200) -> List[Tuple[int,float]]:
        """
        Detect large time gaps between cycles.
        Uses first_time_s and last_time_s from cycle summary.
        """
        df = df.sort_values('cycle_number').copy()
        
        # Calculate gap between end of one cycle and start of next
        df['gap_to_next'] = df['first_time_s'].shift(-1) - df['last_time_s']
        
        gaps = df[df['gap_to_next'] > max_time_gap]
        
        # zip() combins two lists into a list of tuples
        return list(zip(gaps['cycle_number'].tolist(),
                        gaps['gap_to_next'].tolist()))
        
    def detect_negative_energy(self, df: pd.DataFrame) -> List[int]:
        """
        Detect cycles with negative total energy (unphysical).
        """
        negative = df[df['total_e'] < 0]
        return sorted(negative['cycle_number'].tolist())
    
    def detect_zero_capacity(self, df: pd.DataFrame) -> List[int]:
        """
        Detect cycles with zero or near-zero charge transferred.
        Indicates incomplete or failed cycles.
        """
        near_zero = df[df['total_q'].abs() < 0.1]  # Less than 0.1 mAh
        return sorted(near_zero['cycle_number'].tolist())
    
    def detect_abnormal_capacity(self, df: pd.DataFrame) -> List[int]:
        """
        Detect cycles with abnormally high or low capacity.
        Battery capacity should be relatively consistent.
        """
        if len(df) < 10:
            return []
        
        # Filter out cycles with very low capacity first (those are caught elsewhere)
        df_filtered = df[df['total_q'] > 100].copy()
        
        if len(df_filtered) < 10:
            return []
        
        median_q = df_filtered['total_q'].median()
        # Median Absolute Deviation: robust measure of variability (similar to standard deviation, but less affected by outliers)
        mad = (df_filtered['total_q'] - median_q).abs().median()
        
        if mad == 0:
            return []
        
        # Modified z-score using MAD (more robust to outliers)
        df_copy = df.copy()
        df_copy['modified_zscore'] = 0.6745 * (df_copy['total_q'] - median_q) / mad
        
        abnormal = df_copy[df_copy['modified_zscore'].abs() > 3.5]
        return sorted(abnormal['cycle_number'].tolist())
    
    def detect_current_spikes(self, df: pd.DataFrame) -> List[int]:
        """
        Detect cycles with abnormally high current (charge or discharge).
        """
        if len(df) < 10:
            return []
        
        # Check both max (discharge) and min (charge, negative value)
        max_i_median = df['max_i'].median()
        min_i_median = df['min_i'].median()
        
        max_i_std = df['max_i'].std()
        min_i_std = df['min_i'].std()
        
        spikes = []
        
        if max_i_std > 0:
            # 3-sigma rule
            max_threshold = max_i_median + 3 * max_i_std
            spikes.extend(df[df['max_i'] > max_threshold]['cycle_number'].tolist())
        
        if min_i_std > 0:
            min_threshold = min_i_median - 3 * min_i_std
            spikes.extend(df[df['min_i'] < min_threshold]['cycle_number'].tolist())
        
        return sorted(list(set(spikes)))
    
    def detect_duplicate_cycles(self, df: pd.DataFrame) -> List[int]:
        """
        Detect duplicate cycle numbers (should be unique per cell).
        """
        # check only cycle_number column for duplicates, mark all duplicates as True
        duplicates = df[df.duplicated(subset=['cycle_number'], keep=False)]
        return sorted(duplicates['cycle_number'].unique().tolist())
    
    def analyze_cell(self, vah_code: str, verbose: bool = True) -> Dict:
        """
        Run all anomaly detection methods on a specific cell.
        
        Args:
            vah_code: Cell identifier (e.g., 'VAH05')
            verbose: Whether to print results
        
        Returns:
            Dictionary with all detected anomalies
        """
        if verbose:
            # '='*60 for visual separator line
            print(f"\n{'='*60}")
            print(f"Analyzing {vah_code}")
            print(f"{'='*60}")
        
        df = self.get_cycle_summary(vah_code)
        
        if len(df) == 0:
            print(f"No data found for {vah_code}")
            return None
        
        results = {
            'vah_code': vah_code,
            'total_cycles': len(df),
            'incomplete_charges': self.detect_incomplete_charge(df),
            'voltage_out_of_range': self.detect_voltage_out_of_range(df),
            'missing_cycles': self.detect_missing_cycles(df),
            'abnormal_duration': self.detect_abnormal_duration(df),
            'data_gaps': self.detect_data_gaps(df),
            'negative_energy': self.detect_negative_energy(df),
            'zero_capacity': self.detect_zero_capacity(df),
            'abnormal_capacity': self.detect_abnormal_capacity(df),
            'current_spikes': self.detect_current_spikes(df),
            'duplicate_cycles': self.detect_duplicate_cycles(df)
        }
        
        if verbose:
            "_ prefix, this is just used internally by analyze_cell(), not meant for direct use"
            self._print_results(results)
        
        return results
    
    def _print_results(self, results: Dict):
        """Print anomaly detection results in readable format"""
        print(f"\nTotal Cycles: {results['total_cycles']}")
        
        print(f"\n--- Incomplete Charges (<4.15V) ---")
        self._print_list(results['incomplete_charges'])
        
        print(f"\n--- Voltage Out of Range (2.5-4.3V) ---")
        self._print_list(results['voltage_out_of_range'])
        
        print(f"\n--- Missing Cycles ---")
        self._print_list(results['missing_cycles'])
        
        print(f"\n--- Abnormal Duration (z-score > 3) ---")
        self._print_list(results['abnormal_duration'])
        
        print(f"\n--- Data Gaps (>2 hours between cycles) ---")
        if results['data_gaps']:
            print(f"Found {len(results['data_gaps'])} gaps:")
            for cycle, gap in results['data_gaps'][:5]:
                print(f"  After Cycle {cycle}: {gap/3600:.2f} hours")
            if len(results['data_gaps']) > 5:
                print(f"  ... and {len(results['data_gaps']) - 5} more")
        else:
            print("None detected")
        
        print(f"\n--- Negative Energy Values ---")
        self._print_list(results['negative_energy'])
        
        print(f"\n--- Zero/Near-Zero Capacity ---")
        self._print_list(results['zero_capacity'])
        
        print(f"\n--- Abnormal Capacity (modified z-score > 3.5) ---")
        self._print_list(results['abnormal_capacity'])
        
        print(f"\n--- Current Spikes (z-score > 3) ---")
        self._print_list(results['current_spikes'])
        
        print(f"\n--- Duplicate Cycle Numbers ---")
        self._print_list(results['duplicate_cycles'])
    
    def _print_list(self, items: List, limit: int = 10):
        """Helper to print lists with truncation"""
        if items:
            print(f"Found {len(items)} cycles: {items[:limit]}")
            if len(items) > limit:
                print(f"  ... and {len(items) - limit} more")
        else:
            print("None detected")
    
    def analyze_all_cells(self) -> Dict[str, Dict]:
        """
        Analyze all cells in the database.
        """
        vah_codes = self.get_all_vah_codes()
        print(f"Found {len(vah_codes)} cells to analyze")
        
        all_results = {}
        for vah_code in vah_codes:
            # try except for error handling during cell analyzis, prints where errors happend while continuing loop (avoid crashes)
            try:
                results = self.analyze_cell(vah_code, verbose=True)
                if results:
                    all_results[vah_code] = results
            except Exception as e:
                print(f"Error analyzing {vah_code}: {str(e)}")
                # traceback shows full error details, where the error happened, what line, what function
                import traceback #lazy loading, only import if you actually need traceback
                traceback.print_exc()
        
        return all_results
    
    def export_anomalies_to_csv(self, results: Dict[str, Dict], 
                                 output_file: str = 'battery_anomalies.csv'):
        """
        Export all detected anomalies to a CSV file for review.
        """
        records = []
        
        for vah_code, cell_results in results.items():
            anomaly_types = [
                ('incomplete_charges', 'Did not reach expected max voltage (4.2V)'),
                ('voltage_out_of_range', 'Voltage outside safe Li-ion range (2.5-4.3V)'),
                ('missing_cycles', 'Cycle number missing from sequence'),
                ('abnormal_duration', 'Cycle duration is abnormal'),
                ('negative_energy', 'Negative energy value (unphysical)'),
                ('zero_capacity', 'Zero or near-zero capacity'),
                ('abnormal_capacity', 'Capacity significantly different from typical'),
                ('current_spikes', 'Abnormally high current detected'),
                ('duplicate_cycles', 'Duplicate cycle number')
            ]
            
            # Handle normal anomaly types (just cycle numbers)
            for anomaly_type, description in anomaly_types:
                for cycle in cell_results.get(anomaly_type, []):
                    records.append({
                        'vah_code': vah_code,
                        'cycle_number': cycle,
                        'anomaly_type': anomaly_type,
                        'details': description
                    })
            
            # Handle data_gaps separately (has cycle AND gap duration)
            for cycle, gap in cell_results.get('data_gaps', []):
                records.append({
                    'vah_code': vah_code,
                    'cycle_number': cycle,
                    'anomaly_type': 'data_gap',
                    'details': f'Gap of {gap/3600:.2f} hours after this cycle'
                })
        
        if records:
            df = pd.DataFrame(records)
            df = df.sort_values(['vah_code', 'cycle_number'])
            df.to_csv(output_file, index=False)
            
            print(f"\n{'='*60}")
            print(f"Exported {len(records)} anomaly records to {output_file}")
            print(f"{'='*60}")
            
            # Print summary
            print("\nSummary by anomaly type:")
            print(df['anomaly_type'].value_counts())
            print("\nSummary by cell:")
            print(df['vah_code'].value_counts())
        else:
            print("No anomalies detected!")
    
    def compare_with_readme_issues(self, results: Dict[str, Dict]):
        """
        Compare detected anomalies with known issues from README.
        """
        known_issues = {
            'VAH05': [1000],
            'VAH09': [64, 92, 154, 691],
            'VAH10': [248, 631, 735, 1151],
            'VAH11': [817, 1898],
            'VAH13': [816, 817],
            'VAH25': [461, 462],
            'VAH26': [872, 873],
            'VAH27': [20, 256, 257, 585],
            'VAH28': [256, 257, 619, 620, 1066, 1067],
        }
        
        print(f"\n{'='*60}")
        print("COMPARISON WITH README KNOWN ISSUES")
        print(f"{'='*60}")
        
        for vah_code, known_cycles in known_issues.items():
            if vah_code not in results:
                print(f"\n{vah_code}: Not analyzed")
                continue
            
            print(f"\n{vah_code}")
            print(f"  Known issues at cycles: {known_cycles}")
            
            # Collect all detected anomalies
            detected = set()
            for key in results[vah_code]:
                if key in ['vah_code', 'total_cycles']:
                    continue
                if key == 'data_gaps':
                    detected.update([c for c, _ in results[vah_code][key]])
                else:
                    detected.update(results[vah_code][key])
            
            detected_known = detected.intersection(set(known_cycles))
            missed = set(known_cycles) - detected
            
            if detected_known:
                print(f"  ✓ Detected: {sorted(detected_known)}")
            if missed:
                print(f"  ✗ Missed: {sorted(missed)}")


def main():
    """Main execution function"""
    detector = BatteryAnomalyDetector()
    
    # Analyze all cells
    all_results = detector.analyze_all_cells()
    
    # Export results
    detector.export_anomalies_to_csv(all_results, 'battery_anomalies.csv')
    
    # Compare with known issues
    detector.compare_with_readme_issues(all_results)


if __name__ == "__main__":
    main()