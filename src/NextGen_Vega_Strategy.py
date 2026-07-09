"""
Backward-compatibility wrapper for NextGen_Vega_Strategy.
Exposes the same function names, parameters, and in-place DataFrame mutations,
but delegates the mathematical calculations to the new modular strategy.py module.
"""

import pandas as pd

try:
    from . import strategy
except ImportError:
    import strategy

def calculate_realized_volitality(df: pd.DataFrame, col: str = 'SPX', t: int = 21) -> pd.Series:
    """Legacy wrapper for realized volatility calculation."""
    return strategy.calculate_realized_volatility(df[col], window=t)

def calculate_annualized_realized_volitality(df: pd.DataFrame, col: str = 'SPX', t: int = 21) -> None:
    """Legacy wrapper that mutates DataFrame with annualized volatility."""
    daily_vol = strategy.calculate_realized_volatility(df[col], window=t)
    df['Annualized Realized Volitality'] = strategy.calculate_annualized_volatility(daily_vol)

def get_signals(df: pd.DataFrame) -> None:
    """Legacy wrapper that mutates DataFrame with trading signals."""
    if 'Annualized Realized Volitality' not in df.columns:
        calculate_annualized_realized_volitality(df)
    df['Signal'] = strategy.generate_signals(
        df['Annualized Realized Volitality'], df['VIX'], shift=21
    )

def calculate_svxy_daily_returns(df: pd.DataFrame) -> None:
    """Legacy wrapper that mutates DataFrame with SVXY returns."""
    df['SVXY Returns'] = strategy.calculate_returns(df['SVXY Close'])

def calculate_vxx_daily_returns(df: pd.DataFrame) -> None:
    """Legacy wrapper that mutates DataFrame with VXX returns."""
    df['VXX Returns'] = strategy.calculate_returns(df['VXX Close'])

def calculate_return_ratios(df: pd.DataFrame) -> None:
    """Legacy wrapper that mutates DataFrame with SVXY/VXX returns ratio."""
    if 'SVXY Returns' not in df.columns:
        calculate_svxy_daily_returns(df)
    if 'VXX Returns' not in df.columns:
        calculate_vxx_daily_returns(df)
    df['Return Ratio (SVXY/VXX)'] = strategy.calculate_return_ratios(
        df['SVXY Returns'], df['VXX Returns']
    )

def calculate_strategy_returns(df: pd.DataFrame) -> None:
    """Legacy wrapper that mutates DataFrame with strategy returns."""
    if 'Signal' not in df.columns:
        get_signals(df)
    if 'SVXY Returns' not in df.columns:
        calculate_svxy_daily_returns(df)
    if 'VXX Returns' not in df.columns:
        calculate_vxx_daily_returns(df)
    df['Strategy Returns'] = strategy.calculate_strategy_returns(
        df['Signal'], df['VXX Returns'], df['SVXY Returns']
    )

def realized_volitality_difference_to_VIX(df: pd.DataFrame) -> None:
    """Legacy wrapper that mutates DataFrame with volatility difference."""
    if 'Annualized Realized Volitality' not in df.columns:
        calculate_annualized_realized_volitality(df)
    df['Difference between Actual and Predicted vol'] = strategy.calculate_volatility_difference(
        df['Annualized Realized Volitality'], df['VIX'], shift=21
    )

def calculate_leverage(df: pd.DataFrame, base_exposure: float = 0.5, window: int = 21, max_leverage: float = 3.0) -> None:
    """Legacy wrapper that mutates DataFrame with dynamic leverage columns."""
    if 'Signal' not in df.columns:
        get_signals(df)
    if 'SVXY Returns' not in df.columns:
        calculate_svxy_daily_returns(df)
    if 'VXX Returns' not in df.columns:
        calculate_vxx_daily_returns(df)
    if 'Difference between Actual and Predicted vol' not in df.columns:
        realized_volitality_difference_to_VIX(df)
        
    vol_ratio, signal_strength, base_exp, target_leverage = strategy.calculate_leverage(
        signals=df['Signal'],
        svxy_returns=df['SVXY Returns'],
        vxx_returns=df['VXX Returns'],
        vol_difference=df['Difference between Actual and Predicted vol'],
        base_exposure=base_exposure,
        window=window,
        max_leverage=max_leverage
    )
    
    df['Vol Ratio'] = vol_ratio
    df['Signal Strength'] = signal_strength
    df['Base Exposure'] = base_exp
    df['Target Leverage'] = target_leverage
    df['Difference between Actual and Predicted vol'] = df['Difference between Actual and Predicted vol'].abs()
