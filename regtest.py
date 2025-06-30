#regtest

import fitz

doc = fitz.open("sample.pdf")
text = doc[0].get_text()
print(text)