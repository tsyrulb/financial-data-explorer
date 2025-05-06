import React from 'react';
import { LineChart } from '@mui/x-charts/LineChart';
import { ChartsXAxis } from '@mui/x-charts/ChartsXAxis';
import { ChartsYAxis } from '@mui/x-charts/ChartsYAxis';

// Define the type for a single time series data point (matches App.tsx)
type TimeSeriesDataPoint = {
  date: string; // ISO 8601 date string
  [key: string]: number | string; // The value column name is dynamic (e.g., 'UNRATE', 'CPIAUCSL')
};

// Define the type for the fetched time series data (matches App.tsx)
type FetchedTimeSeriesData = {
  [datasetName: string]: TimeSeriesDataPoint[];
};

// Define the props for the TimeSeriesChart component
interface TimeSeriesChartProps {
  data: FetchedTimeSeriesData; // The dictionary of fetched data
  width?: number; // Optional width prop
  height?: number; // Optional height prop
}

const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({ data, width = 600, height = 300 }) => {

  // --- Prepare data for MUI X Charts ---
  // MUI X LineChart typically expects:
  // 1. An array of common X-axis values (dates)
  // 2. An array of series configurations, each with its data (array of numbers)

  const datasetNames = Object.keys(data);

  if (datasetNames.length === 0) {
    return <p>No data available to display chart.</p>;
  }

  // Find the union of all dates across all selected series
  // This is necessary because series might start/end on different dates
  const allDates = new Set<string>();
  datasetNames.forEach(name => {
    data[name].forEach(point => allDates.add(point.date));
  });

  // Sort the unique dates chronologically
  const sortedDates = Array.from(allDates).sort((a, b) => new Date(a).getTime() - new Date(b).getTime());

  // Prepare the series data
  const series = datasetNames.map((name, index) => {
    // Create a map for quick lookup of value by date for the current series
    const dataMap = new Map<string, number | string>();
    data[name].forEach(point => dataMap.set(point.date, point[name]));

    // Create the data array for this series, aligning with the sortedDates
    const seriesData = sortedDates.map(date => {
      // Get the value for this date, or null if the series doesn't have data for this date
      const value = dataMap.get(date);
      // Convert value to number, handling potential nulls or non-numeric data
      return typeof value === 'number' ? value : (value !== undefined && value !== null ? parseFloat(String(value)) : null);
    });

    // Assign a color based on the index (simple approach)
    const colors = [
      '#4CAF50', // Green
      '#FF5722', // Deep Orange
      '#2196F3', // Blue
      '#FFC107', // Amber
      '#9C27B0', // Purple
      '#607D8B'  // Blue Grey
    ];
     const color = colors[index % colors.length];

    return {
      data: seriesData, // Array of values corresponding to sortedDates
      label: name, // Use the dataset name as the label
      color: color, // Assign color
      curve: 'linear' as const, // 'linear', 'natural', 'step'
      showMark: false, // Hide data points
    };
  });

  // Convert sorted date strings to Date objects for the x-axis
  const xData = sortedDates.map(dateStr => new Date(dateStr));

  // --- Render the Chart ---
  return (
    <div style={{ width: '100%', height: height }}> {/* Use height prop for container */}
       {/* MUI X LineChart component */}
      <LineChart
        xAxis={[{
          data: xData,
          scaleType: 'time', // Use time scale for the x-axis
          valueFormatter: (date) => date?.toLocaleDateString() || '', // Format date for tooltip/axis
          // position: 'bottom' is the default for the primary x-axis,
          // so no need to specify it here unless you want 'top'
        }]}
        series={series} // Pass the prepared series data
        width={width} // Use width prop
        height={height} // Use height prop
        margin={{ top: 40, right: 20, bottom: 60, left: 60 }} // Adjust margins
      >
         {/* Render X and Y axes */}
        {/* REMOVED position="bottom" from ChartsXAxis */}
        <ChartsXAxis label="Date" />
        <ChartsYAxis label="Value" />
        {/* Tooltip and Legend are included by default */}
      </LineChart>
    </div>
  );
};

export default TimeSeriesChart;
