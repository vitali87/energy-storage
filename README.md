# energy-storage
A simple energy storage arbitrage profit maximisation model written in Python.

## Context

In typical liberalised wholesale electricity markets, power generators sell the energy they produce and retailers buy energy on behalf of their customers.  Like other goods, the price of electricity depends on supply and demand.  However, both demand and supply fluctuate significantly with time, due to factors such as weather variability and daily work patterns. Although it is possible to store electricity (for example in batteries or hydroelectric dams), it is not cheap to do so. As a result, wholesale electricity prices vary significantly in the short term (e.g. over the course of a day), based on the underlying supply and demand. This price variability creates an opportunity for generators with storage capabilities to generate profits by buying electricity when prices are low and selling when prices are high.

## Task

- This is an optimisation model in Python that charges/discharges the battery over the time period provided (2018-2020) in order to maximise profits. It is assumed that the battery is a price-taker (ie. the actions of the battery have no impact on the market prices).
- In this exercise, we allow the battery to trade across 3 wholesale electricity markets, with prices included in the data file. In each of these markets, the battery can choose to provide some power for some duration of time. The units of the market price are in £/MWh. If the battery were to provide 5MW of power for 30 mins when the market price was 50 £/MWh, it would be paid £125 (5 * 0.5 * 50).

- The battery can export any amount of power up to its maximum discharge rate for any duration of time, as long as it has sufficient energy stored to do so. Likewise, the battery can import any amount of power up to its maximum charge rate for any duration of time, as long as it has sufficient remaining storage capacity to do so Markets 1 and 2 are traded at half-hourly time granularity, whereas Market 3 is traded at daily granularity.

- This means that the price for Markets 1 and 2 changes from one half-hour to the next, whereas the price for Market 3 changes from one day to the next.

- The battery cannot sell the same unit of power into multiple markets, but can divide its power across the markets, e.g. a battery exporting 5MW of power may sell 2MW into Market 1 and 3MW into market, but may not sell 5MW into both Markets 1 and 2.

- For the battery to participate in Markets 1 and 2, it must export/import a constant level of power for the full half-hour period.

- For the battery to participate in Market 3, it must export/import a constant level of power for the full day, i.e. it is not allowed to export/import for a few specific hours only.