set -e
mkdir logs
gen() {
  awk -v s="$2" 'function rnd(n) { s = (s * 75 + 74) % 65537; return s % n }
  BEGIN {
    split("10.0.0.4 10.0.0.9 10.0.0.17 10.0.0.23 10.0.0.31 10.0.0.42 10.0.0.58 10.0.0.77 10.0.1.5 10.0.1.12 10.0.2.8 10.0.2.99", ip, " ")
    split("/ /index.html /login /api/items /api/items/7 /static/app.js /static/app.css /health", path, " ")
    split("200 200 200 200 200 301 404 404 500 503", st, " ")
    for (i = 1; i <= 400; i++) {
      if (i % 97 == 0) { print "-- corrupted line --"; continue }
      k = rnd(16); a = (k >= 12) ? 1 : k + 1
      k = rnd(12); b = (k >= 8) ? 2 : k + 1
      c = rnd(10) + 1; m = rnd(60); sec = rnd(60); bytes = 100 + rnd(5000)
      printf "%s - - [12/Mar/2025:10:%02d:%02d +0000] \"GET %s HTTP/1.1\" %d %d\n", ip[a], m, sec, path[b], st[c], bytes
    }
  }' > "$1"
}
gen logs/web-1.log 11
gen logs/web-2.log 23
gen logs/web-3.log 37
gzip logs/web-3.log
