"""
Data loading and preprocessing utilities for the VIX Trading Strategy.
Handles file ingestion, header detection, and type conversion.
"""

import os
import numpy as np
import pandas as pd

def load_data(file_path: str) -> pd.DataFrame:
    """
    Loads data from an Excel file into a pandas DataFrame, ensuring the data
    is structured correctly, columns are formatted appropriately, and the rows
    are chronologically ordered by the Date column.

    Parameters:
    -----------
    file_path : str
        Path to the Excel file.

    Returns:
    --------
    pd.DataFrame
        A cleaned, sorted DataFrame.

    Raises:
    -------
    FileNotFoundError
        If the Excel file does not exist at the specified path.
    ValueError
        If the file has an incorrect structure or cannot be read.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found at: {file_path}")

    # 1. Detect where the header row actually starts by searching for 'ID'
    # in the first column of the first few rows.
    try:
        df_head = pd.read_excel(file_path, header=None, nrows=10)
    except Exception as e:
        raise ValueError(f"Failed to read file {file_path}: {e}")

    header_row = 0
    for idx, row in df_head.iterrows():
        # Check if the first column cell contains 'id' (case-insensitive)
        val = str(row.iloc[0]).strip().lower()
        if val == 'id':
            header_row = idx
            break

    # 2. Read the Excel file starting from the detected header row
    df = pd.read_excel(file_path, header=header_row)

    # 3. Handle column renaming. The second column (index 1) is expected to be the Date column.
    # We rename it to 'Date' to be consistent.
    if len(df.columns) > 1:
        df = df.rename(columns={df.columns[1]: 'Date'})

    # 4. Clean and convert the 'Date' column to datetime
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        # Drop rows where Date is NaT (e.g. empty rows or footer notes)
        df = df.dropna(subset=['Date'])
    else:
        raise ValueError("Could not identify 'Date' column in the dataset.")

    # 5. Clean and convert the numeric columns
    # We want columns other than 'ID' and 'Date' to be numeric (float64)
    # We coerce errors to NaN to handle any placeholder text values (like 'SVXY Close')
    numeric_cols = df.columns.difference(['ID', 'Date'])
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').replace(0, np.nan)

    # 6. Ensure chronological ordering by Date
    df = df.sort_values(by='Date').reset_index(drop=True)

    return df
