from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import os
from sqlalchemy import create_engine, Table, Column, String, Float, MetaData, DateTime, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker # Import sessionmaker

# Import your data processing functions
# Ensure data_processing.py is in the same directory (src)
try:
    from .data_processing import normalize_series, calculate_rolling_correlation
except ImportError as e:
    print(f"Error importing data processing module: {e}")
    print("Please ensure data_processing.py is in the backend/src directory.")
    # Define dummy functions if import fails to prevent server crash
    normalize_series = lambda df, method: df
    calculate_rolling_correlation = lambda df1, df2, window: None

# --- Database Configuration ---
# Define the path for the SQLite database file
DATABASE_FILE = 'financial_data.db'
# Construct the absolute path to the database file
# Assumes the .db file is in the same directory as app.py (backend/src)
DATABASE_PATH = os.path.join(os.path.dirname(__file__), DATABASE_FILE)

# SQLAlchemy database URL for SQLite
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Create the SQLAlchemy engine
try:
    engine = create_engine(DATABASE_URL)
    # Optional: Test connection
    with engine.connect() as connection:
        print(f"Database connected successfully to {DATABASE_PATH}")
except SQLAlchemyError as e:
    print(f"Error connecting to database: {e}")
    # Exit or handle the error if database connection fails
    engine = None # Set engine to None if connection fails


# Define table schema (must match the definition in setup_database.py)
metadata = MetaData()

time_series_data_table = Table(
    'time_series_data', metadata,
    Column('id', String, primary_key=True),
    Column('series_name', String, nullable=False),
    Column('observation_date', DateTime, nullable=False),
    Column('value', Float, nullable=False),
)

series_catalog_table = Table(
    'series_catalog', metadata,
    Column('name', String, primary_key=True),
    Column('file_name', String, nullable=False),
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Dependency to get DB session ---
def get_db():
    """Provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API Routes ---

@app.route('/')
def hello_world():
    """Basic route to confirm the backend is running."""
    return 'Backend for Financial Data Explorer is running (Database Connected)!'

@app.route('/api/datasets', methods=['GET'])
def list_datasets():
    """
    Returns a JSON list of available dataset names from the database catalog.
    Example: ["UNRATE", "CPIAUCSL", "DFF"]
    """
    if engine is None:
        return jsonify({'error': 'Database connection failed'}), 500

    db = SessionLocal() # Get a database session
    try:
        # Select all names from the series_catalog table
        stmt = select(series_catalog_table.c.name)
        result = db.execute(stmt)
        dataset_names = [row[0] for row in result.fetchall()] # Extract names from results
        return jsonify(dataset_names)
    except SQLAlchemyError as e:
        print(f"Database error fetching dataset list: {e}")
        return jsonify({'error': 'Error fetching dataset list from database'}), 500
    finally:
        db.close() # Close the session

@app.route('/api/data/<string:dataset_name>', methods=['GET'])
def get_dataset_data(dataset_name):
    """
    Returns time series data for a specific dataset from the database as JSON.
    Supports optional 'transform' query parameter (e.g., ?transform=index_100).
    """
    if engine is None:
        return jsonify({'error': 'Database connection failed'}), 500

    db = SessionLocal() # Get a database session
    try:
        # Check if the dataset exists in the catalog first (optional but good practice)
        catalog_stmt = select(series_catalog_table.c.name).where(series_catalog_table.c.name == dataset_name)
        catalog_result = db.execute(catalog_stmt).fetchone()
        if not catalog_result:
            return jsonify({'error': f'Dataset "{dataset_name}" not found in catalog'}), 404

        # Select data for the specific series, ordered by date
        stmt = select(
            time_series_data_table.c.observation_date,
            time_series_data_table.c.value
        ).where(
            time_series_data_table.c.series_name == dataset_name
        ).order_by(time_series_data_table.c.observation_date)

        result = db.execute(stmt)
        # Fetch all results and convert to a list of tuples [(date, value), ...]
        data_tuples = result.fetchall()

        if not data_tuples:
             return jsonify({'error': f'No data found for dataset "{dataset_name}"'}), 404

        # Convert list of tuples to a pandas DataFrame
        # Ensure column names match what the frontend expects ('date', dataset_name)
        df = pd.DataFrame(data_tuples, columns=['date', dataset_name])

        # Set 'date' column as DatetimeIndex for processing functions
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # Get query parameters for transformations
        transform_method = request.args.get('transform')

        if transform_method:
            print(f"Applying transform '{transform_method}' to {dataset_name}")
            # Pass the DataFrame column containing values to normalize_series
            # normalize_series expects a DataFrame with a single column and DatetimeIndex
            df = normalize_series(df, method=transform_method)
            if df is None: # Handle potential error from normalize_series
                 return jsonify({'error': f'Transformation method "{transform_method}" failed or is not supported'}), 400

        # Prepare data for JSON response: convert DatetimeIndex to string/timestamp
        # and DataFrame to dictionary format suitable for frontend charting libraries
        # We need a list of dictionaries [{date: ..., value: ...}, ...]

        # Reset index to turn the DatetimeIndex back into a column for JSON conversion
        df_reset = df.reset_index()

        # Rename the index column (which is now a regular column) to 'date' for clarity in JSON
        # This assumes the index column is the first column after reset
        df_reset.rename(columns={df_reset.columns[0]: 'date'}, inplace=True)

        # Convert datetime objects in the 'date' column to strings (ISO 8601 format is standard)
        df_reset['date'] = df_reset['date'].dt.strftime('%Y-%m-%d') # Or use .isoformat()

        # Convert the DataFrame to a list of dictionaries
        data_list = df_reset.to_dict('records')

        return jsonify(data_list)

    except SQLAlchemyError as e:
        print(f"Database error fetching data for {dataset_name}: {e}")
        return jsonify({'error': 'Error fetching data from database'}), 500
    except Exception as e:
        print(f"An unexpected error occurred fetching data for {dataset_name}: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500
    finally:
        db.close() # Close the session


@app.route('/api/correlation', methods=['GET'])
def get_rolling_correlation():
    """
    Calculates and returns rolling correlation for two specified datasets from the database as JSON.
    Expects 'series1' and 'series2' query parameters (dataset names),
    and an optional 'window' query parameter (integer, default 30).
    Example: /api/correlation?series1=UNRATE&series2=CPIAUCSL&window=60
    """
    if engine is None:
        return jsonify({'error': 'Database connection failed'}), 500

    # Get the dataset names and window size from query parameters
    series1_name = request.args.get('series1')
    series2_name = request.args.get('series2')
    window_str = request.args.get('window', default='30') # Default window size is 30

    # Validate required parameters
    if not series1_name or not series2_name:
        return jsonify({'error': 'Missing required parameters: series1 and series2'}), 400

    db = SessionLocal() # Get a database session
    try:
        # --- Fetch data for both series from the database ---
        data1_stmt = select(
            time_series_data_table.c.observation_date,
            time_series_data_table.c.value
        ).where(
            time_series_data_table.c.series_name == series1_name
        ).order_by(time_series_data_table.c.observation_date)

        data2_stmt = select(
            time_series_data_table.c.observation_date,
            time_series_data_table.c.value
        ).where(
            time_series_data_table.c.series_name == series2_name
        ).order_by(time_series_data_table.c.observation_date)

        result1 = db.execute(data1_stmt)
        data1_tuples = result1.fetchall()

        result2 = db.execute(data2_stmt)
        data2_tuples = result2.fetchall()

        if not data1_tuples or not data2_tuples:
             return jsonify({'error': f'Data not found for one or both datasets: {series1_name}, {series2_name}'}), 404

        # Convert fetched data to pandas DataFrames
        df1 = pd.DataFrame(data1_tuples, columns=['date', series1_name])
        df2 = pd.DataFrame(data2_tuples, columns=['date', series2_name])

        # Set 'date' column as DatetimeIndex for processing functions
        df1['date'] = pd.to_datetime(df1['date'])
        df1.set_index('date', inplace=True)

        df2['date'] = pd.to_datetime(df2['date'])
        df2.set_index('date', inplace=True)

        # Validate the window size parameter
        try:
            window = int(window_str)
            if window <= 1:
                return jsonify({'error': 'Window size must be a positive integer greater than 1'}), 400
        except ValueError:
             return jsonify({'error': 'Invalid window size parameter. Must be an integer.'}), 400

        # --- Calculate the rolling correlation ---
        print(f"Calculating rolling correlation for {series1_name} and {series2_name} with window {window}")
        rolling_corr_df = calculate_rolling_correlation(df1, df2, window=window)

        # Check if the calculation was successful
        if rolling_corr_df is None:
            return jsonify({'error': 'Could not calculate rolling correlation. Data might be incompatible or window too large.'}), 500

        # Prepare the correlation results for JSON response
        # The rolling_corr_df should have a DatetimeIndex and one column (the correlation values)
        if rolling_corr_df.shape[1] == 1:
             # The column name is the name assigned in calculate_rolling_correlation
             data_col_name = rolling_corr_df.columns[0]

             # Reset index and rename for JSON
             df_reset = rolling_corr_df.reset_index()
             df_reset.rename(columns={df_reset.columns[0]: 'date'}, inplace=True)

             # Convert datetime objects to strings
             df_reset['date'] = df_reset['date'].dt.strftime('%Y-%m-%d')

             # Convert DataFrame to a list of dictionaries
             data_list = df_reset.to_dict('records')

             return jsonify(data_list)
        else:
            # Safeguard for unexpected output format from calculate_rolling_correlation
            print(f"Error: Rolling correlation DataFrame has unexpected number of columns ({rolling_corr_df.shape[1]})")
            return jsonify({'error': 'Unexpected data format for correlation result'}), 500

    except SQLAlchemyError as e:
        print(f"Database error fetching data for correlation: {e}")
        return jsonify({'error': 'Error fetching data from database for correlation'}), 500
    except Exception as e:
        print(f"An unexpected error occurred calculating correlation: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500
    finally:
        db.close() # Close the session


# --- Running the App ---

if __name__ == '__main__':
    # This block runs only when you execute this script directly (e.g., python src/app.py)
    # It starts the Flask development server.
    # For production deployment, you would use a production-ready WSGI server like Gunicorn.

    # debug=True provides helpful error messages in the browser and auto-reloads on code changes.
    # Set a specific port if needed, default is 5000.
    print("Starting Flask development server...")
    # Make sure FLASK_APP=src.app is set in your environment before running 'flask run'
    # If running this file directly, use app.run()
    # app.run(debug=True, port=5000)
    print("Please run the application using 'flask run' from the backend directory after setting FLASK_APP=src.app")

