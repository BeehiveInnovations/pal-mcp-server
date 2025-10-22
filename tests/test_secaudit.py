"""
Tests for the secaudit tool using WorkflowTool architecture.
"""

import pytest

from tools.models import ToolModelCategory
from tools.secaudit import SecauditRequest, SecauditTool


class TestSecauditTool:
    """Test suite for SecauditTool using WorkflowTool architecture."""

    def test_tool_metadata(self):
        """Test basic tool metadata and configuration."""
        tool = SecauditTool()

        assert tool.get_name() == "secaudit"
        assert "security audit" in tool.get_description()
        assert tool.get_default_temperature() == 0.2  # TEMPERATURE_ANALYTICAL
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING
        assert tool.requires_model() is True

    def test_request_validation(self):
        """Test Pydantic request model validation."""
        # Valid security audit step request
        step_request = SecauditRequest(
            step="Beginning comprehensive security audit of web application",
            step_number=1,
            total_steps=6,
            next_step_required=True,
            findings="Identified React/Node.js e-commerce application with payment processing",
            files_checked=["/src/auth.py", "/src/payment.py"],
            relevant_files=["/src/auth.py", "/src/payment.py"],
            relevant_context=["AuthController.login", "PaymentService.process"],
            security_scope="Web application - e-commerce platform",
            threat_level="high",
            compliance_requirements=["PCI DSS", "SOC2"],
            audit_focus="comprehensive",
            confidence="medium",
        )

        assert step_request.step_number == 1
        assert step_request.threat_level == "high"
        assert step_request.compliance_requirements == ["PCI DSS", "SOC2"]
        assert step_request.audit_focus == "comprehensive"
        assert len(step_request.relevant_context) == 2

    def test_request_validation_defaults(self):
        """Test default values for optional fields."""
        minimal_request = SecauditRequest(
            step="Security audit step",
            step_number=1,
            total_steps=4,
            next_step_required=True,
            findings="Initial findings",
        )

        assert minimal_request.threat_level == "medium"  # Default value
        assert minimal_request.audit_focus == "comprehensive"  # Default value
        assert minimal_request.confidence == "low"  # Default value
        assert minimal_request.compliance_requirements == []  # Default empty list

    def test_request_validation_invalid_threat_level(self):
        """Test validation with invalid threat level."""
        with pytest.raises(ValueError):
            SecauditRequest(
                step="Security audit step",
                step_number=1,
                total_steps=4,
                next_step_required=True,
                findings="Initial findings",
                threat_level="invalid",  # Should only accept low, medium, high, critical
            )

    def test_request_validation_invalid_audit_focus(self):
        """Test validation with invalid audit focus."""
        with pytest.raises(ValueError):
            SecauditRequest(
                step="Security audit step",
                step_number=1,
                total_steps=4,
                next_step_required=True,
                findings="Initial findings",
                audit_focus="invalid",  # Should only accept defined options
            )

    def test_input_schema_generation(self):
        """Test that input schema is generated correctly."""
        tool = SecauditTool()
        schema = tool.get_input_schema()

        # Verify required security audit fields are present
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]
        assert "total_steps" in schema["properties"]
        assert "next_step_required" in schema["properties"]
        assert "findings" in schema["properties"]

        # Verify security-specific fields
        assert "security_scope" in schema["properties"]
        assert "threat_level" in schema["properties"]
        assert "compliance_requirements" in schema["properties"]
        assert "audit_focus" in schema["properties"]

        # Verify field types
        assert schema["properties"]["threat_level"]["type"] == "string"
        assert schema["properties"]["compliance_requirements"]["type"] == "array"

    def test_step_guidance_step_1(self):
        """Test step-specific guidance for step 1 (Security Scope Analysis)."""
        tool = SecauditTool()
        request = SecauditRequest(
            step="Begin security audit",
            step_number=1,
            total_steps=6,
            next_step_required=True,
            findings="Starting security assessment",
        )

        actions = tool.get_required_actions(
            request.step_number, request.confidence, request.findings, request.total_steps
        )

        assert len(actions) == 4
        assert "Identify application type, technology stack, and security scope" in actions
        assert "Map attack surface, entry points, and data flows" in actions
        assert "Determine relevant security standards and compliance requirements" in actions
        assert "Establish threat landscape and risk context for the application" in actions

    def test_step_guidance_step_2(self):
        """Test step-specific guidance for step 2 (Authentication Assessment)."""
        tool = SecauditTool()
        request = SecauditRequest(
            step="Analyze authentication",
            step_number=2,
            total_steps=6,
            next_step_required=True,
            findings="Authentication analysis",
        )

        actions = tool.get_required_actions(
            request.step_number, request.confidence, request.findings, request.total_steps
        )

        assert len(actions) == 4
        assert "Analyze authentication mechanisms and session management" in actions
        assert "Check authorization controls, access patterns, and privilege escalation risks" in actions
        assert "Assess multi-factor authentication, password policies, and account security" in actions
        assert "Review identity and access management implementations" in actions

    def test_step_guidance_step_4(self):
        """Test step-specific guidance for step 4 (OWASP Top 10 Review)."""
        tool = SecauditTool()
        request = SecauditRequest(
            step="OWASP Top 10 review", step_number=4, total_steps=6, next_step_required=True, findings="OWASP analysis"
        )

        actions = tool.get_required_actions(
            request.step_number, request.confidence, request.findings, request.total_steps
        )

        assert len(actions) == 4
        assert "Conduct OWASP Top 10 (2021) systematic review across all categories" in actions
        assert "Check each OWASP category methodically with specific findings and evidence" in actions
        assert "Cross-reference findings with application context and technology stack" in actions
        assert "Prioritize vulnerabilities based on exploitability and business impact" in actions

    def test_expert_analysis_trigger(self):
        """Test when expert analysis should be triggered."""
        tool = SecauditTool()

        # Create a mock consolidated findings object
        class MockConsolidatedFindings:
            def __init__(self, relevant_files=None, findings=None, issues_found=None):
                self.relevant_files = relevant_files or []
                self.findings = findings or []
                self.issues_found = issues_found or []

        # Should trigger expert analysis when we have meaningful findings
        findings_with_files = MockConsolidatedFindings(
            relevant_files=["/src/auth.py", "/src/payment.py"],
            findings=["Finding 1", "Finding 2"],
            issues_found=[{"severity": "high", "description": "SQL injection"}],
        )
        assert tool.should_call_expert_analysis(findings_with_files) is True

        # Should trigger with just findings
        findings_only = MockConsolidatedFindings(findings=["Finding 1", "Finding 2"])
        assert tool.should_call_expert_analysis(findings_only) is True

        # Should trigger with just issues
        issues_only = MockConsolidatedFindings(issues_found=[{"severity": "high", "description": "SQL injection"}])
        assert tool.should_call_expert_analysis(issues_only) is True

        # Should not trigger with no meaningful data
        no_findings = MockConsolidatedFindings()
        assert tool.should_call_expert_analysis(no_findings) is False

    def test_expert_analysis_context_preparation(self):
        """Test expert analysis context preparation."""
        tool = SecauditTool()

        # Create a mock consolidated findings object
        class MockConsolidatedFindings:
            def __init__(self):
                self.hypotheses = []
                self.files_checked = ["/app/auth.py", "/app/payment.py", "/app/api.py", "/app/db.py"]
                self.relevant_files = ["/app/auth.py", "/app/payment.py", "/app/api.py"]
                self.relevant_context = ["AuthController.login", "PaymentService.process", "APIController.validate"]
                self.issues_found = [
                    {"severity": "critical", "description": "SQL injection vulnerability in login endpoint"},
                    {"severity": "high", "description": "Missing input validation in payment processing"},
                    {"severity": "medium", "description": "Weak session management configuration"},
                ]
                self.findings = [
                    "Step 1: Identified e-commerce web application with payment processing",
                    "Step 2: Found authentication vulnerabilities",
                    "Step 3: Discovered input validation issues",
                ]
                self.hypotheses = [
                    {"step": 1, "confidence": "low", "hypothesis": "Initial security assessment"},
                    {"step": 2, "confidence": "medium", "hypothesis": "Authentication issues confirmed"},
                    {"step": 3, "confidence": "high", "hypothesis": "Multiple security vulnerabilities identified"},
                ]
                self.images = []

        # Set initial request to provide context
        tool.initial_request = "Perform security audit of e-commerce web application"
        tool.security_config = {
            "security_scope": "Web application - e-commerce platform with payment processing",
            "threat_level": "high",
            "compliance_requirements": ["PCI DSS", "SOC2", "GDPR"],
            "audit_focus": "comprehensive",
            "severity_filter": "all",
        }

        consolidated_findings = MockConsolidatedFindings()
        context = tool.prepare_expert_analysis_context(consolidated_findings)

        # Verify context contains all security-specific information
        assert "SECURITY AUDIT REQUEST" in context
        assert "Perform security audit of e-commerce web application" in context
        assert "SECURITY CONFIGURATION" in context
        assert "security_scope: Web application - e-commerce platform with payment processing" in context
        assert "threat_level: high" in context
        assert "compliance_requirements: ['PCI DSS', 'SOC2', 'GDPR']" in context
        assert "/app/auth.py" in context
        assert "AuthController.login" in context
        assert "CRITICAL SEVERITY:" in context
        assert "SQL injection vulnerability" in context
        assert "HIGH SEVERITY:" in context
        assert "Missing input validation" in context

    def test_security_issues_formatting_empty(self):
        """Test security issues formatting with no issues."""
        tool = SecauditTool()
        formatted = tool._format_security_issues([])
        assert "No security issues identified during systematic investigation." in formatted

    def test_security_issues_formatting_with_issues(self):
        """Test security issues formatting with multiple severity levels."""
        tool = SecauditTool()
        issues = [
            {"severity": "critical", "description": "Remote code execution vulnerability"},
            {"severity": "high", "description": "Authentication bypass"},
            {"severity": "medium", "description": "Information disclosure"},
            {"severity": "low", "description": "Missing security headers"},
            {"severity": "unknown", "description": "Unclassified issue"},  # Should go to low
        ]

        formatted = tool._format_security_issues(issues)

        assert "CRITICAL SEVERITY:" in formatted
        assert "Remote code execution vulnerability" in formatted
        assert "HIGH SEVERITY:" in formatted
        assert "Authentication bypass" in formatted
        assert "MEDIUM SEVERITY:" in formatted
        assert "Information disclosure" in formatted
        assert "LOW SEVERITY:" in formatted
        assert "Missing security headers" in formatted
        assert "[UNKNOWN] Unclassified issue" in formatted

    def test_tool_field_definitions(self):
        """Test that all security-specific tool fields are properly defined."""
        tool = SecauditTool()
        fields = tool.get_tool_fields()

        # Verify all expected fields are present
        expected_fields = [
            "step",
            "step_number",
            "total_steps",
            "next_step_required",
            "findings",
            "files_checked",
            "relevant_files",
            "relevant_context",
            "issues_found",
            "confidence",
            "images",
            "security_scope",
            "threat_level",
            "compliance_requirements",
            "audit_focus",
            "severity_filter",
        ]

        for field in expected_fields:
            assert field in fields, f"Field '{field}' not found in tool field definitions"

        # Verify field descriptions are comprehensive
        assert "OWASP Top 10" in fields["step"]
        assert "OWASP Top 10" in fields["step"]
        assert "MANDATORY" in fields["step"]
        assert "Security context" in fields["security_scope"]
        assert "threat level" in fields["threat_level"]
        assert "compliance frameworks" in fields["compliance_requirements"]

    def test_workflow_request_model(self):
        """Test that the workflow request model is correctly configured."""
        tool = SecauditTool()
        request_model = tool.get_workflow_request_model()
        assert request_model == SecauditRequest

    def test_workflow_system_prompt(self):
        """Test that the workflow system prompt is correctly configured."""
        tool = SecauditTool()
        system_prompt = tool.get_system_prompt()

        # Verify it contains key security audit elements
        assert "OWASP Top 10" in system_prompt
        assert "security_analysis_complete" in system_prompt
        assert "vulnerability" in system_prompt
        assert "compliance_assessment" in system_prompt

    def test_compliance_requirements_validation(self):
        """Test compliance requirements validation in model validator."""
        # Test with valid compliance requirements
        valid_request = SecauditRequest(
            step="Security audit with compliance",
            step_number=1,
            total_steps=6,
            next_step_required=True,
            findings="Starting audit",
            compliance_requirements=["SOC2", "PCI DSS", "HIPAA"],
        )
        assert valid_request.compliance_requirements == ["SOC2", "PCI DSS", "HIPAA"]

        # Test with unknown compliance requirement (should warn but not fail)
        unknown_compliance_request = SecauditRequest(
            step="Security audit with unknown compliance",
            step_number=1,
            total_steps=6,
            next_step_required=True,
            findings="Starting audit",
            compliance_requirements=["UNKNOWN_COMPLIANCE"],
        )
        # Should still create the request but log a warning
        assert unknown_compliance_request.compliance_requirements == ["UNKNOWN_COMPLIANCE"]

    def test_comprehensive_workflow_scenario(self):
        """Test a complete workflow scenario from start to finish."""
        tool = SecauditTool()

        # Step 1: Initial security scope analysis
        step1_request = SecauditRequest(
            step="Begin comprehensive security audit of e-commerce web application",
            step_number=1,
            total_steps=6,
            next_step_required=True,
            findings="Identified Node.js/React application with payment processing and user management",
            security_scope="Web application - e-commerce platform",
            threat_level="high",
            compliance_requirements=["PCI DSS"],
            relevant_files=["/src/auth.js", "/src/payment.js"],
        )

        step1_actions = tool.get_required_actions(
            step1_request.step_number, step1_request.confidence, step1_request.findings, step1_request.total_steps
        )
        assert "Identify application type" in step1_actions[0]

        # Test should_call_expert_analysis with mock consolidated findings
        class MockConsolidatedFindings:
            def __init__(self):
                self.hypotheses = []
                self.relevant_files = []
                self.findings = []
                self.issues_found = []

        mock_findings = MockConsolidatedFindings()
        assert not tool.should_call_expert_analysis(mock_findings)

        # Step 6: Final assessment
        step6_request = SecauditRequest(
            step="Complete security assessment and risk evaluation",
            step_number=6,
            total_steps=6,
            next_step_required=False,
            findings="Comprehensive security audit completed with findings documented",
            security_scope="Web application - e-commerce platform",
            threat_level="high",
            compliance_requirements=["PCI DSS"],
            relevant_files=["/src/auth.js", "/src/payment.js", "/src/api.js"],
            relevant_context=["AuthService.authenticate", "PaymentProcessor.charge"],
            issues_found=[
                {"severity": "high", "description": "SQL injection in user search"},
                {"severity": "medium", "description": "Weak password policy"},
            ],
            confidence="high",
        )

        step6_actions = tool.get_required_actions(
            step6_request.step_number, step6_request.confidence, step6_request.findings, step6_request.total_steps
        )
        assert "Evaluate compliance requirements" in step6_actions[0]

        # Create mock consolidated findings for final step
        final_findings = MockConsolidatedFindings()
        final_findings.relevant_files = step6_request.relevant_files
        final_findings.findings = ["Comprehensive security audit completed with findings documented"]
        final_findings.issues_found = step6_request.issues_found
        final_findings.relevant_context = []
        final_findings.images = []
        assert tool.should_call_expert_analysis(final_findings)

        # Test expert analysis context generation with mock consolidated findings
        # Set up tool state as it would be after processing
        tool.initial_request = "Complete security assessment and risk evaluation"
        tool.security_config = {
            "security_scope": step6_request.security_scope,
            "threat_level": step6_request.threat_level,
            "compliance_requirements": step6_request.compliance_requirements,
            "audit_focus": step6_request.audit_focus,
            "severity_filter": step6_request.severity_filter,
        }

        # Create a complete mock consolidated findings
        complete_findings = MockConsolidatedFindings()
        complete_findings.relevant_files = step6_request.relevant_files
        complete_findings.relevant_context = step6_request.relevant_context
        complete_findings.issues_found = step6_request.issues_found
        complete_findings.findings = ["Security audit findings from all steps"]
        complete_findings.files_checked = []
        complete_findings.images = []

        context = tool.prepare_expert_analysis_context(complete_findings)
        assert "PCI DSS" in context
        assert "SQL injection" in context
        assert "HIGH SEVERITY:" in context
