set -e
cd conf
sed -i -E 's/^host = localhost$/host = 0.0.0.0/; s/^port = 80$/port = 8080/; s/^tls = off$/tls = on/; s/^debug = true$/debug = false/' app.ini
sed -i -E 's/^max_connections = 0$/max_connections = 100/' db.ini
sed -i -E 's/^host =$/host = 0.0.0.0/; s/^port = 70000$/port = 6379/; s/^ttl_seconds = -5$/ttl_seconds = 300/' cache.ini
sed -i -E 's/^level = VERBOSE$/level = info/; s/^debug = False$/debug = false/; s/^ttl_seconds = 90000$/ttl_seconds = 86400/' log.ini
cd ..
printf '%s\n' app.ini:debug app.ini:host app.ini:port app.ini:tls cache.ini:host cache.ini:port cache.ini:ttl_seconds db.ini:max_connections log.ini:debug log.ini:level log.ini:ttl_seconds | sort > CHANGES.txt
