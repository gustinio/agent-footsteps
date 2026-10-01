The directory `data/` holds a customer list (`customers.csv`) and two order exports (`orders-q1.csv` and `orders-q2.csv`). The exports overlap, so some orders appear in both files and must be counted once. Some orders belong to a customer id that is not in the customer list. Those orders are orphans and are left out of all totals.

Produce these files in the current directory:

- `revenue_by_region.csv`: the header line `region,total_cents`, then one line per region with the sum of `amount_cents` of its orders, sorted by region name.
- `orphans.txt`: the order ids of the orphan orders, one per line, each once, in ascending numeric order.
- `top_customer.txt`: one line with the name of the customer with the highest total `amount_cents`.
