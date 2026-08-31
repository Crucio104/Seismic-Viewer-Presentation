import re

with open('/Users/helloworld/Downloads/thesis/chapters/03_architecture.tex', 'r') as f:
    original = f.read()

# We need to prepend the missing content to the rest of the file, starting from \subsection{Binary Data Transfer Protocol}
# First, let's extract everything from \subsection{Binary Data Transfer Protocol} onwards.
marker = "\\subsection{Binary Data Transfer Protocol}"
if marker in original:
    rest_of_file = original[original.find(marker):]
else:
    rest_of_file = original

new_content = r"""% ══════════════════════════════════════════════════════════════════════
% CHAPTER 3: SYSTEM ARCHITECTURE
% ══════════════════════════════════════════════════════════════════════

\chapter{System Architecture}
\label{ch:architecture}

This chapter presents the software architecture of Seismic Viewer, detailing the separation between computation and presentation, the communication protocols linking them, and the concurrency model ensuring interactive responsiveness.

\section{High-Level Architecture Overview}
\label{sec:high-level}

Seismic Viewer follows a \textbf{dual-process hybrid architecture} combining a Python scientific processing backend with an embedded Chromium-based frontend. The layers communicate via three distinct channels tailored to specific operational requirements.

\begin{figure}[htbp]
\centering
\begin{tikzpicture}[node distance=1.5cm, auto, scale=0.85, transform shape]
    \node (chromium) [module, minimum width=3.5cm, fill=blue!10] {Chromium Frontend};
    \node (python) [module, minimum width=3.5cm, fill=yellow!10, below=2cm of chromium] {Python Backend};
    
    \draw[<->, thick] (chromium.south west) -- node[left] {pywebview API} (python.north west);
    \draw[<->, thick] (chromium.south) -- node[fill=white] {WebSocket} (python.north);
    \draw[<->, thick] (chromium.south east) -- node[right] {REST API} (python.north east);
\end{tikzpicture}
\caption{System architecture highlighting the three Python-Chromium communication channels.}
\label{fig:architecture}
\end{figure}

\begin{itemize}
    \item \textbf{pywebview Bridge} (\texttt{js\_api}): This channel handles synchronous method calls between Python and JavaScript. It is primarily dedicated to low-latency graphical user interface (GUI) interactions, such as opening native file dialogs, managing application navigation, and handling configuration settings.
    \item \textbf{FastAPI REST API}: Designed for high-throughput data transfer, this channel exposes HTTP endpoints that deliver both session metadata (via \texttt{/api/data/\{id\}}) and fully pre-rendered HTML visualisations (via \texttt{/viz/\{id\}}). To ensure optimal performance with large datasets, it employs GZip compression and transmits heavy numerical arrays as raw Float32 binary buffers.
    \item \textbf{WebSocket}: This bidirectional communication protocol is essential for continuous, asynchronous data exchange. It is specifically used to push real-time progress updates to the user interface during long-running tasks, as well as to handle interactive features like dynamic spatial analysis and the calculation of structural planes on the fly.
\end{itemize}

\begin{table}[htbp]
\centering
\caption{REST API endpoints (\Cref{tab:rest-api}) and WebSocket message protocol (\Cref{tab:ws-messages}).}
\label{tab:rest-api}
\label{tab:ws-messages}
\footnotesize
\renewcommand{\arraystretch}{1.1}
\begin{tabularx}{\textwidth}{@{}l l X@{}}
\toprule
\textbf{Protocol / Endpoint} & \textbf{Direction / Path} & \textbf{Description / Message Types} \\
\midrule
REST (\texttt{GET}) & \texttt{/api/data/\{session\_id\}} & Retrieve session data as GZip-compressed JSON \\
REST (\texttt{GET}) & \texttt{/api/data/\{session\_id\}/bin} & Retrieve numerical data as Float32 binary buffer \\
REST (\texttt{GET}) & \texttt{/viz/\{viz\_id\}} & Serve pre-rendered HTML visualisation page \\
\midrule
WebSocket & Client $\to$ Server & \texttt{ping}, \texttt{get\_cluster\_update}, \texttt{get\_structural\_planes}, \texttt{get\_animated\_clustering} \\
WebSocket & Server $\to$ Client & \texttt{pong}, \texttt{rpc\_response}, \texttt{progress} (broadcast messages) \\
\bottomrule
\end{tabularx}
\end{table}

\section{Backend Architecture}
\label{sec:backend}

\subsection{Application Entry Point \& Bridge Engine}
\label{sec:bridge}

Once the application is running, the \texttt{Api} module acts as the central coordinator. Whenever the user interacts with the interface, such as selecting a file (\texttt{select\allowbreak\_csv()}), loading a 3D view (\texttt{load\allowbreak\_view()}), or exporting results (\texttt{export\allowbreak\_clusters\allowbreak\_csv()}), the frontend sends a request directly to this coordinator.

Many of these requests trigger computationally intensive mathematical operations, including advanced spatial analysis of seismic events. If the software were to perform these calculations on its main execution thread, the entire graphical interface would become unresponsive until the tasks were completed. To prevent this behavior, all heavy processing is delegated to background workers using the \texttt{threading.Thread} module.

Since the calculations occur in the background, the application requires a mechanism to inform the user about the ongoing progress. The coordinator handles this requirement by continuously transmitting real-time updates back to the interface. This ensures the user is constantly provided with a responsive progress bar or status message, resulting in a fluid and stable user experience. These updates are broadcast through the WebSocket protocol.

\subsection{Session Store \& FastAPI Middleware}
\label{sec:session-store}

The system architecture requires a dedicated memory management layer to preserve state between user interactions and to serve data efficiently to the graphical frontend. This functionality is centralized within an internal configuration module (\texttt{core/config.py}), which orchestrates two separate in-memory caches: \texttt{\_data\_store} and \texttt{\_html\_store}.

The \texttt{\_data\_store} structure retains the raw numerical arrays and metadata associated with each active analytical session. To guarantee that the application maintains a stable memory profile even during extensive analytical workflows, this cache is strictly limited to 30 concurrent sessions. In parallel, the \texttt{\_html\_store} caches up to 15 pre-rendered graphical views, allowing the frontend to load complex tridimensional scenes instantaneously. Both structures implement a First-In, First-Out (FIFO) eviction policy. This strategy effectively bounds the overall Random Access Memory utilization without requiring manual intervention from the user.

Positioned between this caching layer and the client interface, the FastAPI server deploys specific middleware to optimize network throughput. The most critical optimization is the automatic application of GZip compression for any outgoing data payload larger than 500 bytes. Compressing the data prior to transmission significantly accelerates the rendering process, particularly when transferring datasets containing tens of thousands of seismic events.

\section{Frontend Architecture}
\label{sec:frontend}

\subsection{Single-Page Application \& UI/UX Design}
\label{sec:spa}

\begin{figure}[htbp]
\centering
\begin{subfigure}{0.48\textwidth}
\includegraphics[width=\textwidth]{images/start_page.png}
\caption{File Picker view (Landing screen with INGV API access).}
\label{fig:start-page}
\end{subfigure}\hfill
\begin{subfigure}{0.48\textwidth}
\includegraphics[width=\textwidth]{images/visualization_hub.png}
\caption{Visualisation Hub with mode selection and auxiliary layer bar.}
\label{fig:viz-hub}
\end{subfigure}
\caption{The Seismic Viewer single-page application structure, showing initial data loading (\subref{fig:start-page}) and the multi-mode analytical selection hub (\subref{fig:viz-hub}).}
\label{fig:gui-hub}
\end{figure}

As illustrated in \Cref{fig:gui-hub}, the primary workflow begins at the landing screen (\subref{fig:start-page}). Here, the system exposes multiple data ingestion pathways, allowing researchers to import local csv files, query the INGV remote web services directly, or restore a previously interrupted session through local historical records.

Once the imported dataset is validated, the software transitions to the visualization hub (\subref{fig:viz-hub}). This primary analytical workspace features specific menus to alternate between the available visualization and analysis algorithms. Furthermore, it incorporates interactive toggles to overlay supplementary spatial context onto the 3D map, facilitating the visual integration of seismic tomography models, GNSS deformation grids, and local monitoring stations.

The 3D rendering pipeline delegates all plotting operations to the WebGL graphics API via the Plotly framework. A critical implementation detail within this rendering layer is the enforcement of a constant user interface revision state across all graphical layouts. By locking this internal property, the engine prevents the virtual camera from resetting its spatial position when new data arrives. Consequently, the software preserves the specific spatial orientation and zoom level chosen by the user even while the system continuously updates and re-processes the underlying data in real time.

\begin{figure}[htbp]
\centering
\begin{tikzpicture}[node distance=1.4cm, auto, scale=0.82, transform shape]
    \node (input) [io] {CSV / INGV API};
    \node (loader) [process, below of=input] {Loader \& Sanitisation};
    \node (precomp) [process, below of=loader] {Visual Pre-computation};
    \node (decision) [decision, below of=precomp, yshift=-0.2cm] {View Style?};
    \node (engine) [process, below of=decision, yshift=-0.4cm] {Engine (Viz/Analysis)};
    \node (template) [process, below of=engine] {HTML Template Assembly};
    \node (store) [io, below of=template] {Session Store + HTML Store};
    \node (render) [startstop, below of=store] {WebGL Rendering};

    \draw [arrow] (input) -- (loader);
    \draw [arrow] (loader) -- (precomp);
    \draw [arrow] (precomp) -- (decision);
    \draw [arrow] (decision) -- node[left, font=\scriptsize] {0/1/2/3/4} (engine);
    \draw [arrow] (engine) -- (template);
    \draw [arrow] (template) -- (store);
    \draw [arrow] (store) -- (render);
    \draw [dashedarrow] (store.east) -- ++(2.4,0) node[right, font=\scriptsize, text width=3.2cm] {Binary Float32 buffer via \texttt{/api/data/\{id\}/bin}};
\end{tikzpicture}
\caption{Linear data pipeline from input parsing to WebGL drawing.}
\label{fig:dataflow}
\end{figure}

\section{Data Flow Pipeline \& Protocols}
\label{sec:dataflow}
\label{sec:protocols}

In order to manage the entire data lifecycle within the application, Seismic Viewer divides its data flow operations clearly between the backend services and the frontend client. This separation is fundamental to maintain performance and ensure responsiveness.

\subsection{Backend Data Processing}
The backend architecture is responsible for all heavy lifting regarding data ingestion, validation, and complex mathematical analysis. As outlined in \Cref{fig:dataflow}, the pipeline begins by importing the CSV dataset or fetching remote data from the INGV API. This data undergoes an initial sanitization and loading phase. Following this, visual pre-computation prepares the structural elements before the engine applies the required analytical algorithm chosen by the researcher. Finally, the results are assembled into an HTML template and stored in the internal \texttt{\_data\_store} and \texttt{\_html\_store} caches, ready to be served.

\subsection{Frontend Rendering and Communication}
Once the backend processing is complete, the frontend seamlessly retrieves the data through the defined REST API and WebSocket endpoints (\Cref{tab:rest-api}). The frontend dynamically renders the 3D scene using WebGL via the Plotly.js library. Continuous status updates, real-time recalculations, and on-the-fly filtering commands are exchanged over the WebSocket channel, ensuring the interface remains fully interactive without necessitating page reloads.

"""

with open('/Users/helloworld/Downloads/thesis/chapters/03_architecture.tex', 'w') as f:
    f.write(new_content + rest_of_file)

print("Done restoring and modifying!")
