"""Two 32x32 renders for the experiment harness smoke test (T1.4)."""

from painterly_analysis.experiment import Job

JOBS = [
    Job.make("smoke", 0, size=32, passes=2),
    Job.make("smoke", 1, size=32, passes=2),
]
