#test_remediator.py

from remediator import remediate_pdf

input_path = "sample.pdf"
output_path = "sample_remediated.pdf"

title, author, keywords = remediate_pdf("sample.pdf", "sample_remediated.pdf")
print("\n✅ Remediation complete:")
print(f"Title: {title}")
print(f"Author: {author}")
print(f"Keywords: {keywords}")

