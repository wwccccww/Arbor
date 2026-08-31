from __future__ import annotations

import json

from arbor.adapters.inbound.demo_smoke import (
    demo_baseline_path,
    demo_manifest_path,
    run_demo_smoke,
)


def test_demo_v1_smoke_matches_baseline():
    live = run_demo_smoke(manifest_path=demo_manifest_path())
    baseline_path = demo_baseline_path()
    assert baseline_path.is_file()
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert live.get("step_pass_rate") == baseline.get("step_pass_rate")
    assert len(live.get("steps") or []) == len(baseline.get("steps") or [])
    for step in live.get("steps") or []:
        assert step.get("ok") is True, step


def test_demo_recording_artifact_present():
    from arbor.paths import repo_root

    recording = repo_root() / "docs" / "demo" / "recordings" / "agent-production-demo.mp4"
    assert recording.is_file(), "P2 recording missing — see docs/demo-script.md"
    assert recording.stat().st_size > 10_000
