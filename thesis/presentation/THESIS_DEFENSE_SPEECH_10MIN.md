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
   - Interactive 2D workspace with zero-latency in-browser filtering and energy release.
   - 3D workspace with physical depth scaling, orthographic drop lines, and dynamic compass.
   - 4D spatiotemporal animation engine with cumulative and sliding-window migration plus the **Afterglow** visual decay.
   - Multi-layer geophysical co-registration: 3D $V_p/V_s$ seismic tomography with IDW Gaussian baseline blending, GNSS ground uplift with Mogi decay, and seismic station markers.
   - Clustering engine: **Why and how algorithms changed** — why K-Means failed on tectonic faults and forced noise points $\to$ why DBSCAN was adopted with automated Kneedle knee-detection $\to$ MiniBatchKMeans for rapid batch partitioning $\to$ confirmed cluster lock.
   - Mathematical fault plane fitting: **Why RANSAC was applied before SVD** to eliminate diffuse outliers, followed by centered SVD for normal vector extraction ($\vec{n}=v_3$), Strike, Dip, and planarity scoring.
   - 4D Cylinder slicing for caldera ring faults & **Global Label Matching** (stochastic spatial voting with Hungarian assignment) to stop cluster color flickering across animation frames.
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
| **6** | 3D Workspace & Underground Cues | 3:25 – 4:05 | 40s | ~85 words | 130 |
| **7** | 4D Dynamic Migration & Afterglow Effect | 4:05 – 4:45 | 40s | ~90 words | 135 |
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

> "Good morning everyone, Professor Avola, and Dr. Bailo.  
> My name is Alessio Curcio, and today I'm glad to present my internship report titled:  
> **'Seismic Viewer: Design, Implementation and Evaluation of an Interactive 4D Spatio-Temporal Visualisation System for Seismological Data'**.  
> 
> This work was carried out during my curricular internship at the National Institute of Geophysics and Volcanology (INGV), in collaboration with Sapienza University of Rome."

---

### Slide 2: Context & Research Motivation
* **Elapsed Time**: `[0:35 – 1:20]` (45 seconds)
* **Visual Action**: Point to the Campi Flegrei context on Card 1, highlight the 2025 Nature study on Card 2, then point to Card 3.

> "To understand why we started this project, we have to look at what's happening right now at the Campi Flegrei volcanic caldera near Naples.  
> Since 2005, this area has been experiencing active bradyseism — meaning continuous ground uplift accompanied by frequent, intense earthquake swarms.  
> 
> Just recently, in 2025, a landmark study published in *Nature Communications Earth & Environment*, co-authored by researchers from INGV and Roma Tre University, made an important discovery: these earthquakes aren't just random noise. Instead, they clearly delineate the pressurization of hydrothermal fluids and the physical growth of an active underground fault plane.  
> 
> However, geophysicists had a major problem: they lacked an interactive tool to explore and track these faults in 3D and 4D over time. That's exactly why Seismic Viewer was proposed."

---

### Slide 3: State of Current Tools & Visualisation Gap
* **Elapsed Time**: `[1:20 – 2:00]` (40 seconds)
* **Visual Action**: Highlight the comparison table on Slide 3, pointing out the all-green column for Seismic Viewer.

> "When we looked at the tools seismologists currently use, we found a clear technological gap:  
> First, standard GIS tools like QGIS or ArcGIS are great for 2D cartography, but they really struggle with high-framerate 3D point clouds and dynamic animations.  
> Second, scientific 3D packages like ParaView are extremely powerful, but they have a steep learning curve, require heavy desktop installations, and don't connect easily to live web catalogues.  
> And third, public web portals only display static 2D maps.  
> 
> So what geophysicists really needed was a lightweight tool running directly in the browser that unifies 2D maps, 3D point clouds, 4D time playback, and automated fault plane extraction in one place."

---

### Slide 4: Requirements & Iterative Implementation Timeline
* **Elapsed Time**: `[2:00 – 2:45]` (45 seconds)
* **Visual Action**: Point to Card 1 for System Requirements, then trace through the 6 Phases on Card 2 on the right.

> "To meet these needs, we defined clear functional goals: smooth 2D/3D/4D navigation, automated fault plane fitting, multi-layer geophysical overlays, and support for both online and offline data. And non-functional goals: 60 frames per second rendering, sub-second latency, and a memory footprint strictly under 500 megabytes.  
> 
> Because this project was developed in close collaboration with geophysicists, we adopted an iterative development approach across six phases:  
> In Phase 1, we built the initial 3D prototype and local CSV parser.  
> In Phase 2, we tested our first clustering algorithms and connected Python to a native web view.  
> In Phase 3, we redesigned the UI and integrated the INGV GOSSIP REST API.  
> In Phase 4, based on direct feedback from researchers, we introduced DBSCAN with automatic knee tuning, 4D cylinder slicing, and cluster locking.  
> In Phase 5, we integrated 3D seismic tomography, GNSS uplift, and monitoring stations.  
> And in Phase 6, we optimized everything with Float32 binary streaming and an asynchronous architecture."

---

### Slide 5: 2D Application Workspace & In-Browser Filtering
* **Elapsed Time**: `[2:45 – 3:25]` (40 seconds)
* **Visual Action**: Point to the 2D map screenshot on the left and the statistical indicators on the right.

> "Now, let's dive into the current application features, starting with the 2D Workspace.  
> 
> On the left panel, users can filter the catalogue in real time by date, depth, and magnitude. All filtering runs instantly directly in JavaScript in the browser, with zero round-trip latency to the server.  
> Earthquakes are mapped using OpenStreetMap, with circles scaled by seismic energy and colored by hypocentral depth.  
> On the right, live summary cards calculate total event count, maximum magnitude, and cumulative energy release in kilojoules.  
> Researchers can immediately isolate swarms around Pozzuoli or the Solfatara crater."

---

### Slide 6: 3D Workspace & Underground Cues
* **Elapsed Time**: `[3:25 – 4:05]` (40 seconds)
* **Visual Action**: Point out the orthographic drop lines, the depth color scale, and the 3D compass widget on the screenshot.

> "Next, switching to the 3D Workspace, earthquakes are rendered in physical space using WebGL.  
> 
> Now, anyone who has worked with 3D point clouds knows that depth perception on a flat screen can be tricky. To solve this, we introduced three visual cues:  
> First, vertical drop lines that project each hypocenter straight down to sea level.  
> Second, a clear depth color gradient.  
> And third, a 3D bounding box with depth marks in kilometers.  
> We also built a dynamic 3D compass in the corner that syncs with camera rotation, so researchers never lose their spatial orientation."

---

### Slide 7: 4D Dynamic Migration & The Afterglow Effect
* **Elapsed Time**: `[4:05 – 4:45]` (40 seconds)
* **Visual Action**: Describe the Afterglow mechanism and how it reveals fluid migration pathways over time.

> "Earthquake swarms aren't static — they migrate. Our 4D Animation Engine lets researchers watch this evolution unfold over time.  
> 
> Users can choose between a cumulative view, which shows seismic buildup, or a moving time window from 1 to 30 days to isolate active migration fronts.  
> To make fault propagation clear without cluttering the screen, we created what we call the 'Afterglow' visual effect. New earthquakes burst onto the screen bright and large, while older events exponentially fade out over time.  
> This lets geophysicists clearly see the direction and speed of fluid-driven fractures across the caldera."

---

### Slide 8: Multi-Layer Geophysics — Tomography, Uplift & Stations
* **Elapsed Time**: `[4:45 – 5:30]` (45 seconds)
* **Visual Action**: Point to the tomography volume, GNSS vectors, and the multi-layer integration cards.

> "What really sets Seismic Viewer apart is that it doesn't just show dots in space — it fuses multiple geophysical datasets in the same 3D scene.  
> 
> First, we render 3D seismic tomography. We interpolate Vp/Vs velocity ratios onto a 3D grid using Inverse Distance Weighting, applying a Gaussian spatial decay that smoothly transitions outside data points to the regional baseline of 1.75.  
> Second, we display surface ground deformation from GNSS satellite networks, both as station vectors and as an interpolated uplift surface with Mogi decay.  
> And third, we plot active seismic monitoring stations right on the surface.  
> By seeing these layers together, researchers can correlate high-fluid zones and surface uplift directly with where faults are breaking."

---

### Slide 9: Machine Learning Engine — Why and How Algorithms Changed
* **Elapsed Time**: `[5:30 – 6:15]` (45 seconds)
* **Visual Action**: Walk through why KMeans failed, why DBSCAN succeeded, and how Cluster Lock works.

> "Now, how do we identify faults from thousands of earthquakes? This brings us to our clustering engine, and why we made specific algorithmic choices.  
> 
> Initially, in early prototypes, we used K-Means. But we quickly realized K-Means has two major flaws for seismology: it forces every single point into a cluster, and it assumes clusters are spherical balls. In reality, earthquakes form elongated planar faults surrounded by diffuse background noise.  
> So, we switched to DBSCAN. DBSCAN naturally finds arbitrary non-linear shapes and correctly labels background noise as unclustered outliers. To avoid making users guess the epsilon parameter, we automated it using the Kneedle algorithm on the k-nearest-neighbor distance plot.  
> We also kept MiniBatchKMeans with a distance cutoff filter for instant partitioning of massive datasets, and we added a 'Cluster Lock' feature, allowing geophysicists to freeze confirmed geological faults and re-cluster only unresolved swarms."

---

### Slide 10: Structural Geology & Fault Plane Fitting
* **Elapsed Time**: `[6:15 – 7:00]` (45 seconds)
* **Visual Action**: Walk through RANSAC filtering -> SVD normal vector -> fitted 3D plane on the right.

> "Once a cluster is isolated, how do we extract the physical fault plane? We designed a two-step mathematical pipeline.  
> 
> Why didn't we just fit a plane using SVD directly? Because if you have even a few stray earthquakes or noise points in a cluster, ordinary least squares or direct SVD gets skewed.  
> So, Step 1 is RANSAC: it randomly samples point triplets over 100 iterations to find the candidate plane with the highest number of spatial inliers, discarding noise.  
> Then, Step 2 runs Singular Value Decomposition on the centered inliers. The normal vector of the fault plane comes directly from the eigenvector with the smallest singular value.  
> From this normal vector, we calculate the geological Strike, Dip, and planarity score, and render the fault as an interactive 3D wireframe mesh."

---

### Slide 11: 4D Cylinder Slicing & Global Label Matching
* **Elapsed Time**: `[7:00 – 7:45]` (45 seconds)
* **Visual Action**: Explain the color flickering problem on the left and the smooth spatial voting solution on the right.

> "We also solved two subtle algorithmic challenges that came up during testing.  
> 
> First, caldera ring faults curve across the volcano. To handle this, we introduced Cylinder Partitioning, cutting the volume into vertical cylindrical wedges where faults are locally planar.  
> Second, when running clustering across 4D time steps, standard algorithms randomly reassign cluster IDs between frames. This caused colors to flicker chaotically in the animation.  
> To fix this, we created a Global Label Matching algorithm. For each new time frame, it takes a stochastic sample of 200 points per cluster, finds their nearest neighbors in the previous frame, and performs spatial majority voting with greedy assignment.  
> This keeps colors and cluster identities perfectly stable across the entire animation."

---

### Slide 12: Data Pipeline, Missing Depths & Binary Streaming
* **Elapsed Time**: `[7:45 – 8:30]` (45 seconds)
* **Visual Action**: Point to the data pipeline steps and highlight the 80% compression and instant parsing.

> "Now, let's look at the data engineering pipeline and the choices we made.  
> 
> The application ingests data either by querying the INGV GOSSIP REST API online, or through local CSV files. It handles coordinate conversion, date parsing, and metadata cleaning.  
> Here, we made a crucial design choice regarding missing depths: earthquakes with null or missing depth are kept in the 2D catalogue for completeness, but they are strictly excluded from 3D and 4D spatial computations. Otherwise, they would artificially flatten onto sea level at depth zero and corrupt fault plane fitting.  
> 
> Furthermore, to avoid sending bulky JSON over the wire, we built a Float32 binary streaming protocol.  
> Instead of parsing thousands of JSON objects, the server streams a raw, contiguous Float32 binary buffer directly into a JavaScript typed array. This slashed payload size by nearly 80% and dropped browser unpacking time from 40 milliseconds to less than 0.01 milliseconds."

---

### Slide 13: Results & Quantitative Validation
* **Elapsed Time**: `[8:30 – 9:15]` (45 seconds)
* **Visual Action**: Point to the validation metrics in the table: Monte Carlo MAE, 42ms clustering, 60 FPS stress test.

> "To validate the system, we carried out extensive benchmarks:  
> 
> First, in Monte Carlo simulations across 500 synthetic faults with noise and 30% random outliers, our RANSAC-SVD method achieved a Mean Absolute Error under 0.5 degrees for Dip, and under 0.9 degrees for Strike.  
> Second, on the real Campi Flegrei catalogue of over 3,200 earthquakes, clustering and plane fitting completed in less than 42 milliseconds.  
> Third, in stress tests with 50,000 synthetic hypocenters, WebGL maintained a smooth 55 to 60 frames per second.  
> And memory management benchmarks confirmed that our session caching and garbage collection keep RAM usage strictly below 500 megabytes throughout extended sessions."

---

### Slide 14: Conclusions & Future Work
* **Elapsed Time**: `[9:15 – 9:40]` (25 seconds)
* **Visual Action**: Thank the committee and supervisors, open the floor for Q&A at exactly ~9m 40s.

> "In conclusion, Seismic Viewer delivers a lightweight, accessible, and fast tool that bridges the gap between raw seismological data and interactive 3D and 4D exploration.  
> It was developed and validated in close collaboration with INGV researchers to directly support volcano monitoring.  
> Looking ahead, future improvements will focus on real-time WebSocket push notifications from INGV feeds, WebGPU shaders for on-the-fly clustering, and focal mechanism beachball inversions.  
> 
> Thank you very much for your time and attention. I would be glad to answer any questions."

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
