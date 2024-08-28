import coverage
import sys

COVERAGE_THRESHOLD = 100

cov = coverage.Coverage()
cov.start()

import pytest
retcode = pytest.main(["./tests/test_json_repair.py", "--cov-config=.coveragerc"])

cov.stop()
cov.save()
coverage_percent = cov.report(show_missing=True)

if coverage_percent < COVERAGE_THRESHOLD:
    print(f"ERROR: Coverage {coverage_percent:.2f}% is below the threshold of {COVERAGE_THRESHOLD}%")
    sys.exit(1)  # This will prevent the commit/push