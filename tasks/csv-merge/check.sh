expected_revenue='region,total_cents
east,1481832
north,1268626
south,1552499
west,1244233'
expected_orphans='1022
1029
1052
1053
1056
1061
1063
1068
1072
1089
1092
1094
1097
1099
1114
1172
1183
1194
1201
1221
1225
1233
1238
1242
1244
1248
1256
1267
1270
1273
1276
1280
1286
1287'

[ "$(cat revenue_by_region.csv 2>/dev/null)" = "$expected_revenue" ] || { echo "revenue_by_region.csv is missing or wrong"; exit 1; }
[ "$(cat orphans.txt 2>/dev/null)" = "$expected_orphans" ] || { echo "orphans.txt is missing or wrong"; exit 1; }
[ "$(cat top_customer.txt 2>/dev/null)" = "Birch Ltd" ] || { echo "top_customer.txt is missing or wrong"; exit 1; }
