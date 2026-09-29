MANIFEST := datasets/raw.sha256

.PHONY: hash verify

hash:
	shasum -a 256 datasets/raw/* > $(MANIFEST)

verify:
	cd datasets/raw && shasum -a 256 -c ../raw.sha256
