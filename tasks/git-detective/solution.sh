set -e
cd repo
{
  git log --format=%H -S'API_TOKEN=abc123' | tail -1
  git log -1 --format=%an -- src/util.sh
  git log --oneline -- src | wc -l
} > ../answers.txt
git checkout -q -b no-token
sed -i '/API_TOKEN/d' config.sh
git add config.sh
GIT_AUTHOR_NAME=Solver GIT_AUTHOR_EMAIL=solver@example.com GIT_COMMITTER_NAME=Solver GIT_COMMITTER_EMAIL=solver@example.com git commit -q -m "Remove the token"
