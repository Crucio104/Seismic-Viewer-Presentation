# Seismic Viewer — Final Internship Defense Talk Track & Consistency Report
**Candidate**: Alessio Curcio  
**Degree**: Applied Computer Science and Artificial Intelligence (ACSAI)  
**Institution**: Sapienza University of Rome  
**Host Institution**: National Institute of Geophysics and Volcanology (INGV)  
**Supervisors**: Prof. Danilo Avola (Sapienza), Dr. Daniele Bailo (INGV)  
**Target Duration**: 9 minutes 40 seconds (Strictly ≤ 10 minutes)  
**Tone & Style**: Spoken, engaging, natural conversational-academic English (clear, direct, and accessible)  

---

## 1. Presentation Structure & 4-Part Roadmap

This presentation is organized into four core parts following the scientific, technical, and architectural narrative of the internship project:

1. **Part 1: Context, Analyzed Domain, State of the Art & Development Timeline** (Slides 1–4, ~2m 45s)
   - Scientific context: The Campi Flegrei caldera crisis, ground uplift, and the recent 2025 *Nature Communications Earth & Environment* study (*Giordano, Alfonsi et al.*) showing active fault plane nucleation.
   - Limits of current tools (2D GIS, heavy scientific 3D packages, static web portals).
   - System requirements (FR/NFR) and the **6-phase iterative implementation timeline** shaped by researcher feedback.
2. **Part 2: Current Application Features & Algorithmic Rationale** (Slides 5–11, ~5m 00s)
   - Interactive 2D workspace with zero-latency in-browser filtering, dual-layer scatter/density maps, and magnitude energy scaling.
   - 3D workspace with physical depth scaling beneath OpenStreetMap surface mesh, aspect ratio correction for meridional convergence, and stateful camera tracking.
   - 4D spatiotemporal animation engine with accumulation, sliding-window, and discrete block modes plus interactive timeline energy tracking.
   - Multi-layer geophysical co-registration: 3D $V_p/V_s$ seismic tomography with IDW Gaussian baseline blending, GNSS ground uplift with Mogi decay, and seismic station markers.
   - Clustering engine: **Why and how algorithms changed** — why K-Means failed on tectonic faults and forced noise points $\to$ why DBSCAN was adopted with automated Kneedle knee-detection $\to$ MiniBatchKMeans for rapid batch partitioning $\to$ confirmed cluster lock.
   - Mathematical fault plane fitting: **Why RANSAC was applied before SVD** to eliminate diffuse outliers, followed by centered SVD for normal vector extraction ($\vec{n}=v_3$), Strike, Dip, and planarity scoring.
   - 4D Cylinder slicing for caldera ring faults & **Global Label Matching** (stochastic spatial voting with greedy majority assignment) to stop cluster color flickering across animation frames.
3. **Part 3: Data Ingestion Pipeline & Architectural Choices** (Slide 12, ~45s)
   - Heterogeneous ingestion: online queries to the INGV GOSSIP REST API and offline CSV file parsing.
   - **Critical design decision**: Handling of missing depths — preserved in 2D views for complete catalogue reporting, but strictly excluded from 3D/4D spatial computations to prevent artificial planar artifacts at $z=0$.
   - **Float32 binary streaming protocol**: Raw contiguous binary transfer directly to client-side typed arrays, cutting network payload by ~80% and dropping parsing time from ~40 ms to $<0.01$ ms.
4. **Part 4: Results & Future Developments** (Slides 13–14, ~1m 10s)
   - Quantitative validation: 500-trial Monte Carlo synthetic fault recovery (Dip error $<0.5^\circ$, Strike error $<0.9^\circ$), real Campi Flegrei catalogue performance (clustering $<42$ ms for 3,225 events), and 50,000-event stress test at 55–60 FPS.
   - Memory bounding strictly $<500$ MB via session pooling and garbage collection.
   - Practical impact and future improvements: real-time WebSocket push notifications, WebGPU compute shaders, and automated focal mechanism tensor inversions.

---

## 2. Pacing & Time Management Table

| Slide # | Slide Title | Window (MM:SS) | Duration | Target Words | Pace (wpm) |
|:---:|:---|:---:|:---:|:---:|:---:|
| **1** | Title & Welcome | 0:00 – 0:35 | 35s | ~70 words | 120 |
| **2** | Context & Motivation (Campi Flegrei & 2025 Nature Study) | 0:35 – 1:20 | 45s | ~105 words | 135 |
| **3** | State of Current Tools & Visualisation Gap | 1:20 – 2:00 | 40s | ~90 words | 135 |
| **4** | Requirements & Iterative Implementation Timeline | 2:00 – 2:45 | 45s | ~110 words | 145 |
| **5** | 2D Workspace & In-Browser Filtering | 2:45 – 3:25 | 40s | ~85 words | 130 |
| **6** | 3D Workspace & Physical Depth Scaling | 3:25 – 4:05 | 40s | ~85 words | 130 |
| **7** | 4D Dynamic Migration & Temporal Playback | 4:05 – 4:45 | 40s | ~90 words | 135 |
| **8** | Multi-Layer Geophysics (Tomography, Uplift & Stations) | 4:45 – 5:30 | 45s | ~100 words | 135 |
| **9** | Clustering Engine: Algorithmic Evolution & Rationale | 5:30 – 6:15 | 45s | ~110 words | 145 |
| **10** | Structural Geology & Fault Plane Fitting (RANSAC + SVD) | 6:15 – 7:00 | 45s | ~105 words | 140 |
| **11** | 4D Cylinder Slicing & Global Label Matching | 7:00 – 7:45 | 45s | ~100 words | 135 |
| **12** | Data Pipeline, Missing Depths & Float32 Streaming | 7:45 – 8:30 | 45s | ~105 words | 140 |
| **13** | Quantitative Validation & Benchmarks | 8:30 – 9:15 | 45s | ~100 words | 135 |
| **14** | Conclusions & Future Work | 9:15 – 9:40 | 25s | ~65 words | 140 |
| **Total** | **Complete Defense Presentation** | **0:00 – 9:40** | **9m 40s** | **~1,260 words** | **~130 wpm** |

> **Safety Margin**: A comfortable **20-second safety buffer** remains before the strict 10:00 cutoff. The language is conversational and spoken, designed to sound natural when delivered aloud without tongue-twisters.

---

## 3. Word-for-Word Spoken Defense Script (Slightly Informal, Natural Spoken English)

### Slide 1: Title & Welcome
* **Elapsed Time**: `[0:00 – 0:35]` (35 seconds)
* **Visual Action**: Stand upright, smile, make warm eye contact with the Committee, project confidence.

> "Hello everyone my name is Alessio Curcio, and today I am going to present my internship project titled:  
> **'Seismic Viewer: Design, Implementation and Evaluation of an Interactive 4D Spatio-Temporal Visualisation System for Seismological Data'**.  
> 
> This work was carried out during my internship at the National Institute of Geophysics and Volcanology"

---

### Slide 2: Context & Research Motivation
* **Elapsed Time**: `[0:35 – 1:20]` (45 seconds)
* **Visual Action**: Point to the Campi Flegrei context on Card 1, highlight the 2025 Nature study on Card 2, then point to Card 3.

> "To understand the motivation behind this project, we look at the ongoing volcanic unrest at the Campi Flegrei caldera near Naples.  
> Since 2005, continuous ground uplift accompanied by dense earthquake swarms has required continuous, multi-parametric spatial monitoring.  
> 
> Furthermore, recent research published in 2025 in *Nature Communications Earth & Environment* by Giordano, Alfonsi and colleagues demonstrated that hypocentres delineate growing planar faults rather than diffuse, isotropic clusters.  
> 
> To support this research, geophysicists at INGV required an interactive desktop tool capable of bridging raw earthquake catalogues with tomography models, clustering dense earthquake swarms to isolate active structures, and automatically extracting fault planes in a single, responsive environment.
---

### Slide 3: State of the Art & Tooling Comparison
* **Elapsed Time**: `[1:20 – 2:00]` (40 seconds)
* **Visual Action**: Walk across the three columns on Slide 3: GIS, Scientific Code, and Seismic Viewer.

> "When analyzing existing seismological software, we observed a clear gap across existing tools:  
> 
> General GIS platforms like QGIS and ArcGIS excel at 2D cartography, but their 2D projection bias flattens the critical depth dimension, their 3D views suffer frame drops under dense hypocentral clouds, and they lack 4D time playback.  
> Scientific scripting packages like ObsPy and GMT produce publication-ready static figures, but they operate in batch mode without graphical interaction, require continuous command-line scripting, and isolate data processing from visualization.  
> 
> Seismic Viewer bridges this gap: delivering hardware-accelerated WebGL 3D/4D rendering, automated RANSAC-SVD fault plane extraction, and a standalone application that runs smoothly without complex GIS installations."

---

### Slide 4: Requirements & Iterative Implementation Timeline
* **Elapsed Time**: `[2:00 – 2:45]` (45 seconds)
* **Visual Action**: Point to Functional and Non-Functional Requirements on Card 1, then follow the 6-Phase Timeline on the right.

> "To guide development, we established core specifications.  
> Functionally, the system provides multi-modal 2D, 3D, and 4D navigation, automated fault plane extraction, multi-layer geophysical fusion of tomography and GNSS uplift, and dual ingestion via INGV APIs and local CSV files.  
> Non-functionally, it ensures real-time rendering, sub-second recalculation, robust sanitisation of corrupted depths, and a bounded memory footprint.  
> 
> Following an iterative workflow with INGV and Roma Tre researchers, development progressed through six phases: from early 3D prototypes and K-Means in Phases 1 and 2, to INGV API integration in Phase 3, DBSCAN auto-tuning and cylinder grid slicing in Phase 4, geophysical layer implementation in Phase 5, and high-throughput Float32 binary streaming in Phase 6."

---

### Slide 5: 2D Application Workspace & In-Browser Filtering
* **Elapsed Time**: `[2:45 – 3:25]` (40 seconds)
* **Visual Action**: Point to the 2D map screenshot and highlight the in-browser drawer filters.

> "Starting with the 2D Application Workspace:  
> 
> All filters on date range, magnitude, and focal depth runs directly in JavaScript in the browser, providing zero-latency local filtering without requiring backend server requests.  
> Earthquakes are projected over OpenStreetMap tiles. Users can toggle between proportional scatter markers—where radius scales with magnitude—and continuous kernel density heatmaps to quickly identify spatial swarm concentrations.  
> This allows analysts to immediately isolate dense seismic swarms across Pozzuoli and the Solfatara crater."

---

### Slide 6: 3D Application Workspace & Physical Depth Scaling
* **Elapsed Time**: `[3:25 – 4:05]` (40 seconds)
* **Visual Action**: Highlight True Depth Scaling beneath the OSM terrain mesh, Aspect Ratio Correction, and camera state retention.

> "Switching to the 3D Workspace, hypocentres are rendered in physical space via WebGL.  
> 
> To ensure geological accuracy, the system incorporates three design principles:  
> First, True Depth Scaling: events are positioned in true physical kilometres beneath an OpenStreetMap surface tile mesh.  
> Second, an Aspect Ratio Correction that compensates for meridional convergence using an auto-equatorial factor and the mean catalogue latitude.  
> And third, Stateful Camera Retention: the user's camera viewpoint and orientation are strictly preserved across filter updates using Plotly's `uirevision` property."

---

### Slide 7: 4D Temporal Animation & Sequence Slicing
* **Elapsed Time**: `[4:05 – 4:45]` (40 seconds)
* **Visual Action**: Point to the three temporal modes on Card 1 and the interactive timeline and energy meter at the bottom.

> "Because earthquake sequences migrate through time, the 4D Temporal Engine provides dynamic sequence slicing across three analytical playback modes:  
> An Accumulation Mode, tracking cumulative seismic buildup from the initial event to monitor stress release;  
> A Sliding Window Mode, moving a defined temporal window to isolate active hypocentral migration fronts;  
> And a Discrete Block Mode, partitioning the timeline into chunks for comparative analysis.  
> At the bottom, an interactive timeline histogram couples chronological navigation with real-time tracking of active event counts, peak magnitude, and cumulative seismic energy release in an informative box at the top right of the screen."

---

### Slide 8: Multi-Layer Geophysics — Tomography, Uplift & Stations
* **Elapsed Time**: `[4:45 – 5:30]` (45 seconds)
* **Visual Action**: Point to the 3D tomography mesh, the GNSS ground uplift columns, and the surface monitoring stations.

> "To provide geological context, Seismic Viewer can register multiple auxiliary geophysical layers directly within the 3D scene.  
> 
> First, 3D Seismic Tomography: raw velocity ratios are interpolated onto a regular volumetric grid using 3D Inverse Distance Weighting, with Gaussian decay smoothly blending toward the regional crustal baseline of 1.75.  
> Second, GNSS Ground Uplift Columns: vertical deformation vectors from continuous GPS stations are rendered directly on the surface, correlating ground swelling with underlying seismic swarms.  
> And finally seismic station markers. These factors enable direct spatial correlation between deep magmatic-hydrothermal fluid pockets and surface bradyseism."

---

### Slide 9: Machine Learning Engine — Clustering Paradigms & Adaptation
* **Elapsed Time**: `[5:30 – 6:15]` (45 seconds)
* **Visual Action**: Walk through DBSCAN with knee tuning, MiniBatchKMeans with distance cutoff, Cylinder Grid, and the Cluster Lock mechanism.

> "To automatically detect geological fault structures, the analytical engine integrates three complementary clustering paradigms:  
> 
> DBSCAN was chosen because it detects arbitrary, non-planar fault geometries without requiring a predefined cluster count, while isolating background noise as label minus one. We automated radius tuning by estimating epsilon from the k-nearest-neighbour knee using the Kneedle algorithm.  
> MiniBatchKMeans provides instant parameter slider response for large datasets by sampling mini-batches of 1024 points, adapted with a maximum distance cutoff to filter forced outliers.  
> Cylinder Grid partitioning divides the volume into regular vertical cylinders, breaking complex regional structures into planar segments.  
> Finally, a Hierarchical Sub-Clustering and Lock mechanism allows researchers to freeze confirmed geological faults and re-cluster only unresolved swarms with refined parameters."

---

### Slide 10: Structural Geology & Fault Plane Fitting (RANSAC + SVD)
* **Elapsed Time**: `[6:15 – 7:00]` (45 seconds)
* **Visual Action**: Walk through Step 1 (RANSAC triplet sampling), Step 2 (SVD eigenvector extraction), and hover vector displays.

> "From clustered hypocentres, the system mathematically reconstructs 3D fault planes through a two-step pipeline.  
> 
> Step 1 runs RANSAC over 100 iterations, sampling random point triplets to extract candidate planes and eliminate diffuse, non-planar outliers.  
> Step 2 applies Singular Value Decomposition to the centered inlier coordinates. The fault plane normal vector is derived directly from the eigenvector corresponding to the smallest singular value.  
> From this normal, the engine calculates the geological Strike, Dip, and Planarity score, rendering interactive 3D rectangular plane meshes that display exact strike and dip vectors on hover."

---

### Slide 11: Algorithmic Innovation — 4D Cylinders & Label Stability
* **Elapsed Time**: `[7:00 – 7:45]` (45 seconds)
* **Visual Action**: Explain why cylinder partitioning was chosen on Card 1, and how Global Label Matching eliminates colour flickering on Card 2.

> "To ensure structural and visual stability during 4D temporal animations, we introduced two key innovations:  
> 
> First, Why Cylinder Partitioning? Caldera ring faults curve across the volcano and cannot be fitted by a single global plane. We replicated the spatial methodology of Giordano and Alfonsi to isolate locally planar fault segments, which also allowed us to validate our automated fitting directly against their published findings.  
> Second, Global Label Matching: standard clustering reassigns arbitrary labels between sequential time steps, causing chaotic colour flickering. Our algorithm takes stochastic samples from the current frame and performs spatial majority voting against the previous frame, ensuring consistent cluster identities and colours throughout playback.  
> Furthermore, a multithreaded ThreadPool with eight workers calculates these cylinder planes in parallel across animation frames."

---

### Slide 12: Data Engineering Pipeline & Binary Streaming
* **Elapsed Time**: `[7:45 – 8:30]` (45 seconds)
* **Visual Action**: Trace through Stage 1 to 5, emphasizing Sentinel Depth handling and the Float32 contiguous binary protocol.

> "Looking at the data engineering pipeline:  
> 
> Stages 1 and 2 handle multi-source loading via dynamic CSV header alias detection and segmented yearly queries to the INGV GOSSIP API.  
> A critical design decision was Depth Handling: earthquakes with missing focal depths are retained in 2D views for complete catalogue reporting, but strictly excluded from 3D views and clustering to prevent artificial horizontal planes at sea level.  
> Stages 3 and 4 enforce physical bounds checks between minus 10 and 800 kilometres, while standardizing all tomography coordinates to WGS84 so all layers overlap with geographic precision.  
> Finally, in Stage 5, we replaced bulky JSON payloads with a Float32 contiguous binary streaming protocol. Packing coordinates into binary buffers reduced payload size by 80% and slashed browser decode time to under 0.01 milliseconds."

---

### Slide 13: Results & Quantitative Validation Benchmarks
* **Elapsed Time**: `[8:30 – 9:15]` (45 seconds)
* **Visual Action**: Highlight the Monte Carlo MAE (<0.51° Dip, <0.93° Strike), real catalogue 42 ms speed, and 50,000-event stress test at 55–60 FPS.

> "We evaluated the system through benchmarks across accuracy, throughput, and memory scaling:  
> 
> In Synthetic Monte Carlo Validation across 500 independent trials under Gaussian noise up to 100 metres and 30% random outlier contamination, our RANSAC-SVD pipeline achieved a Mean Absolute Error under 0.51 degrees for Dip, and under 0.93 degrees for Strike.  
> In Real Catalogue Testing on 3,225 INGV earthquakes from Campi Flegrei, complete clustering and plane extraction executed in under 42 milliseconds.  
> Stress testing up to 50,000 synthetic hypocentres maintained a fluid 55 to 60 frames per second, with cylinder grid partitioning executing in just 36.5 milliseconds.  
> And memory benchmarks confirmed that binary buffer streaming and FIFO caching hold RAM strictly below 500 megabytes."

---

### Slide 14: Conclusions & Future Work
* **Elapsed Time**: `[9:15 – 9:40]` (25 seconds)
* **Visual Action**: Summarize the 3 validated contributions, mention the 3 future extensions, and open the floor for Q&A.

> "To conclude, Seismic Viewer delivers a lightweight, responsive desktop system that combines 4D spatio-temporal visualization, automated structural plane fitting, and a high-throughput binary pipeline validated in collaboration with INGV researchers.  
> 
> Looking forward, future work will target real-time WebSocket streaming for active surveillance rooms, transitioning the graphics engine to WebGPU or Deck.gl for zero-install cloud deployment, and integrating 3D focal mechanism overlays to directly display fault slip directions.  
> 
> Thank you very much for your attention."

---

## 4. Anticipated Committee Q&A Preparation

### Question 1: "Why did you choose DBSCAN over K-Means for seismic swarms?"
> **Spoken Answer**: "K-Means has two major theoretical drawbacks when applied to earthquake hypocenters: first, it assumes spherical, convex clusters of similar size, whereas geological faults are planar, elongated, and irregular. Second, K-Means is forced to partition every single data point into a cluster, which means diffuse tectonic background noise pollutes the fault structures. DBSCAN solves both issues: it finds arbitrarily shaped clusters and treats low-density background seismicity as unclustered noise."

### Question 2: "Why do you exclude earthquakes with missing depths from 3D views?"
> **Spoken Answer**: "In real seismic catalogues, shallow or poorly triangulated micro-earthquakes sometimes lack a reliable focal depth solution (marked as NaN or null). If we defaulted their depth to zero, they would all artificially collapse onto sea level, creating a fake horizontal plane that would distort both 3D visualization and automated fault plane fitting. Therefore, we keep them in 2D views so researchers don't lose catalogue completeness, but strictly filter them out before 3D spatial geometry calculations."

### Question 3: "Why did you use Float32 binary streaming instead of JSON or WebSockets?"
> **Spoken Answer**: "Seismological catalogues contain tens of thousands of coordinates. Encoding them as JSON requires sending ASCII text with brackets, quotes, and commas, which consumes almost 5 megabytes for 50,000 points. Moreover, `JSON.parse()` in the browser blocks the main UI thread for about 40 milliseconds. By streaming contiguous Float32 binary arrays, we drop the payload by nearly 80% to under 1 megabyte, and the browser can instantly map the buffer into WebGL memory via `Float32Array` in less than 0.01 milliseconds."

### Question 4: "Why run RANSAC before SVD for fault plane extraction?"
> **Spoken Answer**: "Singular Value Decomposition finds the plane that minimizes orthogonal squared distances across all points in a cluster. However, SVD is an $L_2$-norm method that is highly sensitive to outliers. Even with DBSCAN, a cluster often contains points from small secondary fractures or location errors. RANSAC acts as a robust filter by sampling triplets to identify the core planar inliers. SVD is then computed strictly on these inliers to determine the exact normal vector and calculate Strike and Dip angles."
