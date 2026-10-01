output=$(bash "$TASK_DIR/files/test_backup.sh" ./backup.sh 2>&1) || { echo "$output" | grep FAIL | head -3; exit 1; }
