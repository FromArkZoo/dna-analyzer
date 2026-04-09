"""Flask application for the DNA Analyzer.

Serves the web UI and provides API endpoints for file upload and analysis.
"""

import io
import os

from flask import Flask, jsonify, render_template, request

from config import DB_PATH, FLASK_HOST, FLASK_PORT, MAX_CONTENT_LENGTH
from analyzers.parser import parse_ancestry_file
from analyzers.report_generator import generate_report

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Accept file upload, parse DNA data, and return analysis report.

    Expects a multipart file upload with field name 'file'.
    The file is read entirely in memory — never written to disk.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Please select a DNA data file."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    # Validate file extension
    allowed_extensions = {".txt", ".csv", ".tsv", ".zip"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({
            "error": f"Unsupported file type '{ext}'. Please upload a .txt, .csv, or .tsv file from AncestryDNA."
        }), 400

    try:
        # Read file content into memory (never write to disk)
        raw_content = file.read()
        try:
            text_content = raw_content.decode("utf-8")
        except UnicodeDecodeError:
            text_content = raw_content.decode("latin-1")

        file_obj = io.StringIO(text_content)

        # Parse the DNA data file
        genotypes = parse_ancestry_file(file_obj)

        if not genotypes:
            return jsonify({
                "error": "No valid genotype data found in the uploaded file. "
                         "Please ensure this is an AncestryDNA raw data file."
            }), 400

        # Run full analysis
        report = generate_report(genotypes, DB_PATH)

        return jsonify(report)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({
            "error": f"An unexpected error occurred during analysis: {str(e)}"
        }), 500


@app.route("/api/status", methods=["GET"])
def status():
    """Return application status including database availability."""
    db_exists = os.path.exists(DB_PATH)
    db_size = os.path.getsize(DB_PATH) if db_exists else 0

    return jsonify({
        "status": "ok",
        "db_exists": db_exists,
        "db_size": db_size,
        "db_size_human": _format_size(db_size),
    })


def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
