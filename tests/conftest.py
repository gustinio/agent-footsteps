import json

import pyarrow.parquet as pq
import pytest

from footsteps import segment


@pytest.fixture
def write_segmentation(tmp_path):
    """Writes a segmentation that puts every step of the given step tables in state 0, to test the exporter apart from the fits."""

    def write(*steps_paths):
        states = {method: {} for method in segment.METHODS}
        for path in steps_paths:
            for row in pq.read_table(path).to_pylist():
                for by_run in states.values():
                    by_run.setdefault(row["run_id"], []).append(0)
        states_path = tmp_path / "segmentation.parquet"
        summary_path = tmp_path / "segmentation_summary.json"
        pq.write_table(segment.states_table(states), states_path)
        summary_path.write_text(
            json.dumps(
                {
                    "n_states": 1,
                    "natural_runs": len(states["hmm"]),
                    "state_shares": {method: [1.0] for method in segment.METHODS},
                }
            )
        )
        return states_path, summary_path

    return write
