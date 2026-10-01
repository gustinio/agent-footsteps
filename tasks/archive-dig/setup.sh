set -e
work=$PWD
build=$(mktemp -d)
cd "$build"
mkdir vault inner parta partb top
echo 'TOKEN-7f3a-91c2-ZEBRA' > vault/token.txt
echo 'not this one' > vault/decoy-token.txt.bak
tar -cf inner/vault.tar -C vault .
echo 'second level note' > inner/b1.txt
tar -czf parta/inner.tar.gz -C inner .
echo 'first part, file one' > parta/a1.txt
echo 'first part, file two' > parta/a2.txt
tar -cjf top/part-a.tar.bz2 -C parta .
echo 'second part, file one' > partb/c1.txt
echo 'a log line' > partb/c2.log
tar -czf top/part-b.tar.gz -C partb .
echo 'Two parts are inside.' > top/README.txt
tar -czf "$work/bundle.tar.gz" -C top .
rm -rf "$build"
