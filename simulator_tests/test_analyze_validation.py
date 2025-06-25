#!/usr/bin/env python3
"""
Analyze Tool Validation Test

Tests the analyze tool's capabilities using the new workflow architecture.
This validates that the new workflow-based implementation provides step-by-step
analysis with expert validation following the same patterns as debug/codereview tools.
"""

import json
from typing import Optional

from .conversation_base_test import ConversationBaseTest


class AnalyzeValidationTest(ConversationBaseTest):
    """Test analyze tool with new workflow architecture"""

    @property
    def test_name(self) -> str:
        return "analyze_validation"

    @property
    def test_description(self) -> str:
        return "AnalyzeWorkflow tool validation with new workflow architecture"

    def run_test(self) -> bool:
        """Test analyze tool capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: AnalyzeWorkflow tool validation (new architecture)")

            # Create test files for analysis
            self._create_analysis_codebase()

            # Test 1: Single analysis session with multiple steps
            if not self._test_single_analysis_session():
                return False

            # Test 2: Analysis with backtracking
            if not self._test_analysis_with_backtracking():
                return False

            # Test 3: Complete analysis with expert validation
            if not self._test_complete_analysis_with_expert():
                return False

            # Test 4: Certain confidence behavior
            if not self._test_certain_confidence():
                return False

            # Test 5: Context-aware file embedding
            if not self._test_context_aware_file_embedding():
                return False

            # Test 6: Different analysis types
            if not self._test_analysis_types():
                return False

            self.logger.info("  ✅ All analyze validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"AnalyzeWorkflow validation test failed: {e}")
            return False

    def _create_analysis_codebase(self):
        """Create test files representing a realistic codebase for analysis"""
        # Create a Python microservice with various architectural patterns
        main_service = """#!/usr/bin/env python3
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import redis
import logging

# Global configurations - could be improved
DATABASE_URL = "postgresql://user:pass@localhost/db"
REDIS_URL = "redis://localhost:6379"

app = FastAPI(title="User Management Service")

# Database setup
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Redis connection - potential singleton pattern issue
redis_client = redis.Redis.from_url(REDIS_URL)

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = redis_client  # Direct dependency on global

    async def get_user(self, user_id: int) -> Optional[Dict]:
        # Cache key generation - could be centralized
        cache_key = f"user:{user_id}"

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached:
            return json.loads(cached)

        # Database query - no error handling
        result = await self.db.execute(
            "SELECT * FROM users WHERE id = %s", (user_id,)
        )
        user_data = result.fetchone()        if user_data:
            # Cache for 1 hour - magic number
            self.cache.setex(cache_key, 3600, json.dumps(user_data, ensure_ascii=False))

        return user_data

    async def create_user(self, user_data: Dict) -> Dict:
        # Input validation missing
        # No transaction handling
        # No audit logging

        query = "INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id"
        result = await self.db.execute(query, (user_data['name'], user_data['email']))
        user_id = result.fetchone()[0]

        # Cache invalidation strategy missing

        return {"id": user_id, **user_data}

@app.get("/users/{user_id}")
async def get_user_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user

@app.post("/users")
async def create_user_endpoint(user_data: dict, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    return await service.create_user(user_data)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
"""

        # Create config module with various architectural concerns
        config_module = """#!/usr/bin/env python3
import os
from dataclasses import dataclass
from typing import Optional

# Configuration approach could be improved
@dataclass
class DatabaseConfig:
    url: str = os.getenv("DATABASE_URL", "postgresql://localhost/app")
    pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    echo: bool = os.getenv("DB_ECHO", "false").lower() == "true"

@dataclass
class CacheConfig:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    default_ttl: int = int(os.getenv("CACHE_TTL", "3600"))
    max_connections: int = int(os.getenv("REDIS_MAX_CONN", "20"))

@dataclass
class AppConfig:
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Nested config objects
    database: DatabaseConfig = DatabaseConfig()
    cache: CacheConfig = CacheConfig()

    # Security settings scattered
    secret_key: str = os.getenv("SECRET_KEY", "dev-key-not-secure")
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 86400  # 24 hours

    def __post_init__(self):
        # Validation logic could be centralized
        if self.environment == "production" and self.secret_key == "dev-key-not-secure":
            raise ValueError("Production environment requires secure secret key")

# Global configuration instance - potential issues
config = AppConfig()

# Helper functions that could be methods
def get_database_url() -> str:
    return config.database.url

def get_cache_config() -> dict:
    return {
        "url": config.cache.redis_url,
        "ttl": config.cache.default_ttl,
        "max_connections": config.cache.max_connections
    }

def is_production() -> bool:
    return config.environment == "production"

def should_enable_debug() -> bool:
    return config.debug and not is_production()
"""

        # Create models module with database concerns
        models_module = """#!/usr/bin/env python3
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import json

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship could be optimized
    profiles = relationship("UserProfile", back_populates="user", lazy="select")
    audit_logs = relationship("AuditLog", back_populates="user")

    def to_dict(self) -> dict:
        # Serialization logic mixed with model - could be separated
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def update_from_dict(self, data: dict):
        # Update logic could be more robust
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'created_at']:
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bio = Column(Text)
    avatar_url = Column(String(500))
    preferences = Column(Text)  # JSON stored as text - could use JSON column

    user = relationship("User", back_populates="profiles")

    def get_preferences(self) -> dict:
        # JSON handling could be centralized
        try:
            return json.loads(self.preferences) if self.preferences else {}
        except json.JSONDecodeError:
            return {}    def set_preferences(self, prefs: dict):
        self.preferences = json.dumps(prefs, ensure_ascii=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text)  # JSON stored as text
    ip_address = Column(String(45))  # IPv6 support
    user_agent = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")

    @classmethod
    def log_action(cls, db_session, user_id: int, action: str, details: dict = None,
                   ip_address: str = None, user_agent: str = None):
        # Factory method pattern - could be improved
        log = cls(
            user_id=user_id,
            action=action,
            details=json.dumps(details, ensure_ascii=False) if details else None,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db_session.add(log)
        return log
"""

        # Create utility module with various helper functions
        utils_module = """#!/usr/bin/env python3
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

# Logging setup - could be centralized
logger = logging.getLogger(__name__)

class ValidationError(Exception):
    \"\"\"Custom exception for validation errors\"\"\"
    pass

def validate_email(email: str) -> bool:
    # Email validation - could use more robust library
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password: str) -> tuple[bool, str]:
    # Password validation rules - could be configurable
    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain uppercase letter"

    if not re.search(r'[a-z]', password):
        return False, "Password must contain lowercase letter"

    if not re.search(r'[0-9]', password):
        return False, "Password must contain number"

    return True, "Valid password"

def hash_password(password: str) -> str:
    # Password hashing - could use more secure algorithm
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{password_hash.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    # Password verification
    try:
        salt, hash_hex = hashed.split(':', 1)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return password_hash.hex() == hash_hex
    except ValueError:
        return False

def generate_cache_key(*args, prefix: str = "", separator: str = ":") -> str:
    # Cache key generation - could be more sophisticated
    parts = [str(arg) for arg in args if arg is not None]
    if prefix:
        parts.insert(0, prefix)
    return separator.join(parts)

def parse_datetime(date_string: str) -> Optional[datetime]:
    # Date parsing with multiple format support
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    logger.warning(f"Unable to parse datetime: {date_string}")
    return None

def calculate_expiry(hours: int = 24) -> datetime:
    # Expiry calculation - could be more flexible
    return datetime.utcnow() + timedelta(hours=hours)

def sanitize_input(data: Dict[str, Any]) -> Dict[str, Any]:
    # Input sanitization - basic implementation
    sanitized = {}

    for key, value in data.items():
        if isinstance(value, str):
            # Basic HTML/script tag removal
            value = re.sub(r'<[^>]*>', '', value)
            value = value.strip()

        # Type validation could be more comprehensive
        if value is not None and value != "":
            sanitized[key] = value

    return sanitized

def format_response(data: Any, status: str = "success", message: str = None) -> Dict[str, Any]:
    # Response formatting - could be more standardized
    response = {
        "status": status,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }

    if message:
        response["message"] = message

    return response

class PerformanceTimer:
    # Performance measurement utility
    def __init__(self, name: str):
        self.name = name
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = datetime.now() - self.start_time
            logger.info(f"Performance: {self.name} took {duration.total_seconds():.3f}s")
"""

        # Create test files
        self.main_service_file = self.create_additional_test_file("main_service.py", main_service)
        self.config_file = self.create_additional_test_file("config.py", config_module)
        self.models_file = self.create_additional_test_file("models.py", models_module)
        self.utils_file = self.create_additional_test_file("utils.py", utils_module)

        self.logger.info("  ✅ Created test codebase with 4 files for analysis")

    def _test_single_analysis_session(self) -> bool:
        """Test a complete analysis session with multiple steps"""
        try:
            self.logger.info("  1.1: Testing single analysis session")

            # Step 1: Start analysis
            self.logger.info("    1.1.1: Step 1 - Initial analysis")
            response1, continuation_id = self.call_mcp_tool(
                "analyze",
                {
                    "step": "I need to analyze this Python microservice codebase for architectural patterns, design decisions, and improvement opportunities. Let me start by examining the overall structure and understanding the technology stack.",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Starting analysis of FastAPI microservice with PostgreSQL, Redis, and SQLAlchemy. Initial examination shows user management functionality with caching layer.",
                    "files_checked": [self.main_service_file],
                    "relevant_files": [self.main_service_file, self.config_file, self.models_file, self.utils_file],
                    "prompt": "Analyze this microservice architecture for scalability, maintainability, and design patterns",
                    "analysis_type": "architecture",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial analysis response")
                return False

            # Parse and validate JSON response
            response1_data = self._parse_analyze_response(response1)
            if not response1_data:
                return False

            # Validate step 1 response structure - expect pause_for_analysis for next_step_required=True
            if not self._validate_step_response(response1_data, 1, 4, True, "pause_for_analysis"):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Deeper examination
            self.logger.info("    1.1.2: Step 2 - Architecture examination")
            response2, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Now examining the configuration and models modules to understand data architecture and configuration management patterns.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found several architectural concerns: direct Redis dependency in service class, global configuration instance, missing error handling in database operations, and mixed serialization logic in models.",
                    "files_checked": [self.main_service_file, self.config_file, self.models_file],
                    "relevant_files": [self.main_service_file, self.config_file, self.models_file],
                    "relevant_context": ["UserService", "AppConfig", "User.to_dict"],
                    "issues_found": [
                        {
                            "severity": "medium",
                            "description": "Direct dependency on global Redis client in UserService",
                        },
                        {"severity": "low", "description": "Global configuration instance could cause testing issues"},
                    ],
                    "confidence": "medium",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue analysis to step 2")
                return False

            response2_data = self._parse_analyze_response(response2)
            if not self._validate_step_response(response2_data, 2, 4, True, "pause_for_analysis"):
                return False

            # Check analysis status tracking
            analysis_status = response2_data.get("analysis_status", {})
            if analysis_status.get("files_checked", 0) < 3:
                self.logger.error("Files checked count not properly tracked")
                return False

            if analysis_status.get("insights_by_severity", {}).get("medium", 0) < 1:
                self.logger.error("Medium severity insights not properly tracked")
                return False

            if analysis_status.get("analysis_confidence") != "medium":
                self.logger.error("Confidence level not properly tracked")
                return False

            self.logger.info("    ✅ Step 2 successful with proper tracking")

            # Store continuation_id for next test
            self.analysis_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Single analysis session test failed: {e}")
            return False

    def _test_analysis_with_backtracking(self) -> bool:
        """Test analysis with backtracking to revise findings"""
        try:
            self.logger.info("  1.2: Testing analysis with backtracking")

            # Start a new analysis for testing backtracking
            self.logger.info("    1.2.1: Start analysis for backtracking test")
            response1, continuation_id = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Analyzing performance characteristics of the data processing pipeline",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial analysis suggests database queries might be the bottleneck",
                    "files_checked": [self.main_service_file],
                    "relevant_files": [self.main_service_file, self.utils_file],
                    "prompt": "Analyze performance bottlenecks in this microservice",
                    "analysis_type": "performance",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start backtracking test analysis")
                return False

            # Step 2: Wrong direction
            self.logger.info("    1.2.2: Step 2 - Incorrect analysis path")
            response2, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Focusing on database optimization strategies",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Database queries seem reasonable, might be looking in wrong direction",
                    "files_checked": [self.main_service_file, self.models_file],
                    "relevant_files": [],
                    "relevant_context": [],
                    "issues_found": [],
                    "confidence": "low",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            # Step 3: Backtrack from step 2
            self.logger.info("    1.2.3: Step 3 - Backtrack and revise approach")
            response3, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Backtracking - the performance issue might not be database related. Let me examine the caching and serialization patterns instead.",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found potential performance issues in JSON serialization and cache key generation patterns in utils module",
                    "files_checked": [self.utils_file, self.models_file],
                    "relevant_files": [self.utils_file, self.models_file],
                    "relevant_context": ["generate_cache_key", "User.to_dict", "sanitize_input"],
                    "issues_found": [
                        {"severity": "medium", "description": "JSON serialization in model classes could be optimized"},
                        {"severity": "low", "description": "Cache key generation lacks proper escaping"},
                    ],
                    "confidence": "medium",
                    "backtrack_from_step": 2,  # Backtrack from step 2
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to backtrack")
                return False

            response3_data = self._parse_analyze_response(response3)
            if not self._validate_step_response(response3_data, 3, 4, True, "pause_for_analysis"):
                return False

            self.logger.info("    ✅ Backtracking working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Backtracking test failed: {e}")
            return False

    def _test_complete_analysis_with_expert(self) -> bool:
        """Test complete analysis ending with expert validation"""
        try:
            self.logger.info("  1.3: Testing complete analysis with expert validation")

            # Use the continuation from first test
            continuation_id = getattr(self, "analysis_continuation_id", None)
            if not continuation_id:
                # Start fresh if no continuation available
                self.logger.info("    1.3.0: Starting fresh analysis")
                response0, continuation_id = self.call_mcp_tool(
                    "analyze",
                    {
                        "step": "Analyzing the microservice architecture for improvement opportunities",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": "Found dependency injection and configuration management issues",
                        "files_checked": [self.main_service_file, self.config_file],
                        "relevant_files": [self.main_service_file, self.config_file],
                        "relevant_context": ["UserService", "AppConfig"],
                        "prompt": "Analyze architectural patterns and improvement opportunities",
                        "analysis_type": "architecture",
                    },
                )
                if not response0 or not continuation_id:
                    self.logger.error("Failed to start fresh analysis")
                    return False

            # Final step - trigger expert validation
            self.logger.info("    1.3.1: Final step - complete analysis")
            response_final, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Analysis complete. I have identified key architectural patterns and strategic improvement opportunities across scalability, maintainability, and performance dimensions.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - triggers expert validation
                    "findings": "Key findings: 1) Tight coupling via global dependencies, 2) Missing error handling and transaction management, 3) Mixed concerns in model classes, 4) Configuration management could be more flexible, 5) Opportunities for dependency injection and better separation of concerns.",
                    "files_checked": [self.main_service_file, self.config_file, self.models_file, self.utils_file],
                    "relevant_files": [self.main_service_file, self.config_file, self.models_file, self.utils_file],
                    "relevant_context": ["UserService", "AppConfig", "User", "validate_email"],
                    "issues_found": [
                        {"severity": "high", "description": "Tight coupling via global Redis client and configuration"},
                        {"severity": "medium", "description": "Missing transaction management in create_user"},
                        {"severity": "medium", "description": "Serialization logic mixed with model classes"},
                        {"severity": "low", "description": "Magic numbers and hardcoded values scattered throughout"},
                    ],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                    "model": "flash",  # Use flash for expert validation
                },
            )

            if not response_final:
                self.logger.error("Failed to complete analysis")
                return False

            response_final_data = self._parse_analyze_response(response_final)
            if not response_final_data:
                return False

            # Validate final response structure - expect calling_expert_analysis for next_step_required=False
            if response_final_data.get("status") != "calling_expert_analysis":
                self.logger.error(
                    f"Expected status 'calling_expert_analysis', got '{response_final_data.get('status')}'"
                )
                return False

            if not response_final_data.get("analysis_complete"):
                self.logger.error("Expected analysis_complete=true for final step")
                return False  # Check for expert analysis
            if "expert_analysis" not in response_final_data:
                self.logger.error("Missing expert_analysis in final response")
                return False

            expert_analysis = response_final_data.get("expert_analysis", {})

            # Check for expected analysis content (checking common patterns)
            analysis_text = json.dumps(expert_analysis, ensure_ascii=False).lower()

            # Look for architectural analysis indicators
            arch_indicators = ["architecture", "pattern", "coupling", "dependency", "scalability", "maintainability"]
            found_indicators = sum(1 for indicator in arch_indicators if indicator in analysis_text)

            if found_indicators >= 3:
                self.logger.info("    ✅ Expert analysis identified architectural patterns correctly")
            else:
                self.logger.warning(
                    f"    ⚠️ Expert analysis may not have fully analyzed architecture (found {found_indicators}/6 indicators)"
                )

            # Check complete analysis summary
            if "complete_analysis" not in response_final_data:
                self.logger.error("Missing complete_analysis in final response")
                return False

            complete_analysis = response_final_data["complete_analysis"]
            if not complete_analysis.get("relevant_context"):
                self.logger.error("Missing relevant context in complete analysis")
                return False

            if "UserService" not in complete_analysis["relevant_context"]:
                self.logger.error("Expected context not found in analysis summary")
                return False

            self.logger.info("    ✅ Complete analysis with expert validation successful")
            return True

        except Exception as e:
            self.logger.error(f"Complete analysis test failed: {e}")
            return False

    def _test_certain_confidence(self) -> bool:
        """Test final step analysis completion (analyze tool doesn't use confidence levels)"""
        try:
            self.logger.info("  1.4: Testing final step analysis completion")

            # Test final step - analyze tool doesn't use confidence levels, but we test completion
            self.logger.info("    1.4.1: Final step analysis")
            response_final, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "I have completed a comprehensive analysis of the architectural patterns and improvement opportunities.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step - should trigger expert analysis
                    "findings": "Complete architectural analysis reveals: FastAPI microservice with clear separation needs, dependency injection opportunities, and performance optimization potential. Key patterns identified: service layer, repository-like data access, configuration management, and utility functions.",
                    "files_checked": [self.main_service_file, self.config_file, self.models_file, self.utils_file],
                    "relevant_files": [self.main_service_file, self.config_file, self.models_file, self.utils_file],
                    "relevant_context": ["UserService", "AppConfig", "User", "validate_email"],
                    "issues_found": [
                        {"severity": "high", "description": "Global dependencies create tight coupling"},
                        {"severity": "medium", "description": "Transaction management missing in critical operations"},
                    ],
                    "prompt": "Comprehensive architectural analysis",
                    "analysis_type": "architecture",
                    "model": "flash",
                },
            )

            if not response_final:
                self.logger.error("Failed to test final step analysis")
                return False

            response_final_data = self._parse_analyze_response(response_final)
            if not response_final_data:
                return False

            # Validate final step response - should trigger expert analysis
            expected_status = "calling_expert_analysis"
            if response_final_data.get("status") != expected_status:
                self.logger.error(f"Expected status '{expected_status}', got '{response_final_data.get('status')}'")
                return False

            # Check that expert analysis was performed
            expert_analysis = response_final_data.get("expert_analysis", {})
            if not expert_analysis:
                self.logger.error("Expert analysis should be present for final step")
                return False

            # Expert analysis should complete successfully
            if expert_analysis.get("status") != "analysis_complete":
                self.logger.error(
                    f"Expert analysis status: {expert_analysis.get('status')} (expected analysis_complete)"
                )
                return False

            self.logger.info("    ✅ Final step analysis completion working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Final step analysis test failed: {e}")
            return False

    def _test_context_aware_file_embedding(self) -> bool:
        """Test context-aware file embedding optimization"""
        try:
            self.logger.info("  1.5: Testing context-aware file embedding")

            # Test 1: New conversation, intermediate step - should only reference files
            self.logger.info("    1.5.1: New conversation intermediate step (should reference only)")
            response1, continuation_id = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Starting architectural analysis of microservice components",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,  # Intermediate step
                    "findings": "Initial analysis of service layer and configuration patterns",
                    "files_checked": [self.main_service_file, self.config_file],
                    "relevant_files": [self.main_service_file],  # This should be referenced, not embedded
                    "relevant_context": ["UserService"],
                    "issues_found": [{"severity": "medium", "description": "Direct Redis dependency in service class"}],
                    "confidence": "low",
                    "prompt": "Analyze service architecture patterns",
                    "analysis_type": "architecture",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start context-aware file embedding test")
                return False

            response1_data = self._parse_analyze_response(response1)
            if not response1_data:
                return False

            # Check file context - should be reference_only for intermediate step
            file_context = response1_data.get("file_context", {})
            if file_context.get("type") != "reference_only":
                self.logger.error(f"Expected reference_only file context, got: {file_context.get('type')}")
                return False

            if "Files referenced but not embedded" not in file_context.get("context_optimization", ""):
                self.logger.error("Expected context optimization message for reference_only")
                return False

            self.logger.info("    ✅ Intermediate step correctly uses reference_only file context")

            # Test 2: Final step - should embed files for expert validation
            self.logger.info("    1.5.2: Final step (should embed files)")
            response2, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Analysis complete - identified key architectural patterns and improvement opportunities",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Complete analysis reveals dependency injection opportunities, configuration management improvements, and separation of concerns enhancements",
                    "files_checked": [self.main_service_file, self.config_file, self.models_file],
                    "relevant_files": [self.main_service_file, self.config_file],  # Should be fully embedded
                    "relevant_context": ["UserService", "AppConfig"],
                    "issues_found": [
                        {"severity": "high", "description": "Global dependencies create architectural coupling"},
                        {"severity": "medium", "description": "Configuration management lacks flexibility"},
                    ],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to complete to final step")
                return False

            response2_data = self._parse_analyze_response(response2)
            if not response2_data:
                return False

            # Check file context - should be fully_embedded for final step
            file_context2 = response2_data.get("file_context", {})
            if file_context2.get("type") != "fully_embedded":
                self.logger.error(
                    f"Expected fully_embedded file context for final step, got: {file_context2.get('type')}"
                )
                return False

            if "Full file content embedded for expert analysis" not in file_context2.get("context_optimization", ""):
                self.logger.error("Expected expert analysis optimization message for fully_embedded")
                return False

            # Verify expert analysis was called for final step
            if response2_data.get("status") != "calling_expert_analysis":
                self.logger.error("Final step should trigger expert analysis")
                return False

            if "expert_analysis" not in response2_data:
                self.logger.error("Expert analysis should be present in final step")
                return False

            self.logger.info("    ✅ Context-aware file embedding test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Context-aware file embedding test failed: {e}")
            return False

    def _test_analysis_types(self) -> bool:
        """Test different analysis types (architecture, performance, security, quality)"""
        try:
            self.logger.info("  1.6: Testing different analysis types")

            # Test security analysis
            self.logger.info("    1.6.1: Security analysis")
            response_security, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Conducting security analysis of authentication and data handling patterns",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Security analysis reveals: password hashing implementation, input validation patterns, SQL injection prevention via parameterized queries, but missing input sanitization in some areas and weak default secret key handling.",
                    "files_checked": [self.main_service_file, self.utils_file],
                    "relevant_files": [self.main_service_file, self.utils_file],
                    "relevant_context": ["hash_password", "validate_email", "sanitize_input"],
                    "issues_found": [
                        {"severity": "critical", "description": "Weak default secret key in production detection"},
                        {"severity": "medium", "description": "Input sanitization not consistently applied"},
                    ],
                    "confidence": "high",
                    "prompt": "Analyze security patterns and vulnerabilities",
                    "analysis_type": "security",
                    "model": "flash",
                },
            )

            if not response_security:
                self.logger.error("Failed security analysis test")
                return False

            response_security_data = self._parse_analyze_response(response_security)
            if not response_security_data:
                return False

            # Check that security analysis was processed
            issues = response_security_data.get("complete_analysis", {}).get("issues_found", [])
            critical_issues = [issue for issue in issues if issue.get("severity") == "critical"]

            if not critical_issues:
                self.logger.warning("Security analysis should have identified critical security issues")
            else:
                self.logger.info("    ✅ Security analysis identified critical issues")

            # Test quality analysis
            self.logger.info("    1.6.2: Quality analysis")
            response_quality, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Conducting code quality analysis focusing on maintainability and best practices",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Code quality analysis shows: good use of type hints, proper error handling in some areas but missing in others, mixed separation of concerns, and opportunities for better abstraction.",
                    "files_checked": [self.models_file, self.utils_file],
                    "relevant_files": [self.models_file, self.utils_file],
                    "relevant_context": ["User.to_dict", "ValidationError", "PerformanceTimer"],
                    "issues_found": [
                        {"severity": "medium", "description": "Serialization logic mixed with model classes"},
                        {"severity": "low", "description": "Inconsistent error handling patterns"},
                    ],
                    "confidence": "high",
                    "prompt": "Analyze code quality and maintainability patterns",
                    "analysis_type": "quality",
                    "model": "flash",
                },
            )

            if not response_quality:
                self.logger.error("Failed quality analysis test")
                return False

            response_quality_data = self._parse_analyze_response(response_quality)
            if not response_quality_data:
                return False

            # Verify quality analysis was processed
            quality_context = response_quality_data.get("complete_analysis", {}).get("relevant_context", [])
            if not any("User" in ctx for ctx in quality_context):
                self.logger.warning("Quality analysis should have analyzed model classes")
            else:
                self.logger.info("    ✅ Quality analysis examined relevant code elements")

            self.logger.info("    ✅ Different analysis types test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Analysis types test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool in-process - override for analyze-specific response handling"""
        # Use in-process implementation to maintain conversation memory
        response_text, _ = self.call_mcp_tool_direct(tool_name, params)

        if not response_text:
            return None, None

        # Extract continuation_id from analyze response specifically
        continuation_id = self._extract_analyze_continuation_id(response_text)

        return response_text, continuation_id

    def _extract_analyze_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from analyze response"""
        try:
            # Parse the response
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")

        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for analyze continuation_id: {e}")
            return None

    def _parse_analyze_response(self, response_text: str) -> dict:
        """Parse analyze tool JSON response"""
        try:
            # Parse the response - it should be direct JSON
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse analyze response as JSON: {e}")
            self.logger.error(f"Response text: {response_text[:500]}...")
            return {}

    def _validate_step_response(
        self,
        response_data: dict,
        expected_step: int,
        expected_total: int,
        expected_next_required: bool,
        expected_status: str,
    ) -> bool:
        """Validate an analyze investigation step response structure"""
        try:
            # Check status
            if response_data.get("status") != expected_status:
                self.logger.error(f"Expected status '{expected_status}', got '{response_data.get('status')}'")
                return False

            # Check step number
            if response_data.get("step_number") != expected_step:
                self.logger.error(f"Expected step_number {expected_step}, got {response_data.get('step_number')}")
                return False

            # Check total steps
            if response_data.get("total_steps") != expected_total:
                self.logger.error(f"Expected total_steps {expected_total}, got {response_data.get('total_steps')}")
                return False

            # Check next_step_required
            if response_data.get("next_step_required") != expected_next_required:
                self.logger.error(
                    f"Expected next_step_required {expected_next_required}, got {response_data.get('next_step_required')}"
                )
                return False

            # Check analysis_status exists
            if "analysis_status" not in response_data:
                self.logger.error("Missing analysis_status in response")
                return False

            # Check next_steps guidance
            if not response_data.get("next_steps"):
                self.logger.error("Missing next_steps guidance in response")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating step response: {e}")
            return False
