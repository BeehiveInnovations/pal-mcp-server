"""
SECAUDIT Workflow tool - Comprehensive security audit with systematic investigation

This tool provides a structured workflow for comprehensive security assessment and analysis.
It guides the CLI agent through systematic investigation steps with forced pauses between each step
to ensure thorough security examination, vulnerability identification, and compliance assessment
before proceeding. The tool supports complex security scenarios including OWASP Top 10 coverage,
compliance framework mapping, and technology-specific security patterns.

Key features:
- Step-by-step security audit workflow with progress tracking
- Context-aware file embedding (references during investigation, full content for analysis)
- Automatic security issue tracking with severity classification
- Expert analysis integration with external models
- Support for focused security audits (OWASP, compliance, technology-specific)
- Confidence-based workflow optimization
- Risk-based prioritization and remediation planning
"""

import logging
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import SECAUDIT_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for security audit workflow
SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS = {
    "step": (
        "Describe what you're currently investigating for security audit by thinking deeply about security "
        "implications, threat vectors, and protection mechanisms. In step 1, clearly state your security "
        "audit plan and begin forming a systematic approach after identifying the application type, "
        "technology stack, and relevant security requirements. You must begin by passing the file path "
        "for the initial code you are about to audit in relevant_files. CRITICAL: Follow the OWASP Top 10 "
        "systematic checklist, examine authentication/authorization mechanisms, analyze input validation "
        "and data handling, assess dependency vulnerabilities, and evaluate infrastructure security. "
        "Consider not only obvious vulnerabilities but also subtle security gaps, configuration issues, "
        "design flaws, and compliance requirements. Map out the attack surface, understand the threat "
        "landscape, and identify areas requiring deeper security analysis. In all later steps, continue "
        "exploring with precision: trace security dependencies, verify security assumptions, and adapt "
        "your understanding as you uncover security evidence."
    ),
    "step_number": (
        "The index of the current step in the security audit sequence, beginning at 1. Each step should "
        "build upon or revise the previous one."
    ),
    "total_steps": (
        "Your current estimate for how many steps will be needed to complete the security audit. "
        "Adjust and increase as new security findings emerge."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the investigation with another step. False means you believe "
        "the security audit analysis is complete and ALL threats have been uncovered, ready for expert validation."
    ),
    "findings": (
        "Summarize everything discovered in this step about security aspects of the code being audited. "
        "Include analysis of security vulnerabilities, authentication/authorization issues, input validation "
        "gaps, encryption weaknesses, configuration problems, and compliance concerns. Be specific and avoid "
        "vague language—document what you now know about the security posture and how it affects your "
        "assessment. IMPORTANT: Document both positive security findings (proper implementations, good "
        "security practices) and concerns (vulnerabilities, security gaps, compliance issues). In later "
        "steps, confirm or update past findings with additional evidence."
    ),
    "files_checked": (
        "List all files (as absolute paths, do not clip or shrink file names) examined during the security "
        "audit investigation so far. Include even files ruled out or found to be unrelated, as this tracks "
        "your exploration path."
    ),
    "relevant_files": (
        "For when this is the first step, please pass absolute file paths of relevant code to audit (do not clip "
        "file paths). When used for the final step, this contains a subset of files_checked (as full absolute paths) "
        "that contain code directly relevant to the security audit or contain significant security issues, patterns, "
        "or examples worth highlighting. Only list those that are directly tied to important security findings, "
        "vulnerabilities, authentication issues, or security architectural decisions. This could include "
        "authentication modules, input validation files, configuration files, or files with notable security patterns."
    ),
    "relevant_context": (
        "List methods, functions, classes, or modules that are central to the security audit findings, in the "
        "format 'ClassName.methodName', 'functionName', or 'module.ClassName'. Prioritize those that contain "
        "security vulnerabilities, demonstrate security patterns, show authentication/authorization logic, or "
        "represent key security architectural decisions."
    ),
    "issues_found": (
        "List of security issues identified during the investigation. Each issue should be a dictionary with "
        "'severity' (critical, high, medium, low) and 'description' fields. Include security vulnerabilities, "
        "authentication bypasses, authorization flaws, injection vulnerabilities, cryptographic weaknesses, "
        "configuration issues, compliance gaps, etc."
    ),
    "confidence": (
        "Indicate your current confidence in the security audit assessment. Use: 'exploring' (starting analysis), "
        "'low' (early investigation), 'medium' (some evidence gathered), 'high' (strong evidence), "
        "'very_high' (very strong evidence), 'almost_certain' (nearly complete audit), 'certain' "
        "(100% confidence - security audit is thoroughly complete and all significant security issues are identified with no need for external model validation). "
        "Do NOT use 'certain' unless the security audit is comprehensively complete, use 'very_high' or 'almost_certain' instead if not 100% sure. "
        "Using 'certain' means you have complete confidence locally and prevents external model validation."
    ),
    "backtrack_from_step": (
        "If an earlier finding or assessment needs to be revised or discarded, specify the step number from which "
        "to start over. Use this to acknowledge investigative dead ends and correct the course."
    ),
    "images": (
        "Optional list of absolute paths to architecture diagrams, security models, threat models, or visual "
        "references that help with security audit context. Only include if they materially assist understanding "
        "or assessment of security posture."
    ),
    "security_scope": (
        "Define the security scope and application context (web app, mobile app, API, enterprise system, "
        "cloud service). Include technology stack, user types, data sensitivity, and threat landscape. "
        "This helps focus the security assessment appropriately."
    ),
    "threat_level": (
        "Assess the threat level based on application context: 'low' (internal tools, low-risk data), "
        "'medium' (customer-facing, business data), 'high' (financial, healthcare, regulated industry), "
        "'critical' (payment processing, sensitive personal data). This guides prioritization."
    ),
    "compliance_requirements": (
        "List applicable compliance frameworks and security standards (SOC2, PCI DSS, HIPAA, GDPR, "
        "ISO 27001, NIST). Include industry-specific requirements that affect security controls."
    ),
    "audit_focus": "Primary security focus areas for this audit (owasp, compliance, infrastructure, dependencies)",
    "severity_filter": "Minimum severity level to report on the security issues found",
}


class SecauditRequest(WorkflowRequest):
    """Request model for security audit workflow investigation steps"""

    # Required fields for each investigation step
    step: str = Field(..., description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["findings"])
    files_checked: list[str] = Field(
        default_factory=list, description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"]
    )
    relevant_files: list[str] = Field(
        default_factory=list, description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"]
    )
    relevant_context: list[str] = Field(
        default_factory=list, description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["relevant_context"]
    )
    issues_found: list[dict] = Field(
        default_factory=list, description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["issues_found"]
    )
    confidence: Optional[str] = Field("low", description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["confidence"])

    # Optional backtracking field
    backtrack_from_step: Optional[int] = Field(
        None, description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"]
    )

    # Optional images for visual context
    images: Optional[list[str]] = Field(default=None, description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["images"])

    # Security audit-specific fields
    security_scope: Optional[str] = Field(None, description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["security_scope"])
    threat_level: Optional[Literal["low", "medium", "high", "critical"]] = Field(
        "medium", description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["threat_level"]
    )
    compliance_requirements: Optional[list[str]] = Field(
        default_factory=list, description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["compliance_requirements"]
    )
    audit_focus: Optional[Literal["owasp", "compliance", "infrastructure", "dependencies", "comprehensive"]] = Field(
        "comprehensive", description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["audit_focus"]
    )
    severity_filter: Optional[Literal["critical", "high", "medium", "low", "all"]] = Field(
        "all", description=SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["severity_filter"]
    )

    @model_validator(mode="after")
    def validate_security_audit_request(self):
        """Validate security audit request parameters"""
        # Ensure security scope is provided for comprehensive audits
        if self.step_number == 1 and not self.security_scope:
            logger.warning("Security scope not provided for security audit - defaulting to general application")

        # Validate compliance requirements format
        if self.compliance_requirements:
            valid_compliance = {"SOC2", "PCI DSS", "HIPAA", "GDPR", "ISO 27001", "NIST", "FedRAMP", "FISMA"}
            for req in self.compliance_requirements:
                if req not in valid_compliance:
                    logger.warning(f"Unknown compliance requirement: {req}")

        return self


class SecauditTool(WorkflowTool):
    """
    Comprehensive security audit workflow tool.

    Provides systematic security assessment through multi-step investigation
    covering OWASP Top 10, compliance requirements, and technology-specific
    security patterns. Follows established WorkflowTool patterns while adding
    security-specific capabilities.
    """

    def __init__(self):
        super().__init__()
        self.initial_request = None
        self.security_config = {}

    def get_name(self) -> str:
        """Return the unique name of the tool."""
        return "secaudit"

    def get_description(self) -> str:
        """Return a description of the tool."""
        return (
            "COMPREHENSIVE SECURITY AUDIT WORKFLOW - Step-by-step security assessment with expert analysis. "
            "This tool guides you through a systematic investigation process where you:\n\n"
            "1. Start with step 1: describe your security investigation plan\n"
            "2. STOP and investigate code structure, patterns, and security issues\n"
            "3. Report findings in step 2 with concrete evidence from actual code analysis\n"
            "4. Continue investigating between each step\n"
            "5. Track findings, relevant files, and security issues throughout\n"
            "6. Update assessments as understanding evolves\n"
            "7. Once investigation is complete, receive expert security analysis\n\n"
            "IMPORTANT: This tool enforces investigation between steps:\n"
            "- After each call, you MUST investigate before calling again\n"
            "- Each step must include NEW evidence from code examination\n"
            "- No recursive calls without actual investigation work\n"
            "- The tool will specify which step number to use next\n"
            "- Follow the required_actions list for investigation guidance\n\n"
            "Perfect for: comprehensive security assessment, OWASP Top 10 analysis, compliance evaluation, "
            "vulnerability identification, threat modeling, security architecture review."
        )

    def get_system_prompt(self) -> str:
        """Return the system prompt for expert security analysis."""
        return SECAUDIT_PROMPT

    def get_default_temperature(self) -> float:
        """Return the temperature for security audit analysis"""
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Return the model category for security audit"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self) -> type:
        """Return the workflow request model class"""
        return SecauditRequest

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """
        Get security audit tool field definitions.

        Returns comprehensive field definitions including security-specific
        parameters while maintaining compatibility with existing workflow patterns.
        """
        return SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int) -> list[str]:
        """
        Provide step-specific guidance for systematic security analysis.

        Each step focuses on specific security domains to ensure comprehensive
        coverage without missing critical security aspects.
        """
        if step_number == 1:
            return [
                "Identify application type, technology stack, and security scope",
                "Map attack surface, entry points, and data flows",
                "Determine relevant security standards and compliance requirements",
                "Establish threat landscape and risk context for the application",
            ]
        elif step_number == 2:
            return [
                "Analyze authentication mechanisms and session management",
                "Check authorization controls, access patterns, and privilege escalation risks",
                "Assess multi-factor authentication, password policies, and account security",
                "Review identity and access management implementations",
            ]
        elif step_number == 3:
            return [
                "Examine input validation and sanitization mechanisms across all entry points",
                "Check for injection vulnerabilities (SQL, XSS, Command, LDAP, NoSQL)",
                "Review data encryption, sensitive data handling, and cryptographic implementations",
                "Analyze API input validation, rate limiting, and request/response security",
            ]
        elif step_number == 4:
            return [
                "Conduct OWASP Top 10 (2021) systematic review across all categories",
                "Check each OWASP category methodically with specific findings and evidence",
                "Cross-reference findings with application context and technology stack",
                "Prioritize vulnerabilities based on exploitability and business impact",
            ]
        elif step_number == 5:
            return [
                "Analyze third-party dependencies for known vulnerabilities and outdated versions",
                "Review configuration security, default settings, and hardening measures",
                "Check for hardcoded secrets, credentials, and sensitive information exposure",
                "Assess logging, monitoring, incident response, and security observability",
            ]
        elif step_number == 6:
            return [
                "Evaluate compliance requirements and identify gaps in controls",
                "Assess business impact and risk levels of all identified findings",
                "Create prioritized remediation roadmap with timeline and effort estimates",
                "Document comprehensive security posture and recommendations",
            ]
        else:
            return [
                "Continue systematic security investigation based on emerging findings",
                "Deep-dive into specific security concerns identified in previous steps",
                "Validate security hypotheses and confirm vulnerability assessments",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """
        Determine when to call expert security analysis.

        Expert analysis is triggered when the security audit has meaningful findings
        unless the user requested to skip assistant model.
        """
        # Check if user requested to skip assistant model
        if request and not self.get_request_use_assistant_model(request):
            return False

        # Check if we have meaningful investigation data
        return (
            len(consolidated_findings.relevant_files) > 0
            or len(consolidated_findings.findings) >= 2
            or len(consolidated_findings.issues_found) > 0
        )

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """
        Prepare comprehensive context for expert security model analysis.

        Provides security-specific context including scope, threat level,
        compliance requirements, and systematic findings for expert validation.
        """
        context_parts = [
            f"=== SECURITY AUDIT REQUEST ===\n{self.initial_request or 'Security audit workflow initiated'}\n=== END REQUEST ==="
        ]

        # Add investigation summary
        investigation_summary = self._build_security_audit_summary(consolidated_findings)
        context_parts.append(
            f"\n=== AGENT'S SECURITY INVESTIGATION ===\n{investigation_summary}\n=== END INVESTIGATION ==="
        )

        # Add security configuration context if available
        if self.security_config:
            config_text = "\n".join(f"- {key}: {value}" for key, value in self.security_config.items() if value)
            context_parts.append(f"\n=== SECURITY CONFIGURATION ===\n{config_text}\n=== END CONFIGURATION ===")

        # Add relevant files if available
        if consolidated_findings.relevant_files:
            files_text = "\n".join(f"- {file}" for file in consolidated_findings.relevant_files)
            context_parts.append(f"\n=== RELEVANT FILES ===\n{files_text}\n=== END FILES ===")

        # Add relevant security elements if available
        if consolidated_findings.relevant_context:
            methods_text = "\n".join(f"- {method}" for method in consolidated_findings.relevant_context)
            context_parts.append(
                f"\n=== SECURITY-CRITICAL CODE ELEMENTS ===\n{methods_text}\n=== END CODE ELEMENTS ==="
            )

        # Add security issues found if available
        if consolidated_findings.issues_found:
            issues_text = self._format_security_issues(consolidated_findings.issues_found)
            context_parts.append(f"\n=== SECURITY ISSUES IDENTIFIED ===\n{issues_text}\n=== END ISSUES ===")

        # Add assessment evolution if available
        if consolidated_findings.hypotheses:
            assessments_text = "\n".join(
                f"Step {h['step']} ({h['confidence']} confidence): {h['hypothesis']}"
                for h in consolidated_findings.hypotheses
            )
            context_parts.append(f"\n=== ASSESSMENT EVOLUTION ===\n{assessments_text}\n=== END ASSESSMENTS ===")

        # Add images if available
        if consolidated_findings.images:
            images_text = "\n".join(f"- {img}" for img in consolidated_findings.images)
            context_parts.append(
                f"\n=== VISUAL SECURITY INFORMATION ===\n{images_text}\n=== END VISUAL INFORMATION ==="
            )

        return "\n".join(context_parts)

    def _format_security_issues(self, issues_found: list[dict]) -> str:
        """
        Format security issues for expert analysis.

        Organizes security findings by severity for clear expert review.
        """
        if not issues_found:
            return "No security issues identified during systematic investigation."

        # Group issues by severity
        severity_groups = {"critical": [], "high": [], "medium": [], "low": []}

        for issue in issues_found:
            severity = issue.get("severity", "low").lower()
            description = issue.get("description", "No description provided")
            if severity in severity_groups:
                severity_groups[severity].append(description)
            else:
                severity_groups["low"].append(f"[{severity.upper()}] {description}")

        formatted_issues = []
        for severity in ["critical", "high", "medium", "low"]:
            if severity_groups[severity]:
                formatted_issues.append(f"\n{severity.upper()} SEVERITY:")
                for issue in severity_groups[severity]:
                    formatted_issues.append(f"  • {issue}")

        return "\n".join(formatted_issues) if formatted_issues else "No security issues identified."

    def _build_security_audit_summary(self, consolidated_findings) -> str:
        """Prepare a comprehensive summary of the security audit investigation."""
        summary_parts = [
            "=== SYSTEMATIC SECURITY AUDIT INVESTIGATION SUMMARY ===",
            f"Total steps: {len(consolidated_findings.findings)}",
            f"Files examined: {len(consolidated_findings.files_checked)}",
            f"Relevant files identified: {len(consolidated_findings.relevant_files)}",
            f"Security-critical elements analyzed: {len(consolidated_findings.relevant_context)}",
            f"Security issues identified: {len(consolidated_findings.issues_found)}",
            "",
            "=== INVESTIGATION PROGRESSION ===",
        ]

        for finding in consolidated_findings.findings:
            summary_parts.append(finding)

        return "\n".join(summary_parts)

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with security audit-specific overrides."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Security audit workflow-specific field overrides
        secaudit_field_overrides = {
            "step": {
                "type": "string",
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["step"],
            },
            "step_number": {
                "type": "integer",
                "minimum": 1,
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["step_number"],
            },
            "total_steps": {
                "type": "integer",
                "minimum": 1,
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"],
            },
            "next_step_required": {
                "type": "boolean",
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"],
            },
            "findings": {
                "type": "string",
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["findings"],
            },
            "files_checked": {
                "type": "array",
                "items": {"type": "string"},
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
            },
            "confidence": {
                "type": "string",
                "enum": ["exploring", "low", "medium", "high", "very_high", "almost_certain", "certain"],
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["confidence"],
            },
            "backtrack_from_step": {
                "type": "integer",
                "minimum": 1,
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"],
            },
            "issues_found": {
                "type": "array",
                "items": {"type": "object"},
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["issues_found"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["images"],
            },
            # Security audit-specific fields (for step 1)
            "security_scope": {
                "type": "string",
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["security_scope"],
            },
            "threat_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "default": "medium",
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["threat_level"],
            },
            "compliance_requirements": {
                "type": "array",
                "items": {"type": "string"},
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["compliance_requirements"],
            },
            "audit_focus": {
                "type": "string",
                "enum": ["owasp", "compliance", "infrastructure", "dependencies", "comprehensive"],
                "default": "comprehensive",
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["audit_focus"],
            },
            "severity_filter": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low", "all"],
                "default": "all",
                "description": SECAUDIT_WORKFLOW_FIELD_DESCRIPTIONS["severity_filter"],
            },
        }

        # Use WorkflowSchemaBuilder with security audit-specific tool fields
        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=secaudit_field_overrides,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
            tool_name=self.get_name(),
        )

    # Hook method overrides for security audit-specific behavior

    def prepare_step_data(self, request) -> dict:
        """Map security audit-specific fields for internal processing."""
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": request.files_checked,
            "relevant_files": request.relevant_files,
            "relevant_context": request.relevant_context,
            "issues_found": request.issues_found,
            "confidence": request.confidence,
            "hypothesis": request.findings,  # Map findings to hypothesis for compatibility
            "images": request.images or [],
        }

        # Store security-specific configuration on first step
        if request.step_number == 1:
            self.security_config = {
                "security_scope": request.security_scope,
                "threat_level": request.threat_level,
                "compliance_requirements": request.compliance_requirements,
                "audit_focus": request.audit_focus,
                "severity_filter": request.severity_filter,
            }

        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """Security audit workflow skips expert analysis when the CLI agent has "certain" confidence."""
        return request.confidence == "certain" and not request.next_step_required

    def store_initial_issue(self, step_description: str):
        """Store initial request for expert analysis."""
        self.initial_request = step_description

    def should_include_files_in_expert_prompt(self) -> bool:
        """Include files in expert analysis for comprehensive security audit."""
        return True

    def should_embed_system_prompt(self) -> bool:
        """Embed system prompt in expert analysis for proper context."""
        return True

    def get_expert_thinking_mode(self) -> str:
        """Use high thinking mode for thorough security analysis."""
        return "high"

    def get_expert_analysis_instruction(self) -> str:
        """Get specific instruction for security audit expert analysis."""
        return (
            "Please provide comprehensive security analysis based on the investigation findings. "
            "Focus on identifying any remaining vulnerabilities, validating the completeness of the analysis, "
            "and providing final recommendations for security improvements, following the OWASP-based "
            "format specified in the system prompt."
        )

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        """
        Security audit-specific completion message.
        """
        base_message = (
            "SECURITY AUDIT IS COMPLETE. You MUST now summarize and present ALL security findings organized by "
            "severity (Critical → High → Medium → Low), specific code locations with line numbers, and exact "
            "remediation steps for each vulnerability. Clearly prioritize the top 3 security issues that need "
            "immediate attention. Provide concrete, actionable guidance for each vulnerability—make it easy for "
            "developers to understand exactly what needs to be fixed and how to implement the security improvements."
        )

        # Add expert analysis guidance only when expert analysis was actually used
        if expert_analysis_used:
            expert_guidance = self.get_expert_analysis_guidance()
            if expert_guidance:
                return f"{base_message}\n\n{expert_guidance}"

        return base_message

    def get_expert_analysis_guidance(self) -> str:
        """
        Provide specific guidance for handling expert analysis in security audits.
        """
        return (
            "IMPORTANT: Analysis from an assistant model has been provided above. You MUST critically evaluate and validate "
            "the expert security findings rather than accepting them blindly. Cross-reference the expert analysis with "
            "your own investigation findings, verify that suggested security improvements are appropriate for this "
            "application's context and threat model, and ensure recommendations align with the project's security requirements. "
            "Present a synthesis that combines your systematic security review with validated expert insights, clearly "
            "distinguishing between vulnerabilities you've independently confirmed and additional insights from expert analysis."
        )

    def get_step_guidance_message(self, request) -> str:
        """
        Security audit-specific step guidance with detailed investigation instructions.
        """
        step_guidance = self.get_security_audit_step_guidance(request.step_number, request.confidence, request)
        return step_guidance["next_steps"]

    def get_security_audit_step_guidance(self, step_number: int, confidence: str, request) -> dict[str, Any]:
        """
        Provide step-specific guidance for security audit workflow.
        """
        # Generate the next steps instruction based on required actions
        required_actions = self.get_required_actions(step_number, confidence, request.findings, request.total_steps)

        if step_number == 1:
            next_steps = (
                f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first examine "
                f"the code files thoroughly using appropriate tools. CRITICAL AWARENESS: You need to understand "
                f"the security landscape, identify potential vulnerabilities across OWASP Top 10 categories, "
                f"and look for authentication flaws, injection points, cryptographic issues, and authorization bypasses. "
                f"Use file reading tools, security analysis, and systematic examination to gather comprehensive information. "
                f"Only call {self.get_name()} again AFTER completing your security investigation. When you call "
                f"{self.get_name()} next time, use step_number: {step_number + 1} and report specific "
                f"files examined, vulnerabilities found, and security assessments discovered."
            )
        elif confidence in ["exploring", "low"]:
            next_steps = (
                f"STOP! Do NOT call {self.get_name()} again yet. Based on your findings, you've identified areas that need "
                f"deeper security analysis. MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\n\nOnly call {self.get_name()} again with step_number: {step_number + 1} AFTER "
                + "completing these security audit tasks."
            )
        elif confidence in ["medium", "high"]:
            next_steps = (
                f"WAIT! Your security audit needs final verification. DO NOT call {self.get_name()} immediately. REQUIRED ACTIONS:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\n\nREMEMBER: Ensure you have identified all significant vulnerabilities across all severity levels and "
                f"verified the completeness of your security review. Document findings with specific file references and "
                f"line numbers where applicable, then call {self.get_name()} with step_number: {step_number + 1}."
            )
        else:
            next_steps = (
                f"PAUSE SECURITY AUDIT. Before calling {self.get_name()} step {step_number + 1}, you MUST examine more code thoroughly. "
                + "Required: "
                + ", ".join(required_actions[:2])
                + ". "
                + f"Your next {self.get_name()} call (step_number: {step_number + 1}) must include "
                f"NEW evidence from actual security analysis, not just theories. NO recursive {self.get_name()} calls "
                f"without investigation work!"
            )

        return {"next_steps": next_steps}

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match security audit workflow format.
        """
        # Store initial request on first step
        if request.step_number == 1:
            self.initial_request = request.step
            # Store security configuration for expert analysis
            if request.relevant_files:
                self.security_config = {
                    "relevant_files": request.relevant_files,
                    "security_scope": request.security_scope,
                    "threat_level": request.threat_level,
                    "compliance_requirements": request.compliance_requirements,
                    "audit_focus": request.audit_focus,
                    "severity_filter": request.severity_filter,
                }

        # Convert generic status names to security audit-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "security_audit_in_progress",
            f"pause_for_{tool_name}": "pause_for_security_audit",
            f"{tool_name}_required": "security_audit_required",
            f"{tool_name}_complete": "security_audit_complete",
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        # Rename status field to match security audit workflow
        if f"{tool_name}_status" in response_data:
            response_data["security_audit_status"] = response_data.pop(f"{tool_name}_status")
            # Add security audit-specific status fields
            response_data["security_audit_status"]["vulnerabilities_by_severity"] = {}
            for issue in self.consolidated_findings.issues_found:
                severity = issue.get("severity", "unknown")
                if severity not in response_data["security_audit_status"]["vulnerabilities_by_severity"]:
                    response_data["security_audit_status"]["vulnerabilities_by_severity"][severity] = 0
                response_data["security_audit_status"]["vulnerabilities_by_severity"][severity] += 1
            response_data["security_audit_status"]["audit_confidence"] = self.get_request_confidence(request)

        # Map complete_secaudit to complete_security_audit
        if f"complete_{tool_name}" in response_data:
            response_data["complete_security_audit"] = response_data.pop(f"complete_{tool_name}")

        # Map the completion flag to match security audit workflow
        if f"{tool_name}_complete" in response_data:
            response_data["security_audit_complete"] = response_data.pop(f"{tool_name}_complete")

        return response_data

    # Override inheritance hooks for security audit-specific behavior

    def get_completion_status(self) -> str:
        """Security audit tools use audit-specific status."""
        return "security_analysis_complete"

    def get_completion_data_key(self) -> str:
        """Security audit uses 'complete_security_audit' key."""
        return "complete_security_audit"

    def get_final_analysis_from_request(self, request):
        """Security audit tools use 'findings' field."""
        return request.findings

    def get_confidence_level(self, request) -> str:
        """Security audit tools use 'certain' for high confidence."""
        return "certain"

    def get_completion_message(self) -> str:
        """Security audit-specific completion message."""
        return (
            "Security audit complete with CERTAIN confidence. You have identified all significant vulnerabilities "
            "and provided comprehensive security analysis. MANDATORY: Present the user with the complete security audit results "
            "categorized by severity, and IMMEDIATELY proceed with implementing the highest priority security fixes "
            "or provide specific guidance for vulnerability remediation. Focus on actionable security recommendations."
        )

    def get_skip_reason(self) -> str:
        """Security audit-specific skip reason."""
        return "Completed comprehensive security audit with full confidence locally"

    def get_skip_expert_analysis_status(self) -> str:
        """Security audit-specific expert analysis skip status."""
        return "skipped_due_to_certain_audit_confidence"

    def prepare_work_summary(self) -> str:
        """Security audit-specific work summary."""
        return self._build_security_audit_summary(self.consolidated_findings)

    def get_request_model(self):
        """Return the request model for this tool"""
        return SecauditRequest

    async def prepare_prompt(self, request: SecauditRequest) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
