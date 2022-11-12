# Trends

## lg-trend.py

### Usage:
`lg-trend.py <option>`

### Options:
`--hours HOURS` : Create a bar graph of electricity usage per hour for the given number of hours.

Example:
`lektrix/bin/lg-trend.py --hours 84`
![alt](lex_pasthours_mains.png)

Two different modifiers are possible:  
`--balance`
![alt](lex_pasthours_mains_balance.png)

`--balances`
![alt](lex_pasthours_mains_balances.png)

The effect of balancing is not always very well visible when using the hours-graph.

`lektrix/bin/lg-trend.py --days 168`
![alt](lex_pastdays_mains.png)

Two different modifiers are possible:  
`--balance`
![alt](lex_pastdays_mains_balance.png)

`--balances`
![alt](lex_pastdays_mains_balances.png)
