"""
Monte Carlo simulation engine for the VIX Trading Strategy.
Performs contemporaneous vector bootstrapping (both simple and block bootstrapping)
to generate synthetic price paths, runs the strategy/backtester pipeline,
and computes detailed performance statistics and premium visualizations.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Tuple, List, Dict, Any, Optional

from src.strategy import run_strategy_pipeline
from src.backtester import VIXBacktester

class VIXMonteCarlo:
    """
    Orchestrates Monte Carlo simulations for the VIX trading strategy
    using historical return bootstrapping to preserve contemporaneous correlations.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        spx_col: str = 'SPX',
        vix_col: str = 'VIX',
        svxy_col: str = 'SVXY Close',
        vxx_col: str = 'VXX Close'
    ):
        """
        Initializes the Monte Carlo engine with the historical price dataset.

        Parameters:
        -----------
        df : pd.DataFrame
            Cleaned historical pricing DataFrame.
        spx_col : str
            Column name of SPX index.
        vix_col : str
            Column name of VIX index.
        svxy_col : str
            Column name of SVXY close.
        vxx_col : str
            Column name of VXX close.
        """
        self.df = df.copy()
        self.spx_col = spx_col
        self.vix_col = vix_col
        self.svxy_col = svxy_col
        self.vxx_col = vxx_col

        # Store initial price values for path reconstruction
        self.initial_prices = {
            'spx': self.df[self.spx_col].iloc[0],
            'vix': self.df[self.vix_col].iloc[0],
            'svxy': self.df[self.svxy_col].iloc[0],
            'vxx': self.df[self.vxx_col].iloc[0]
        }

        # Calculate joint historical daily returns
        self.returns_df = pd.DataFrame(index=self.df.index)
        self.returns_df['SPX_ret'] = self.df[self.spx_col].pct_change()
        self.returns_df['VIX_ret'] = self.df[self.vix_col].pct_change()
        self.returns_df['SVXY_ret'] = self.df[self.svxy_col].pct_change()
        self.returns_df['VXX_ret'] = self.df[self.vxx_col].pct_change()
        
        # Drop first row of NaNs to have a clean returns matrix
        self.returns_df = self.returns_df.dropna()

    def generate_returns_path(
        self,
        horizon: int,
        method: str = 'block',
        block_size: int = 21
    ) -> pd.DataFrame:
        """
        Generates a synthetic path of contemporaneous asset returns.

        Parameters:
        -----------
        horizon : int
            Number of business days to simulate.
        method : str, default 'block'
            Bootstrapping method: 'simple' (independent daily) or 'block' (circular block).
        block_size : int, default 21
            Lookback block size in days for block bootstrap.

        Returns:
        --------
        pd.DataFrame
            DataFrame of resampled daily returns of length horizon.
        """
        n_rows = len(self.returns_df)

        if method == 'simple':
            # Randomly sample rows with replacement
            resampled = self.returns_df.sample(n=horizon, replace=True).reset_index(drop=True)
            return resampled

        elif method == 'block':
            # Circular Block Bootstrap
            chunks = []
            accumulated = 0
            while accumulated < horizon:
                start_idx = np.random.randint(0, n_rows)
                if start_idx + block_size <= n_rows:
                    chunk = self.returns_df.iloc[start_idx:start_idx + block_size]
                else:
                    # Wrap around to the beginning (circular bootstrap)
                    part1 = self.returns_df.iloc[start_idx:]
                    part2 = self.returns_df.iloc[:(start_idx + block_size) - n_rows]
                    chunk = pd.concat([part1, part2])
                chunks.append(chunk)
                accumulated += len(chunk)
            
            resampled = pd.concat(chunks).iloc[:horizon].reset_index(drop=True)
            return resampled
        else:
            raise ValueError(f"Unknown bootstrap method: {method}. Use 'simple' or 'block'.")

    def reconstruct_prices(self, returns_path: pd.DataFrame) -> pd.DataFrame:
        """
        Reconstructs price paths from return paths starting at historical initial values.

        Parameters:
        -----------
        returns_path : pd.DataFrame
            Daily resampled returns.

        Returns:
        --------
        pd.DataFrame
            Reconstructed prices DataFrame (length horizon + 1).
        """
        horizon = len(returns_path)
        prices = pd.DataFrame(index=range(horizon + 1))
        
        # Set column names matching the strategy's expected names
        prices[self.spx_col] = np.nan
        prices[self.vix_col] = np.nan
        prices[self.svxy_col] = np.nan
        prices[self.vxx_col] = np.nan

        # Initialize at day 0
        prices.loc[0, [self.spx_col, self.vix_col, self.svxy_col, self.vxx_col]] = [
            self.initial_prices['spx'],
            self.initial_prices['vix'],
            self.initial_prices['svxy'],
            self.initial_prices['vxx']
        ]

        # Apply returns compound-wise
        prices.loc[1:, self.spx_col] = self.initial_prices['spx'] * (1.0 + returns_path['SPX_ret']).cumprod().values
        prices.loc[1:, self.vix_col] = self.initial_prices['vix'] * (1.0 + returns_path['VIX_ret']).cumprod().values
        prices.loc[1:, self.svxy_col] = self.initial_prices['svxy'] * (1.0 + returns_path['SVXY_ret']).cumprod().values
        prices.loc[1:, self.vxx_col] = self.initial_prices['vxx'] * (1.0 + returns_path['VXX_ret']).cumprod().values

        # Clip VIX to prevent it from drifting below realistic minimums
        prices[self.vix_col] = prices[self.vix_col].clip(lower=8.0)

        # Match date index if possible
        if isinstance(self.df.index, pd.DatetimeIndex):
            if len(self.df) == len(prices):
                prices.index = self.df.index
            else:
                prices.index = pd.date_range(start=self.df.index[0], periods=len(prices), freq='B')
                prices.index.name = 'Date'
        else:
            prices.index.name = 'Day'

        return prices

    def run_simulations(
        self,
        n_simulations: int = 200,
        horizon: Optional[int] = None,
        method: str = 'block',
        block_size: int = 21,
        initial_portfolio: float = 1000000.0,
        trading_cost: float = 0.002,
        rebalance_threshold: float = 0.05,
        signal_activation_threshold: float = 2.0,
        base_exposure: float = 0.25,
        vol_window: int = 21,
        leverage_window: int = 21,
        max_leverage: float = 3.0
    ) -> Dict[str, Any]:
        """
        Runs multiple Monte Carlo simulations.

        Returns a dictionary containing raw simulation paths, final metrics,
        and statistical summary.
        """
        if horizon is None:
            horizon = len(self.df) - 1  # Match the length of historical returns

        portfolio_paths = []
        terminal_values = []
        cagrs = []
        volatilities = []
        sharpe_ratios = []
        max_drawdowns = []

        print(f"Starting {n_simulations} Monte Carlo simulations (horizon={horizon} days, method={method})...")

        for sim_idx in range(n_simulations):
            # 1. Generate return path
            ret_path = self.generate_returns_path(horizon=horizon, method=method, block_size=block_size)
            
            # 2. Reconstruct price paths
            sim_prices = self.reconstruct_prices(ret_path)

            # 3. Run Strategy Pipeline
            sim_strategy = run_strategy_pipeline(
                sim_prices,
                spx_col=self.spx_col,
                vix_col=self.vix_col,
                svxy_col=self.svxy_col,
                vxx_col=self.vxx_col,
                base_exposure=base_exposure,
                vol_window=vol_window,
                leverage_window=leverage_window,
                max_leverage=max_leverage
            )

            # 4. Run Backtester Simulation
            backtester = VIXBacktester(
                sim_strategy,
                initial_portfolio=initial_portfolio,
                exposure=base_exposure,
                trading_cost=trading_cost,
                rebalance_threshold=rebalance_threshold,
                signal_activation_threshold=signal_activation_threshold
            )
            sim_results = backtester.run_simulation(sim_strategy)

            # 5. Extract portfolio path and calculate metrics
            paths_v = sim_results['Portfolio Value']
            portfolio_paths.append(paths_v)

            # Terminal Portfolio Value
            v_final = paths_v.iloc[-1]
            terminal_values.append(v_final)

            # CAGR (annualized return)
            n_years = len(paths_v) / 252.0
            cagr = (v_final / initial_portfolio) ** (1.0 / n_years) - 1.0
            cagrs.append(cagr)

            # Annualized Volatility
            daily_returns = sim_results['Net Returns']
            ann_vol = daily_returns.std() * np.sqrt(252.0)
            volatilities.append(ann_vol)

            # Sharpe Ratio (assuming risk-free rate of 0)
            sharpe = cagr / ann_vol if ann_vol > 0 else 0.0
            sharpe_ratios.append(sharpe)

            # Max Drawdown
            peaks = paths_v.cummax()
            drawdowns = (paths_v - peaks) / peaks
            max_dd = drawdowns.min()
            max_drawdowns.append(max_dd)

        # Convert lists to numpy arrays for calculation
        terminal_values = np.array(terminal_values)
        cagrs = np.array(cagrs)
        volatilities = np.array(volatilities)
        sharpe_ratios = np.array(sharpe_ratios)
        max_drawdowns = np.array(max_drawdowns)

        # Run historical backtest for comparison
        hist_strategy = run_strategy_pipeline(
            self.df,
            spx_col=self.spx_col,
            vix_col=self.vix_col,
            svxy_col=self.svxy_col,
            vxx_col=self.vxx_col,
            base_exposure=base_exposure,
            vol_window=vol_window,
            leverage_window=leverage_window,
            max_leverage=max_leverage
        )
        hist_backtester = VIXBacktester(
            hist_strategy,
            initial_portfolio=initial_portfolio,
            exposure=base_exposure,
            trading_cost=trading_cost,
            rebalance_threshold=rebalance_threshold,
            signal_activation_threshold=signal_activation_threshold
        )
        hist_results = hist_backtester.run_simulation(hist_strategy)
        
        hist_v_final = hist_results['Portfolio Value'].iloc[-1]
        hist_years = len(self.df) / 252.0
        hist_cagr = (hist_v_final / initial_portfolio) ** (1.0 / hist_years) - 1.0
        hist_vol = hist_results['Net Returns'].dropna().std() * np.sqrt(252.0)
        hist_sharpe = hist_cagr / hist_vol if hist_vol > 0 else 0.0
        hist_peaks = hist_results['Portfolio Value'].cummax()
        hist_drawdowns = (hist_results['Portfolio Value'] - hist_peaks) / hist_peaks
        hist_mdd = hist_drawdowns.min()

        # Calculate statistics summaries
        summary = {
            'CAGR': {
                'mean': cagrs.mean(),
                'median': np.median(cagrs),
                'std': cagrs.std(),
                'p5': np.percentile(cagrs, 5),
                'p25': np.percentile(cagrs, 25),
                'p75': np.percentile(cagrs, 75),
                'p95': np.percentile(cagrs, 95),
                'historical': hist_cagr
            },
            'Volatility': {
                'mean': volatilities.mean(),
                'median': np.median(volatilities),
                'std': volatilities.std(),
                'p5': np.percentile(volatilities, 5),
                'p25': np.percentile(volatilities, 25),
                'p75': np.percentile(volatilities, 75),
                'p95': np.percentile(volatilities, 95),
                'historical': hist_vol
            },
            'Sharpe Ratio': {
                'mean': sharpe_ratios.mean(),
                'median': np.median(sharpe_ratios),
                'std': sharpe_ratios.std(),
                'p5': np.percentile(sharpe_ratios, 5),
                'p25': np.percentile(sharpe_ratios, 25),
                'p75': np.percentile(sharpe_ratios, 75),
                'p95': np.percentile(sharpe_ratios, 95),
                'historical': hist_sharpe
            },
            'Max Drawdown': {
                'mean': max_drawdowns.mean(),
                'median': np.median(max_drawdowns),
                'std': max_drawdowns.std(),
                'p5': np.percentile(max_drawdowns, 5),
                'p25': np.percentile(max_drawdowns, 25),
                'p75': np.percentile(max_drawdowns, 75),
                'p95': np.percentile(max_drawdowns, 95),
                'historical': hist_mdd
            },
            'Terminal Value': {
                'mean': terminal_values.mean(),
                'median': np.median(terminal_values),
                'p5': np.percentile(terminal_values, 5),
                'p25': np.percentile(terminal_values, 25),
                'p75': np.percentile(terminal_values, 75),
                'p95': np.percentile(terminal_values, 95),
                'historical': hist_v_final
            },
            'Win Rate': np.mean(cagrs > 0.0),
            'VaR 95%': np.percentile(cagrs, 5),
            'CVaR 95%': cagrs[cagrs <= np.percentile(cagrs, 5)].mean()
        }

        # Create simulated paths DataFrame for visualization
        sim_paths_df = pd.DataFrame(portfolio_paths).T
        sim_paths_df.index = sim_results.index

        return {
            'sim_paths': sim_paths_df,
            'terminal_values': terminal_values,
            'cagrs': cagrs,
            'volatilities': volatilities,
            'sharpe_ratios': sharpe_ratios,
            'max_drawdowns': max_drawdowns,
            'historical_path': hist_results['Portfolio Value'],
            'summary': summary
        }

def plot_simulated_paths(
    sim_results: Dict[str, Any],
    n_paths_to_plot: int = 100,
    title: str = "VIX Strategy Monte Carlo Paths"
) -> go.Figure:
    """
    Plots a subset of simulated portfolio value paths with the historical path highlighted.
    """
    sim_paths = sim_results['sim_paths']
    hist_path = sim_results['historical_path']
    
    # Pick a subset of columns to plot
    n_total_paths = sim_paths.shape[1]
    paths_to_select = min(n_paths_to_plot, n_total_paths)
    selected_indices = np.random.choice(n_total_paths, size=paths_to_select, replace=False)
    
    fig = go.Figure()

    # Plot simulated paths (semi-transparent)
    for idx in selected_indices:
        fig.add_trace(go.Scatter(
            x=sim_paths.index,
            y=sim_paths.iloc[:, idx],
            mode='lines',
            line=dict(color='rgba(15, 151, 142, 0.08)', width=1),
            showlegend=False,
            hoverinfo='skip'
        ))

    # Add historical path in bold
    fig.add_trace(go.Scatter(
        x=hist_path.index,
        y=hist_path,
        mode='lines',
        name='Historical Realized Path',
        line=dict(color='#d35400', width=3.0),
        hovertemplate='Date: %{x}<br>Portfolio Value: $%{y:,.2f}<extra></extra>'
    ))

    # Add Median Path for reference
    median_path = sim_paths.median(axis=1)
    fig.add_trace(go.Scatter(
        x=median_path.index,
        y=median_path,
        mode='lines',
        name='Median Simulated Path',
        line=dict(color='#0f978e', width=2.0, dash='dash'),
        hovertemplate='Date: %{x}<br>Median Value: $%{y:,.2f}<extra></extra>'
    ))

    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=18, family='Arial', color='#2c3e50')),
        xaxis=dict(title='Date', gridcolor='#eef2f3', showline=True, linecolor='#bdc3c7', mirror=True),
        yaxis=dict(title='Portfolio Value (USD)', gridcolor='#eef2f3', tickprefix='$', showline=True, linecolor='#bdc3c7', mirror=True),
        plot_bgcolor='white',
        hovermode='x unified',
        height=600,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='#bdc3c7',
            borderwidth=1
        )
    )
    return fig

def plot_fan_chart(
    sim_results: Dict[str, Any],
    title: str = "VIX Strategy Monte Carlo Fan Chart"
) -> go.Figure:
    """
    Plots a premium fan chart of percentiles (5%, 25%, 50%, 75%, 95%) of portfolio values over time.
    """
    sim_paths = sim_results['sim_paths']
    hist_path = sim_results['historical_path']
    index = sim_paths.index

    # Calculate percentiles
    p5 = sim_paths.quantile(0.05, axis=1)
    p25 = sim_paths.quantile(0.25, axis=1)
    p50 = sim_paths.quantile(0.50, axis=1)
    p75 = sim_paths.quantile(0.75, axis=1)
    p95 = sim_paths.quantile(0.95, axis=1)

    fig = go.Figure()

    # 95% interval (5% to 95%)
    fig.add_trace(go.Scatter(
        x=index, y=p95, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=index, y=p5, mode='lines', fill='tonexty',
        fillcolor='rgba(15, 151, 142, 0.10)', line=dict(width=0),
        name='5% - 95% Confidence Band', hoverinfo='skip'
    ))

    # 50% interval (25% to 75%)
    fig.add_trace(go.Scatter(
        x=index, y=p75, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=index, y=p25, mode='lines', fill='tonexty',
        fillcolor='rgba(15, 151, 142, 0.20)', line=dict(width=0),
        name='25% - 75% Confidence Band', hoverinfo='skip'
    ))

    # Median Path
    fig.add_trace(go.Scatter(
        x=index, y=p50, mode='lines', name='Median Path (50%)',
        line=dict(color='#0f978e', width=2.0),
        hovertemplate='Date: %{x}<br>Median: $%{y:,.2f}<extra></extra>'
    ))

    # Historical Path
    fig.add_trace(go.Scatter(
        x=hist_path.index, y=hist_path, mode='lines', name='Historical Realized Path',
        line=dict(color='#d35400', width=2.5),
        hovertemplate='Date: %{x}<br>Historical: $%{y:,.2f}<extra></extra>'
    ))

    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=18, family='Arial', color='#2c3e50')),
        xaxis=dict(title='Date', gridcolor='#eef2f3', showline=True, linecolor='#bdc3c7', mirror=True),
        yaxis=dict(title='Portfolio Value (USD)', gridcolor='#eef2f3', tickprefix='$', showline=True, linecolor='#bdc3c7', mirror=True),
        plot_bgcolor='white',
        hovermode='x unified',
        height=600,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='#bdc3c7',
            borderwidth=1
        )
    )
    return fig

def plot_metrics_distributions(
    sim_results: Dict[str, Any],
    title: str = "VIX Strategy Risk/Reward Distributions"
) -> go.Figure:
    """
    Creates a dual-subplot histogram showing the distributions of Sharpe Ratios and Max Drawdowns.
    """
    sharpes = sim_results['sharpe_ratios']
    drawdowns = sim_results['max_drawdowns'] * 100.0  # convert to %
    
    hist_sharpe = sim_results['summary']['Sharpe Ratio']['historical']
    hist_mdd = sim_results['summary']['Max Drawdown']['historical'] * 100.0

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Sharpe Ratio Distribution", "Maximum Drawdown Distribution (%)"))

    # Sharpe Ratio Histogram
    fig.add_trace(go.Histogram(
        x=sharpes,
        name='Simulated Sharpe',
        xbins=dict(size=0.1),
        marker=dict(color='#3498db', line=dict(color='white', width=0.5)),
        opacity=0.75,
        hovertemplate='Sharpe Bin: %{x:.2f}<br>Count: %{y}<extra></extra>'
    ), row=1, col=1)

    # Add historical Sharpe vertical line
    fig.add_vline(
        x=hist_sharpe,
        line_width=2.5,
        line_dash="dash",
        line_color="#d35400",
        annotation_text=f"Hist: {hist_sharpe:.2f}",
        annotation_position="top right",
        row=1, col=1
    )

    # Drawdown Histogram
    fig.add_trace(go.Histogram(
        x=drawdowns,
        name='Simulated Max DD',
        xbins=dict(size=2.0),
        marker=dict(color='#e74c3c', line=dict(color='white', width=0.5)),
        opacity=0.75,
        hovertemplate='Max DD Bin: %{x:.1f}%<br>Count: %{y}<extra></extra>'
    ), row=1, col=2)

    # Add historical Max DD vertical line
    fig.add_vline(
        x=hist_mdd,
        line_width=2.5,
        line_dash="dash",
        line_color="#d35400",
        annotation_text=f"Hist: {hist_mdd:.1f}%",
        annotation_position="top left",
        row=1, col=2
    )

    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=18, family='Arial', color='#2c3e50')),
        plot_bgcolor='white',
        showlegend=False,
        height=450,
        margin=dict(l=50, r=50, t=80, b=50)
    )

    # Update axes styling
    fig.update_xaxes(title_text="Sharpe Ratio", gridcolor='#eef2f3', showline=True, linecolor='#bdc3c7', row=1, col=1)
    fig.update_yaxes(title_text="Count", gridcolor='#eef2f3', showline=True, linecolor='#bdc3c7', row=1, col=1)
    fig.update_xaxes(title_text="Max Drawdown (%)", gridcolor='#eef2f3', showline=True, linecolor='#bdc3c7', row=1, col=2)
    fig.update_yaxes(title_text="Count", gridcolor='#eef2f3', showline=True, linecolor='#bdc3c7', row=1, col=2)

    return fig
