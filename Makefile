PYTHON ?= python3

.PHONY: install install-dev lint typecheck test security contract-test check ci

install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m compileall throughput_lab llama_nexus_lab scripts tests

typecheck:
	$(PYTHON) -m py_compile throughput_lab/execution_core.py throughput_lab/runtime_service.py scripts/run_core_job.py scripts/run_nexus_pipeline.py scripts/run_nexus_governed_smoke.py scripts/run_nexus_tui.py llama_nexus_lab/config_loader.py llama_nexus_lab/models.py llama_nexus_lab/pipeline.py llama_nexus_lab/router.py llama_nexus_lab/runtime.py llama_nexus_lab/verify.py llama_nexus_lab/gauntlet.py llama_nexus_lab/email_turn_adapter.py

test:
	$(PYTHON) -m unittest tests/test_execution_core.py tests/test_nexus_config.py tests/test_nexus_pipeline.py tests/test_verify.py tests/test_nexus_tui.py tests/test_nexus_presets.py tests/test_nexus_queue.py tests/test_email_turn_adapter.py tests/test_run_core_job_cli.py tests/test_packet_schema.py tests/test_runner_cli_envelopes.py tests/test_automation_runtime_state.py tests/test_control_plane.py

security:
	$(PYTHON) scripts/security_check.py

contract-test:
	$(PYTHON) -m unittest tests/test_run_core_job_cli.py tests/test_packet_schema.py

check: lint typecheck test security

ci: check
