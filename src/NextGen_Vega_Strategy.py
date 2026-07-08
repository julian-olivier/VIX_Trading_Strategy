# pyrefly: ignore [missing-import]
import numpy as np
import pandas as pd

def calculate_realized_volitality(df : pd.DataFrame , col : str = 'SPX', t : int = 21, ):
    
    log_daily_returns = np.log(df[col]/df[col].shift(1))
    daily_vol = log_daily_returns.rolling(window=t).std()

    return daily_vol

def calculate_annualized_realized_volitality(df : pd.DataFrame , col : str = 'SPX', t : int = 21, ):
    
    daily_vol = calculate_realized_volitality(df, col, t)
    
    return daily_vol * np.sqrt(252)

def get_signals(df : pd.DataFrame ):
    df['Signal'] = np.where(calculate_annualized_realized_volitality(df) * 100> df['VIX'].shift(21) , 'Long', 'Short')

    return df


