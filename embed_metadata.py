import pikepdf
import csv
from pathlib import Path

def embed_metadata(input_pdf_path, output_pdf_path, pdf_base_name, output_dir_for_logs, title=None, author=None, subjects=None):
    """
    Embeds metadata (title, author, subjects) into a PDF file and logs changes to a CSV.

    Args:
        input_pdf_path (Path): The path to the input PDF file.
        output_pdf_path (Path): The path where the modified PDF will be saved.
        pdf_base_name (str): The base name of the PDF file (without extension) for log naming.
        output_dir_for_logs (Path): The directory where the metadata log CSV will be saved.
        title (str, optional): The title to embed. Defaults to None.
        author (str, optional): The author to embed. Defaults to None.
        subjects (list, optional): A list of subjects/keywords to embed. Defaults to None.

    Returns:
        bool: True if metadata embedding and logging was successful, False otherwise.
    """
    log_data = []
    
    try:
        # Open the PDF with allow_overwriting_input=True
        with pikepdf.Pdf.open(input_pdf_path, allow_overwriting_input=True) as pdf:
            info = pdf.docinfo

            # Helper to record changes
            def record_change(field_name, old_value, new_value):
                changed = (str(old_value).strip() != str(new_value).strip()) if old_value is not None and new_value is not None else (old_value is not None or new_value is not None)
                log_data.append([field_name, str(old_value), str(new_value), changed])

            # Process Title
            original_title = info.get("/Title", "")
            if title is not None:
                record_change("Title", original_title, title)
                info["/Title"] = str(title)
            else: # Still log if no new title provided, but keep original
                record_change("Title", original_title, original_title)


            # Process Author
            original_author = info.get("/Author", "")
            if author is not None:
                record_change("Author", original_author, author)
                info["/Author"] = str(author)
            else: # Still log if no new author provided, but keep original
                record_change("Author", original_author, original_author)


            # Process Subjects (Keywords)
            original_keywords = info.get("/Keywords", "")
            new_keywords_str = ""
            if subjects is not None:
                if isinstance(subjects, list):
                    new_keywords_str = ", ".join(subjects)
                else:
                    new_keywords_str = str(subjects)
                record_change("Subjects", original_keywords, new_keywords_str)
                info["/Keywords"] = new_keywords_str
            else: # Still log if no new subjects provided, but keep original
                record_change("Subjects", original_keywords, original_keywords)

            pdf.save(output_pdf_path)
        
        # Save the log to a CSV file
        log_filename = output_dir_for_logs / f"{pdf_base_name}_metadata_log.csv"
        with open(log_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["Field", "Original Value", "New Value", "Changed"])
            csv_writer.writerows(log_data)

        return True

    except Exception as e:
        print(f"❌ embed_metadata error for {output_pdf_path}: {e}")
        # Log the error to a minimal CSV if possible, or just print
        log_filename = output_dir_for_logs / f"{pdf_base_name}_metadata_log_error.csv"
        with open(log_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["Field", "Original Value", "New Value", "Changed", "Error"])
            csv_writer.writerows(log_data) # Write any data collected before error
            csv_writer.writerow(["Error", "", "", "", str(e)])
        return False
