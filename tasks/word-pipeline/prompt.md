This directory holds a small text-processing pipeline driven by a `Makefile`, over the text files in `corpus/`. The three scripts in `scripts/` are unfinished stubs, and running `make` does not work yet. Finish the pipeline so that `make` (from a clean checkout, with no `out/` directory) writes `out/top5.txt`.

What each script must do:

- `scripts/normalize.sh`: read text on standard input and write one word per line on standard output. A word is a maximal run of English letters, lowercased. Digits, punctuation and spaces only separate words. Write no empty lines.
- `scripts/freq.sh`: read one word per line and write one line per distinct word as `<count> <word>` (a single space between them), ordered by count from highest to lowest and, for equal counts, by word in byte order.
- `scripts/top.sh N`: write the first N lines of standard input.

Fix whatever else in the `Makefile` stops it from working, and keep the three scripts as separate steps of the pipeline.
