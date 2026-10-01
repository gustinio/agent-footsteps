expected_answers='a1e3a057f438e01f276663d2747709c972a65f45
Cy
5'

fail() { echo "$1"; exit 1; }

[ "$(cat answers.txt 2>/dev/null)" = "$expected_answers" ] || fail "answers.txt is missing or wrong"
cd repo 2> /dev/null || fail "repo/ is missing"
git rev-parse --verify -q no-token > /dev/null || fail "branch no-token does not exist"
[ "$(git rev-list --count main..no-token)" = 1 ] || fail "no-token is not exactly one commit ahead of main"
[ "$(git rev-parse no-token~1)" = "$(git rev-parse main)" ] || fail "no-token does not start at main"
[ "$(git show no-token:config.sh)" = "PORT=8080" ] || fail "config.sh on no-token is wrong"
[ "$(git show main:config.sh)" = "$(printf 'PORT=8080\nAPI_TOKEN=changeme')" ] || fail "main was changed"
