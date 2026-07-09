# VIX_Trading_Strategy

ETF structual changes:
 - in nov 2017 the price of the VXX ETF skyrockets because of the nature of the ETF. The ETF constantly bleeds money ebcasue of the premiums its has to pay on the VIX futures becasue of the contago shape of futures price. 

Gearing Reccomendation with suppuorting analysis:

Alternative instruments:

Results with methodology breakdown:

Extra stuff - including key decisions, ambiguity found and assumptions made:

- Sliced the dataframe as to discard the fault data from 2026-03-31 onwards because all the VIX values from that date onwards are 25.25
- sliced original df again becasue the data pre 2018 for the VXX is noisy and not reliable enough to use for this strategy as seen in the 48% negative values for the return ratio during this time.
