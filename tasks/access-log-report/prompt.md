The directory `logs/` holds web server access logs. One of them is gzip-compressed, and a few lines in each file are corrupted, meaning they do not follow the access log format of the other lines. Ignore the corrupted lines everywhere.

Write `report.txt` with exactly these five lines, in this order:

```
total_requests: <number of valid log lines across all files>
total_bytes: <sum of the bytes field across all valid lines>
errors_5xx: <number of valid lines whose status starts with 5>
top_ip: <the most frequent client IP> <its count>
top_path: <the most requested path> <its count>
```

Also write `status.tsv` with one line per status code that occurs, in ascending order of the code, each as the code, a tab, and the number of valid lines with that code.
