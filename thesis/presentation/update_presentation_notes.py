import pptx

SPEECH_NOTES_INFORMAL_ACADEMIC = [
    # SLIDE 1
    """[SLIDE 1 | TIME: 0:00 - 0:35 | TARGET: 35 SECONDS]

SPEECH (EN):
"Good morning everyone, Professor Avola, and Dr. Bailo.
My name is Alessio Curcio, and today I am pleased to present my internship project titled:
'Seismic Viewer: Design, Implementation and Evaluation of an Interactive 4D Spatio-Temporal Visualisation System for Seismological Data'.

This work was carried out during my curricular internship at the National Institute of Geophysics and Volcanology (INGV), in collaboration with Sapienza University of Rome."

[VISUAL ACTION: Stand upright, smile, make warm eye contact with the Committee, project confidence]""",

    # SLIDE 2
    """[SLIDE 2 | TIME: 0:35 - 1:20 | TARGET: 45 SECONDS]

SPEECH (EN):
"To understand the motivation behind this project, we look at the ongoing volcanic unrest at the Campi Flegrei caldera near Naples.
Since 2005, continuous ground uplift accompanied by dense earthquake swarms has required continuous, multi-parametric spatial monitoring.

Furthermore, recent research published in 2025 in Nature Communications Earth & Environment by Giordano, Alfonsi and colleagues demonstrated that hypocentres delineate growing planar faults rather than diffuse, isotropic clusters.

To support this research, geophysicists at INGV required an interactive desktop tool capable of bridging raw earthquake catalogues, subsurface tomography models, and automated fault plane extraction in a single, responsive environment."

[VISUAL ACTION: Point to Campi Flegrei context on Card 1, highlight the 2025 Nature study on Card 2, then point to Card 3]""",

    # SLIDE 3
    """[SLIDE 3 | TIME: 1:20 - 2:00 | TARGET: 40 SECONDS]

SPEECH (EN):
"When analyzing existing seismological software, we observed a clear gap across existing tools:

General GIS platforms like QGIS and ArcGIS excel at 2D cartography, but their 2D projection bias flattens the critical depth dimension, their 3D views suffer frame drops under dense hypocentral clouds, and they lack 4D time playback.
Scientific scripting packages like ObsPy and GMT produce publication-ready static figures, but they operate in batch mode without graphical interaction, require continuous command-line scripting, and isolate data processing from visualization.

Seismic Viewer bridges this gap: delivering hardware-accelerated WebGL 3D/4D rendering, automated RANSAC-SVD fault plane extraction, and a standalone application that runs smoothly without complex GIS installations."

[VISUAL ACTION: Walk across the three columns on Slide 3: GIS, Scientific Code, and Seismic Viewer]""",

    # SLIDE 4
    """[SLIDE 4 | TIME: 2:00 - 2:45 | TARGET: 45 SECONDS]

SPEECH (EN):
"To guide development, we established core specifications.
Functionally, the system provides multi-modal 2D, 3D, and 4D navigation, automated fault plane extraction, multi-layer geophysical fusion of tomography and GNSS uplift, and dual ingestion via INGV APIs and local CSV files.
Non-functionally, it ensures real-time rendering, sub-second recalculation, robust sanitisation of corrupted depths, and a bounded memory footprint strictly below 500 megabytes.

Following an iterative workflow with INGV and Roma Tre researchers, development progressed through six phases: from early 3D prototypes and K-Means in Phases 1 and 2, to INGV API integration in Phase 3, DBSCAN auto-tuning and cylinder grid slicing in Phase 4, geophysical layer fusion in Phase 5, and high-throughput Float32 binary streaming in Phase 6."

[VISUAL ACTION: Point to Functional and Non-Functional Requirements on Card 1, then follow the 6-Phase Timeline on the right]""",

    # SLIDE 5
    """[SLIDE 5 | TIME: 2:45 - 3:25 | TARGET: 40 SECONDS]

SPEECH (EN):
"Starting with the 2D Application Workspace:

All filtering on date range, magnitude, and focal depth runs directly in JavaScript in the browser, providing zero-latency local filtering without requiring backend server requests.
Earthquakes are projected over OpenStreetMap tiles. Users can toggle between proportional scatter markers—where radius scales with magnitude and colour maps to depth—and continuous kernel density heatmaps to quickly identify spatial swarm concentrations.
This allows analysts to immediately isolate dense seismic swarms across Pozzuoli and the Solfatara crater."

[VISUAL ACTION: Point to the 2D map screenshot and highlight the in-browser drawer filters]""",

    # SLIDE 6
    """[SLIDE 6 | TIME: 3:25 - 4:05 | TARGET: 40 SECONDS]

SPEECH (EN):
"Switching to the 3D Workspace, hypocentres are rendered in physical space via WebGL.

To ensure genuine geological accuracy rather than arbitrary scaling, the system incorporates three design principles:
First, True Depth Scaling: events are positioned in true physical kilometres beneath an OpenStreetMap surface tile mesh.
Second, an Aspect Ratio Correction that compensates for meridional convergence using an auto-equatorial factor and the mean catalogue latitude.
And third, Stateful Camera Retention: the user's camera viewpoint and orientation are strictly preserved across filter updates using Plotly's uirevision property, supported by instant preset cardinal views."

[VISUAL ACTION: Highlight True Depth Scaling beneath the OSM terrain mesh, Aspect Ratio Correction, and camera state retention]""",

    # SLIDE 7
    """[SLIDE 7 | TIME: 4:05 - 4:45 | TARGET: 40 SECONDS]

SPEECH (EN):
"Because earthquake sequences migrate through time, the 4D Temporal Engine provides dynamic sequence slicing across three analytical playback modes:
An Accumulation Mode, tracking cumulative seismic buildup from the initial event to monitor stress release;
A Sliding Window Mode, moving a defined temporal window to isolate active hypocentral migration fronts;
And a Discrete Block Mode, partitioning the timeline into non-overlapping chronological chunks for comparative analysis.
At the bottom, an interactive timeline histogram couples chronological navigation with real-time tracking of active event counts, peak magnitude, and cumulative seismic energy release."

[VISUAL ACTION: Point to the three temporal modes on Card 1 and the interactive timeline and energy meter at the bottom]""",

    # SLIDE 8
    """[SLIDE 8 | TIME: 4:45 - 5:30 | TARGET: 45 SECONDS]

SPEECH (EN):
"To provide geological context, Seismic Viewer co-registers multiple auxiliary geophysical layers directly within the 3D scene.

First, 3D Vp/Vs Seismic Tomography: raw velocity ratios are interpolated onto a regular volumetric grid using 3D Inverse Distance Weighting, with Gaussian decay smoothly blending toward the regional crustal baseline of 1.75 outside surveyed points.
Second, GNSS Ground Uplift Columns: vertical deformation vectors from continuous GPS stations are rendered directly on the surface, correlating ground swelling with underlying seismic swarms.
Combined with surface seismic station markers, this enables direct spatial correlation between deep magmatic-hydrothermal fluid pockets and surface bradyseism."

[VISUAL ACTION: Point to the 3D tomography mesh, the GNSS ground uplift columns, and the surface monitoring stations]""",

    # SLIDE 9
    """[SLIDE 9 | TIME: 5:30 - 6:15 | TARGET: 45 SECONDS]

SPEECH (EN):
"To automatically detect geological fault structures, the analytical engine integrates three complementary clustering paradigms:

DBSCAN was chosen because it detects arbitrary, non-planar fault geometries without requiring a predefined cluster count, while isolating background noise as label minus one. We automated radius tuning by estimating epsilon from the k-nearest-neighbour knee using the Kneedle algorithm.
MiniBatchKMeans provides instant parameter slider response for large datasets by sampling mini-batches of 1024 points, adapted with a maximum distance cutoff to filter forced outliers.
Cylinder Grid partitioning divides the volume into regular vertical cylinders of 0.5-kilometre radius, breaking complex regional structures into planar segments.
Finally, a Hierarchical Sub-Clustering and Lock mechanism allows researchers to freeze confirmed geological faults and re-cluster only unresolved swarms with refined parameters."

[VISUAL ACTION: Walk through DBSCAN with knee tuning, MiniBatchKMeans with distance cutoff, Cylinder Grid, and the Cluster Lock mechanism]""",

    # SLIDE 10
    """[SLIDE 10 | TIME: 6:15 - 7:00 | TARGET: 45 SECONDS]

SPEECH (EN):
"From clustered hypocentres, the system mathematically reconstructs 3D fault planes through a two-step pipeline.

Step 1 runs RANSAC over 100 iterations, sampling random point triplets to extract candidate planes and eliminate diffuse, non-planar outliers.
Step 2 applies Singular Value Decomposition to the centered inlier coordinates. The fault plane normal vector is derived directly from the eigenvector corresponding to the smallest singular value.
From this normal, the engine calculates the geological Strike, Dip, and Planarity score, rendering interactive 3D rectangular plane meshes that display exact strike and dip vectors on hover."

[VISUAL ACTION: Walk through Step 1 (RANSAC triplet sampling), Step 2 (SVD eigenvector extraction), and hover vector displays]""",

    # SLIDE 11
    """[SLIDE 11 | TIME: 7:00 - 7:45 | TARGET: 45 SECONDS]

SPEECH (EN):
"To ensure structural and visual stability during 4D temporal animations, we introduced two key innovations:

First, Why Cylinder Partitioning? Caldera ring faults curve across the volcano and cannot be fitted by a single global plane. We replicated the spatial methodology of Giordano and Alfonsi to isolate locally planar fault segments, which also allowed us to validate our automated fitting directly against their published findings.
Second, Global Label Matching: standard clustering reassigns arbitrary labels between sequential time steps, causing chaotic colour flickering. Our algorithm takes stochastic samples from the current frame and performs spatial majority voting against the previous frame, ensuring consistent cluster identities and colours throughout playback.
Furthermore, a multithreaded ThreadPool with eight workers calculates these cylinder planes in parallel across animation frames."

[VISUAL ACTION: Explain why cylinder partitioning was chosen on Card 1, and how Global Label Matching eliminates colour flickering on Card 2]""",

    # SLIDE 12
    """[SLIDE 12 | TIME: 7:45 - 8:30 | TARGET: 45 SECONDS]

SPEECH (EN):
"Looking at the data engineering pipeline:

Stages 1 and 2 handle multi-source loading via dynamic CSV header alias detection and segmented yearly queries to the INGV GOSSIP API.
A critical design decision was Sentinel Depth Handling: earthquakes with missing focal depths are retained in 2D views for complete catalogue reporting, but strictly excluded from 3D views and clustering to prevent artificial horizontal planes at sea level.
Stages 3 and 4 enforce physical bounds checks between minus 10 and 800 kilometres, while standardizing all UTM Zone 33N tomography coordinates to WGS84 so all layers overlap with geographic precision.
Finally, in Stage 5, we replaced bulky JSON payloads with a Float32 contiguous binary streaming protocol. Packing coordinates into binary buffers reduced payload size by 80% and slashed browser decode time from nearly 40 milliseconds to under 0.01 milliseconds."

[VISUAL ACTION: Trace through Stage 1 to 5, emphasizing Sentinel Depth handling and the Float32 contiguous binary protocol]""",

    # SLIDE 13
    """[SLIDE 13 | TIME: 8:30 - 9:15 | TARGET: 45 SECONDS]

SPEECH (EN):
"We evaluated the system through extensive benchmarks across accuracy, throughput, and memory scaling:

In Synthetic Monte Carlo Validation across 500 independent trials under Gaussian noise up to 100 metres and 30% random outlier contamination, our RANSAC-SVD pipeline achieved a Mean Absolute Error under 0.51 degrees for Dip, and under 0.93 degrees for Strike.
In Real Catalogue Testing on 3,225 INGV earthquakes from Campi Flegrei, complete clustering and plane extraction executed in under 42 milliseconds.
Stress testing up to 50,000 synthetic hypocentres maintained a fluid 55 to 60 frames per second, with cylinder grid partitioning executing in just 36.5 milliseconds.
And memory benchmarks confirmed that binary buffer streaming and FIFO caching hold RAM strictly below 500 megabytes."

[VISUAL ACTION: Highlight the Monte Carlo MAE (<0.51° Dip, <0.93° Strike), real catalogue 42 ms speed, and 50,000-event stress test at 55–60 FPS]""",

    # SLIDE 14
    """[SLIDE 14 | TIME: 9:15 - 9:40 | TARGET: 25 SECONDS]

SPEECH (EN):
"To conclude, Seismic Viewer delivers a lightweight, responsive desktop system that combines 4D spatio-temporal visualization, automated structural plane fitting, and a high-throughput binary pipeline validated in collaboration with INGV researchers.

Looking forward, future work will target real-time WebSocket and SeedLink streaming for active surveillance rooms, transitioning the graphics engine to WebGPU or Deck.gl for zero-install cloud deployment, and integrating 3D focal mechanism overlays to directly display fault slip directions.

Thank you very much for your attention. I am happy to answer any questions."

[VISUAL ACTION: Summarize the 3 validated contributions, mention the 3 future extensions, and open the floor for Q&A]"""
]

from pptx.dml.color import RGBColor
from pptx.util import Pt

prs = pptx.Presentation('thesis/presentation/Seismic Viewer - Thesis Defense.pptx')
assert len(prs.slides) == len(SPEECH_NOTES_INFORMAL_ACADEMIC), f"Mismatch: {len(prs.slides)} slides vs {len(SPEECH_NOTES_INFORMAL_ACADEMIC)} notes"

for i, slide in enumerate(prs.slides):
    notes_slide = slide.notes_slide
    tf = notes_slide.notes_text_frame
    tf.text = SPEECH_NOTES_INFORMAL_ACADEMIC[i]

# Also update Slide 11 Card 1 visual text
slide11 = prs.slides[10]
for sh in slide11.shapes:
    if sh.name == 'Google Shape;292;p23':
        sh.text_frame.clear()
        p = sh.text_frame.paragraphs[0]
        run = p.add_run()
        run.text = 'Replicates the methodology of Giordano & Alfonsi (2025) to isolate locally planar faults and validate our automated fitting against published results.'
        run.font.name = 'Plus Jakarta Sans'
        run.font.size = Pt(11.25)
        run.font.color.rgb = RGBColor(0x2D, 0x26, 0x28)

prs.save('thesis/presentation/Seismic Viewer - Thesis Defense.pptx')
print("Successfully injected all 14 informal-academic English notes and updated Slide 11 text into 'Seismic Viewer - Thesis Defense.pptx'!")
