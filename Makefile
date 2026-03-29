PYTHON ?= python3

.PHONY: install install-dev lint typecheck test security contract-test check ci

install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m compileall throughput_lab llama_nexus_lab scripts tests

typecheck:
	$(PYTHON) -m py_compile throughput_lab/execution_core.py throughput_lab/runtime_service.py scripts/run_core_job.py scripts/run_nexus_pipeline.py llama_nexus_lab/config_loader.py llama_nexus_lab/models.py llama_nexus_lab/pipeline.py llama_nexus_lab/router.py

test:
	$(PYTHON) -m unittest tests/test_execution_core.py tests/test_nexus_config.py tests/test_nexus_pipeline.py tests/test_run_core_job_cli.py tests/test_packet_schema.py

security:
	$(PYTHON) scripts/security_check.py

contract-test:
	$(PYTHON) -m unittest tests/test_run_core_job_cli.py tests/test_packet_schema.py

check: lint typecheck test security

ci: check
