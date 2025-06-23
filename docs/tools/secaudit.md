# Secaudit Tool - Comprehensive Security Audit

**Systematic OWASP-based security assessment with compliance evaluation through workflow-driven investigation**

The `secaudit` tool provides comprehensive security auditing capabilities with systematic OWASP Top 10 assessment, compliance framework evaluation, 
and threat modeling. This workflow tool guides Claude through methodical security investigation steps with forced pauses between each step to ensure 
thorough vulnerability assessment, security pattern analysis, and compliance verification before providing expert analysis.

**Important**: AI models may not identify all security vulnerabilities. Always perform additional manual security reviews, 
penetration testing, and verification.

## How the Workflow Works

The secaudit tool implements a **structured 6-step security workflow** that ensures comprehensive security assessment:

**Investigation Phase (Claude-Led):**
1. **Step 1**: Security Scope Analysis - Claude identifies application type, tech stack, attack surface, and compliance requirements
2. **Step 2**: Authentication & Authorization Assessment - Analyzes auth mechanisms, session management, and access controls
3. **Step 3**: Input Validation & Data Security - Reviews input handling, data protection, and injection vulnerabilities
4. **Step 4**: OWASP Top 10 (2021) Review - Systematic assessment of all OWASP categories with specific findings
5. **Step 5**: Dependencies & Infrastructure - Security analysis of third-party components and deployment configurations
6. **Step 6**: Compliance & Risk Assessment - Evaluation against specified compliance frameworks and risk prioritization

**Expert Analysis Phase:**
After Claude completes the investigation (unless confidence is **certain**):
- Complete security assessment summary with all vulnerabilities and evidence
- OWASP Top 10 systematic findings with severity classifications
- Compliance framework gap analysis and remediation recommendations
- Risk-prioritized remediation roadmap based on threat level and business impact

**Special Note**: If you want Claude to perform the entire security audit without calling another model, you can include "don't use any other model" in your prompt, and Claude will complete the full workflow independently.

## Model Recommendation

This tool particularly benefits from Gemini Pro or O3 models due to their advanced reasoning capabilities and large context windows, which allow comprehensive security analysis across complex codebases. Security audits require understanding subtle attack vectors and cross-component interactions that benefit from deeper analytical capabilities.

## Example Prompts

```
Perform a secaudit with o3 on this e-commerce web application focusing on payment processing security and PCI DSS compliance
```

```
Use secaudit to conduct a comprehensive security audit of the authentication system, threat level high, focus on enterprise 
security patterns and HIPAA compliance
```

## Pro Tip: Multi-Scope Security Assessment

**You can run parallel security audits for different application components:**

```
Start separate sub-tasks, in one start a secaudit for critical payment processing components focusing on PCI DSS with gemini pro, 
and in the other for user management focusing on OWASP authentication vulnerabilities with o4-mini, then combine into a unified 
security remediation plan using planner 
```

## Key Features

- **OWASP Top 10 (2021) systematic assessment** with specific vulnerability identification
- **Multi-compliance framework support**: SOC2, PCI DSS, HIPAA, GDPR, FedRAMP
- **Threat-level aware analysis**: Critical, high, medium, low threat classifications
- **Technology-specific security patterns**: Web apps, APIs, mobile, cloud, enterprise systems
- **Risk-based prioritization**: Business impact and exploitability assessment
- **Audit focus customization**: Comprehensive, authentication, data protection, infrastructure
- **Image support**: Security analysis from architecture diagrams, network topology, or security findings
- **Multi-file security analysis**: Cross-component vulnerability identification
- **Compliance gap analysis**: Specific framework requirements with remediation guidance
- **Attack surface mapping**: Entry points, data flows, and privilege boundaries
- **Security control effectiveness**: Evaluation of existing security measures

## Tool Parameters

**Workflow Investigation Parameters (used during step-by-step process):**
- `step`: Current security investigation step description (required for each step)
- `step_number`: Current step number in audit sequence (required)
- `total_steps`: Estimated total investigation steps (typically 4-6, adjustable)
- `next_step_required`: Whether another investigation step is needed
- `findings`: Security discoveries and evidence collected in this step (required)
- `files_checked`: All files examined during security investigation
- `relevant_files`: Files directly relevant to security assessment (required in step 1)
- `relevant_context`: Methods/functions/classes central to security findings
- `issues_found`: Security issues identified with severity levels
- `confidence`: Confidence level in security assessment completeness (exploring/low/medium/high/certain)
- `backtrack_from_step`: Step number to backtrack from (for revisions)
- `images`: Architecture diagrams, security documentation, or visual references

**Initial Security Configuration (used in step 1):**
- `model`: auto|pro|flash|o3|o3-mini|o4-mini|gpt4.1 (default: server default)
- `security_scope`: Application context, technology stack, and security boundary definition (required)
- `threat_level`: low|medium|high|critical (default: medium) - determines assessment depth and urgency
- `compliance_requirements`: List of compliance frameworks to assess against (e.g., ["PCI DSS", "SOC2"])
- `audit_focus`: comprehensive|authentication|data_protection|infrastructure|api_security (default: comprehensive)
- `severity_filter`: critical|high|medium|low|all (default: all)
- `temperature`: Temperature for analytical consistency (0-1, default 0.2)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `use_websearch`: Enable web search for security best practices and vulnerability databases (default: true)
- `use_assistant_model`: Whether to use expert security analysis phase (default: true)
- `continuation_id`: Continue previous security audit discussions

## Audit Focus Areas

**Comprehensive (default):**
- Full OWASP Top 10 assessment with all security domains
- Authentication, authorization, data protection, infrastructure
- Best for complete security posture evaluation

**Authentication:**
- Focused on identity, access management, and session security
- Multi-factor authentication, password policies, privilege escalation
- Best for user management and access control systems

**Data Protection:**
- Encryption, data handling, privacy controls, and compliance
- Input validation, output encoding, data classification
- Best for applications handling sensitive or regulated data

**Infrastructure:**
- Deployment security, configuration management, dependency security
- Network security, container security, cloud security posture
- Best for DevOps and infrastructure security assessment

**API Security:**
- REST/GraphQL security, rate limiting, API authentication
- Input validation, authorization patterns, API gateway security
- Best for API-first applications and microservices

## Threat Levels

Security assessment depth and urgency:

- **🔴 CRITICAL**: Mission-critical systems, high-value targets, regulatory requirements
- **🟠 HIGH**: Business-critical applications, customer data handling, financial systems
- **🟡 MEDIUM**: Standard business applications, internal tools, moderate risk exposure
- **🟢 LOW**: Development environments, non-sensitive applications, proof-of-concepts

## Compliance Frameworks

Supported compliance assessments:

- **SOC2**: Security, availability, processing integrity, confidentiality, privacy
- **PCI DSS**: Payment card industry data security standards
- **HIPAA**: Healthcare information privacy and security
- **GDPR**: General data protection regulation compliance
- **FedRAMP**: Federal risk and authorization management program
- **ISO27001**: Information security management systems
- **NIST**: Cybersecurity framework controls

## OWASP Top 10 (2021) Coverage

Systematic assessment includes:

1. **A01 Broken Access Control**: Authorization flaws and privilege escalation
2. **A02 Cryptographic Failures**: Encryption and data protection issues
3. **A03 Injection**: SQL, NoSQL, OS, and LDAP injection vulnerabilities
4. **A04 Insecure Design**: Security design flaws and threat modeling gaps
5. **A05 Security Misconfiguration**: Configuration and hardening issues
6. **A06 Vulnerable Components**: Third-party and dependency vulnerabilities
7. **A07 Identification & Authentication Failures**: Authentication bypass and session management
8. **A08 Software & Data Integrity Failures**: Supply chain and integrity violations
9. **A09 Security Logging & Monitoring Failures**: Detection and response capabilities
10. **A10 Server-Side Request Forgery**: SSRF and related vulnerabilities

## Usage Examples

**Comprehensive E-commerce Security Audit:**
```
"Conduct a comprehensive secaudit with gemini pro for our Node.js e-commerce platform, threat level high, 
compliance requirements PCI DSS and SOC2, focus on payment processing security"
```

**Authentication System Security Review:**
```
"Use o3 to perform secaudit on authentication microservice, focus on authentication, 
threat level critical, check for OWASP A07 and multi-factor authentication implementation"
```

**API Security Assessment:**
```
"Secaudit our REST API gateway with gemini pro, audit focus api_security, 
compliance requirements GDPR, threat level medium"
```

**Infrastructure Security Review:**
```
"Perform secaudit on Kubernetes deployment manifests with o3, focus infrastructure, 
threat level high, include container security and network policies"
```

**Quick Security Scan:**
```
"Fast secaudit of user registration flow with flash, focus authentication, 
severity filter critical and high only"
```

## Best Practices

- **Define clear security scope**: Specify application type, tech stack, and security boundaries
- **Set appropriate threat levels**: Match assessment depth to risk exposure and criticality
- **Include compliance requirements**: Specify relevant frameworks for regulatory alignment
- **Use parallel audits**: Run separate assessments for different components or compliance frameworks
- **Provide architectural context**: Include system diagrams, data flow documentation, or deployment topology
- **Focus audit scope**: Use audit_focus for targeted assessments of specific security domains
- **Follow up on findings**: Use continuation feature to dive deeper into specific vulnerabilities

## Output Format

Security audits include:
- **Executive Security Summary**: Overall security posture and critical findings
- **OWASP Top 10 Assessment**: Systematic review of each category with specific findings
- **Compliance Gap Analysis**: Framework-specific requirements and current compliance status
- **Risk-Prioritized Findings**: Vulnerabilities ordered by exploitability and business impact
- **Remediation Roadmap**: Phased approach to security improvements with quick wins
- **Security Architecture Recommendations**: Structural improvements for long-term security posture

## When to Use Secaudit vs Other Tools

- **Use `secaudit`** for: Comprehensive security assessment, compliance evaluation, OWASP-based vulnerability analysis
- **Use `codereview`** for: General code quality with some security considerations
- **Use `analyze`** for: Understanding security architecture without vulnerability assessment
- **Use `debug`** for: Investigating specific security incidents or exploit attempts
- **Use `precommit`** for: Pre-deployment security validation and change impact assessment