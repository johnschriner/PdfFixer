#!/bin/bash
set -e

echo "🔄 Starting remediation pipeline..."
echo "📁 Cleaning previous results..."
rm -rf results/*
rm -rf visuals/*
rm -rf structured_output/*

echo "✅ Input folder: input"
echo "✅ Results folder: results"
echo "✅ Visuals folder: visuals"
echo "✅ Structured output folder: structured_output"

for input_pdf in input/*.pdf; do
    filename=$(basename "$input_pdf")
    base="${filename%.*}"
    echo "➡️ Processing: $input_pdf"

    echo "🔎 Step 1: Extracting visuals (direct & AI fallback)..."
    python3 extract_visuals.py "$input_pdf" --output visuals

    echo "📝 Step 2: Generating alt-text for visuals..."
    python3 generate_alt_text.py --visuals visuals

    echo "🔗 Step 3: Embedding alt-text into PDF..."
    python3 embed_alt_text.py "$input_pdf" --visuals visuals --output "results/${base}_alt_text_embedded.pdf"

    echo "🌐 Step 4: Setting document language tag..."
    python3 set_lang.py "results/${base}_alt_text_embedded.pdf" "results/${base}_lang.pdf"

    echo "🗂 Step 5: Extracting structured metadata (title, author)..."
    python3 extract_structured_data.py "$input_pdf" --output structured_output

    echo "🛠 Step 6: Adding PDF structure, metadata & headings..."
    python3 add_structure.py "results/${base}_lang.pdf" --structured structured_output --output "results/${base}_final.pdf"

    echo "✅ Processing complete for $filename"
done

echo "🎉 All PDFs processed. Check the results folder for output."
