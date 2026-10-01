set -e
mkdir data
printf 'id,name,region\r\n1,Acme Corp,north\r\n2,Birch Ltd,south\r\n3,Cedar Inc,east\r\n4,Delta Co,west\r\n5,Elm Works,north\r\n6,Fjord AB,south\r\n7,Gale GmbH,east\r\n8,Harbor LLC,west\r\n9,Iris SA,north\r\n10,Juniper BV,south\r\n11,Kestrel Oy,east\r\n12,Linden AS,west\r\n' > data/customers.csv
awk 'function rnd(n) { s = (s * 75 + 74) % 65537; return s % n }
BEGIN {
  s = 5
  for (i = 1; i <= 300; i++) { c = rnd(14) + 1; a = 500 + rnd(49500); printf "%d,%d,%d\n", 1000 + i, c, a }
}' > data/all-orders.tmp
{ echo 'order_id,customer_id,amount_cents'; sed -n '1,150p' data/all-orders.tmp; } > data/orders-q1.csv
{ echo 'order_id,customer_id,amount_cents'; sed -n '121,300p' data/all-orders.tmp; } > data/orders-q2.csv
rm data/all-orders.tmp
