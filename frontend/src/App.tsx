import { useState, useEffect, useMemo } from "react";
import TimeSeriesChart from "./components/TimeSeriesChart";
import "./App.css"; // Keep your CSS file import

export type TimeSeriesPoint = {
  date: string; // ISO 8601 date string
  // Value can be number or string (like '.') initially, but we expect number after processing
  [key: string]: number | string;
};

export type SeriesPayload = Record<string, TimeSeriesPoint[]>;

const API = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5000";

// Helper function to build query string from an object
const qs = (o: Record<string, string>) =>
  Object.entries(o)
    .filter(([, v]) => v) // Filter out empty values
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`) // Encode values
    .join("&"); // Join with &


export default function App() {
  // ── State ────────────────────────────────────────────────────────────────
  // State for the list of all available dataset names fetched from backend
  const [datasets, setDatasets] = useState<string[]>([]);
  // State for the dataset names currently selected by the user
  const [selected, setSelected] = useState<string[]>([]);
  // State for the actual time series data fetched from the backend for selected datasets
  const [payload, setPayload] = useState<SeriesPayload>({});

  // State to handle loading and errors for *all* data fetching (catalogue and series)
  const [loading, setLoading] = useState(false);
  // State to store error messages
  const [error, setError] = useState<string | null>(null);

  // State for filters / transforms (to be sent as query parameters to backend)
  const [start, setStart] = useState(""); // Start date filter
  const [end, setEnd] = useState(""); // End date filter
  const [frequency, setFrequency] = useState("d"); // Data frequency (daily, weekly, etc.)
  const [transform, setTransform] = useState(""); // Data transformation (index_100, etc.)

  // ── Catalogue Fetch (runs once on mount) ─────────────────────────────────────
  useEffect(() => {
    setLoading(true); // Start loading indicator for initial fetch
    fetch(`${API}/api/datasets`)
      .then((r) => {
        if (!r.ok) {
          throw new Error(`HTTP error fetching datasets: ${r.statusText}`);
        }
        return r.json();
      })
      .then(setDatasets) // Update state with the list of dataset names
      .catch((e) => {
        console.error("Failed to fetch datasets:", e);
        setError(`Failed to load datasets: ${String(e)}`); // Set error state
      })
      .finally(() => setLoading(false)); // End loading indicator
  }, []); // Empty dependency array means this effect runs only once

  // ── Series Fetch (debounced effect triggered by selections/filters) ────────────
  useEffect(() => {
    // If no datasets are selected, clear the payload and stop loading
    if (!selected.length) {
      setPayload({});
      setError(null); // Clear any previous errors
      setLoading(false); // Ensure loading is false if selection is empty
      return;
    }

    // Start loading state when selection or filters change
    setLoading(true);
    setError(null); // Clear previous errors

    const ctrl = new AbortController();

    const id = setTimeout(async () => {
      try {
        const resObj: SeriesPayload = {};
        // Fetch data for each selected dataset concurrently
        await Promise.all(
          selected.map(async (sid) => {
            // Construct the URL with query parameters for filters/transforms
            const url = `${API}/api/data/${sid}?` + qs({ start, end, frequency, transform });
            const res = await fetch(url, { signal: ctrl.signal }); // Pass signal for aborting
            if (!res.ok) {
              throw new Error(`${sid}: ${res.statusText || 'Failed to fetch'}`);
            }
            const dataPoints: TimeSeriesPoint[] = await res.json();

             const formattedData = dataPoints.map(point => {
                 const value = point.value !== undefined ? point.value : point[sid]; 
                 return { date: point.date, [sid]: value } as TimeSeriesPoint;
             });


            resObj[sid] = formattedData; // Store fetched data by dataset name
          })
        );
        // Update the payload state with the fetched data for all selected series
        setPayload(resObj);
        setError(null); // Clear error if all fetches were successful
      } catch (e) {
        // Catch any errors during the fetch process (network issues, HTTP errors, aborts)
        if (e instanceof Error) {
             // Check if the error was due to aborting (user changed selection quickly)
             if (e.name === 'AbortError') {
                 console.log('Fetch aborted:', e.message);
                 // No need to set error state for aborts, just stop loading
             } else {
                console.error("Failed to fetch time series data:", e);
                setError(`Failed to load data: ${e.message}`); // Set error state
                setPayload({}); // Clear data on error
             }
        } else {
             // Handle unexpected error types
             console.error("An unexpected error occurred during fetch:", e);
             setError(`An unexpected error occurred: ${String(e)}`);
             setPayload({}); // Clear data on error
        }
      } finally {
        // Set loading to false once fetching is complete (whether success, error, or abort)
         // Only set loading to false if it's not an abort error, as a new fetch might start immediately
         if (ctrl.signal.aborted) {
             console.log("Fetch aborted, new fetch likely started.");
         } else {
            setLoading(false); // End loading state
         }
      }
    }, 300); // Debounce delay

    // Cleanup function: This runs when the component unmounts or when the dependencies change
    // before the next effect runs. It clears the timeout and aborts the fetch.
    return () => {
      clearTimeout(id);
      ctrl.abort(); // Abort any ongoing fetch requests
    };
  }, [selected, start, end, frequency, transform]); // Dependencies: Re-run effect if any of these change

  // Memoize the check for whether we have data to display
  const hasData = useMemo(() => Object.keys(payload).length > 0, [payload]);

  // Handler for selecting/deselecting datasets (used by the chips)
  const toggle = (sid: string) => setSelected((p) => (p.includes(sid) ? p.filter((x) => x !== sid) : [...p, sid]));

  // ── UI Layout ────────────────────────────────────────────────────────────
  return (
    // Main container with background gradients and minimum height
    <div className="min-h-screen text-neutral-100 bg-gradient-to-br from-[#111] via-[#1a1a1a] to-[#202225] relative overflow-hidden">
      {/* Backdrop blob - purely decorative */}
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-teal-600/20 via-indigo-600/10 to-transparent" />

      {/* Header */}
      <header className="h-14 flex items-center gap-3 pl-4 pr-6 border-b border-neutral-800 backdrop-blur-md bg-neutral-900/60 sticky top-0 z-20">
        {/* SVG Icon Placeholder - ensure you have this icon defined elsewhere */}
        {/* Example: In your index.html or as a separate SVG component */}
        <svg width="18" height="18" className="text-teal-400"><use href="#icon-chart" /></svg>
        <h1 className="font-semibold tracking-wide text-lg">Financial&nbsp;Data&nbsp;Explorer</h1>
        {/* Link to FRED website */}
        <a href="https://fred.stlouisfed.org/" target="_blank" rel="noopener noreferrer" className="ml-auto text-xs text-neutral-400 hover:text-teal-400 transition-colors">Powered by FRED</a>
      </header>

      {/* Main content area - uses grid layout */}
      <main className="grid md:grid-cols-[260px_1fr] xl:grid-cols-[280px_1fr] gap-6 p-4 pb-10 max-w-screen-2xl mx-auto">
        {/* Sidebar for dataset selection */}
        {/* Hidden on small screens, flex column on medium and larger */}
        <aside className="hidden md:flex flex-col max-h-[85vh] rounded-xl bg-neutral-900/70 border border-neutral-800 backdrop-blur-md overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-800">
            <h2 className="font-medium text-sm tracking-wide">Datasets</h2>
            {/* Display number of available datasets */}
            <p className="text-[10px] text-neutral-500">{datasets.length} available</p>
          </div>
          {/* Scrollable area for dataset chips */}
          <div className="flex-1 overflow-y-auto p-3 flex flex-wrap gap-1 content-start">
            {/* Map through available datasets to create clickable chips */}
            {datasets.map((sid) => (
              <button
                key={sid}
                onClick={() => toggle(sid)} // Toggle selection on click
                // Apply active class if dataset is selected
                className={`dataset-chip ${selected.includes(sid) ? "dataset-chip--active" : ""}`}
              >
                {sid}
              </button>
            ))}
          </div>
        </aside>

        {/* Main column for controls and chart */}
        <section className="flex flex-col gap-6">
          {/* Controls panel for filters and transforms */}
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4 p-4 rounded-xl bg-neutral-900/70 backdrop-blur-md border border-neutral-800">
            {/* Date inputs (Start and End) */}
            {[{ lbl: "Start", val: start, set: setStart }, { lbl: "End", val: end, set: setEnd }].map(({ lbl, val, set }) => (
              <div key={lbl} className="flex flex-col gap-1">
                <label className="text-[11px] text-neutral-400">{lbl}</label>
                {/* Input type date with value and change handler */}
                <input type="date" value={val} onChange={(e) => set(e.target.value)} />
              </div>
            ))}
            {/* Frequency Select */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-neutral-400">Freq</label>
              <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
                <option value="d">Daily</option>
                <option value="w">Weekly</option>
                <option value="m">Monthly</option>
                <option value="q">Quarterly</option>
                <option value="a">Annual</option>
              </select>
            </div>
            {/* Transform Select */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-neutral-400">Transform</label>
              <select value={transform} onChange={(e) => setTransform(e.target.value)}>
                <option value="">None</option>
                <option value="index_100">Index 100</option>
                {/* Add other transform options as implemented in backend */}
                {/* <option value="pct_change">% Change</option> */}
                {/* <option value="log_return">Log Return</option> */}
              </select>
            </div>
            {/* Clear Selection Button */}
            <button
              onClick={() => setSelected([])}
              className="col-span-2 sm:col-span-1 flex items-center justify-center rounded bg-red-600/70 hover:bg-red-600 transition-colors text-xs font-medium px-4 py-2" // Added padding for better click area
            >
              Clear Selection
            </button>
          </div>

          {/* Chart Area */}
          <div className="relative flex-1 min-h-[420px] rounded-xl bg-neutral-900/70 border border-neutral-800 backdrop-blur-md p-4 flex items-center justify-center"> {/* Added flex centering for messages */}
            {/* Loading Overlay */}
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-neutral-900/60 backdrop-blur-sm rounded-xl z-10">
                <span className="animate-pulse text-neutral-400 text-sm">Fetching data…</span>
              </div>
            )}
            {/* Error Message */}
            {error && !loading && (
              <div className="text-red-400 text-sm text-center">
                <p>Error: {error}</p>
                {/* Optional: Add a retry button */}
                {/* <button onClick={fetchSeriesData} className="mt-2 text-blue-400 hover:underline">Retry</button> */}
              </div>
            )}
            {/* Chart Component or Placeholder Messages */}
            {!loading && !error && (
              hasData ? (
                // Render the TimeSeriesChart component if data is available
                // Pass the fetched payload and set a height
                <div style={{ width: '100%', height: '100%' }}> {/* Container to make chart fill area */}
                    <TimeSeriesChart data={payload} height={400} /> {/* Pass data and height */}
                </div>
              ) : (
                // Display message if no data is available
                <div className="text-neutral-500 text-sm text-center">
                    {selected.length ? "No data for selected parameters or series." : "Select datasets on the left to visualize data."}
                </div>
              )
            )}
          </div>

          {/* Controls for Correlation/Transformations Placeholder (Future) */}
          {/* You can add more complex controls here later */}
          {/*
          <div className="controls-panel p-4 rounded-xl bg-neutral-900/70 backdrop-blur-md border border-neutral-800">
             <h3>Analysis Controls</h3>
             <p className="text-neutral-400 text-sm">Add controls for rolling correlation, event markers here.</p>
             {/* Example: <CorrelationControls selectedDatasets={selected} onCalculate={handleCalculateCorrelation} /> }
          </div>
          */}

        </section>
      </main>

       {/* Mobile Dataset Selection (Optional - requires more work) */}
       {/* You might want a modal or slide-out panel for dataset selection on small screens */}
       {/*
       <div className="md:hidden fixed bottom-4 right-4 z-30">
           <button className="p-3 rounded-full bg-teal-600 text-white shadow-lg">
               <svg width="24" height="24"><use href="#icon-list" /></svg>
           </button>
       </div>
       */}

    </div>
  );
}
