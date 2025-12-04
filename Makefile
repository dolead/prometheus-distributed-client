CODE=prometheus_distributed_client/

clean:
	rm -rf build dist .coverage

test:
	PYTHONPATH=$(PYTHONPATH):$(shell pwd) poetry run pytest

build: clean lint test
	poetry build

publish: build
	poetry publish
	git tag $(shell poetry version -s)
	git push --tags

lint:
	poetry check
	poetry run pycodestyle --ignore=E126,E127,E128,W503 $(CODE)
	# poetry run mypy --ignore-missing-imports $(CODE)
	poetry run black --check --verbose $(CODE)
	# poetry run pylint $(CODE) -d I0011,R0901,R0902,R0801,C0111,C0103,C0411,C0415,R0903,R0913,R0914,R0915,R1710,W0613,W0703
