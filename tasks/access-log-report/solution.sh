set -e
valid=$( { cat logs/web-1.log logs/web-2.log; zcat logs/web-3.log.gz; } | grep -E '" [0-9]{3} [0-9]+$')
{
  echo "total_requests: $(echo "$valid" | wc -l)"
  echo "total_bytes: $(echo "$valid" | awk '{ s += $NF } END { print s }')"
  echo "errors_5xx: $(echo "$valid" | awk '$(NF-1) ~ /^5/ { n++ } END { print n + 0 }')"
  echo "top_ip: $(echo "$valid" | awk '{ print $1 }' | sort | uniq -c | sort -k1,1nr | head -1 | awk '{ print $2, $1 }')"
  echo "top_path: $(echo "$valid" | awk '{ print $7 }' | sort | uniq -c | sort -k1,1nr | head -1 | awk '{ print $2, $1 }')"
} > report.txt
echo "$valid" | awk '{ print $(NF-1) }' | sort | uniq -c | awk '{ print $2 "\t" $1 }' > status.tsv
