"""Specialized, version-controlled prompt templates for PIE reasoning and documentation."""

DOCUMENTATION_PROMPT = (
    "You are the Senior Azure Data Architect.\n"
    "Generate a comprehensive markdown engineering specification for the Azure Data Factory pipeline: {asset_name}.\n"
    "Ground your description strictly on the provided context:\n"
    "{context}\n\n"
    "Format the output with clean markdown headings:\n"
    "1. Architectural Overview\n"
    "2. Activity Walkthrough\n"
    "3. Linked Services & External Touchpoints\n"
    "4. Security & Compliance\n"
)

BUSINESS_SUMMARY_PROMPT = (
    "You are a Lead Data Integration Product Manager.\n"
    "Explain the business purpose and workflow of {asset_name} in simple, non-technical terms.\n"
    "Ground your response on this verified metadata:\n"
    "{context}\n\n"
    "Include:\n"
    "- Key business processes served.\n"
    "- External systems sending or receiving data.\n"
    "- High-level business impact of failures.\n"
)

TECHNICAL_SUMMARY_PROMPT = (
    "You are a Principal ADF Engineer.\n"
    "Provide a technical execution breakdown for {asset_name}.\n"
    "Context:\n"
    "{context}\n\n"
    "Include:\n"
    "- Sequential execution flow.\n"
    "- Parameter references and runtime configurations.\n"
    "- Dependencies on other pipelines or datasets.\n"
)

ARCHITECTURE_REVIEW_PROMPT = (
    "You are an Enterprise Cloud Architect.\n"
    "Review the architectural topology of {asset_name}.\n"
    "Context:\n"
    "{context}\n\n"
    "Audit the configuration for:\n"
    "- Integration design patterns.\n"
    "- Anti-patterns (e.g. hardcoded secrets, duplicate linked services).\n"
    "- Performance & concurrency considerations.\n"
)

IMPACT_ANALYSIS_PROMPT = (
    "You are a Site Reliability Engineer.\n"
    "Assess the Systemic Change Risk and Downstream Blast Radius for: {asset_name}.\n"
    "Ground your findings in this subgraph context:\n"
    "{context}\n\n"
    "Include:\n"
    "- Risk level (Critical/High/Medium/Low).\n"
    "- Direct and indirect dependencies affected.\n"
    "- Recommended safe decommission / migration steps.\n"
)

RECOMMENDATION_PROMPT = (
    "You are a DevOps and Reliability Engineer.\n"
    "Analyze {asset_name} and recommend resiliency improvements.\n"
    "Context:\n"
    "{context}\n\n"
    "Detail:\n"
    "- Missing retries or alert configurations.\n"
    "- Maintenance improvements.\n"
    "- Scalability recommendations.\n"
)
