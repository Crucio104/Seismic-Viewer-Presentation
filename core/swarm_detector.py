import logging
import pandas as pd
import numpy as np
from typing import Any

logger = logging.getLogger(__name__)

def detect_ingv_swarms(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Detect seismic swarms according to official INGV definition:
    1) >= 4 events in 30 minutes (all with Md >= 0.0 and at least 1 event with Md >= 1.5)
    2) >= 10 events in 1 hour (all with Md >= 0.0 and at least 1 event with Md >= 1.0)
    
    Overlapping and contiguous time windows meeting either criteria are merged into
    a single continuous swarm.
    
    Returns a list of dictionary metadata for each detected swarm, with indices
    pointing to the chronological positions in df.
    """
    if df.empty or 'time_dt' not in df.columns or 'mag' not in df.columns:
        return []

    # Ensure chronological order with clean sequential index matching visual arrays
    if not df['time_dt'].is_monotonic_increasing:
        sorted_df = df.sort_values('time_dt').reset_index(drop=True)
    else:
        sorted_df = df.reset_index(drop=True)
    
    # Filter events with magnitude >= 0.0
    valid_mask = (sorted_df['mag'] >= 0.0).to_numpy()
    valid_indices = np.where(valid_mask)[0]
    
    if len(valid_indices) < 4:
        return []

    valid_df = sorted_df.iloc[valid_indices].reset_index(drop=True)
    times = valid_df['time_dt'].to_numpy()
    mags = valid_df['mag'].to_numpy(dtype=float, copy=False)

    windows: list[tuple[np.datetime64, np.datetime64, int, int]] = []
    n = len(valid_df)
    
    delta_30m = np.timedelta64(30, 'm')
    delta_60m = np.timedelta64(60, 'm')

    # Vectorized window boundary calculations in C
    ends_30 = np.searchsorted(times, times + delta_30m, side='right')
    ends_60 = np.searchsorted(times, times + delta_60m, side='right')
    counts_30 = ends_30 - np.arange(n)
    counts_60 = ends_60 - np.arange(n)

    # Filter only indices that satisfy candidate count thresholds
    cand_30 = np.where(counts_30 >= 4)[0]
    for i in cand_30:
        idx_30 = ends_30[i]
        if np.max(mags[i:idx_30]) >= 1.5:
            windows.append((times[i], times[idx_30 - 1], i, idx_30 - 1))

    cand_60 = np.where(counts_60 >= 10)[0]
    for i in cand_60:
        idx_60 = ends_60[i]
        if np.max(mags[i:idx_60]) >= 1.0:
            windows.append((times[i], times[idx_60 - 1], i, idx_60 - 1))

    if not windows:
        return []

    # Merge overlapping or contiguous time windows
    windows.sort(key=lambda w: w[0])
    merged: list[tuple[np.datetime64, np.datetime64, int, int]] = []
    
    curr_start, curr_end, curr_i, curr_j = windows[0]
    for s, e, i_idx, j_idx in windows[1:]:
        if s <= curr_end:  # Overlaps or touches
            curr_end = max(curr_end, e)
            curr_j = max(curr_j, j_idx)
        else:
            merged.append((curr_start, curr_end, curr_i, curr_j))
            curr_start, curr_end, curr_i, curr_j = s, e, i_idx, j_idx
    merged.append((curr_start, curr_end, curr_i, curr_j))

    swarms: list[dict[str, Any]] = []
    for swarm_id, (s_time, e_time, i_idx, j_idx) in enumerate(merged, start=1):
        dataset_indices = valid_indices[i_idx:j_idx + 1].tolist()
        slice_mags = mags[i_idx:j_idx + 1]
        
        start_str = pd.Timestamp(s_time).strftime('%Y-%m-%d %H:%M:%S')
        end_str = pd.Timestamp(e_time).strftime('%Y-%m-%d %H:%M:%S')
        event_times = [pd.Timestamp(t).strftime('%Y-%m-%d %H:%M:%S') for t in times[i_idx:j_idx + 1]]
        
        swarms.append({
            'id': swarm_id,
            'start_time': start_str,
            'end_time': end_str,
            'event_count': len(dataset_indices),
            'max_mag': float(np.max(slice_mags)),
            'min_mag': float(np.min(slice_mags)),
            'indices': dataset_indices,
            'times': event_times,
            'mags': [float(m) for m in slice_mags],
        })

    logger.info(f"Detected {len(swarms)} INGV seismic swarms.")
    return swarms
