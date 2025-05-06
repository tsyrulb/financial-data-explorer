import pandas as pd
import numpy as np

def normalize_series(df, method='index_100', date_col='DATE'):
    """
    Applies normalization to a pandas DataFrame column (assuming time series).
    Assumes DataFrame has a DatetimeIndex.

    Args:
        df (pd.DataFrame): DataFrame with a single data column and DatetimeIndex.
        method (str): Normalization method ('index_100').
        date_col (str): The name of the column that was the date before indexing (used in some methods).

    Returns:
        pd.DataFrame: DataFrame with the normalized series.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
         print("Warning: DataFrame index is not DatetimeIndex. Normalization may not work as expected.")
         # Attempt to convert if possible
         try:
             df.index = pd.to_datetime(df.index)
         except:
             print("Error: Could not convert index to DatetimeIndex.")
             return df # Return original if conversion fails

    if method == 'index_100':
        # Find the value at the earliest date
        first_value = df.iloc[0].iloc[0] # Assumes single data column
        if first_value == 0:
             print("Warning: First value is 0, cannot index to 100.")
             return df
        return (df / first_value) * 100
    # Add more normalization methods here later (e.g., percentage change)
    else:
        print(f"Warning: Unknown normalization method '{method}'.")
        return df

def calculate_rolling_correlation(df1, df2, window=30):
    """
    Calculates the rolling correlation between two time series DataFrames.
    Assumes both DataFrames have a DatetimeIndex.

    Args:
        df1 (pd.DataFrame): First time series DataFrame (single column).
        df2 (pd.DataFrame): Second time series DataFrame (single column).
        window (int): The rolling window size (number of periods).

    Returns:
        pd.DataFrame: DataFrame with the rolling correlation series and DatetimeIndex.
    """
    if not isinstance(df1.index, pd.DatetimeIndex) or not isinstance(df2.index, pd.DatetimeIndex):
         print("Warning: One or both DataFrames do not have a DatetimeIndex. Correlation may not work as expected.")
         return None

    # Ensure both dataframes are aligned by date
    # Use inner join to only keep dates present in both
    combined_df = pd.merge(df1, df2, left_index=True, right_index=True, how='inner')

    if combined_df.shape[1] != 2:
         print("Error: Could not merge dataframes for correlation.")
         return None

    # Calculate rolling correlation
    # The .iloc[:, 0] and .iloc[:, 1] get the first and second data columns regardless of name
    rolling_corr = combined_df.iloc[:, 0].rolling(window=window).corr(combined_df.iloc[:, 1])

    # Convert to DataFrame with a meaningful name
    corr_df = rolling_corr.to_frame(name=f'Rolling Correlation (Window={window})')

    # Drop rows where correlation couldn't be calculated due to window size (NaNs at the start)
    corr_df.dropna(inplace=True)

    return corr_df

# Example Usage (for testing processing scripts directly)
if __name__ == '__main__':
    # Create dummy dataframes with DatetimeIndex
    dates = pd.to_datetime(pd.date_range(start='2020-01-01', periods=100, freq='D'))
    data1 = np.random.rand(100) * 100
    data2 = np.random.rand(100) * 50 + np.sin(np.arange(100)/10) * 20

    df1 = pd.DataFrame(data1, index=dates, columns=['SeriesA'])
    df2 = pd.DataFrame(data2, index=dates, columns=['SeriesB'])

    print("Original df1 head:")
    print(df1.head())

    normalized_df1 = normalize_series(df1, method='index_100')
    print("\nNormalized df1 head (Index 100):")
    print(normalized_df1.head())

    # Align dummy dataframes by date before calculating correlation if needed
    # For this simple case, they have the same dates, so direct merge is fine

    rolling_corr_df = calculate_rolling_correlation(df1, df2, window=10)
    if rolling_corr_df is not None:
        print("\nRolling Correlation (window=10) head:")
        print(rolling_corr_df.head())