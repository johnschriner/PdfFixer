#!/bin/bash
# Embed fonts and prepare final output PDF
gs   -dPDFA=2 -dBATCH -dNOPAUSE   -sColorConversionStrategy=UseDeviceIndependent   -sDEVICE=pdfwrite -dEmbedAllFonts=true   -dPDFSETTINGS=/prepress   -sOutputFile=results/sample_structured_final.pdf   results/sample_structured_struct.pdf
