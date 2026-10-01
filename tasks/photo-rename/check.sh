expected_files='a_b.jpg
already_ok.jpg
beach_day.jpg
dots_in_name.jpg
holiday_pics_1.jpg
holiday_pics_1_2.jpg
img_001_final.jpg
img_002_copy.jpg
img_003.jpg
img_004.jpg
leading_space.jpg
mixed_case_name.jpg
notes.txt
r_sum_scan.jpg
upper.jpg'
expected_renames=$(cat <<'TSV'
  leading space.jpg	leading_space.jpg
Beach Day!!.jpeg	beach_day.jpg
Holiday Pics (1).JPG	holiday_pics_1.jpg
IMG 001 (final).JPG	img_001_final.jpg
IMG 003.jpg	img_003.jpg
IMG 004.JPEG	img_004.jpg
UPPER.JPG	upper.jpg
a  b.jpg	a_b.jpg
dots.in.name.jpg	dots_in_name.jpg
holiday pics (1).jpg	holiday_pics_1_2.jpg
img_002-Copy.jpeg	img_002_copy.jpg
mixed-Case_Name.Jpg	mixed_case_name.jpg
résumé scan.jpg	r_sum_scan.jpg
TSV
)

[ "$(ls photos 2>/dev/null)" = "$expected_files" ] || { echo "photos/ does not hold the expected names"; exit 1; }
[ "$(cat renames.tsv 2>/dev/null)" = "$expected_renames" ] || { echo "renames.tsv is missing or wrong"; exit 1; }
while IFS=$'\t' read -r original renamed; do
  [ "$(cat "photos/$renamed")" = "$original" ] || { echo "contents of $renamed changed"; exit 1; }
done <<< "$expected_renames"
[ "$(cat photos/already_ok.jpg)" = "already_ok.jpg" ] || { echo "already_ok.jpg changed"; exit 1; }
[ "$(cat photos/notes.txt)" = "notes.txt" ] || { echo "notes.txt changed"; exit 1; }
