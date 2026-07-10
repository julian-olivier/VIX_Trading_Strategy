"""
Backtesting engine for the VIX Trading Strategy.
Performs path-dependent portfolio simulation with transaction costs.
"""

from typing import Tuple, Optional
import numpy as np
import pandas as pd

class VIXBacktester:
    """
    Backtester class for VIX trading strategies.
    Computes portfolio values, transaction costs, and benchmarks.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        initial_portfolio: float = 1000000.0,
        exposure: float = 0.5,
        trading_cost: float = 0.002
    ):
        """
        Initializes the backtester.

        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame containing prices, returns, and signals.
        initial_portfolio : float, default 1,000,000.0
            Initial portfolio value in USD.
        exposure : float, default 0.5
            Base asset exposure to use if Target Leverage is not computed.
        trading_cost : float, default 0.002
            Transaction cost rate per leg (e.g. 0.002 = 20 bps).
        """
        self.portfolio = initial_portfolio
        self.trading_cost = trading_cost
        self.exposure = exposure

    def calculate_rebalance_step(
        self,
        count: int,
        V_before: float,
        P_current: float,
        L_target: float,
        pos_new: Optional[str],
        pos_prev: Optional[str]
    ) -> Tuple[float, float]:
        """
        Calculates the daily rebalanced portfolio value and transaction cost.

        Parameters:
        -----------
        V_before : float
            Portfolio value before today's transaction costs.
        P_current : float
            Current value of the active position before rebalancing.
        L_target : float
            Target leverage for today.
        pos_new : Optional[str]
            Target position ('Long', 'Short', or None).
        pos_prev : Optional[str]
            Previous day's position ('Long', 'Short', or None).

        Returns:
        --------
        Tuple[float, float]
            (V_t, cost_total) - new portfolio value and total transaction cost.
        """
        
        if pos_new != pos_prev:
            # Asset switch (or initial entry/complete exit)
            # Sell old position completely, buy new position
            cost_liq = self.trading_cost * P_current
            V_t = (V_before - cost_liq) / (1.0 + self.trading_cost * L_target)
            cost_total = cost_liq + self.trading_cost * L_target * V_t
            count += 1
        else:
            # Same asset (addition or reduction of the position)
            
            if L_target * V_before >= P_current:
                # Addition: buying more of the same asset
                V_t = (V_before + self.trading_cost * P_current) / (1.0 + self.trading_cost * L_target)
                count += 1
            else:
                # Reduction: selling some of the same asset
                V_t = (V_before - self.trading_cost * P_current) / (1.0 - self.trading_cost * L_target)
                count += 1
            cost_total = self.trading_cost * abs(L_target * V_t - P_current)
            
        return V_t, cost_total, count

    def run_simulation(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Runs the step-by-step path-dependent backtest simulation with daily rebalancing,
        dynamic leverage (exposure), and transaction costs for additions/reductions/switches.

        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame containing returns and signal columns.

        Returns:
        --------
        pd.DataFrame
            A copy of the input DataFrame containing the results of the simulation.
        """
        # Prevent mutating the input DataFrame
        df = df.copy()

        # Validate required columns
        if 'VXX Returns' not in df.columns or 'SVXY Returns' not in df.columns:
            raise ValueError("DataFrame must contain 'VXX Returns' and 'SVXY Returns'.")
        if 'Signal' not in df.columns:
            raise ValueError("DataFrame must contain 'Signal' column.")

        # Fallback if target leverage is not present
        if 'Target Leverage' not in df.columns:
            df['Target Leverage'] = self.exposure

        portfolio_values = []
        transaction_costs = []
        leverage_held = []
        cash_balance = []
        position_values = []
        net_returns = []

        count = 0
        V_t = self.portfolio
        L_prev = 0.0
        pos_prev = None

        for idx, row in df.iterrows():
            V_prev = V_t
            ret_vxx = row['VXX Returns']
            ret_svxy = row['SVXY Returns']
            sig = row['Signal']
            L_target = row['Target Leverage']

            # Coerce NaNs to zero returns (e.g. first row)
            ret_vxx = 0.0 if pd.isna(ret_vxx) else ret_vxx
            ret_svxy = 0.0 if pd.isna(ret_svxy) else ret_svxy

            # Determine return of active asset held from day t-1 to t
            if pos_prev == 'Long':
                R_t = ret_vxx
            elif pos_prev == 'Short':
                R_t = ret_svxy
            else:
                R_t = 0.0

            # 1. Portfolio value before transaction costs
            V_before = V_t * (1.0 + L_prev * R_t)
            
            # 2. Value of the position before rebalancing
            P_current = L_prev * V_t * (1.0 + R_t)

            # Determine target position for today
            pos_new = sig if L_target > 0 else None

            # 3. Calculate rebalanced portfolio value and costs
            V_t, cost_total, count = self.calculate_rebalance_step(
                count, V_before, P_current, L_target, pos_new, pos_prev
            )

            # Append stats
            portfolio_values.append(V_t)
            transaction_costs.append(cost_total)
            leverage_held.append(L_target)
            
            # Cash balance is negative if leverage is greater than 1.0 (representing margin debt)
            cash_balance.append((1.0 - L_target) * V_t)
            position_values.append(L_target * V_t)

            # Daily net return of portfolio
            daily_net_return = (V_t - V_prev) / V_prev if V_prev > 0 else 0.0
            net_returns.append(daily_net_return)

            # Update state variables
            L_prev = L_target
            pos_prev = pos_new if L_target > 0 else None

        # Add simulation results to output DataFrame
        df['Portfolio Value'] = portfolio_values
        df['Transaction Cost'] = transaction_costs
        df['Leverage Held'] = leverage_held
        df['Cash Balance'] = cash_balance
        df['Position Value'] = position_values
        df['Net Returns'] = net_returns

        # Calculate Buy and Hold SPX benchmark
        if 'SPX' in df.columns:
            valid_spx = df['SPX'].dropna()
            if not valid_spx.empty:
                spx_initial = valid_spx.iloc[0]
                df['SPX Buy Hold'] = self.portfolio * (df['SPX'] / spx_initial)
            else:
                df['SPX Buy Hold'] = self.portfolio


        print (count)
        return df