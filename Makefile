install:
	poetry update

test:
	PYTHONPATH=$(PYTHONPATH):$(shell pwd) poetry run pytest

clean:
	rm -rf build dist

build: clean
	poetry build

deploy: build
	poetry publish
	git tag $(shell poetry version -s)
	git push --tags

