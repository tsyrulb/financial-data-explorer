import pandas as pd
import os
from sqlalchemy import create_engine, Table, Column, String, Float, MetaData, DateTime
from sqlalchemy.exc import SQLAlchemyError

# --- Configuration ---
# Define the path for the SQLite database file
DATABASE_FILE = 'financial_data.db'
DATABASE_PATH = os.path.join(os.path.dirname(__file__), DATABASE_FILE)
# Define the path to the directory containing your public data CSVs
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'public_datasets')

# SQLAlchemy database URL for SQLite
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# --- Database Setup ---
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Define a table to store the time series data
# We'll store data from all series in one 'time_series_data' table
# Each row will be a specific observation for a specific series on a specific date
time_series_data_table = Table(
    'time_series_data', metadata,
    Column('id', String, primary_key=True), # Unique ID (e.g., 'UNRATE_1948-01-01')
    Column('series_name', String, nullable=False), # e.g., 'UNRATE', 'CPIAUCSL'
    Column('observation_date', DateTime, nullable=False), # The date of the observation
    Column('value', Float, nullable=False), # The numerical value of the observation
    # Add a unique constraint to prevent duplicate entries for the same series/date
    # This assumes one observation per series per date.
    # You might need to adjust if your data has multiple observations per day.
    unique_constraint = ('series_name', 'observation_date')
)

# Define a table to list the available series
series_catalog_table = Table(
    'series_catalog', metadata,
    Column('name', String, primary_key=True), # e.g., 'UNRATE', 'CPIAUCSL'
    Column('file_name', String, nullable=False), # Original CSV file name, e.g., 'UNRATE.csv'
    # Add other metadata columns later if needed (e.g., description, source URL)
)

def create_tables():
    """Creates the database tables if they don't exist."""
    try:
        metadata.create_all(engine)
        print(f"Database tables created or already exist in {DATABASE_PATH}")
    except SQLAlchemyError as e:
        print(f"Error creating database tables: {e}")

# --- Data Loading Functions ---

def load_fred_csv_to_db(file_name):
    """
    Loads a single FRED CSV file into the time_series_data table.
    Assumes a simple format with 'observation_date' and the series ticker as columns.
    """
    file_path = os.path.join(DATA_DIR, file_name)
    series_name = file_name.replace('.csv', '')

    try:
        # Check if the series already exists in the catalog
        with engine.connect() as connection:
            select_stmt = series_catalog_table.select().where(series_catalog_table.c.name == series_name)
            result = connection.execute(select_stmt).fetchone()
            if result:
                print(f"Series '{series_name}' already exists in catalog. Skipping load from CSV.")
                return # Skip loading if already cataloged

        # Read the CSV using pandas
        df = pd.read_csv(file_path, index_col='observation_date', parse_dates=True)

        # Ensure the DataFrame has exactly one data column besides the index
        if df.shape[1] != 1:
             print(f"Warning: File {file_name} does not have exactly one data column after indexing. Skipping.")
             return

        # Get the actual column name (should be the series ticker)
        original_col_name = df.columns[0]

        # Prepare data for insertion
        # We need a list of dictionaries, one for each row/observation
        data_to_insert = []
        for index, row in df.iterrows():
            obs_date = index # This is already a datetime from the index
            value = row[original_col_name] # Get the value from the single column

            # Create a unique ID (optional but good practice)
            unique_id = f"{series_name}_{obs_date.strftime('%Y-%m-%d')}"

            data_to_insert.append({
                'id': unique_id,
                'series_name': series_name,
                'observation_date': obs_date,
                'value': value
            })

        # Insert data into the time_series_data table
        with engine.connect() as connection:
            # Insert into time_series_data table
            insert_stmt_data = time_series_data_table.insert().values(data_to_insert)
            # Use 'on_conflict_do_nothing' if your SQLite version supports it,
            # or handle duplicates by checking existence first if not.
            # For simplicity here, we assume no duplicates are loaded initially.
            connection.execute(insert_stmt_data)

            # Insert into series_catalog table
            insert_stmt_catalog = series_catalog_table.insert().values(
                name=series_name,
                file_name=file_name
            )
            connection.execute(insert_stmt_catalog)

            connection.commit() # Commit the transaction

        print(f"Successfully loaded data from {file_name} into the database.")

    except FileNotFoundError:
        print(f"Error: Data file not found at {file_path}")
    except SQLAlchemyError as e:
        print(f"Database error loading {file_name}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred loading {file_name}: {e}")


def load_all_datasets_from_files():
    """Loads all CSV files found in the public_datasets directory into the database."""
    try:
        files = os.listdir(DATA_DIR)
        csv_files = [f for f in files if f.endswith('.csv')]

        if not csv_files:
            print(f"No CSV files found in {DATA_DIR}. Nothing to load.")
            return

        print(f"Found {len(csv_files)} CSV files to potentially load.")
        for file_name in csv_files:
            load_fred_csv_to_db(file_name)

    except FileNotFoundError:
        print(f"Error: Data directory not found at {DATA_DIR}")
    except Exception as e:
        print(f"An error occurred listing files: {e}")


# --- Main Execution Block ---
if __name__ == '__main__':
    print("Starting database setup and data loading...")
    create_tables() # Ensure tables exist
    load_all_datasets_from_files() # Load data from CSVs
    print("Database setup and data loading complete.")

    # Optional: Verify data in the database
    # from sqlalchemy.sql import select
    # with engine.connect() as connection:
    #     count_stmt = select(time_series_data_table).count()
    #     total_records = connection.execute(count_stmt).scalar()
    #     print(f"\nTotal records in time_series_data table: {total_records}")

    #     catalog_stmt = select(series_catalog_table)
    #     catalog_entries = connection.execute(catalog_stmt).fetchall()
    #     print("\nSeries Catalog:")
    #     for entry in catalog_entries:
    #         print(f"- {entry.name} (File: {entry.file_name})")

