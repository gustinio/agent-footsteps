`bundle.tar.gz` is an archive that contains other archives, nested several levels deep, mixed with ordinary files. Do not modify `bundle.tar.gz`.

Write two files in the current directory:

- `answer.txt`: the contents of the file named exactly `token.txt` that is stored somewhere inside the nested archives (a single line, as it appears in that file). Another file has a similar name, so check the exact name.
- `inventory.txt`: the names (without directories) of every ordinary file found at any level, one per line, sorted in byte order. Archives themselves are not listed, only the files they contain.
