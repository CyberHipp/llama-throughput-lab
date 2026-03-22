PYTHON ?= python3

.PHONY: test lint typecheck check ci

test:
	$(PYTHON) -m unittest tests/test_execution_core.py

lint:
	$(PYTHON) -m compileall throughput_lab scripts/run_core_job.py tests/test_execution_core.py

typecheck:
	$(PYTHON) -m py_compile throughput_lab/execution_core.py throughput_lab/runtime_service.py scripts/run_core_job.py

check: lint typecheck test

ci: check
