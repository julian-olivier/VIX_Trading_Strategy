# pyrefly: ignore [missing-import]
import numpy as np 
import src.NextGen_Vega_Strategy as nextgen
import pandas as pd


class VIXBacktester:

    def __init__(self, initial_portfolio : float = 1000000):
        self.portfolio = initial_portfolio

    def load_values(self, df : pd.DataFrame):

        df['SVXY_Returns'] = df['SVXY Close'].pct_change()
        df['VXX_Returns'] = df['VXX Close'].pct_change()
        df['Signal'] = np.where(nextgen.calculate_annualized_realized_volitality(df) * 100> df['VIX'].shift(21) , 'Long', 'Short')

    def run_simulation(self, df):

        # Calculate daily strategy returns: holding VXX if previous day's signal was 'Long', else SVXY.
        df['Strategy_Returns'] = np.where(df['Signal'].shift(1) == 'Long', df['VXX_Returns'], df['SVXY_Returns'])
        
        # Compound daily returns to calculate portfolio value
        df['Portfolio_Value'] = self.portfolio * (1 + df['Strategy_Returns'].fillna(0.0)).cumprod()
            