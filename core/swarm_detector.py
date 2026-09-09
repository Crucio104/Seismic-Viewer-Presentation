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
    times = valid_df['time_dt'].values
    mags = valid_df['mag'].values

    windows: list[tuple[np.datetime64, np.datetime64, int, int]] = []
    n = len(valid_df)
    
    delta_30m = np.timedelta64(30, 'm')
    delta_60m = np.timedelta64(60, 'm')

    for i in range(n):
        t0 = times[i]
        
        # Rule 1: 30 minutes window (>= 4 events, at least one >= 1.5)
        t_end_30 = t0 + delta_30m
        idx_30 = int(np.searchsorted(times, t_end_30, side='right'))
        count_30 = idx_30 - i
        if count_30 >= 4:
            if np.max(mags[i:idx_30]) >= 1.5:
                windows.append((times[i], times[idx_30 - 1], i, idx_30 - 1))

        # Rule 2: 60 minutes window (>= 10 events, at least one >= 1.0)
        t_end_60 = t0 + delta_60m
        idx_60 = int(np.searchsorted(times, t_end_60, side='right'))
        count_60 = idx_60 - i
        if count_60 >= 10:
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
            if e > curr_end:
                curr_end = e
            if j_idx > curr_j:
                curr_j = j_idx
        else:
            merged.append((curr_start, curr_end, curr_i, curr_j))
            curr_start, curr_end, curr_i, curr_j = s, e, i_idx, j_idx
    merged.append((curr_start, curr_end, curr_i, curr_j))

    swarms: list[dict[str, Any]] = []
    for swarm_id, (s_time, e_time, i_idx, j_idx) in enumerate(merged, start=1):
        swarm_events = valid_df.iloc[i_idx:j_idx + 1]
        dataset_indices = valid_indices[i_idx:j_idx + 1].tolist()
        
        start_str = pd.Timestamp(s_time).strftime('%Y-%m-%d %H:%M:%S')
        end_str = pd.Timestamp(e_time).strftime('%Y-%m-%d %H:%M:%S')
        event_times = [pd.Timestamp(t).strftime('%Y-%m-%d %H:%M:%S') for t in swarm_events['time_dt']]
        
        swarms.append({
            'id': swarm_id,
            'start_time': start_str,
            'end_time': end_str,
            'event_count': len(dataset_indices),
            'max_mag': float(swarm_events['mag'].max()),
            'min_mag': float(swarm_events['mag'].min()),
            'indices': dataset_indices,
            'times': event_times,
            'mags': [float(m) for m in swarm_events['mag']],
        })

    logger.info(f"Detected {len(swarms)} INGV seismic swarms.")
    return swarms
