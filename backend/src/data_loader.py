import pandas as pd
import os

# Define the path to the data directory
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'public_datasets')

def load_fred_csv(file_name):
    """
    Loads a FRED CSV file, assuming a simple format
    with 'observation_date' and the series ticker as columns.
    Sets 'observation_date' as the index and converts it to datetime.
    """
    file_path = os.path.join(DATA_DIR, file_name)
    try:
        # Read the CSV, assuming the first row is the header
        # Use 'observation_date' as the index column and parse dates
        df = pd.read_csv(file_path, index_col='observation_date', parse_dates=True)

        # The column name will be the series ticker (e.g., 'UNRATE', 'CPIAUCSL')
        # We don't need to rename 'VALUE' anymore as it doesn't exist

        # Handle potential missing values - forward fill or drop.
        # Dropping rows with ANY missing values for simplicity.
        df.dropna(inplace=True)

        # Ensure the column name matches the file name base for consistency in the app,
        # but only if there's a single data column.
        if df.shape[1] == 1:
             original_col_name = df.columns[0]
             expected_col_name = file_name.replace('.csv', '')
             if original_col_name != expected_col_name:
                  print(f"Warning: Column name '{original_col_name}' in {file_name} doesn't match expected '{expected_col_name}'. Renaming for consistency.")
                  df.rename(columns={original_col_name: expected_col_name}, inplace=True)
        else:
             print(f"Warning: File {file_name} does not have exactly one data column after indexing.")
             # Decide how to handle multi-column files if they appear - for now, just warn.


        return df

    except FileNotFoundError:
        print(f"Error: Data file not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error loading file {file_name}: {e}")
        return None

def get_available_datasets():
    """Lists the CSV files available in the public_datasets directory."""
    try:
        files = os.listdir(DATA_DIR)
        # Filter for CSV files and remove the .csv extension for display
        return [f.replace('.csv', '') for f in files if f.endswith('.csv')]
    except FileNotFoundError:
        print(f"Error: Data directory not found at {DATA_DIR}")
        return []
    except Exception as e:
        print(f"Error listing files: {e}")
        return []

if __name__ == '__main__':
    available = get_available_datasets()
    print("Available Datasets:", available)

    # Test with one of your actual file names without the .csv extension
    if 'UNRATE' in available:
        unrate_df = load_fred_csv('UNRATE.csv')
        if unrate_df is not None:
            print("\nUNRATE Data Head:")
            print(unrate_df.head())
            print("\nUNRATE Data Info:")
            unrate_df.info()
        else:
            print("\nFailed to load UNRATE data.")
    else:
         print("\nUNRATE data file not found in public_datasets.")

    if 'CPIAUCSL' in available:
        cpi_df = load_fred_csv('CPIAUCSL.csv')
        if cpi_df is not None:
            print("\nCPIAUCSL Data Head:")
            print(cpi_df.head())
        else:
            print("\nFailed to load CPIAUCSL data.")
    else:
         print("\nCPIAUCSL data file not found in public_datasets.")

