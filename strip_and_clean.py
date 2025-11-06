#!/usr/bin/env python3
import argparse, os, sys, glob
from datetime import datetime, timezone
import pikepdf

def get_info_str(info, key):
    try:
        v = info.get(key, "")
        return "" if v is None else str(v)
    except Exception:
        return ""

def build_xmp_packet(title, author, keywords):
    def esc(s):
        return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # dc:title
    title_xml = f'''
      <dc:title>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">{esc(title)}</rdf:li>
        </rdf:Alt>
      </dc:title>''' if title else ""

    # dc:creator
    creators_xml = ""
    if author:
        creators_xml = f'''
      <dc:creator>
        <rdf:Seq>
          <rdf:li>{esc(author.strip())}</rdf:li>
        </rdf:Seq>
      </dc:creator>'''

    # pdf:Keywords
    keywords_xml = f'''
      <pdf:Keywords>{esc(keywords)}</pdf:Keywords>''' if keywords else ""

    # return clean XMP (no BOM)
    return f'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF
     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:xmp="http://ns.adobe.com/xap/1.0/"
     xmlns:pdf="http://ns.adobe.com/pdf/1.3/">
    <rdf:Description rdf:about="">
{title_xml}{creators_xml}{keywords_xml}
      <xmp:CreateDate>{now}</xmp:CreateDate>
      <xmp:ModifyDate>{now}</xmp:ModifyDate>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''


def get_root(pdf):
    return getattr(pdf, "root", None) or pdf.trailer["/Root"]

def hard_reset_info(pdf):
    for k in list(pdf.docinfo.keys()):
        try: del pdf.docinfo[k]
        except Exception:
            try:
                pdf.docinfo[k] = pikepdf.String(""); del pdf.docinfo[k]
            except Exception: pass

def clean_one(in_path, out_path, inplace=False, verbose=True):
    try:
        with pikepdf.open(in_path) as pdf:
            info = pdf.docinfo or pikepdf.Dictionary()
            title    = get_info_str(info, "/Title")
            author   = get_info_str(info, "/Author")
            keywords = get_info_str(info, "/Keywords")
            # We intentionally IGNORE any existing /Subject

            if verbose:
                print(f"[READ] {in_path}")
                print(f"       Title   : {title}")
                print(f"       Author  : {author}")
                print(f"       Keywords: {keywords}")

            # Remove existing XMP
            try:
                root = get_root(pdf)
                if "/Metadata" in root: del root["/Metadata"]
            except Exception: pass

            # Clear all Info keys
            hard_reset_info(pdf)

            # Re-add ONLY Title, Author, Keywords (NO Subject, NO Creator)
            if title:    pdf.docinfo["/Title"]    = pikepdf.String(title)
            if author:   pdf.docinfo["/Author"]   = pikepdf.String(author)
            if keywords: pdf.docinfo["/Keywords"] = pikepdf.String(keywords)
            # Do not set /Creator at all

            # Fresh minimal XMP (no pdf:Subject, no dc:subject)
            xmp_xml = build_xmp_packet(title, author, keywords)
            metadata_stream = pikepdf.Stream(pdf, xmp_xml.encode("utf-8"))
            metadata_stream.Type = pikepdf.Name("/Metadata")
            metadata_stream.Subtype = pikepdf.Name("/XML")
            get_root(pdf)["/Metadata"] = metadata_stream

            if inplace:
                pdf.save(in_path)
                if verbose: print(f"[WRITE] In-place updated: {in_path}\n")
            else:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                pdf.save(out_path)
                if verbose: print(f"[WRITE] {out_path}\n")

    except Exception as e:
        print(f"[ERROR] {in_path}: {e}", file=sys.stderr)

def collect_inputs(input_path, glob_pattern=None):
    if os.path.isdir(input_path):
        pattern = glob_pattern or "*.pdf"
        return sorted(glob.glob(os.path.join(input_path, pattern)))
    else:
        return [input_path]

def main():
    ap = argparse.ArgumentParser(description="Keep Title/Author/Keywords; remove Subject; leave /Creator unset; write XMP dc:creator and pdf:Keywords.")
    ap.add_argument("input", help="Input PDF file or directory")
    ap.add_argument("output", nargs="?", help="Output directory (ignored with --inplace)")
    ap.add_argument("--glob", default=None, help='Glob for directory input, e.g. "*.pdf"')
    ap.add_argument("--inplace", action="store_true", help="Modify files in place")
    ap.add_argument("--quiet", action="store_true", help="Less logging")
    args = ap.parse_args()

    files = collect_inputs(args.input, args.glob)
    if not files:
        print("No files matched.", file=sys.stderr); sys.exit(1)

    if args.inplace:
        for fp in files:
            clean_one(fp, None, inplace=True, verbose=not args.quiet)
    else:
        if not args.output:
            print("Please provide an output directory (or use --inplace).", file=sys.stderr); sys.exit(1)
        for fp in files:
            outfp = os.path.join(args.output, os.path.basename(fp))
            clean_one(fp, outfp, inplace=False, verbose=not args.quiet)

if __name__ == "__main__":
    main()
