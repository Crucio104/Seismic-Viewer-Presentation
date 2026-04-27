# Core package for Seismic Viewer
import multiprocessing
if multiprocessing.current_process().name == 'MainProcess':
    print("Core package imported")
