set -e
mkdir corpus scripts out_placeholder
rmdir out_placeholder
for pair in a:7 b:19 c:31; do
  awk -v s="${pair##*:}" 'function rnd(n) { s = (s * 75 + 74) % 65537; return s % n }
  BEGIN {
    n = split("the The the agent Agent runs steps tests and and checks its own work! don'"'"'t mid-run x2 again, the tool calls. Steps steps and TOOL 42 -- the", w, " ")
    for (line = 1; line <= 60; line++) {
      out = ""
      for (i = 0; i < 8; i++) out = out w[rnd(n) + 1] " "
      print out
    }
  }' > "corpus/${pair%%:*}.txt"
done
for name in normalize freq; do
  printf '#!/bin/bash\necho "TODO: %s" >&2\nexit 1\n' "$name" > "scripts/$name.sh"
done
printf '#!/bin/bash\necho "TODO: top" >&2\nexit 1\n' > scripts/top.sh
sed 's/^    /\t/' > Makefile <<'MAKE'
all: out/top5.txt

out/words.txt: corpus/a.txt corpus/b.txt corpus/c.txt
    cat $^ | bash scripts/normalize.sh > $@

out/freq.txt: out/words.txt
    bash scripts/freq.sh < $< > $@

out/top5.txt: out/freq.txt
    bash scripts/top.sh 5 < $< > $@
MAKE
