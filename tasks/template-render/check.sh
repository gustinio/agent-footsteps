fail() { echo "$1"; exit 1; }

expected_server='# Orbit Dashboard (staging)
listen 8443
workers 4
owner "platform team"'
expected_motd='Welcome to Orbit Dashboard.
Environment: staging
Contact: nobody@example.com'

# Each scenario runs in its own copy so the agent's out/ directory does not matter.
scenario() {
  copy=$(mktemp -d)
  cp -r render.sh templates values.env "$copy"
  cd "$copy" || exit 1
}

# One key is missing: the other templates still render, and the run fails.
scenario
stderr=$(bash render.sh 2>&1 > /dev/null)
status=$?
[ "$status" = 1 ] || fail "exit status should be 1 when a key is missing"
[ "$stderr" = "missing: REGION" ] || fail "the missing key is not reported as expected"
[ ! -e out/health.json ] || fail "a template with a missing key must not be written"
[ "$(cat out/server.conf 2>/dev/null)" = "$expected_server" ] || fail "server.conf is wrong"
[ "$(cat out/motd.txt 2>/dev/null)" = "$expected_motd" ] || fail "motd.txt is wrong"
cd - > /dev/null || exit 1

# Several missing keys are each reported once, in order of first use.
scenario
echo '{{B_KEY}} {{A_KEY}} {{B_KEY}}' > templates/zz.tmpl
stderr=$(bash render.sh 2>&1 > /dev/null)
[ "$stderr" = "$(printf 'missing: REGION\nmissing: B_KEY\nmissing: A_KEY')" ] || fail "missing keys are not reported once each in order"
[ ! -e out/zz ] || fail "zz must not be written"
cd - > /dev/null || exit 1

# With every key set the run succeeds.
scenario
echo 'REGION=eu-west' >> values.env
bash render.sh 2> /dev/null || fail "exit status should be 0 when nothing is missing"
[ "$(cat out/health.json 2>/dev/null)" = '{"service": "Orbit Dashboard", "port": 8443, "region": "eu-west"}' ] || fail "health.json is wrong"
[ "$(cat out/server.conf)" = "$expected_server" ] || fail "server.conf is wrong when all keys are set"
