import { useState, useEffect } from "react";
import "./App.css"; // Keep or remove this depending on your styling needs
import TimeSeriesChart from "./components/TimeSeriesChart"; // Import the new chart component

// Define the type for the data we expect from the /api/datasets endpoint
type DatasetNames = string[];

// Define the type for a single time series data point
// Matches the JSON structure from /api/data/<dataset_name>
type TimeSeriesDataPoint = {
  date: string; // ISO 8601 date string
  [key: string]: number | string; // The value column name is dynamic (e.g., 'UNRATE', 'CPIAUCSL')
};

// Define the type for the fetched time series data
// A dictionary where keys are dataset names and values are arrays of data points
type FetchedTimeSeriesData = {
  [datasetName: string]: TimeSeriesDataPoint[];
};

function App() {
  // State for the list of all available dataset names
  const [availableDatasets, setAvailableDatasets] = useState<DatasetNames>([]);
  // State for the dataset names currently selected by the user
  const [selectedDatasets, setSelectedDatasets] = useState<DatasetNames>([]);
  // State for the actual time series data fetched from the backend for selected datasets
  const [timeSeriesData, setTimeSeriesData] = useState<FetchedTimeSeriesData>(
    {}
  );

  // State to handle loading and errors for fetching the *list* of datasets
  const [loadingDatasets, setLoadingDatasets] = useState<boolean>(true);
  const [errorLoadingDatasets, setErrorLoadingDatasets] =
    useState<Error | null>(null);

  // State to handle loading and errors for fetching the *time series data*
  const [loadingTimeSeries, setLoadingTimeSeries] = useState<boolean>(false);
  const [errorLoadingTimeSeries, setErrorLoadingTimeSeries] =
    useState<Error | null>(null);

  // Define the base URL for your backend API
  const API_BASE_URL: string = "http://127.0.0.1:5000"; // !! Make sure this matches your backend URL !!

  // --- Effect to fetch the list of available datasets (runs once on mount) ---
  useEffect(() => {
    const fetchAvailableDatasets = async (): Promise<void> => {
      try {
        setLoadingDatasets(true); // Start loading state
        const response: Response = await fetch(`${API_BASE_URL}/api/datasets`);

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data: DatasetNames = await response.json();
        setAvailableDatasets(data); // Store the list of names
      } catch (error: unknown) {
        console.error("Failed to fetch available datasets:", error);
        setErrorLoadingDatasets(
          error instanceof Error ? error : new Error(String(error))
        );
      } finally {
        setLoadingDatasets(false); // End loading state
      }
    };

    fetchAvailableDatasets();
  }, []); // Empty dependency array means this runs only once

  // --- Handler for selecting/deselecting datasets ---
  const handleDatasetSelect = (datasetName: string): void => {
    setSelectedDatasets((prevSelected) => {
      // Check if the dataset is already selected
      if (prevSelected.includes(datasetName)) {
        // If selected, remove it (deselect)
        return prevSelected.filter((name) => name !== datasetName);
      } else {
        // If not selected, add it (select)
        // Optional: Limit the number of selected datasets for clarity on the chart
        // if (prevSelected.length < 5) { // Example limit
        return [...prevSelected, datasetName];
        // } else {
        //    alert("You can select up to 5 datasets for comparison.");
        //    return prevSelected; // Don't add if limit reached
        // }
      }
    });
  };

  // --- Function to fetch time series data for selected datasets ---
  const fetchTimeSeriesData = async (): Promise<void> => {
    if (selectedDatasets.length === 0) {
      setTimeSeriesData({}); // Clear data if nothing is selected
      setErrorLoadingTimeSeries(null);
      return; // Nothing to fetch
    }

    setLoadingTimeSeries(true); // Start loading state for time series data
    setErrorLoadingTimeSeries(null); // Clear previous errors
    const fetchedData: FetchedTimeSeriesData = {};

    try {
      // Fetch data for each selected dataset concurrently
      const fetchPromises = selectedDatasets.map(async (datasetName) => {
        const response = await fetch(`${API_BASE_URL}/api/data/${datasetName}`);
        if (!response.ok) {
          // If fetching a single series fails, throw an error to be caught below
          throw new Error(
            `Failed to fetch data for ${datasetName}: ${response.statusText}`
          );
        }
        const data: TimeSeriesDataPoint[] = await response.json();
        fetchedData[datasetName] = data; // Store fetched data by dataset name
      });

      // Wait for all fetch promises to complete
      await Promise.all(fetchPromises);

      // Update the state with the fetched data for all selected series
      setTimeSeriesData(fetchedData);
    } catch (error: unknown) {
      console.error("Failed to fetch time series data:", error);
      setErrorLoadingTimeSeries(
        error instanceof Error ? error : new Error(String(error))
      );
      setTimeSeriesData({}); // Clear data on error
    } finally {
      setLoadingTimeSeries(false); // End loading state
    }
  };

  // --- Render the UI ---
  return (
    <div className="App">
      <header className="App-header">
        <h1>Financial Data Explorer</h1>
      </header>
      <main className="main-content">
        {" "}
        {/* Add a class for layout */}
        <div className="dataset-selection-panel">
          {" "}
          {/* Panel for dataset list */}
          <h2>Available Datasets</h2>
          {loadingDatasets && <p>Loading datasets list...</p>}
          {errorLoadingDatasets && (
            <p>Error loading datasets list: {errorLoadingDatasets.message}</p>
          )}
          {!loadingDatasets &&
            !errorLoadingDatasets &&
            (availableDatasets.length > 0 ? (
              <ul>
                {/* Map over available datasets to create selectable list items */}
                {availableDatasets.map((datasetName: string, index: number) => (
                  <li
                    key={index}
                    // Add a class to style selected items
                    className={
                      selectedDatasets.includes(datasetName) ? "selected" : ""
                    }
                    // Add click handler to select/deselect
                    onClick={() => handleDatasetSelect(datasetName)}
                    style={{ cursor: "pointer" }} // Indicate it's clickable
                  >
                    {datasetName}
                  </li>
                ))}
              </ul>
            ) : (
              <p>No datasets found.</p>
            ))}
        </div>
        <div className="chart-area">
          {" "}
          {/* Area for the chart and controls */}
          <h2>Selected Datasets</h2>
          {/* Display selected dataset names */}
          <p>Selected: {selectedDatasets.join(", ") || "None"}</p>
          {/* Button to trigger data fetching */}
          <button
            onClick={fetchTimeSeriesData}
            disabled={selectedDatasets.length === 0 || loadingTimeSeries} // Disable if nothing selected or loading
          >
            {loadingTimeSeries ? "Loading Data..." : "Load Data & Show Chart"}
          </button>
          {/* Display loading/error states for time series data */}
          {errorLoadingTimeSeries && (
            <p style={{ color: "red" }}>
              Error loading data: {errorLoadingTimeSeries.message}
            </p>
          )}
          {loadingTimeSeries && <p>Fetching time series data...</p>}
          {/* --- Charting Component Integration --- */}
          {/* Render the chart only if data is loaded and there's no error and data is available */}
          {!loadingTimeSeries &&
            !errorLoadingTimeSeries &&
            Object.keys(timeSeriesData).length > 0 && (
              <div
                className="data-visualization"
                style={{ width: "100%", height: "500px" }}
              >
                {" "}
                {/* Added style for chart container */}
                {/* Render the TimeSeriesChart component, passing the fetched data */}
                <TimeSeriesChart data={timeSeriesData} height={500} />{" "}
                {/* Pass height prop */}
              </div>
            )}
          {/* Message to prompt user to load data */}
          {!loadingTimeSeries &&
            !errorLoadingTimeSeries &&
            selectedDatasets.length > 0 &&
            Object.keys(timeSeriesData).length === 0 && (
              <p>Click "Load Data & Show Chart" to fetch data.</p>
            )}
          {/* Message when no datasets are selected */}
          {!loadingDatasets &&
            !errorLoadingDatasets &&
            selectedDatasets.length === 0 && (
              <p>Select datasets from the list to the left.</p>
            )}
          {/* --- Controls for Correlation/Transformations Placeholder --- */}
          {/* This is where you'll add controls for rolling correlation, normalization, etc. */}
          <div className="controls-panel">
            <h3>Analysis Controls Placeholder</h3>
            <p>
              Add controls for rolling correlation, normalization, event markers
              here.
            </p>
            {/* Example: <CorrelationControls selectedDatasets={selectedDatasets} onCalculate={handleCalculateCorrelation} /> */}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
