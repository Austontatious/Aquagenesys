PYTHON ?= python3

.PHONY: run web test eval lint

run:
	$(PYTHON) -m aquagenesys.web.app --host 127.0.0.1 --port 8765

web:
	$(PYTHON) -m aquagenesys.web.app --host 127.0.0.1 --port 8765

smoke:
	$(PYTHON) -m pytest -q tests/test_aquagenesys_v03.py

demo:
	$(PYTHON) -m aquagenesys.web.app --host 127.0.0.1 --port 8765 --seed 42

longrun:
	$(PYTHON) -m pytest -q tests/test_aquagenesys_v03.py

test:
	$(PYTHON) -m pytest -q tests

eval:
	$(PYTHON) evals/runner.py --check

lint:
	$(PYTHON) -m py_compile core/config.py core/prompt_loader.py core/llm.py core/trace.py evals/runner.py
	$(PYTHON) -m compileall -q aquagenesys tests
