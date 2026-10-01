set -e
customers=$(mktemp)
orders=$(mktemp)
tr -d '\r' < data/customers.csv | tail -n +2 > "$customers"
{ tail -n +2 data/orders-q1.csv; tail -n +2 data/orders-q2.csv; } | sort -t, -k1,1n -u > "$orders"
{
  echo 'region,total_cents'
  awk -F, 'NR == FNR { region[$1] = $3; next } $2 in region { total[region[$2]] += $3 } END { for (r in total) print r "," total[r] }' "$customers" "$orders" | sort
} > revenue_by_region.csv
awk -F, 'NR == FNR { known[$1]; next } !($2 in known) { print $1 }' "$customers" "$orders" | sort -n > orphans.txt
awk -F, 'NR == FNR { name[$1] = $2; next } $2 in name { total[$2] += $3 } END { for (c in total) print total[c], name[c] }' "$customers" "$orders" | sort -k1,1nr | head -1 | cut -d' ' -f2- > top_customer.txt
