#!/usr/bin/env python3
"""Test cases for PII sanitizer."""

import unittest
from tests.pii_sanitizer import PIISanitizer, PIIPattern


class TestPIISanitizer(unittest.TestCase):
    """Test PII sanitization functionality."""
    
    def setUp(self):
        """Set up test sanitizer."""
        self.sanitizer = PIISanitizer()
    
    def test_api_key_sanitization(self):
        """Test various API key formats are sanitized."""
        test_cases = [
            # OpenAI keys
            ("sk-proj-abcd1234567890ABCD1234567890abcd1234567890ABCD12", "sk-proj-SANITIZED"),
            ("sk-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN", "sk-SANITIZED"),
            
            # Anthropic keys
            ("sk-ant-abcd1234567890ABCD1234567890abcd1234567890ABCD12", "sk-ant-SANITIZED"),
            
            # Google keys
            ("AIzaSyD-1234567890abcdefghijklmnopqrstuv", "AIza-SANITIZED"),
            
            # GitHub tokens
            ("ghp_1234567890abcdefghijklmnopqrstuvwxyz", "gh_SANITIZED"),
            ("ghs_1234567890abcdefghijklmnopqrstuvwxyz", "gh_SANITIZED"),
        ]
        
        for original, expected in test_cases:
            with self.subTest(original=original):
                result = self.sanitizer.sanitize_string(original)
                self.assertEqual(result, expected)
    
    def test_personal_info_sanitization(self):
        """Test personal information is sanitized."""
        test_cases = [
            # Email addresses
            ("john.doe@example.com", "user@example.com"),
            ("test123@company.org", "user@example.com"),
            
            # Phone numbers (all now use the same pattern)
            ("(555) 123-4567", "(XXX) XXX-XXXX"),
            ("555-123-4567", "(XXX) XXX-XXXX"),
            ("+1-555-123-4567", "(XXX) XXX-XXXX"),
            
            # SSN
            ("123-45-6789", "XXX-XX-XXXX"),
            
            # Credit card
            ("1234 5678 9012 3456", "XXXX-XXXX-XXXX-XXXX"),
            ("1234-5678-9012-3456", "XXXX-XXXX-XXXX-XXXX"),
        ]
        
        for original, expected in test_cases:
            with self.subTest(original=original):
                result = self.sanitizer.sanitize_string(original)
                self.assertEqual(result, expected)
    
    def test_header_sanitization(self):
        """Test HTTP header sanitization."""
        headers = {
            "Authorization": "Bearer sk-proj-abcd1234567890ABCD1234567890abcd1234567890ABCD12",
            "API-Key": "sk-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN",
            "Content-Type": "application/json",
            "User-Agent": "MyApp/1.0",
            "Cookie": "session=abc123; user=john.doe@example.com"
        }
        
        sanitized = self.sanitizer.sanitize_headers(headers)
        
        self.assertEqual(sanitized["Authorization"], "Bearer SANITIZED")
        self.assertEqual(sanitized["API-Key"], "sk-SANITIZED")
        self.assertEqual(sanitized["Content-Type"], "application/json")
        self.assertEqual(sanitized["User-Agent"], "MyApp/1.0")
        self.assertIn("user@example.com", sanitized["Cookie"])
    
    def test_nested_structure_sanitization(self):
        """Test sanitization of nested data structures."""
        data = {
            "user": {
                "email": "john.doe@example.com",
                "api_key": "sk-proj-abcd1234567890ABCD1234567890abcd1234567890ABCD12"
            },
            "tokens": [
                "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
                "Bearer sk-ant-abcd1234567890ABCD1234567890abcd1234567890ABCD12"
            ],
            "metadata": {
                "ip": "192.168.1.100",
                "phone": "(555) 123-4567"
            }
        }
        
        sanitized = self.sanitizer.sanitize_value(data)
        
        self.assertEqual(sanitized["user"]["email"], "user@example.com")
        self.assertEqual(sanitized["user"]["api_key"], "sk-proj-SANITIZED")
        self.assertEqual(sanitized["tokens"][0], "gh_SANITIZED")
        self.assertEqual(sanitized["tokens"][1], "Bearer sk-ant-SANITIZED")
        self.assertEqual(sanitized["metadata"]["ip"], "0.0.0.0")
        self.assertEqual(sanitized["metadata"]["phone"], "(XXX) XXX-XXXX")
    
    def test_url_sanitization(self):
        """Test URL parameter sanitization."""
        urls = [
            ("https://api.example.com/v1/users?api_key=sk-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN",
             "https://api.example.com/v1/users?api_key=SANITIZED"),
            ("https://example.com/login?token=ghp_1234567890abcdefghijklmnopqrstuvwxyz&user=test",
             "https://example.com/login?token=SANITIZED&user=test"),
        ]
        
        for original, expected in urls:
            with self.subTest(url=original):
                result = self.sanitizer.sanitize_url(original)
                self.assertEqual(result, expected)
    
    def test_disable_sanitization(self):
        """Test that sanitization can be disabled."""
        self.sanitizer.sanitize_enabled = False
        
        sensitive_data = "sk-proj-abcd1234567890ABCD1234567890abcd1234567890ABCD12"
        result = self.sanitizer.sanitize_string(sensitive_data)
        
        # Should return original when disabled
        self.assertEqual(result, sensitive_data)
    
    def test_custom_pattern(self):
        """Test adding custom PII patterns."""
        # Add custom pattern for internal employee IDs
        custom_pattern = PIIPattern.create(
            name="employee_id",
            pattern=r'EMP\d{6}',
            replacement="EMP-REDACTED",
            description="Internal employee IDs"
        )
        
        self.sanitizer.add_pattern(custom_pattern)
        
        text = "Employee EMP123456 has access to the system"
        result = self.sanitizer.sanitize_string(text)
        
        self.assertEqual(result, "Employee EMP-REDACTED has access to the system")


if __name__ == "__main__":
    unittest.main()