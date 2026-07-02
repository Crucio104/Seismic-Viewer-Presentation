import logging
import math
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from core.config import BASE_DIR

logger = logging.getLogger(__name__)

def utm33_to_latlon_numpy(x_km: np.ndarray | float, y_km: np.ndarray | float) -> tuple[np.ndarray | float, np.ndarray | float]:
    """
    Convert UTM Zone 33N coordinates (in km) to WGS84 Latitude and Longitude (in degrees).
    Uses standard Transverse Mercator projection equations on WGS84 ellipsoid.
    """
    x = np.asarray(x_km, dtype=np.float64) * 1000.0 - 500000.0
    y = np.asarray(y_km, dtype=np.float64) * 1000.0
    
    a = 6378137.0
    e = 0.08181919104281579
    k0 = 0.9996
    e1sq = 0.006739496742276434
    
    M = y / k0
    mu = M / (a * (1 - e**2/4 - 3*e**4/64 - 5*e**6/256))
    e1 = (1 - (1 - e**2)**0.5) / (1 + (1 - e**2)**0.5)
    
    phi1 = mu + (3*e1/2 - 27*e1**3/32)*np.sin(2*mu) + (21*e1**2/16 - 55*e1**4/32)*np.sin(4*mu) + (151*e1**3/96)*np.sin(6*mu) + (1097*e1**4/512)*np.sin(8*mu)
    
    C1 = e1sq * np.cos(phi1)**2
    T1 = np.tan(phi1)**2
    N1 = a / (1 - (e * np.sin(phi1))**2)**0.5
    R1 = a * (1 - e**2) / (1 - (e * np.sin(phi1))**2)**1.5
    D = x / (N1 * k0)
    
    lat = phi1 - (N1 * np.tan(phi1) / R1) * (
        D**2/2 - (5 + 3*T1 + 10*C1 - 4*C1**2 - 9*e1sq)*D**4/24 + 
        (61 + 90*T1 + 298*C1 + 45*T1**2 - 252*e1sq - 3*C1**2)*D**6/720
    )
    lon = np.radians(15.0) + (
        D - (1 + 2*T1 + C1)*D**3/6 + 
        (5 - 2*C1 + 28*T1 - 3*C1**2 + 8*e1sq + 24*T1**2)*D**5/120
    ) / np.cos(phi1)
    
    if isinstance(x_km, (int, float)):
        return float(np.degrees(lat)), float(np.degrees(lon))
    return np.degrees(lat), np.degrees(lon)


def process_tomography_data(csv_path: str | Path) -> dict[str, Any]:
    """Read tomography CSV, convert UTM coordinates, and extract Vp/Vs ratio."""
    try:
        path = Path(csv_path)
        if not path.exists():
            return {'error': f"File non trovato: {csv_path}"}
        
        # Try reading with semicolon or comma
        try:
            df = pd.read_csv(path, sep=';', encoding='utf-8', engine='python')
            if len(df.columns) <= 1:
                df = pd.read_csv(path, sep=',', encoding='utf-8', engine='python')
        except Exception:
            df = pd.read_csv(path, sep=None, engine='python')
            
        # Clean column names
        df.columns = [c.strip().upper() for c in df.columns]
        
        # Find required columns
        utmx_col = next((c for c in df.columns if 'UTMX' in c or 'X' == c), None)
        utmy_col = next((c for c in df.columns if 'UTMY' in c or 'Y' == c), None)
        utmz_col = next((c for c in df.columns if 'UTMZ' in c or 'Z' == c or 'DEPTH' in c), None)
        vpvs_col = next((c for c in df.columns if 'VP/VS' in c or 'VPXVS' in c or 'VPVS' in c or 'VP_VS' in c), None)
        
        if not all([utmx_col, utmy_col, utmz_col, vpvs_col]):
            return {'error': f"Colonne mancanti nel CSV di tomografia. Trovate: {list(df.columns)}"}
            
        # Drop NaN or invalid rows
        df = df.dropna(subset=[utmx_col, utmy_col, utmz_col, vpvs_col]).reset_index(drop=True)
        
        # Escludi le celle di background non calibrate (dove VP == 0)
        vp_col = next((c for c in df.columns if c == 'VP' or 'V_P' in c or 'P_VEL' in c), None)
        if vp_col:
            df = df[df[vp_col] != 0].reset_index(drop=True)
            
        # Rimuovi i nodi della griglia che non sono stati perturbati dall'inversione (dove Vp/Vs è rimasto esattamente 1.750)
        df = df[~np.isclose(df[vpvs_col].astype(float), 1.75, atol=1e-5)].reset_index(drop=True)
        
        # Convert UTM Zone 33N km to Lat/Lon
        lats, lons = utm33_to_latlon_numpy(df[utmx_col].values, df[utmy_col].values)
        
        # In our 3D plot, Z is depth in km (positive downwards is represented as negative Z coordinates in 3D space)
        depths = -np.abs(df[utmz_col].values.astype(float))
        vp_vs = df[vpvs_col].values.astype(float)
        
        logger.info(f"Elaborati {len(df)} punti di tomografia da {path.name}")
        
        hover_texts = [f"Vp/Vs: {val:.3f}<br>Profondità: {abs(dep):.2f} km" for val, dep in zip(vp_vs, depths)]
        
        return {
            'status': 'success',
            'type': 'tomography',
            'filename': path.name,
            'count': len(df),
            'x': lons.tolist(),
            'y': lats.tolist(),
            'z': depths.tolist(),
            'lons': lons.tolist(),
            'lats': lats.tolist(),
            'depths': depths.tolist(),
            'vp_vs': vp_vs.tolist(),
            'hover': hover_texts,
            'min_vp_vs': float(np.min(vp_vs)),
            'max_vp_vs': float(np.max(vp_vs))
        }
    except Exception as e:
        logger.error(f"Errore durante l'elaborazione della tomografia: {e}", exc_info=True)
        return {'error': f"Errore elaborazione tomografia: {str(e)}"}


def process_uplift_data(csv_path: str | Path, target_date_str: str | None = None, stations_path: str | Path | None = None) -> dict[str, Any]:
    """Read GNSS uplift CSV, match station coordinates, and extract latest/closest uplift values."""
    try:
        path = Path(csv_path)
        if not path.exists():
            return {'error': f"File non trovato: {csv_path}"}
            
        try:
            df = pd.read_csv(path, sep=';', encoding='utf-8', engine='python')
            if len(df.columns) <= 1:
                df = pd.read_csv(path, sep=',', encoding='utf-8', engine='python')
        except Exception:
            df = pd.read_csv(path, sep=None, engine='python')
            
        df.columns = [c.strip().lower() for c in df.columns]
        
        station_col = next((c for c in df.columns if 'station' in c or 'staz' in c or 'id' == c), None)
        up_col = next((c for c in df.columns if 'up_m' in c or 'up' == c or 'height' in c or 'quota' in c), None)
        date_col = next((c for c in df.columns if 'date' in c or 'data' in c or 'time' in c), None)
        
        if not station_col or not up_col:
            return {'error': f"Colonne 'station' o 'up_m' mancanti nel CSV uplift. Trovate: {list(df.columns)}"}
            
        # Parse dates if date column exists
        if date_col:
            df['parsed_date'] = pd.to_datetime(df[date_col], format='%d/%m/%Y', errors='coerce')
            if df['parsed_date'].isna().all():
                df['parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')
        
        # Load station coordinates mapping
        coord_map = _load_station_coordinates(path.parent, stations_path=stations_path)
        if not coord_map:
            return {'error': "Impossibile trovare le coordinate delle stazioni (flegrei_station_coordinates.csv)"}
            
        # Filter stations present in coordinate map
        df = df[df[station_col].str.upper().isin(coord_map.keys())].copy()
        if len(df) == 0:
            return {'error': "Nessuna stazione nel file corrisponde a quelle nel file di coordinate."}
            
        stations = []
        lons = []
        lats = []
        up_m_list = []
        dates_used = []
        
        # Group by station to find latest or target date
        for st_name, group in df.groupby(station_col):
            st_name = str(st_name).strip().upper()
            if st_name not in coord_map:
                continue
            lat, lon = coord_map[st_name]
            
            if date_col and 'parsed_date' in group.columns and not group['parsed_date'].isna().all():
                valid_group = group.dropna(subset=['parsed_date'])
                if target_date_str:
                    try:
                        t_date = pd.to_datetime(target_date_str)
                        idx = (valid_group['parsed_date'] - t_date).abs().idxmin()
                        row = valid_group.loc[idx]
                    except Exception:
                        row = valid_group.sort_values('parsed_date').iloc[-1]
                else:
                    row = valid_group.sort_values('parsed_date').iloc[-1]
                dt_str = row['parsed_date'].strftime('%Y-%m-%d')
            else:
                row = group.iloc[-1]
                dt_str = str(row[date_col]) if date_col in row else "Latest"
                
            up_val = float(row[up_col])
            
            stations.append(st_name)
            lons.append(lon)
            lats.append(lat)
            up_m_list.append(up_val)
            dates_used.append(dt_str)
            
        # Visual scaling factor: scale uplift meters so that columns rise cleanly above z=0 plane
        # Since differences between stations can be just a few millimeters, we scale the variation
        # dynamically between 0.3 km and 2.5 km in visual Z space so differences are clearly legible.
        min_up = min(up_m_list) if up_m_list else 0.0
        max_up = max(up_m_list) if up_m_list else 0.0
        
        if max_up - min_up < 1e-6:
            z_scaled = [1.0 for _ in up_m_list]
        else:
            z_scaled = [0.3 + ((v - min_up) / (max_up - min_up)) * 2.2 for v in up_m_list]
        
        lines_x = []
        lines_y = []
        lines_z = []
        lines_hover = []
        for st, lon, lat, z_val, up_val, dt in zip(stations, lons, lats, z_scaled, up_m_list, dates_used):
            txt = f"Stazione: {st}<br>Uplift reale: {up_val * 1000:.1f} mm ({up_val:.4f} m)<br>Data: {dt}"
            lines_x.extend([lon, lon, None])
            lines_y.extend([lat, lat, None])
            lines_z.extend([0.0, z_val, None])
            lines_hover.extend([txt, txt, None])
        
        logger.info(f"Elaborate {len(stations)} stazioni GNSS di uplift da {path.name}")
        
        return {
            'status': 'success',
            'type': 'uplift',
            'filename': path.name,
            'count': len(stations),
            'stations': stations,
            'lons': lons,
            'lats': lats,
            'up_m': up_m_list,
            'z_scaled': z_scaled,
            'dates': dates_used,
            'lines': {
                'x': lines_x,
                'y': lines_y,
                'z': lines_z,
                'hover': lines_hover
            },
            'surface': {
                'x': lons,
                'y': lats,
                'z': z_scaled
            }
        }
    except Exception as e:
        logger.error(f"Errore durante l'elaborazione dell'uplift: {e}", exc_info=True)
        return {'error': f"Errore elaborazione uplift: {str(e)}"}


def _load_station_coordinates(search_dir: Path, stations_path: str | Path | None = None) -> dict[str, tuple[float, float]]:
    """Locate and load flegrei_station_coordinates.csv into {station: (lat, lon)}."""
    candidates = []
    if stations_path:
        p = Path(stations_path)
        if p.exists():
            candidates.append(p)
    candidates.extend([
        search_dir / 'flegrei_station_coordinates.csv',
        BASE_DIR / 'Dati_tomografia' / 'flegrei_station_coordinates.csv',
        BASE_DIR / 'flegrei_station_coordinates.csv'
    ])
    
    coord_file = next((f for f in candidates if f.exists()), None)
    if not coord_file:
        logger.warning("flegrei_station_coordinates.csv non trovato nei percorsi standard.")
        return {}
        
    try:
        df = pd.read_csv(coord_file, sep=';', encoding='utf-8', engine='python')
        if len(df.columns) <= 1:
            df = pd.read_csv(coord_file, sep=',', encoding='utf-8', engine='python')
        df.columns = [c.strip().lower() for c in df.columns]
        
        st_col = next((c for c in df.columns if 'station' in c or 'staz' in c), None)
        lat_col = next((c for c in df.columns if 'lat' in c), None)
        lon_col = next((c for c in df.columns if 'lon' in c), None)
        
        if not all([st_col, lat_col, lon_col]):
            return {}
            
        coord_map = {}
        for _, row in df.iterrows():
            st = str(row[st_col]).strip().upper()
            coord_map[st] = (float(row[lat_col]), float(row[lon_col]))
            
        return coord_map
    except Exception as e:
        logger.error(f"Errore lettura file coordinate stazioni: {e}")
        return {}


def process_stations_data(stations_path: str | Path) -> dict[str, Any]:
    """Load station coordinates and format them for visualization."""
    try:
        p = Path(stations_path)
        coord_map = _load_station_coordinates(p.parent if p.exists() else BASE_DIR, stations_path=stations_path)
        if not coord_map:
            return {'error': 'No station coordinates found in file.'}
        
        names = []
        lats = []
        lons = []
        hover_texts = []
        for name, (lat, lon) in coord_map.items():
            names.append(name)
            lats.append(lat)
            lons.append(lon)
            hover_texts.append(f"<b>Station: {name}</b><br>Lat: {lat:.5f}°<br>Lon: {lon:.5f}°")
            
        return {
            'names': names,
            'lats': lats,
            'lons': lons,
            'hover': hover_texts,
            'count': len(names)
        }
    except Exception as e:
        logger.error(f"Error processing station data: {e}", exc_info=True)
        return {'error': f"Error processing stations: {str(e)}"}
