The directory `repo/` is a git repository whose branch is `main`. Answer three questions about its history and then make one change on a new branch.

Write `answers.txt` in the current directory (not inside `repo/`) with exactly three lines:

1. The full hash of the commit that first added the text `API_TOKEN=abc123` to the repository.
2. The name of the author of the most recent commit that changed `src/util.sh`.
3. The number of commits on `main` that changed any file under `src/`.

Then, in `repo/`, create a branch `no-token` with exactly one new commit on top of the current `main` that removes every line containing `API_TOKEN` from `config.sh`. Leave `main` as it is.
