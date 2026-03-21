import csv
import os

MIN_MAGNITUDE = 0.5

def load_csv(source_file):
    """Parse a seismic CSV and return extracted data arrays.

    Returns a dict with keys: latitude, longitude, depth, magnitude, times,
    and a summary dict with event_count, date_range.
    Raises ValueError if the CSV is invalid or has no qualifying events.
    """
    with open(source_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("The CSV file is empty.")

        # Basic validation: need at least 6 columns
        if len(header) < 6:
            raise ValueError(
                "The CSV must have at least 6 columns "
                "(EventID, Time, Latitude, Longitude, Depth, Magnitude)."
            )
        
        earthquakes = []
        for row in reader:
            if (len(row) > 5 and all(row[i].strip() != '' for i in [2, 3, 4, 5])):
                try:
                    if float(row[5]) >= MIN_MAGNITUDE:
                        earthquakes.append(row)
                except ValueError:
                    continue # Skip malformed rows
                    
    if not earthquakes:
        raise ValueError(
            f"No seismic events found with M ≥ {MIN_MAGNITUDE}."
        )

    # Sort by time ascending for visualization consistency
    # (Assuming column 1 is time)
    earthquakes.sort(key=lambda x: x[1])

    latitude = [float(e[2]) for e in earthquakes]
    longitude = [float(e[3]) for e in earthquakes]
    depth = [-float(e[4]) for e in earthquakes]
    magnitude = [float(e[5]) for e in earthquakes]
    times = [e[1] for e in earthquakes]

    # Date range from first to last (after sorting)
    date_range = f"{times[0][:10]} → {times[-1][:10]}"
    print(f"Loaded {len(earthquakes)} seismic events (M ≥ {MIN_MAGNITUDE}).")

    return {
        'latitude': latitude,
        'longitude': longitude,
        'depth': depth,
        'magnitude': magnitude,
        'times': times,
        'summary': {
            'event_count': len(earthquakes),
            'date_range': date_range,
        },
    }
