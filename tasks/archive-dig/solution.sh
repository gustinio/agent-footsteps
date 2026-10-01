set -e
work=$PWD
scratch=$(mktemp -d)
cp bundle.tar.gz "$scratch"
cd "$scratch"
tar -xzf bundle.tar.gz
rm bundle.tar.gz
while archive=$(find . -type f \( -name '*.tar' -o -name '*.tar.gz' -o -name '*.tar.bz2' \) | head -1) && [ -n "$archive" ]; do
  tar -xf "$archive" -C "$(dirname "$archive")"
  rm "$archive"
done
cat "$(find . -name token.txt)" > "$work/answer.txt"
find . -type f -printf '%f\n' | sort > "$work/inventory.txt"
rm -rf "$scratch"
