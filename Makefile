.PHONY: dev test verify

dev:
	cd meditech_rag && python app.py

test:
	cd meditech_rag && python -m unittest discover -s tests -v

verify:
	cd meditech_rag && python scripts/verify_five_day_mvp.py
