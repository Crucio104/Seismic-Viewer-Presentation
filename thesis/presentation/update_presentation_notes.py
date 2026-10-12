import pptx

SPEECH_NOTES_INFORMAL_ACADEMIC = [
    # SLIDE 1
    """[SLIDE 1 | TIME: 0:00 - 0:35 | TARGET: 35 SECONDS]

SPEECH (EN):
"Hello everyone.
My name is Alessio Curcio, and today I'm glad to present my internship report titled:
'Seismic Viewer: Design, Implementation and Evaluation of an Interactive 4D Spatio-Temporal Visualisation System for Seismological Data'.

This work was carried out during my curricular internship at the National Institute of Geophysics and Volcanology."

[VISUAL ACTION: Smile, welcome the committee, make eye contact, project confidence, advance to Slide 2 at 0:35]""",

    # SLIDE 2
    """[SLIDE 2 | TIME: 0:35 - 1:20 | TARGET: 45 SECONDS]

SPEECH (EN):
"To understand why we started this project, we have to look at what's happening right now at the Campi Flegrei volcanic caldera near Naples.
Since 2005, this area has been experiencing active bradyseism — meaning continuous ground uplift accompanied by frequent, intense earthquake swarms.

Just recently, in 2025, a study published in Nature Communications Earth & Environment, co-authored by researchers from INGV and Roma Tre University, made an important discovery: these earthquakes aren't just random noise. Instead, they clearly delineate the pressurization of hydrothermal fluids and the physical growth of an active underground fault plane.

However, geophysicists had a major problem: they lacked an interactive tool to explore and track these faults in 3D and 4D over time. That's exactly why Seismic Viewer was proposed."

[VISUAL ACTION: Point to Campi Flegrei context on Card 1, highlight the 2025 Nature study on Card 2, then point to Card 3]""",

    # SLIDE 3
    """[SLIDE 3 | TIME: 1:20 - 2:00 | TARGET: 40 SECONDS]

SPEECH (EN):
"When we looked at the tools seismologists currently use, we found a clear technological gap:
First, standard GIS tools like QGIS or ArcGIS are great for 2D cartography, but they really struggle with high-framerate 3D point clouds and dynamic animations.
Second, scientific 3D packages like ParaView are extremely powerful, but they have a steep learning curve, require heavy desktop installations, and don't connect easily to live web catalogues.
And third, public web portals only display static 2D maps.

So what geophysicists really needed was a lightweight tool running directly in the browser that unifies 2D maps, 3D point clouds, 4D time playback, and automated fault plane extraction in one place."

[VISUAL ACTION: Highlight the comparison table on Slide 3, pointing out the all-green column for Seismic Viewer]""",

    # SLIDE 4
    """[SLIDE 4 | TIME: 2:00 - 2:45 | TARGET: 45 SECONDS]

SPEECH (EN):
"To meet these needs, we defined clear functional goals: smooth 2D/3D/4D navigation, automated fault plane fitting, multi-layer geophysical overlays, and support for both online and offline data. And non-functional goals: 60 frames per second rendering, sub-second latency, and a memory footprint strictly under 500 megabytes.

Because this project was developed in close collaboration with geophysicists, we adopted an iterative development approach across six phases:
In Phase 1, we built the initial 3D prototype and local CSV parser.
In Phase 2, we tested our first clustering algorithms and connected Python to a native web view.
In Phase 3, we integrated the INGV GOSSIP REST API.
In Phase 4, based on direct feedback from researchers, we introduced DBSCAN with automatic knee tuning, 4D cylinder slicing, and cluster locking.
In Phase 5, we integrated 3D seismic tomography, GNSS uplift, and monitoring stations.
And in Phase 6, we optimized everything with Float32 binary streaming and an asynchronous architecture."

[VISUAL ACTION: Point to Card 1 for System Requirements, then trace through the 6 Phases on Card 2 on the right]""",

    # SLIDE 5
    """[SLIDE 5 | TIME: 2:45 - 3:25 | TARGET: 40 SECONDS]

SPEECH (EN):
"Now, let's dive into the current application features, starting with the 2D Workspace.

On the left panel, users can filter the catalogue in real time by date, depth, and magnitude. All filtering runs instantly directly in JavaScript in the browser, with zero round-trip latency to the server.
Earthquakes are mapped using OpenStreetMap, with circles scaled by seismic energy and colored by hypocentral depth.
On the right, live summary cards calculate total event count, maximum magnitude, and cumulative energy release in kilojoules.
Researchers can immediately isolate swarms around Pozzuoli or the Solfatara crater."

[VISUAL ACTION: Point to the 2D map screenshot on the left and the statistical indicators on the right]""",

    # SLIDE 6
    """[SLIDE 6 | TIME: 3:25 - 4:05 | TARGET: 40 SECONDS]

SPEECH (EN):
"Next, switching to the 3D Workspace, earthquakes are rendered in physical space using WebGL.

Now, anyone who has worked with 3D point clouds knows that depth perception on a flat screen can be tricky. To solve this, we introduced three visual cues:
First, vertical drop lines that project each hypocenter straight down to sea level.
Second, a clear depth color gradient.
And third, a 3D bounding box with depth marks in kilometers.
We also built a dynamic 3D compass in the corner that syncs with camera rotation, so researchers never lose their spatial orientation."

[VISUAL ACTION: Point out the orthographic drop lines, the depth color scale, and the 3D compass widget on the screenshot]""",

    # SLIDE 7
    """[SLIDE 7 | TIME: 4:05 - 4:45 | TARGET: 40 SECONDS]

SPEECH (EN):
"Earthquake swarms aren't static — they migrate. Our 4D Animation Engine lets researchers watch this evolution unfold over time.

Users can choose between a cumulative view, which shows seismic buildup, or a moving time window from 1 to 30 days to isolate active migration fronts.
To make fault propagation clear without cluttering the screen, we created what we call the 'Afterglow' visual effect. New earthquakes burst onto the screen bright and large, while older events exponentially fade out over time.
This lets geophysicists clearly see the direction and speed of fluid-driven fractures across the caldera."

[VISUAL ACTION: Describe the Afterglow mechanism and how it reveals fluid migration pathways over time]""",

    # SLIDE 8
    """[SLIDE 8 | TIME: 4:45 - 5:30 | TARGET: 45 SECONDS]

SPEECH (EN):
"What really sets Seismic Viewer apart is that it doesn't just show dots in space — it fuses multiple geophysical datasets in the same 3D scene.

First, we render 3D seismic tomography. We interpolate Vp/Vs velocity ratios onto a 3D grid using Inverse Distance Weighting, applying a Gaussian spatial decay that smoothly transitions outside data points to the regional baseline of 1.75.
Second, we display surface ground deformation from GNSS satellite networks, both as station vectors and as an interpolated uplift surface with Mogi decay.
And third, we plot active seismic monitoring stations right on the surface.
By seeing these layers together, researchers can correlate high-fluid zones and surface uplift directly with where faults are breaking."

[VISUAL ACTION: Point to the tomography volume, GNSS vectors, and the multi-layer integration cards]""",

    # SLIDE 9
    """[SLIDE 9 | TIME: 5:30 - 6:15 | TARGET: 45 SECONDS]

SPEECH (EN):
"Now, how do we identify faults from thousands of earthquakes? This brings us to our clustering engine, and why we made specific algorithmic choices.

Initially, in early prototypes, we used K-Means. But we quickly realized K-Means has two major flaws for seismology: it forces every single point into a cluster, and it assumes clusters are spherical balls. In reality, earthquakes form elongated planar faults surrounded by diffuse background noise.
So, we switched to DBSCAN. DBSCAN naturally finds arbitrary non-linear shapes and correctly labels background noise as unclustered outliers. To avoid making users guess the epsilon parameter, we automated it using the Kneedle algorithm on the k-nearest-neighbor distance plot.
We also kept MiniBatchKMeans with a distance cutoff filter for instant partitioning of massive datasets, and we added a 'Cluster Lock' feature, allowing geophysicists to freeze confirmed geological faults and re-cluster only unresolved swarms."

[VISUAL ACTION: Walk through why KMeans failed, why DBSCAN succeeded, and how Cluster Lock works]""",

    # SLIDE 10
    """[SLIDE 10 | TIME: 6:15 - 7:00 | TARGET: 45 SECONDS]

SPEECH (EN):
"Once a cluster is isolated, how do we extract the physical fault plane? We designed a two-step mathematical pipeline.

Why didn't we just fit a plane using SVD directly? Because if you have even a few stray earthquakes or noise points in a cluster, ordinary least squares or direct SVD gets skewed.
So, Step 1 is RANSAC: it randomly samples point triplets over 100 iterations to find the candidate plane with the highest number of spatial inliers, discarding noise.
Then, Step 2 runs Singular Value Decomposition on the centered inliers. The normal vector of the fault plane comes directly from the eigenvector with the smallest singular value.
From this normal vector, we calculate the geological Strike, Dip, and planarity score, and render the fault as an interactive 3D wireframe mesh."

[VISUAL ACTION: Walk through RANSAC filtering -> SVD normal vector -> fitted 3D plane on the right]""",

    # SLIDE 11
    """[SLIDE 11 | TIME: 7:00 - 7:45 | TARGET: 45 SECONDS]

SPEECH (EN):
"We also solved two subtle algorithmic challenges that came up during testing.

First, caldera ring faults curve across the volcano. To handle this, we introduced Cylinder Partitioning, cutting the volume into vertical cylindrical wedges where faults are locally planar.
Second, when running clustering across 4D time steps, standard algorithms randomly reassign cluster IDs between frames. This caused colors to flicker chaotically in the animation.
To fix this, we created a Global Label Matching algorithm. For each new time frame, it takes a stochastic sample of 200 points per cluster, finds their nearest neighbors in the previous frame, and performs spatial majority voting with greedy assignment.
This keeps colors and cluster identities perfectly stable across the entire animation."

[VISUAL ACTION: Explain the color flickering problem on the left and the smooth spatial voting solution on the right]""",

    # SLIDE 12
    """[SLIDE 12 | TIME: 7:45 - 8:30 | TARGET: 45 SECONDS]

SPEECH (EN):
"Now, let's look at the data engineering pipeline and the choices we made.

The application ingests data either by querying the INGV GOSSIP REST API online, or through local CSV files. It handles coordinate conversion, date parsing, and metadata cleaning.
Here, we made a crucial design choice regarding missing depths: earthquakes with null or missing depth are kept in the 2D catalogue for completeness, but they are strictly excluded from 3D and 4D spatial computations. Otherwise, they would artificially flatten onto sea level at depth zero and corrupt fault plane fitting.

Furthermore, to avoid sending bulky JSON over the wire, we built a Float32 binary streaming protocol.
Instead of parsing thousands of JSON objects, the server streams a raw, contiguous Float32 binary buffer directly into a JavaScript typed array. This slashed payload size by nearly 80% and dropped browser unpacking time from 40 milliseconds to less than 0.01 milliseconds."

[VISUAL ACTION: Point to the data pipeline steps and highlight the 80% compression and instant parsing]""",

    # SLIDE 13
    """[SLIDE 13 | TIME: 8:30 - 9:15 | TARGET: 45 SECONDS]

SPEECH (EN):
"To validate the system, we carried out extensive benchmarks:

First, in Monte Carlo simulations across 500 synthetic faults with noise and 30% random outliers, our RANSAC-SVD method achieved a Mean Absolute Error under 0.5 degrees for Dip, and under 0.9 degrees for Strike.
Second, on the real Campi Flegrei catalogue of over 3,200 earthquakes, clustering and plane fitting completed in less than 42 milliseconds.
Third, in stress tests with 50,000 synthetic hypocenters, WebGL maintained a smooth 55 to 60 frames per second.
And memory management benchmarks confirmed that our session caching and garbage collection keep RAM usage strictly below 500 megabytes throughout extended sessions."

[VISUAL ACTION: Point to the validation metrics in the table: Monte Carlo MAE, 42ms clustering, 60 FPS stress test]""",

    # SLIDE 14
    """[SLIDE 14 | TIME: 9:15 - 9:40 | TARGET: 25 SECONDS]

SPEECH (EN):
"In conclusion, Seismic Viewer delivers a lightweight, accessible, and fast tool that bridges the gap between raw seismological data and interactive 3D and 4D exploration.
It was developed and validated in close collaboration with INGV researchers to directly support volcano monitoring.
Looking ahead, future improvements will focus on real-time WebSocket push notifications from INGV feeds, WebGPU shaders for on-the-fly clustering, and focal mechanism beachball inversions.

Thank you very much for your time and attention. I would be glad to answer any questions."

[VISUAL ACTION: Thank the committee and supervisors, open the floor for Q&A at exactly ~9m 40s]"""
]

prs = pptx.Presentation('thesis/presentation/Seismic Viewer - Thesis Defense.pptx')
assert len(prs.slides) == len(SPEECH_NOTES_INFORMAL_ACADEMIC), f"Mismatch: {len(prs.slides)} slides vs {len(SPEECH_NOTES_INFORMAL_ACADEMIC)} notes"

for i, slide in enumerate(prs.slides):
    notes_slide = slide.notes_slide
    tf = notes_slide.notes_text_frame
    tf.text = SPEECH_NOTES_INFORMAL_ACADEMIC[i]

prs.save('thesis/presentation/Seismic Viewer - Thesis Defense.pptx')
print("Successfully injected all 14 informal-academic English notes into 'Seismic Viewer - Thesis Defense.pptx'!")
