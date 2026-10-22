# Seismic Viewer — Final Internship Defense Talk Track & Consistency Report
**Candidate**: Alessio Curcio  
**Degree**: Applied Computer Science and Artificial Intelligence (ACSAI)  
**Institution**: Sapienza University of Rome  
**Host Institution**: National Institute of Geophysics and Volcanology (INGV)  
**Supervisors**: Prof. Danilo Avola (Sapienza), Dr. Daniele Bailo (INGV)  
**Research Collaboration**: Dr. Guido Giordano (Roma Tre / INGV), Dr. Lucilla Alfonsi (INGV)  
**Target Duration**: 9 minutes 35 seconds (Strictly ≤ 10 minutes)  
**Tone & Style**: Clear, simple, fluent spoken English (natural, accessible, conversational, directly citing slide contents without unnecessary jargon)  

---

## 1. Presentation Structure & 4-Part Roadmap

This presentation is organized into four core parts following the scientific, technical, and architectural narrative of the internship project:

1. **Part 1: Context, Analyzed Domain, State of the Art & Development Timeline** (Slides 1–4, ~2m 40s)
   - Scientific context: Ongoing volcanic crisis at Campi Flegrei, ground uplift, and the recent 2025 *Nature Communications Earth & Environment* study (*Giordano, Alfonsi et al.*) showing active underground fault plane growth.
   - **Direct collaboration with Giordano and Alfonsi** during the internship to bridge research needs with software development.
   - Limitations of current tools: 2D GIS projection bias (QGIS/ArcGIS), command-line static scripts (ObsPy/GMT), and complex pipelines (ParaView).
   - Core functional pillars and the **6-phase iterative implementation timeline** developed with direct researcher feedback.
2. **Part 2: Current Application Features & Algorithmic Rationale** (Slides 5–11, ~4m 55s)
   - 2D Application Workspace: Zero-latency in-browser JavaScript filtering and bi-modal spatial display (proportional scatter markers vs continuous Gaussian kernel density heatmaps).
   - 3D Application Workspace: Geographic coordinate retention in degrees, aspect ratio metric proportionality (1 km in X, Y, Z renders identically), and viewpoint persistence with Plotly `uirevision='constant'`.
   - Multi-layer geophysics: 3D $V_p/V_s$ seismic velocity tomography with IDW interpolation and Gaussian decay, plus GNSS ground uplift vertical deformation columns.
   - 4D temporal animation engine: Sequence slicing across Accumulation Mode, Sliding Window Mode (width $W$), and Block Mode (custom step), alongside interactive timeline histogram and energy tracking.
   - Algorithmic innovation: 4D Cylinder slicing for curved caldera ring faults (**replicating the spatial segmentation of Giordano & Alfonsi 2025**), Global Label Matching (historical majority voting to stop color flickering), and 8-worker parallel thread pool.
   - Machine learning clustering engine: Why K-Means failed on tectonic faults $\to$ switching to DBSCAN with automatic Kneedle knee detection $\to$ MiniBatchKMeans $\to$ Hierarchical Sub-Clustering and Cluster Lock.
   - Structural geology & fault plane fitting: Why RANSAC inlier consensus (100 iterations) is run before SVD to eliminate outliers, followed by centered SVD for normal vector extraction ($\vec{n}=v_3$), Strike, Dip, Dip Direction, Planarity, and interactive 3D meshes with hover vectors.
3. **Part 3: Data Ingestion Pipeline & Architectural Choices** (Slide 12, ~45s)
   - Heterogeneous ingestion: Segmented yearly queries to the INGV GOSSIP online REST API and local offline CSV parsing with alias detection.
   - **Quality sanitisation & missing depth principle**: kept in 2D views for catalogue completeness, but strictly excluded from 3D views and clustering to prevent fake flat planes at sea level. Physical bounds checks ($-10$ to $+800$ km).
   - **High-Performance Float32 binary streaming**: contiguous binary buffers directly mapped into browser typed arrays, cutting payload by ~80% (4.75 MB $\to$ 976 KB) and dropping decode time from ~40 ms to $<0.01$ ms.
4. **Part 4: Results & Future Developments** (Slides 13–15, ~1m 15s)
   - Quantitative validation: 500-run Monte Carlo synthetic testing (Dip MAE $\Delta d < 0.51^\circ$, Strike MAE $\Delta s < 0.93^\circ$), real Campi Flegrei catalogue performance (clustering and plane fitting in $<42$ ms for 3,225 events), and 50,000-event stress test at 55–60 FPS.
   - Memory strictly under 500 MB via binary buffers and FIFO session caching.
   - Conclusions and future work: real-time WebSocket and SeedLink feeds for observatory control rooms, WebGPU compute shaders for client-side DBSCAN re-clustering, and 3D focal mechanism "beachballs".
   - Formal closing and opening of the floor for Committee Q&A.

---

## 2. Pacing & Time Management Table (15 Slides)

| Slide # | Slide Title | Window (MM:SS) | Duration | Target Words | Pace (wpm) |
|:---:|:---|:---:|:---:|:---:|:---:|
| **1** | Title & Welcome | 0:00 – 0:30 | 30s | ~60 words | 120 |
| **2** | Context & Motivation (Campi Flegrei, Nature 2025 & Collaboration) | 0:30 – 1:15 | 45s | ~95 words | 125 |
| **3** | State of Current Tools & Visualisation Gap | 1:15 – 1:55 | 40s | ~90 words | 135 |
| **4** | System Design & 6-Phase Timeline | 1:55 – 2:40 | 45s | ~100 words | 135 |
| **5** | 2D Workspace & In-Browser Filtering | 2:40 – 3:20 | 40s | ~85 words | 125 |
| **6** | 3D Workspace & Physical Depth Scaling | 3:20 – 4:00 | 40s | ~85 words | 125 |
| **7** | Multi-Layer Geophysics (Tomography & GNSS Uplift) | 4:00 – 4:45 | 45s | ~90 words | 120 |
| **8** | 4D Dynamic Migration & Temporal Playback | 4:45 – 5:25 | 40s | ~90 words | 135 |
| **9** | Algorithmic Innovation (Cylinders & Label Matching) | 5:25 – 6:05 | 40s | ~100 words | 145 |
| **10** | Clustering Engine (DBSCAN, Kneedle, Cluster Lock) | 6:05 – 6:50 | 45s | ~100 words | 135 |
| **11** | Structural Geology & Plane Fitting (RANSAC + SVD) | 6:50 – 7:35 | 45s | ~95 words | 125 |
| **12** | Data Pipeline, Missing Depths & Float32 Protocol | 7:35 – 8:20 | 45s | ~105 words | 140 |
| **13** | Quantitative Validation & Benchmarks | 8:20 – 9:05 | 45s | ~105 words | 140 |
| **14** | Conclusions & Future Work | 9:05 – 9:35 | 30s | ~80 words | 135 |
| **15** | Closing & Committee Q&A | 9:35 – 9:45 | 10s | ~25 words | 120 |
| **Total** | **Complete Defense Presentation** | **0:00 – 9:45** | **9m 45s** | **~1,205 words** | **~128 wpm** |

> **Safety Margin**: A comfortable **15-second safety buffer** remains before the strict 10:00 cutoff. The language is simple, natural, and conversational English—directly citing the text and numbers on the slides, free of tongue-twisters, and easy to deliver calmly and confidently.

---

## 3. Word-for-Word Spoken Defense Script (Directly Based on Slide Contents)

### Slide 1: Title & Welcome
* **Elapsed Time**: `[0:00 – 0:30]` (30 seconds)
* **Word Count**: ~60 words
* **Visual Action**: Stand upright, smile, make warm eye contact with the Committee, project confidence.

> "Hello everyone, my name is Alessio Curcio, and today I am pleased to present my internship project titled:  
> **'Seismic Viewer: Design, Implementation and Evaluation of an Interactive 4D Spatio-Temporal Visualisation System for Seismological Data'**.  
> 
> This work was carried out during my curricular internship at the National Institute of Geophysics and Volcanology (INGV), under the supervision of Prof. Danilo Avola from Sapienza and Dr. Daniele Bailo from INGV."

---

### Slide 2: Context & Research Motivation
* **Elapsed Time**: `[0:30 – 1:15]` (45 seconds)
* **Word Count**: ~95 words
* **Visual Action**: Point to Active Volcanic Unrest on Card 1, highlight the Giordano & Alfonsi Nature 2025 study on Card 2, and point to INGV Operational Need on Card 3.

> "To understand the motivation of this project, we look at the ongoing volcanic unrest at Campi Flegrei near Naples.  
> Since 2005, continuous ground uplift accompanied by dense earthquake swarms has required multi-parametric monitoring.  
> 
> Recently, in 2025, a landmark study published in *Nature Communications Earth & Environment* by Dr. Guido Giordano and Dr. Lucilla Alfonsi showed that these earthquakes aren't just diffuse clusters: they outline active, growing planar fault structures.  
> 
> During my internship, I worked in direct collaboration with Giordano and Alfonsi.  
> Our goal was to solve an operational need at INGV: building an interactive desktop system that bridges raw earthquake catalogues, subsurface tomography, and automated fault plane extraction in one responsive workspace."

---

### Slide 3: State of the Art & Tooling Comparison
* **Elapsed Time**: `[1:15 – 1:55]` (40 seconds)
* **Word Count**: ~90 words
* **Visual Action**: Walk through the three columns on Slide 3: GIS platforms, Scientific Code (ObsPy/GMT/ParaView), and our solution Seismic Viewer.

> "When we analyzed existing seismological tools, we found a clear functional gap:  
> 
> First, General GIS platforms like QGIS and ArcGIS have a 2D projection bias that flattens depth into static plan-views. When navigating dense 3D point clouds over 10,000 events, they suffer major frame drops and lack native 4D time playback.  
> Second, Scientific Code like ObsPy and GMT produces static image files in batch mode without real-time interaction, requiring continuous scripting. Even 3D tools like ParaView involve complex manual pipelines and lack direct seismological integrations.  
> 
> Seismic Viewer bridges this gap: providing hardware-accelerated 2D, 3D, and 4D WebGL navigation, automated fault plane fitting, and an easy standalone application without heavy GIS overhead."

---

### Slide 4: System Design & Implementation Timeline
* **Elapsed Time**: `[1:55 – 2:40]` (45 seconds)
* **Word Count**: ~100 words
* **Visual Action**: Point to the three functional pillars on Card 1, then follow the 6-Phase Timeline from Phase 1 to Phase 6 on Card 2.

> "We defined three core functional pillars:  
> Hardware-accelerated Interactive Visualisations in 2D, 3D, and 4D;  
> Automated Structural Analysis combining spatial clustering with RANSAC-SVD plane fitting;  
> and Multi-Layer Geophysical Fusion combining tomography, ground uplift, and seismic stations.  
> 
> Working closely with researchers Giordano and Alfonsi, development progressed through six iterative phases:  
> starting with 3D prototypes and CSV parsing in Phase 1,  
> testing K-Means and the Python-WebView bridge in Phase 2,  
> building the analytical dashboard and querying the INGV GOSSIP API in Phase 3,  
> introducing DBSCAN with knee tuning, 4D cylinders, and cluster locking in Phase 4,  
> integrating Vp/Vs tomography and GNSS surface deformation in Phase 5,  
> and finalizing high-speed Float32 binary streaming in Phase 6."

---

### Slide 5: 2D Application Workspace & In-Browser Filtering
* **Elapsed Time**: `[2:40 – 3:20]` (40 seconds)
* **Word Count**: ~85 words
* **Visual Action**: Point to the interactive drawer filters on the left and show the switch between Proportional Scatter Markers and Continuous Kernel Density.

> "Starting with the 2D Application Workspace:  
> 
> All event filtering across Magnitude, Depth, and Date ranges runs entirely in JavaScript inside the browser. This eliminates HTTP roundtrips during parameter adjustments, providing instant, zero-latency filtering without re-fetching raw catalogues.  
> For spatial representation, we provide a bi-modal display:  
> Users can toggle between Proportional Scatter Markers—where marker radius scales with earthquake magnitude—and a Continuous Kernel Density heatmap that aggregates hypocentres into Gaussian density fields.  
> This allows geophysicists to immediately highlight dense swarm concentrations across Pozzuoli and the Solfatara crater."

---

### Slide 6: 3D Application Workspace & Physical Depth Scaling
* **Elapsed Time**: `[3:20 – 4:00]` (40 seconds)
* **Word Count**: ~85 words
* **Visual Action**: Highlight Geographic Coordinate Retention, Aspect Ratio Correction (1 km metric proportionality), and Viewpoint Persistence on the cards.

> "Switching to the 3D Workspace, hypocentres are rendered in physical space via WebGL.  
> To guarantee scientific fidelity, we implemented three key mechanisms:  
> 
> First, Geographic Coordinate Retention: horizontal axes preserve standard geographic degrees alongside physical focal depth measured in kilometres.  
> Second, Aspect Ratio Correction: to prevent distortion caused by Earth's sphericity, the system scales the 3D bounding box so that 1 kilometre along X, Y, and Z renders with identical physical proportions.  
> And third, Viewpoint Persistence: camera azimuth, elevation, and zoom coordinates are strictly preserved across filter updates using Plotly's `uirevision` property."

---

### Slide 7: Multi-Layer Geophysics (Tomography & Ground Uplift)
* **Elapsed Time**: `[4:00 – 4:45]` (45 seconds)
* **Word Count**: ~90 words
* **Visual Action**: Point to the 3D Vp/Vs tomography volume on Card 1 and the GNSS vertical uplift columns on Card 2.

> "A central contribution of Seismic Viewer is fusing multiple geophysical layers in the exact same 3D coordinate space.  
> 
> First, 3D Vp/Vs Seismic Tomography: we convert tomographic velocity ratios into a 3D volumetric grid using Inverse Distance Weighting with 16 nearest neighbours, applying a Gaussian spatial decay that smoothly blends toward the regional crustal baseline outside sampled points.  
> Second, GNSS Ground Uplift Columns: we ingest GPS deformation time-series across Campi Flegrei, rendering explicit 3D vertical displacement columns directly at station locations.  
> By seeing these layers together, researchers can directly correlate surface ground swelling with underlying fluid pockets and earthquake swarms."

---

### Slide 8: 4D Temporal Animation & Sequence Slicing
* **Elapsed Time**: `[4:45 – 5:25]` (40 seconds)
* **Word Count**: ~90 words
* **Visual Action**: Walk through the three modes (Accumulation, Sliding Window, Block Mode) and point to the interactive timeline histogram and energy meter at the bottom.

> "Earthquake swarms migrate dynamically over time. Our 4D engine provides sequence slicing across three distinct analytical playback modes:  
> 
> Accumulation Mode, showing cumulative seismic buildup from the first event to track stress release over time;  
> Sliding Window Mode, which moves a window of width W across time—typically one frame per day—to isolate active hypocentral migration fronts;  
> and Block Mode, moving a window with a custom step to allow flexible temporal downsampling and multi-day epoch comparisons.  
> At the bottom, an Interactive Timeline Histogram couples chronological navigation with real-time tracking of active event counts, peak magnitude, and cumulative seismic energy release."

---

### Slide 9: Algorithmic Innovation — Cylinders & Label Stability
* **Elapsed Time**: `[5:25 – 6:05]` (40 seconds)
* **Word Count**: ~100 words
* **Visual Action**: Point to Why Cylinder Partitioning on Card 1, Global Label Matching on Card 2, and the 8-worker thread pool on Card 3.

> "Next, we solved two practical algorithmic challenges:  
> 
> First, Why Cylinder Partitioning? Caldera ring faults curve along the volcanic perimeter, so attempting to fit a single global plane produces large geometric errors. Working directly with Giordano and Alfonsi, we replicated their spatial segmentation methodology, partitioning the crust into vertical cylindrical columns to isolate locally planar fault segments and validate our automated fitting against their published results.  
> Second, Global Label Matching: in 4D animations, standard clustering randomly reassigns cluster IDs between time steps, causing chaotic color flickering. We developed a historical majority voting algorithm that maintains stable cluster identities across frames.  
> Finally, an asynchronous worker pool of 8 threads parallelizes cylinder fitting across animation steps."

---

### Slide 10: Machine Learning Clustering Engine
* **Elapsed Time**: `[6:05 – 6:50]` (45 seconds)
* **Word Count**: ~100 words
* **Visual Action**: Explain why K-Means failed and DBSCAN succeeded, then highlight the Hierarchical Sub-Clustering and Cluster Lock mechanism on the main card.

> "To automatically isolate fault structures from thousands of earthquakes, we designed a flexible clustering engine.  
> 
> We initially evaluated K-Means, but it fails in seismology: it forces every point into a cluster and assumes spherical shapes. In reality, geological faults are elongated, and tectonic background noise surrounds them.  
> Therefore, we adopted DBSCAN: it detects arbitrary, non-planar fault shapes without requiring a predefined cluster count, and correctly isolates background noise as label minus one. We automated radius tuning by estimating epsilon from the k-nearest-neighbour knee using the Kneedle algorithm.  
> We also retained MiniBatchKMeans for rapid centroid preview, and introduced a Hierarchical Cluster Lock mechanism: researchers can selectively lock confirmed faults and re-cluster only unresolved swarms with refined local parameters."

---

### Slide 11: Structural Geology & Fault Plane Fitting (RANSAC + SVD)
* **Elapsed Time**: `[6:50 – 7:35]` (45 seconds)
* **Word Count**: ~95 words
* **Visual Action**: Walk through Step 1 (RANSAC Inlier Consensus), Step 2 (SVD & Geological Angles), and point to the Strike, Dip, and Planarity outputs.

> "From clustered hypocentres, the system mathematically reconstructs 3D fault planes in two steps:  
> 
> Why not just fit a plane using SVD directly? Because outlier points or secondary micro-cracks will pull the plane off its true orientation.  
> So, Step 1 is RANSAC Inlier Consensus: it tests random 3-point combinations over 100 iterations to find the planar consensus and discard non-planar noise.  
> Step 2 applies Singular Value Decomposition strictly to those centered inliers. The fault normal vector comes directly from the eigenvector of the smallest singular value.  
> From this normal vector, the system calculates geological Strike, Dip, Dip Direction, and Planarity, rendering interactive 3D rectangular plane meshes with hover vectors."

---

### Slide 12: Data Engineering Pipeline & Binary Streaming
* **Elapsed Time**: `[7:35 – 8:20]` (45 seconds)
* **Word Count**: ~105 words
* **Visual Action**: Trace through the 4 top cards (Ingestion, Missing Depth Principle, Physical Bounds, WGS84) and highlight the -80% size and <0.01ms badges on the bottom card.

> "Looking at the data engineering pipeline:  
> 
> Stage 1 handles Heterogeneous Ingestion: querying the INGV GOSSIP REST API in yearly chunks alongside local offline CSV parsing, supported by automatic alias detection for column headers.  
> Stage 2 enforces Quality Sanitisation and our Missing Depth Principle: earthquakes without a recorded depth are retained in 2D views for catalogue completeness, but strictly excluded from 3D views and clustering to prevent artificial planes at sea level. Physical bounds checks restrict depths between minus 10 and 800 kilometres.  
> Finally, in the bottom hero card, we replaced heavy JSON with our High-Performance Float32 Binary Protocol.  
> Streaming raw contiguous binary buffers slashed payload size by nearly 80%—from 4.75 megabytes to 976 kilobytes—and dropped browser decode time to less than 0.01 milliseconds."

---

### Slide 13: Results & Quantitative Validation Benchmarks
* **Elapsed Time**: `[8:20 – 9:05]` (45 seconds)
* **Word Count**: ~105 words
* **Visual Action**: Walk through the 4 benchmark cards: Monte Carlo MAE badges (<0.51° Dip, <0.93° Strike), Real Catalogue 42ms speed, 60 FPS stress test, and <500 MB RAM.

> "We evaluated the system thoroughly across four benchmark dimensions:  
> 
> First, Structural Accuracy in Monte Carlo simulations across 500 synthetic faults with noise up to 100 metres and 30% outlier contamination: our RANSAC-SVD pipeline achieved a Mean Absolute Error under 0.51 degrees for Dip, and under 0.93 degrees for Strike.  
> Second, Real Catalogue Testing on 3,225 INGV events from Campi Flegrei executed clustering and plane extraction in under 42 milliseconds.  
> Third, Algorithmic Throughput: cylinder grid partitioning runs in 36.5 milliseconds, and stress tests with 50,000 synthetic hypocentres maintained 55 to 60 frames per second.  
> And fourth, Serialization & Memory: browser decode dropped from 39.7 to under 0.01 milliseconds, and FIFO session management holds RAM strictly below 500 megabytes."

---

### Slide 14: Conclusions & Future Work
* **Elapsed Time**: `[9:05 – 9:35]` (30 seconds)
* **Word Count**: ~80 words
* **Visual Action**: Highlight the 3 Validated Contributions on the left, the 3 Future Extensions on the right, and then transition to Slide 15.

> "To conclude, Seismic Viewer delivers on three validated contributions:  
> A High-Performance Architecture pairing a pywebview client with an asynchronous FastAPI server and Float32 streaming;  
> Multi-Layer Visualisation integrating 4D animations with 3D tomography and GNSS uplift;  
> and Robust Structural Analysis benchmarked with sub-degree angular accuracy.  
> 
> Looking forward, future extensions will focus on Real-Time Surveillance Feeds with WebSockets and SeedLink, WebGPU compute shaders for client-side DBSCAN re-clustering, and 3D focal mechanism 'beachballs' for kinematic seismotectonics."

---

### Slide 15: Closing Slide (Thank You for Your Attention & Q&A)
* **Elapsed Time**: `[9:35 – 9:45]` (10 seconds)
* **Word Count**: ~25 words
* **Visual Action**: Smile warmly, acknowledge Professor Avola and Dr. Bailo, thank the entire committee, and open the floor for questions.

> "Thank you very much for your time and attention.  
> I would be glad to answer any questions from the Committee."

---

## 4. Anticipated Committee Q&A Preparation (Clear & Direct Answers)

### Question 1: "Why did you choose DBSCAN over K-Means for seismic swarms?"
> **Spoken Answer**: "K-Means assumes clusters are spherical balls of equal size, and it forces every single point into a cluster. But geological faults are flat, elongated fractures, and real catalogues contain scattered background noise. DBSCAN solves both problems: it finds arbitrary, non-spherical shapes and labels low-density background points as noise (label -1), so they don't pollute the fault geometry."

### Question 2: "Why do you exclude earthquakes with missing depths from 3D views?"
> **Spoken Answer**: "In real seismic catalogues, shallow micro-earthquakes sometimes lack a reliable depth calculation. If we defaulted their depth to zero, they would all artificially pile up on sea level, forming a fake flat plane that would distort both 3D visualization and automated fault plane fitting. Keeping them in 2D maintains catalogue completeness, while excluding them from 3D keeps the geometry scientifically valid."

### Question 3: "Why did you use Float32 binary streaming instead of JSON or WebSockets?"
> **Spoken Answer**: "Seismological catalogues can contain tens of thousands of coordinates. Encoding them in JSON creates huge text files—almost 5 megabytes for 50,000 points—and parsing that text blocks the browser for about 40 milliseconds. By streaming raw, contiguous Float32 binary buffers, we reduced the payload by 80% to under 1 megabyte, and the browser maps it directly into WebGL memory in less than 0.01 milliseconds."

### Question 4: "Why run RANSAC before SVD for fault plane extraction?"
> **Spoken Answer**: "SVD finds the best-fitting plane by minimizing squared distances, but it is very sensitive to outliers. Even inside a clustered swarm, secondary micro-cracks or location errors can pull the plane off-angle. RANSAC tests random 3-point samples to find the dense planar core and throw away outliers. Once we have clean inliers, SVD calculates the exact normal vector, Strike, and Dip with high mathematical accuracy."
