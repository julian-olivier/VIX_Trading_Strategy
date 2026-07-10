"""
Strategy logic for the VIX/Vega Trading Strategy.
Contains pure, modular calculation functions that operate on pandas Series
to avoid in-place mutations, along with standard spellings and type annotations.
"""

import numpy as np
import pandas as pd
from typing import Tuple

def calculate_realized_volatility(
    prices: pd.Series,
    window: int = 21
) -> pd.Series:
    """
    Calculates the rolling realized volatility of a price series using log returns.

    Parameters:
    -----------
    prices : pd.Series
        Historical price series (e.g. S&P 500 Close).
    window : int, default 21
        Rolling window size.

    Returns:
    --------
    pd.Series
        Rolling standard deviation of daily log returns.
    """
    log_returns = np.log(prices / prices.shift(1))
    return log_returns.rolling(window=window).std()

def calculate_annualized_volatility(
    realized_vol: pd.Series,
    trading_days: int = 252
) -> pd.Series:
    """
    Annualizes a rolling realized volatility series.

    Parameters:
    -----------
    realized_vol : pd.Series
        Daily rolling standard deviation of log returns.
    trading_days : int, default 252
        Number of trading days in a year.

    Returns:
    --------
    pd.Series
        Annualized volatility percentage (0-100 scale).
    """
    return realized_vol * np.sqrt(trading_days) * 100

def calculate_volatility_difference(
    annualized_vol: pd.Series,
    vix: pd.Series,
    shift: int = 21
) -> pd.Series:
    """
    Calculates the difference between annualized realized volatility and lagged VIX.

    Parameters:
    -----------
    annualized_vol : pd.Series
        Annualized realized volatility series.
    vix : pd.Series
        VIX index series.
    shift : int, default 21
        Lag to apply to the VIX index.

    Returns:
    --------
    pd.Series
        Signed difference series.
    """
    return annualized_vol - vix.shift(shift)

def generate_signals(
    annualized_vol: pd.Series,
    vix: pd.Series,
    shift: int = 21
) -> pd.Series:
    """
    Generates trading signals: 'Long' if annualized volatility > lagged VIX, else 'Short'.

    Parameters:
    -----------
    annualized_vol : pd.Series
        Annualized realized volatility series.
    vix : pd.Series
        VIX index series.
    shift : int, default 21
        Lag to apply to the VIX index.

    Returns:
    --------
    pd.Series
        String series containing 'Long' or 'Short' signals.
    """
    condition = annualized_vol > vix.shift(shift)
    return pd.Series(np.where(condition, 'Long', 'Short'), index=annualized_vol.index)

def calculate_returns(prices: pd.Series) -> pd.Series:
    """
    Calculates the daily percentage change (returns) of a series.

    Parameters:
    -----------
    prices : pd.Series
        Historical price series.

    Returns:
    --------
    pd.Series
        Percentage change returns.
    """
    return prices.pct_change()

def calculate_return_ratios(
    svxy_returns: pd.Series,
    vxx_returns: pd.Series
) -> pd.Series:
    """
    Calculates the returns ratio between SVXY and VXX (multiplied by -1).

    Parameters:
    -----------
    svxy_returns : pd.Series
        Daily returns of SVXY.
    vxx_returns : pd.Series
        Daily returns of VXX.

    Returns:
    --------
    pd.Series
        Returns ratio series.
    """
    return (svxy_returns / vxx_returns) * -1

def calculate_leverage(
    signals: pd.Series,
    svxy_returns: pd.Series,
    vxx_returns: pd.Series,
    vol_difference: pd.Series,
    base_exposure: float = 0.5,
    window: int = 21,
    max_leverage: float = 3.0
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Calculates dynamic leverage components based on volatility ratios and signal strength.

    Parameters:
    -----------
    signals : pd.Series
        Trading signals ('Long' or 'Short').
    svxy_returns : pd.Series
        Daily returns of SVXY.
    vxx_returns : pd.Series
        Daily returns of VXX.
    vol_difference : pd.Series
        Difference between realized volatility and VIX.
    base_exposure : float, default 0.5
        Default base exposure level.
    window : int, default 21
        Rolling window size for calculating returns volatility.
    max_leverage : float, default 3.0
        Maximum allowed leverage level.

    Returns:
    --------
    Tuple[pd.Series, pd.Series, pd.Series, pd.Series]
        (vol_ratio, signal_strength, base_exposure, target_leverage)
    """
    # 1. Calculate rolling standard deviations of returns and the Vol Ratio to ensure the ratio is always positive
    svxy_vol = svxy_returns.rolling(window).std()
    vxx_vol = vxx_returns.rolling(window).std()
    
    vol_ratio = svxy_vol / vxx_vol
    vol_ratio = vol_ratio.fillna(0.50)  # Fallback to post-2018 median
    
    # 2. Normalize signal strength using rolling 252-day mean absolute difference
    abs_diff = vol_difference.abs()
    diff_abs_mean_252 = abs_diff.rolling(252).mean().bfill()
    signal_strength = abs_diff / diff_abs_mean_252
    signal_strength = signal_strength.fillna(1.0)
    
    # 3. Base exposure: VXX is base_exposure, SVXY is base_exposure / Vol Ratio
    base_exp = pd.Series(
        np.where(signals == 'Long', base_exposure, base_exposure / vol_ratio),
        index=signals.index
    )
    
    # 4. Target leverage is Base Exposure scaled by Signal Strength
    target_leverage = base_exp * signal_strength
    target_leverage = target_leverage.clip(0.0, max_leverage).fillna(base_exposure)
    
    return vol_ratio, signal_strength, base_exp, target_leverage

def run_strategy_pipeline(
    df: pd.DataFrame,
    spx_col: str = 'SPX',
    vix_col: str = 'VIX',
    svxy_col: str = 'SVXY Close',
    vxx_col: str = 'VXX Close',
    base_exposure: float = 0.5,
    vol_window: int = 21,
    leverage_window: int = 21,
    max_leverage: float = 3.0
) -> pd.DataFrame:
    """
    Orchestrates the entire volatility strategy pipeline on a DataFrame,
    returning a copy of the input DataFrame with all calculated columns.

    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame containing raw price data.
    spx_col : str, default 'SPX'
        Name of S&P 500 column.
    vix_col : str, default 'VIX'
        Name of VIX index column.
    svxy_col : str, default 'SVXY Close'
        Name of SVXY close column.
    vxx_col : str, default 'VXX Close'
        Name of VXX close column.
    base_exposure : float, default 0.5
        Base target exposure.
    vol_window : int, default 21
        Lookback window for realized volatility calculation.
    leverage_window : int, default 21
        Lookback window for returns volatility calculation.
    max_leverage : float, default 3.0
        Maximum allowed target leverage.

    Returns:
    --------
    pd.DataFrame
        New DataFrame with calculated columns.
    """
    result = df.copy()
    
    # 1. Asset daily returns
    result['SVXY Returns'] = calculate_returns(result[svxy_col])
    result['VXX Returns'] = calculate_returns(result[vxx_col])
    result['Return Ratio (SVXY/VXX)'] = calculate_return_ratios(result['SVXY Returns'], result['VXX Returns'])
    
    # 2. Realized Volatility and signals
    real_vol = calculate_realized_volatility(result[spx_col], window=vol_window)
    result['Annualized Realized Volatility'] = calculate_annualized_volatility(real_vol)
    result['Signal'] = generate_signals(result['Annualized Realized Volatility'], result[vix_col], shift=vol_window)
    
    # 3. Volatility Difference (signed)
    result['VRP ( Realized - VIX )'] = calculate_volatility_difference(
        result['Annualized Realized Volatility'], result[vix_col], shift=vol_window
    )
    
    # 4. Leverage calculations
    vol_ratio, signal_strength, base_exp, target_leverage = calculate_leverage(
        signals=result['Signal'],
        svxy_returns=result['SVXY Returns'],
        vxx_returns=result['VXX Returns'],
        vol_difference=result['VRP ( Realized - VIX )'],
        base_exposure=base_exposure,
        window=leverage_window,
        max_leverage=max_leverage
    )
    
    result['Vol Ratio'] = vol_ratio
    result['Signal Strength'] = signal_strength
    result['Base Exposure'] = base_exp
    result['Target Leverage'] = target_leverage
    
    # We keep the VRP difference signed for clearer plotting and output interpretation
    
    return result
