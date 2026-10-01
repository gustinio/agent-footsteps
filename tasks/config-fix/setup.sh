set -e
mkdir conf
cat > conf/POLICY.txt <<'POLICY'
1. Every `port` is a number from 1024 to 65535.
2. `debug` is `false` in every file.
3. `max_connections` is a number from 1 to 500.
4. `ttl_seconds` is a number from 1 to 86400.
5. `level` is one of debug, info, warn, error, in lower case.
6. `host` is never empty and never `localhost`; use `0.0.0.0`.
7. `tls` is `on` wherever a `port` is set.
POLICY
cat > conf/app.ini <<'INI'
# web application
[server]
host = localhost
port = 80
tls = off
debug = true

[limits]
max_connections = 200
INI
cat > conf/db.ini <<'INI'
# database client
[server]
host = 0.0.0.0
port = 5432
tls = on
debug = false

[limits]
max_connections = 0
INI
cat > conf/cache.ini <<'INI'
# cache layer
[server]
host =
port = 70000
tls = on
debug = false

[expiry]
ttl_seconds = -5
INI
cat > conf/log.ini <<'INI'
# log shipper
[output]
level = VERBOSE
debug = False

[expiry]
ttl_seconds = 90000
INI
