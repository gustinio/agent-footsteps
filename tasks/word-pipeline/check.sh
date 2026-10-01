fail() { echo "$1"; exit 1; }

expected_top5='268 the
148 and
126 steps
105 tool
101 agent'

# The checks run in a copy so that the agent's own out/ directory does not matter.
copy=$(mktemp -d)
cp -r Makefile corpus scripts "$copy"
(cd "$copy" && make > /dev/null 2>&1) || fail "make fails from a clean checkout"
[ "$(cat "$copy/out/top5.txt" 2>/dev/null)" = "$expected_top5" ] || fail "out/top5.txt is missing or wrong"
rm -rf "$copy"

[ "$(printf 'Hello, World! hello42 x-y\n\n' | bash scripts/normalize.sh)" = "$(printf 'hello\nworld\nhello\nx\ny')" ] || fail "normalize.sh is wrong"
[ "$(printf 'b\na\nb\nc\na\nb\nc\n' | bash scripts/freq.sh)" = "$(printf '3 b\n2 a\n2 c')" ] || fail "freq.sh is wrong"
[ "$(printf '1\n2\n3\n' | bash scripts/top.sh 2)" = "$(printf '1\n2')" ] || fail "top.sh is wrong"
