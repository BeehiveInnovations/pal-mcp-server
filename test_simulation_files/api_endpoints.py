#!/usr/bin/env python3
import os
import subprocess

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# A05: Security Misconfiguration - Debug mode enabled
app.config["DEBUG"] = True
app.config["SECRET_KEY"] = "dev-secret-key"  # Hardcoded secret


@app.route("/api/search", methods=["GET"])
def search():
    """Search endpoint with multiple vulnerabilities"""
    # A03: Injection - XSS vulnerability, no input sanitization
    query = request.args.get("q", "")

    # A03: Injection - Command injection vulnerability
    if "file:" in query:
        filename = query.split("file:")[1]
        # Direct command execution
        result = subprocess.run(f"cat {filename}", shell=True, capture_output=True, text=True)
        return jsonify({"result": result.stdout})

    # A10: Server-Side Request Forgery (SSRF)
    if query.startswith("http"):
        # No validation of URL, allows internal network access
        response = requests.get(query)
        return jsonify({"content": response.text})

    # Return search results without output encoding
    return f"<h1>Search Results for: {query}</h1>"


@app.route("/api/admin", methods=["GET"])
def admin_panel():
    """Admin panel with broken access control"""
    # A01: Broken Access Control - No authentication check
    # Anyone can access admin functionality
    action = request.args.get("action")

    if action == "delete_user":
        user_id = request.args.get("user_id")
        # Performs privileged action without authorization
        return jsonify({"status": "User deleted", "user_id": user_id})

    return jsonify({"status": "Admin panel"})


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """File upload with security issues"""
    # A05: Security Misconfiguration - No file type validation
    file = request.files.get("file")
    if file:
        # Saves any file type to server
        filename = file.filename
        file.save(os.path.join("/tmp", filename))

        # A03: Path traversal vulnerability
        return jsonify({"status": "File uploaded", "path": f"/tmp/{filename}"})

    return jsonify({"error": "No file provided"})


# A06: Vulnerable and Outdated Components
# Using old Flask version with known vulnerabilities (hypothetical)
# requirements.txt: Flask==0.12.2 (known security issues)

if __name__ == "__main__":
    # A05: Security Misconfiguration - Running on all interfaces
    app.run(host="0.0.0.0", port=5000, debug=True)
