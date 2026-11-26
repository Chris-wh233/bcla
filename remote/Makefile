.PHONY: help check build up deploy status down
.DEFAULT_GOAL := help

help:
	@./deploy.sh --help

check:
	bash -n deploy.sh
	sh -n container/entrypoint.sh
	sh -n container/stdio.sh
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s ../tests -v

build up deploy status down:
	./deploy.sh $@
