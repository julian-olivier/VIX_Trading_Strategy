import numpy as np 
import src.NextGen_Vega_Strategy as nextgen
import pandas as pd


class VIXBacktester:

    def __init__(self, df : pd.DataFrame, initial_portfolio : float = 1000000, exposure: float = 0.5, trading_cost : float = 0.002, ):

        self.portfolio = initial_portfolio
        self.trading_cost = trading_cost
        self.exposure = exposure


    def calculate_transaction_costs(self, df : pd.DataFrame):
        #current signal & previous signal  
        position = df['Signal'].shift(1)
        prev_position = df['Signal'].shift(2)

        #Compute transaction costs based on legs traded
        df['Transaction Cost'] = 0.0
        
        #Initial entry (first day we take a position) 
        initial_entry = position.notna() & prev_position.isna()
        df.loc[initial_entry, 'Transaction Cost'] = self.trading_cost
        
        #Switch positions (Long to Short or Short to Long) 
        switch = position.notna() & prev_position.notna() & (position != prev_position)
        df.loc[switch, 'Transaction Cost'] = 2 * self.trading_cost

    def run_simulation(self, df : pd.DataFrame):

        # Compute transaction costs using the helper function
        self.calculate_transaction_costs(df)
        
        # Initialize Cash column
        df['Cash'] = self.portfolio * (1 - self.exposure)
        
        # Calculate daily net returns after deducting transaction costs
        df['Net Returns'] = (1 + df['Strategy Returns'].fillna(0.0)) * (1 - df['Transaction Cost']) - 1
        
        # Compound net daily returns to calculate portfolio value
        df['Vega Returns'] = self.portfolio * self.exposure * (1 + df['Net Returns']).cumprod()
        df['Portfolio Value'] = df['Vega Returns'] + df['Cash']

        # Calculate Buy and Hold SPX Portfolio Value
        df['SPX Buy Hold'] = self.portfolio * (df['SPX'] / df['SPX'].iloc[0])

        return df