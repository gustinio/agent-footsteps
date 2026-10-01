The directory `photos/` holds photo files with messy names, plus one text file. Rename the photos by these rules:

1. Only files with the extension `jpg` or `jpeg`, in any letter case, are renamed. Other files stay as they are.
2. The new name is built from the part of the name before the final dot. Lowercase it, replace every run of characters other than `a-z` and `0-9` with a single underscore, then remove underscores from the start and the end. The new extension is always `.jpg`.
3. If two files would get the same new name, the file whose original name comes first in plain byte order keeps it, and each later one gets `_2`, `_3` and so on added before the extension, in byte order of the original names.
4. A file that already has its new name is left alone.

Keep every file's contents unchanged. Also write `renames.tsv` in the current directory with one line per file you renamed, as the original name, a tab, and the new name, sorted by original name in byte order.
