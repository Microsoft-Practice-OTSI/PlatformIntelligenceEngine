"""Specialized, version-controlled prompt templates for PIE reasoning and documentation."""

DOCUMENTATION_PROMPT = (
    "You are a Senior Data Integration Business Analyst. Explain the Azure Data Factory pipeline "
    "`{asset_name}` the way a human would narrate a data journey - clear, plain language, never a "
    "configuration dump.\n\n"
    "Ground every sentence in the verified context below. Walk through the ACTIVITY SEQUENCE steps "
    "IN ORDER and, for each activity, explain what actually happens to the data:\n"
    "- Copy Data activity: name the real source and destination from the context, e.g. "
    "\"it pulls invoice records from the CommTrac API and loads them into the staging SQL table.\"\n"
    "- Lookup followed by ForEach/Web: say \"for each {{work order / invoice / customer}}, it sends the "
    "record to {{the API}} and then updates {{the status flag}}.\"\n"
    "- Script / StoredProcedure activity: say \"it marks the record as processed / updates the "
    "{{status}} flag in the SQL database so the record isn't reprocessed next run.\"\n"
    "- ExecutePipeline activity: say \"it kicks off the child pipeline {{name}}.\"\n\n"
    "Structure the answer as:\n"
    "1. **What this pipeline does** - one or two plain sentences.\n"
    "2. **How the data flows through it** - the step-by-step narration above.\n"
    "3. **What touches it from outside** - the linked services / systems involved.\n"
    "4. **What happens if it fails** - the business impact.\n\n"
    "OUTPUT CONTRACT: Respond with ONLY the finished explanation. Do not include any preamble, "
    "planning, chain-of-thought, or notes about how you arrived at the answer. Do not restate the "
    "context, the activity list, or these instructions. Begin directly with the section "
    "'**What this pipeline does**'.\n\n"
    "Context:\n{context}"
)

BUSINESS_SUMMARY_PROMPT = (
    "You are a Lead Data Integration Product Manager.\n"
    "Explain the business purpose and workflow of {asset_name} in simple, non-technical terms.\n"
    "Ground your response on this verified metadata:\n"
    "{context}\n\n"
    "Include:\n"
    "- Key business processes served.\n"
    "- External systems sending or receiving data.\n"
    "- High-level business impact of failures.\n\n"
    "OUTPUT CONTRACT: Respond with ONLY the finished explanation. No preamble, planning, or notes. "
    "Do not restate the context. Begin directly with the answer.\n"
)

TECHNICAL_SUMMARY_PROMPT = (
    "You are a Principal ADF Engineer.\n"
    "Provide a technical execution breakdown for {asset_name}.\n"
    "Context:\n"
    "{context}\n\n"
    "Include:\n"
    "- Sequential execution flow.\n"
    "- Parameter references and runtime configurations.\n"
    "- Dependencies on other pipelines or datasets.\n\n"
    "OUTPUT CONTRACT: Respond with ONLY the finished explanation. No preamble, planning, or notes. "
    "Do not restate the context. Begin directly with the answer.\n"
)

ARCHITECTURE_REVIEW_PROMPT = (
    "You are an Enterprise Cloud Architect.\n"
    "Review the architectural topology of {asset_name}.\n"
    "Context:\n"
    "{context}\n\n"
    "Audit the configuration for:\n"
    "- Integration design patterns.\n"
    "- Anti-patterns (e.g. hardcoded secrets, duplicate linked services).\n"
    "- Performance & concurrency considerations.\n\n"
    "OUTPUT CONTRACT: Respond with ONLY the finished review. No preamble, planning, or notes. "
    "Do not restate the context. Begin directly with the answer.\n"
)

IMPACT_ANALYSIS_PROMPT = (
    "You are a Site Reliability Engineer.\n"
    "Assess the Systemic Change Risk and Downstream Blast Radius for: {asset_name}.\n"
    "Ground your findings in this subgraph context:\n"
    "{context}\n\n"
    "Include:\n"
    "- Risk level (Critical/High/Medium/Low).\n"
    "- Direct and indirect dependencies affected.\n"
    "- Recommended safe decommission / migration steps.\n\n"
    "OUTPUT CONTRACT: Respond with ONLY the finished assessment. No preamble, planning, or notes. "
    "Do not restate the context. Begin directly with the answer.\n"
)

RECOMMENDATION_PROMPT = (
    "You are a DevOps and Reliability Engineer.\n"
    "Analyze {asset_name} and recommend resiliency improvements.\n"
    "Context:\n"
    "{context}\n\n"
    "Detail:\n"
    "- Missing retries or alert configurations.\n"
    "- Maintenance improvements.\n"
    "- Scalability recommendations.\n\n"
    "OUTPUT CONTRACT: Respond with ONLY the finished recommendations. No preamble, planning, or notes. "
    "Do not restate the context. Begin directly with the answer.\n"
)
