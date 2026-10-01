set -e
git init -q -b main repo
cd repo
mkdir src
commit() {
  local who=$1 day=$2 message=$3
  git add -A
  GIT_AUTHOR_NAME="$who" GIT_AUTHOR_EMAIL="$who@example.com" GIT_COMMITTER_NAME="$who" GIT_COMMITTER_EMAIL="$who@example.com" \
    GIT_AUTHOR_DATE="2025-01-$day"T10:00:00+0000 GIT_COMMITTER_DATE="2025-01-$day"T10:00:00+0000 \
    git commit -q -m "$message"
}
echo 'greet() { echo hi; }' > src/util.sh
echo 'PORT=8080' > config.sh
echo '# demo' > README.md
commit Ana 01 "Add util and config"
echo '. src/util.sh; greet' > src/main.sh
commit Ben 02 "Add main script"
echo 'greet() { echo "hello, $1"; }' > src/util.sh
commit Ana 03 "Improve greet"
echo 'API_TOKEN=abc123' >> config.sh
commit Cy 04 "Add token for staging"
echo 'echo "version 1"' >> src/main.sh
commit Ben 05 "Print the version"
echo 'Run src/main.sh.' >> README.md
commit Ana 06 "Document the entry point"
echo 'farewell() { echo "bye, $1"; }' >> src/util.sh
commit Cy 07 "Add farewell"
sed -i 's/abc123/changeme/' config.sh
commit Ben 08 "Scrub the token"
echo 'See config.sh for settings.' >> README.md
commit Ana 09 "Point to the settings"
