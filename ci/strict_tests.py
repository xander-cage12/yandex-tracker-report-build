import json
import os
import sys
import unittest
from pathlib import Path
suite = unittest.defaultTestLoader.discover("tests")
result = unittest.TextTestRunner(verbosity=2).run(suite)
summary = {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures), "unexpected_successes": len(result.unexpectedSuccesses)}
Path(os.environ["YTR_TEST_RESULTS"]).write_text(json.dumps(summary), encoding="utf-8")
ok = result.wasSuccessful() and result.testsRun == 42 and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
sys.exit(0 if ok else 1)
