# VIX Trading Strategy Backtesting Report & Analysis

This repository contains a quantitative research and backtesting framework for a **VIX/Vega Trading Strategy**. The strategy dynamically switches between long volatility exposure (via **VXX**) and short volatility exposure (via **SVXY**) based on the Volatility Risk Premium (VRP), defined as the difference between rolling annualized realized volatility of the S&P 500 and the lagged VIX index.

---

## 1. ETF Structural Changes & Data Quality Adjustments

To ensure a robust backtest, we identified and adjusted for several critical structural changes in the underlying ETFs and anomalies in the data:

### ETF Structural Dynamics
*   **VXX Roll Yield Decay (Contango Bleed):** 
    The VXX ETF holds a daily rolling long position in first- and second-month VIX futures. Because the VIX futures term structure is in contango ~85% of the time, VXX is forced to constantly sell cheaper near-month contracts and buy more expensive next-month contracts. This negative roll yield leads to a constant long-term decay (often losing 99%+ of its value over multi-year horizons), which triggers frequent reverse stock splits. This explains the extremely high back-adjusted price of VXX in the pre-2018 historical data (e.g., exceeding $1,900/share in late 2017).
*   **SVXY Leverage Halving (February 2018):** 
    During the "Volpocalypse" event of February 5, 2018, the VIX index surged by a record 115% in a single day. The sudden spike wiped out short volatility products (including the liquidation of XIV). To mitigate the risk of a total wipeout, ProShares structurally altered SVXY's target exposure on **February 27, 2018**, reducing its leverage from **-1.0x to -0.5x** of the daily VIX futures index.

### Strategy Adjustments & Risk Parity
*   **Dynamic Exposure Scaling (Vol Ratio):** 
    The strategy incorporates a rolling 21-day volatility ratio of the two ETFs ($VolRatio = \frac{\sigma(SVXY)}{\sigma(VXX)}$) to dynamically adjust position sizes and achieve risk parity:
    *   **Pre-Feb 2018:** SVXY had -1x leverage, resulting in a Vol Ratio of $\approx 1.0$. The strategy held symmetric exposures ($\approx 0.50$ base exposure for both legs).
    *   **Post-Feb 2018:** SVXY leverage was reduced to -0.5x, causing the Vol Ratio to drop to $\approx 0.50$. The strategy dynamically divides SVXY's exposure by this Vol Ratio:
        $$\text{SVXY Exposure} = \frac{\text{Base Exposure}}{\text{Vol Ratio}} = \frac{0.50}{0.50} = 1.00$$
        This doubling of the SVXY position size compensates for the leverage halving, keeping the net volatility risk exposure to the VIX futures constant across the pre- and post-2018 periods.

### Data Cleaning Decisions
*   **Pre-2018 Data Exclusion:** 
    We discarded all data prior to **2018-01-01**. Analysis of the pre-2018 period revealed that **46.52%** of trading days had a negative return ratio between SVXY and VXX. Since one is long VIX and the other is short, their daily returns must be inversely correlated (positive return ratio under our formula). A 46.52% negative ratio indicates severe data corruption, misalignment, or asynchronous pricing in the pre-2018 data. Post-2018, this discrepancy drops to only **2.61%**, validating the cleanliness of the post-2018 data.
*   **Post-March 2026 Cutoff:** 
    The historical dataset was truncated at **2026-03-31**. From this date onwards, the VIX index values in the raw dataset flatline at exactly **25.25** every single day, which represents a corrupted data feed.

---

## 2. Gearing Recommendation & Risk-Management Analysis

We simulated the updated volatility strategy across several base exposures (gearing levels). The codebase has been updated to incorporate two key risk-management and transaction-cost reduction thresholds: a **Rebalance Threshold** (0.05) and a **Signal Activation Threshold** (2.0).

### Performance Comparison Table (2018-01-01 to 2026-03-31)

| Strategy / Gearing Option | Total Return (%) | CAGR (%) | Ann. Volatility (%) | Sharpe Ratio | Sortino Ratio | Max Drawdown (%) | Rebalance Frequency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **S&P 500 Buy & Hold** | **179.33%** | **12.78%** | **19.10%** | **0.7257** | **0.8713** | **-33.79%** | **0.00%** |
| **Strategy (Base=0.25)** | 85.69% | 7.52% | 54.38% | 0.3724 | 0.5081 | -76.79% | 8.60% |
| **Strategy (Base=0.50)** | 3.64% | 0.42% | 86.84% | 0.3945 | 0.5264 | -92.37% | 15.99% |
| **Strategy (Base=0.75)** | -55.05% | -8.94% | 108.72% | 0.4223 | 0.5511 | -96.60% | 32.90% |
| **Strategy (Base=1.00)** | -79.22% | -16.80% | 116.01% | 0.3879 | 0.5102 | -97.27% | 35.87% |

### Gearing Recommendation & Analysis
1.  **Lower Gearing is Superior:** 
    A lower base exposure (such as **0.25**) is strongly recommended over higher exposure levels. At Base = 0.25, the strategy achieves a total return of **85.69%** (CAGR: **7.52%**) and a Sharpe ratio of **0.3724**, while keeping the maximum drawdown at **-76.79%**. 
    At higher exposures (Base = 0.50 to 1.00), the strategy suffers from severe **volatility drag** (compounding decay), resulting in a complete erosion of capital (e.g., losing **79.22%** for Base = 1.00) and catastrophic drawdowns exceeding **-92%**.
2.  **Impact of Rebalancing Thresholds:**
    The introduction of the rebalancing and signal activation thresholds has a massive positive impact on performance:
    *   **Transaction Cost Reduction:** By skipping rebalances when the leverage shift is $< 0.05$ (5%), the rebalance frequency was cut from daily (100%) to only **8.60% of trading days** (for Base = 0.25) and **15.99%** (for Base = 0.50). This saved a massive amount of transaction costs.
    *   **Performance Uplift:** For Base = 0.25, the CAGR improved from **-2.00%** (without thresholds/corrections) to **+7.52%**. For Base = 0.50, the CAGR improved from **-11.85%** to **+0.42%**.
3.  **Final Recommendation:**
    If deploying this strategy, we recommend a **conservative base exposure of 0.25** paired with the active threshold settings.
    However, because the strategy still significantly underperforms the S&P 500 Buy & Hold benchmark on a absolute and risk-adjusted basis (CAGR of 7.52% vs 12.78% with much higher volatility and drawdown), **we do not recommend deploying this strategy in production** in its current form. Further work is required to enhance signal generation (e.g., using VIX futures term structure/roll yield instead of raw realized volatility vs lagged VIX).

---

## 3. Alternative Instruments

*Omitted per user instructions.*

---

## 4. Performance Results & Statistical Significance Testing

### Methodology
*   **Backtest Period:** 2018-01-01 to 2026-03-31 (2,152 trading days).
*   **Transaction Costs:** 20 bps (0.20%) applied as a round-trip fee on the rebalanced volume (both additions, reductions, and switches).
*   **Paired t-Test (vs S&P 500):** We conducted a two-tailed paired-sample t-test on the daily returns of the strategy ($R_{strat, t}$) against the daily returns of the S&P 500 Buy & Hold ($R_{spx, t}$) to evaluate if the strategy's returns are statistically different from the benchmark.
*   **One-Sample t-Test (vs 0):** We conducted a one-sample t-test on the daily returns of the strategy to verify if the average daily return is statistically different from zero.

### Statistical Results (Base = 0.50 Baseline)
*   **Strategy (Base=0.50) vs S&P 500 Buy & Hold:**
    *   **t-statistic:** $0.6538$
    *   **p-value:** $0.5133$
    *   *Interpretation:* There is **no statistically significant difference** between the daily returns of the strategy and the S&P 500.
*   **Strategy (Base=0.50) vs 0:**
    *   **t-statistic:** $1.1529$
    *   **p-value:** $0.2491$
    *   *Interpretation:* The strategy's average daily return is not statistically different from zero.
*   **S&P 500 Buy & Hold vs 0:**
    *   **t-statistic:** $2.1206$
    *   **p-value:** **$0.0341$**
    *   *Interpretation:* The S&P 500 Buy & Hold returns are **statistically significant** ($p < 0.05$), confirming a robust upward drift in the benchmark.

---

## 5. Write-Up: Key Decisions, Ambiguities, & Code Audits

### Key Decisions
1.  **Excluding Pre-2018 Data:** Discarding pre-2018 data was critical. Running the backtester on the noisy pre-2018 data would have yielded completely distorted results because the VXX and SVXY return series in the Excel sheet were moving in the same direction on 46.5% of the days, violating the basic definition of inverse exchange-traded products.
2.  **Dynamic Risk Parity Adjustment:** Implementing the dynamic Vol Ratio scaling for SVXY was essential to correct for the structural halving of its leverage in February 2018.

### Resolved Code Bugs & Enhancements
In the latest updates, we successfully resolved two critical mathematical bugs in the backtester ([src/backtester.py](file:///c:/Users/julia/OneDrive/Documents/Mazi%20-%20internship/VIX_Trading_Strategy/src/backtester.py)) and implemented new rebalancing thresholds:

#### Bug 1: Sign Errors in Addition & Reduction Formulas (Resolved)
The rebalancing formulas for post-rebalance portfolio value $V_t$ were corrected. The buggy code had flipped signs which caused transaction fees to act as an artificial portfolio cash subsidy:
*   **Correct Addition Formula ($L_{target} V_t \ge P_{current}$):** 
    $$V_t = \frac{V_{before} + c \cdot P_{current}}{1 + c \cdot L_{target}}$$
*   **Correct Reduction Formula ($L_{target} V_t < P_{current}$):** 
    $$V_t = \frac{V_{before} - c \cdot P_{current}}{1 - c \cdot L_{target}}$$
    *(Where $c$ is the transaction cost rate, $P_{current}$ is pre-rebalance position value, and $V_{before}$ is pre-rebalance portfolio value).*

#### Bug 2: Daily Net Return Formula Bug (Resolved)
The daily return was corrected to reflect the change in portfolio value from the end of the previous day, rather than relative to the pre-rebalance value $V_{before}$:
*   **Correct Portfolio Return:**
    $$R_{portfolio, t} = \frac{V_t - V_{t-1}}{V_{t-1}}$$
    This resolved the issue where the printed logs incorrectly reported a **0.89%** annualized volatility and a **8.43 Sharpe ratio** instead of the true portfolio fluctuations.

#### Enhancements: Sizing & Rebalance Thresholds (Added)
*   **Rebalance Threshold (`rebalance_threshold = 0.05`):** Skips rebalancing when holding the same asset if the target leverage and effective leverage differ by less than 5%, minimizing transaction cost erosion.
*   **Signal Activation Threshold (`signal_activation_threshold = 2.0`):** Prevents changes in target leverage on weak signals (strength $< 2.0$), keeping exposure at the previous day's level to avoid over-trading in choppy markets.

### Assumptions
*   **Risk-Free Rate:** Assumed to be 0% for Sharpe and Sortino calculations.
*   **Rebalancing execution:** Assumed that rebalancing occurs exactly at the daily closing price without execution slippage.
*   **Liquidity:** Assumed infinite market liquidity and no market impact from trades.
