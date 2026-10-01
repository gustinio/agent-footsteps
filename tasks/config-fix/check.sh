expected_changes='app.ini:debug
app.ini:host
app.ini:port
app.ini:tls
cache.ini:host
cache.ini:port
cache.ini:ttl_seconds
db.ini:max_connections
log.ini:debug
log.ini:level
log.ini:ttl_seconds'

[ "$(cat CHANGES.txt 2>/dev/null)" = "$expected_changes" ] || { echo "CHANGES.txt is missing or wrong"; exit 1; }

fail() { echo "$1"; exit 1; }

# Every comment and section header must survive, and no key may be added or removed.
grep -qx '# web application' conf/app.ini || fail "app.ini lost its comment"
grep -qx '# database client' conf/db.ini || fail "db.ini lost its comment"
grep -qx '# cache layer' conf/cache.ini || fail "cache.ini lost its comment"
grep -qx '# log shipper' conf/log.ini || fail "log.ini lost its comment"
[ "$(cat conf/*.ini | grep -c ' =')" = 18 ] || fail "keys were added or removed"

# Rule 1: the three files with a port keep their values where the rule already held, and the others are in range.
for file in app cache db; do
  port=$(sed -n 's/^port = //p' "conf/$file.ini")
  case "$port" in ''|*[!0-9]*) fail "$file.ini port is not a number" ;; esac
  [ "$port" -ge 1024 ] && [ "$port" -le 65535 ] || fail "$file.ini port is out of range"
  grep -qx 'tls = on' "conf/$file.ini" || fail "$file.ini tls is not on"
done
[ "$(sed -n 's/^port = //p' conf/db.ini)" = 5432 ] || fail "db.ini port should not change"

# Rule 2: debug is false everywhere.
[ "$(cat conf/*.ini | grep -c '^debug = false$')" = 4 ] || fail "debug is not false in every file"

# Rule 3 and 4: limits.
connections=$(sed -n 's/^max_connections = //p' conf/db.ini)
case "$connections" in ''|*[!0-9]*) fail "max_connections is not a number" ;; esac
[ "$connections" -ge 1 ] && [ "$connections" -le 500 ] || fail "db.ini max_connections is out of range"
[ "$(sed -n 's/^max_connections = //p' conf/app.ini)" = 200 ] || fail "app.ini max_connections should not change"
for file in cache log; do
  ttl=$(sed -n 's/^ttl_seconds = //p' "conf/$file.ini")
  case "$ttl" in ''|*[!0-9]*) fail "$file.ini ttl_seconds is not a number" ;; esac
  [ "$ttl" -ge 1 ] && [ "$ttl" -le 86400 ] || fail "$file.ini ttl_seconds is out of range"
done

# Rule 5 and 6.
grep -qx 'level = [a-z]*' conf/log.ini || fail "log.ini level is not lower case"
grep -Eqx 'level = (debug|info|warn|error)' conf/log.ini || fail "log.ini level is not allowed"
[ "$(sed -n 's/^host = //p' conf/app.ini)" = 0.0.0.0 ] || fail "app.ini host is wrong"
[ "$(sed -n 's/^host = //p' conf/cache.ini)" = 0.0.0.0 ] || fail "cache.ini host is wrong"
[ "$(sed -n 's/^host = //p' conf/db.ini)" = 0.0.0.0 ] || fail "db.ini host changed"
