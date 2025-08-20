#!/usr/bin/env python3
from flask import Flask, request, jsonify
import sqlite3
import os

app = Flask(__name__)


@app.route("/api/user/<user_id>", methods=["GET"])
def get_user(user_id):
    """Get user information by ID"""
    # Potential SQL injection vulnerability
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # BUG: Direct string interpolation creates SQL injection risk
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)

    result = cursor.fetchone()
    conn.close()

    if result:
        return jsonify(
            {
                "id": result[0],
                "username": result[1],
                "email": result[2],
                "password_hash": result[3],  # Security issue: exposing password hash
            }
        )
    else:
        return jsonify({"error": "User not found"}), 404


@app.route("/api/admin/users", methods=["GET"])
def list_all_users():
    """Admin endpoint to list all users"""
    # Missing authentication check
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users")

    users = []
    for row in cursor.fetchall():
        users.append({"id": row[0], "username": row[1], "email": row[2]})

    conn.close()
    return jsonify(users)


if __name__ == "__main__":
    # Debug mode in production is a security risk
    app.run(debug=True, host="0.0.0.0")
