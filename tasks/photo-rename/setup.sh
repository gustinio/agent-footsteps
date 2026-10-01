set -e
mkdir photos
cd photos
for name in "IMG 001 (final).JPG" "img_002-Copy.jpeg" "IMG 003.jpg" "IMG 004.JPEG" "Holiday Pics (1).JPG" "holiday pics (1).jpg" "Beach Day!!.jpeg" "  leading space.jpg" "UPPER.JPG" "mixed-Case_Name.Jpg" "dots.in.name.jpg" "résumé scan.jpg" "a  b.jpg" "already_ok.jpg" "notes.txt"; do
  printf '%s' "$name" > "$name"
done
