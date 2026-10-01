set -e
cat > scripts/normalize.sh <<'SCRIPT'
#!/bin/bash
tr 'A-Z' 'a-z' | tr -cs 'a-z' '\n' | sed '/^$/d'
SCRIPT
cat > scripts/freq.sh <<'SCRIPT'
#!/bin/bash
sort | uniq -c | sort -k1,1nr -k2,2 | awk '{ print $1, $2 }'
SCRIPT
cat > scripts/top.sh <<'SCRIPT'
#!/bin/bash
head -n "$1"
SCRIPT
sed -i 's/^\tcat/\t@mkdir -p out\n\tcat/; s/^\tbash/\t@mkdir -p out\n\tbash/' Makefile
