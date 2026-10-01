expected_inventory='README.txt
a1.txt
a2.txt
b1.txt
c1.txt
c2.log
decoy-token.txt.bak
token.txt'

[ "$(cat answer.txt 2>/dev/null)" = "TOKEN-7f3a-91c2-ZEBRA" ] || { echo "answer.txt is missing or wrong"; exit 1; }
[ "$(cat inventory.txt 2>/dev/null)" = "$expected_inventory" ] || { echo "inventory.txt is missing or wrong"; exit 1; }
[ "$(tar -tzf bundle.tar.gz 2>/dev/null | wc -l)" -ge 4 ] || { echo "bundle.tar.gz was changed"; exit 1; }
