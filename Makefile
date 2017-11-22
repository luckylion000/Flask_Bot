.PHONY: clean install pep8

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . \( -name '*.pyc' -o -name '*.pyo' -o -type d -empty \) -exec rm -rf {} +

distclean: clean
	rm -rf node_modules bower_components

pep8:
	flake8 .

eslint:
	npm run lint

lint: pep8 eslint

install-py:
	pip3 install -r requirements/base.txt

install-static:
	npm install bower
	./node_modules/bower/bin/bower install --allow-root

copy-fonts:
	mkdir -p static/dist/fonts
	cp bower_components/bootstrap/dist/fonts/* static/dist/fonts
	cp bower_components/open-sans-fontface/fonts/Bold/* static/dist/fonts
	cp bower_components/open-sans-fontface/fonts/Semibold/* static/dist/fonts
	cp static/inspinia_v2.7.1/font-awesome/fonts/* static/dist/fonts
	cp -r static/landing/icomoon-fonts static/dist/fonts

copy-datatable-icons:
	mkdir -p static/dist/images
	cp bower_components/datatables/media/images/* static/dist/images

copy-amcharts-images:
	mkdir -p static/dist/amcharts/images
	cp bower_components/amcharts/dist/amcharts/images/* static/dist/amcharts/images

install: install-py install-static copy-fonts copy-datatable-icons copy-amcharts-images

test:
	PYTHONPATH=. pytest tests
