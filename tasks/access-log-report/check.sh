expected_report='total_requests: 1188
total_bytes: 3170235
errors_5xx: 271
top_ip: 10.0.0.4 378
top_path: /index.html 490'
expected_status=$'200\t578\n301\t108\n404\t231\n500\t128\n503\t143'

[ "$(cat report.txt 2>/dev/null)" = "$expected_report" ] || { echo "report.txt is missing or wrong"; exit 1; }
[ "$(cat status.tsv 2>/dev/null)" = "$expected_status" ] || { echo "status.tsv is missing or wrong"; exit 1; }
