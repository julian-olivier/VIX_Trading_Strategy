# pyrefly: ignore [missing-import]
import numpy as np 
import src.NextGen_Vega_Strategy as nextgen
import pandas as pd


class VIXBacktester:

    def __init__(self, df : pd.DataFrame, initial_portfolio : float = 1000000, exposure: float = 0.5, trading_cost : float = 0.002, ):

        self.portfolio = initial_portfolio
        self.trading_cost = trading_cost
        self.exposure = exposure

        df['Cash'] = self.portfolio * (1 - self.exposure)
        df['SVXY_Returns'] = df['SVXY Close'].pct_change()
        df['VXX_Returns'] = df['VXX Close'].pct_change()
        df['Signal'] = np.where(nextgen.calculate_annualized_realized_volitality(df) * 100> df['VIX'].shift(21) , 'Long', 'Short')


    def calculate_transaction_costs(self, df):
        #current signal & previous signal  
        position = df['Signal'].shift(1)
        prev_position = df['Signal'].shift(2)

        #Compute transaction costs based on legs traded
        df['Transaction_Cost'] = 0.0
        
        #Initial entry (first day we take a position) 
        initial_entry = position.notna() & prev_position.isna()
        df.loc[initial_entry, 'Transaction_Cost'] = self.trading_cost
        
        #Switch positions (Long to Short or Short to Long) 
        switch = position.notna() & prev_position.notna() & (position != prev_position)
        df.loc[switch, 'Transaction_Cost'] = 2 * self.trading_cost

    def run_simulation(self, df):

        # Calculate daily strategy returns: holding VXX if previous day's signal was 'Long', else SVXY.
        df['Strategy_Returns'] = np.where(df['Signal'].shift(1) == 'Long', df['VXX_Returns'], df['SVXY_Returns'])

        # Compute transaction costs using the helper function
        self.calculate_transaction_costs(df)
        
        #Calculate daily net returns after deducting transaction costs
        df['Net_Returns'] = (1 + df['Strategy_Returns'].fillna(0.0)) * (1 - df['Transaction_Cost']) - 1
        
        #Compound net daily returns to calculate portfolio value
        df['Vega_Returns'] = self.portfolio * self.exposure * (1 + df['Net_Returns']).cumprod()
        df['Portfolio_Value'] = df['Vega_Returns'] + df['Cash']

        # Calculate Buy and Hold SPX Portfolio Value
        df['SPX_Buy_Hold'] = self.portfolio * (df['SPX'] / df['SPX'].iloc[0])

        return df