#!/usr/bin/env python3
import hashlib
import pickle
import sqlite3


class AuthenticationManager:
    def __init__(self, db_path="users.db"):
        # A01: Broken Access Control - No proper session management
        self.db_path = db_path
        self.sessions = {}  # In-memory session storage

    def login(self, username, password):
        """User login with various security vulnerabilities"""
        # A03: Injection - SQL injection vulnerability
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Direct string interpolation in SQL query
        query = f"SELECT id, password_hash FROM users WHERE username = '{username}'"
        cursor.execute(query)

        user = cursor.fetchone()
        if not user:
            return {"status": "failed", "message": "User not found"}

        # A02: Cryptographic Failures - Weak hashing algorithm
        password_hash = hashlib.md5(password.encode()).hexdigest()

        if user[1] == password_hash:
            # A07: Identification and Authentication Failures - Weak session generation
            session_id = hashlib.md5(f"{username}{password}".encode()).hexdigest()
            self.sessions[session_id] = {"user_id": user[0], "username": username}

            return {"status": "success", "session_id": session_id}
        else:
            return {"status": "failed", "message": "Invalid password"}

    def reset_password(self, email):
        """Password reset with security issues"""
        # A04: Insecure Design - No rate limiting or validation
        reset_token = hashlib.md5(email.encode()).hexdigest()

        # A09: Security Logging and Monitoring Failures - No security event logging
        # Simply returns token without any verification or logging
        return {"reset_token": reset_token, "url": f"/reset?token={reset_token}"}

    def deserialize_user_data(self, data):
        """Unsafe deserialization"""
        # A08: Software and Data Integrity Failures - Insecure deserialization
        return pickle.loads(data)

    def get_user_profile(self, user_id):
        """Get user profile with authorization issues"""
        # A01: Broken Access Control - No authorization check
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Fetches any user profile without checking permissions
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
