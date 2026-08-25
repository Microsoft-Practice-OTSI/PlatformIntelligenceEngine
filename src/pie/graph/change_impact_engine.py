"""Change Impact Intelligence Engine: Orchestrates deterministic impact analysis
for any proposed change to an ADF object.

Follows the 13-step analysis pipeline:
1. Identify target → 2. Identify change → 3. Resolve metadata → 4. Direct deps →
5. Expression refs → 6. Downstream graph → 7. Upstream graph → 8. External systems →
9. Affected workflows → 10. Build evidence → 11. Risk → 12. Recommendation → 13. Summary
"""

from pie.core.logging import get_logger
from pie.graph.models import (
    NodeType,
    EdgeType,
    GraphNode,
    ChangeType,
    ChangeRequest,
    ImpactFinding,
    RiskAssessment,
    ImpactAnalysis,
    ConfidenceLevel,
    DependencyClassification,
    ImpactScope,
)
from pie.graph.builder import KnowledgeGraph
from pie.graph.traversal import GraphTraversalService
from pie.graph.expression_analyzer import ExpressionAnalyzer

logger = get_logger(__name__)

# Disambiguation response model (for when multiple nodes match)
class DisambiguationInfo:
    """Returned when multiple nodes match a name, requiring user clarification."""

    def __init__(self, matches: list[GraphNode], target_name: str):
        self.matches = matches
        self.target_name = target_name
        self.needs_disambiguation = len(matches) > 1

    def to_clarification_message(self) -> str:
        """Build a focused clarification question listing the ambiguous matches."""
        if not self.needs_disambiguation:
            return ""
        lines = [f"Multiple objects match '{self.target_name}'. Which one do you mean?"]
        for i, node in enumerate(self.matches, 1):
            ctx = node.properties.get("pipeline_name", "")
            node_type = node.type.value
            context_hint = f" (in pipeline `{ctx}`)" if ctx else ""
            lines.append(f"  {i}. `{node.name}` [{node_type}]{context_hint} (ID: `{node.id}`)")
        return "\n".join(lines)

# Base risk scores per object type (higher = more critical to remove)
_OBJECT_TYPE_BASE_SCORE: dict[NodeType, int] = {
    NodeType.INTEGRATION_RUNTIME: 40,
    NodeType.LINKED_SERVICE: 35,
    NodeType.DATASET: 25,
    NodeType.TRIGGER: 20,
    NodeType.PIPELINE: 15,
    NodeType.DATA_FLOW: 15,
    NodeType.ACTIVITY: 10,
}

# Change type severity multipliers
_CHANGE_TYPE_SEVERITY: dict[ChangeType, float] = {
    ChangeType.DELETE: 1.0,
    ChangeType.REMOVE: 0.9,
    ChangeType.DECOMMISSION: 0.85,
    ChangeType.REPLACE: 0.7,
    ChangeType.DISABLE: 0.5,
    ChangeType.MODIFY: 0.4,
    ChangeType.RENAME: 0.3,
}

# Known external system patterns (from audit engine)
_EXTERNAL_SYSTEM_PATTERNS = {
    "SAP": ["sap", "s4hana", "successfactors"],
    "Dynamics CRM": ["crm", "dynamics"],
    "Databricks": ["databricks"],
    "Coupa": ["coupa"],
    "Datex": ["datex", "footprintwms"],
    "OpenText": ["ecm", "opentext"],
    "RailCarRx": ["railcarrx"],
    "Cleo": ["cleo"],
}


def _risk_level_from_score(score: int) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


class ChangeImpactEngine:
    """Central orchestration engine for Change Impact Analysis.

    Combines dependency analysis, expression reference detection, graph traversal,
    and risk assessment into a single structured ImpactAnalysis result.
    """

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.traversal = GraphTraversalService(graph)
        self.expr_analyzer = graph.expr_analyzer or ExpressionAnalyzer()

    def analyze(self, request: ChangeRequest) -> ImpactAnalysis:
        """Execute the full 13-step change impact analysis pipeline."""
        # Step 1: Identify target — check for ambiguity
        all_matches = self.traversal.resolve_all_matches(request.target_object)

        if not all_matches:
            return self._not_found(request)

        # Disambiguation: if multiple nodes match, return clarification info
        disambiguation = DisambiguationInfo(all_matches, request.target_object)
        if disambiguation.needs_disambiguation:
            # Pick the first match as default but flag the ambiguity
            target_node = all_matches[0]
            logger.info(
                f"Ambiguous target '{request.target_object}' matched {len(all_matches)} nodes. "
                f"Using first match: {target_node.id}"
            )
        else:
            resolved_id = self.traversal.resolve_node_id(request.target_object)
            target_node = self.graph.nodes[resolved_id]

        # Step 2: Change type is from the request
        change_type = request.change_type

        # Step 3: Resolve target metadata (already have target_node)

        # Steps 4-9: Run all analysis methods
        direct_impacts = self._find_direct_impacts(target_node, change_type)
        object_specific_impacts = self._get_object_specific_impacts(target_node, direct_impacts)
        expression_impacts = self._find_expression_impacts(target_node, request)
        downstream_impacts = self._find_downstream_impacts(target_node, change_type)
        upstream_context = self._find_upstream_context(target_node)
        external_systems = self._identify_external_systems(target_node)
        affected_pipelines = self._collect_affected_pipelines(
            direct_impacts + object_specific_impacts + expression_impacts + downstream_impacts
        )

        # Step 10: Build evidence
        all_findings = direct_impacts + object_specific_impacts + expression_impacts + downstream_impacts
        evidence = self._build_evidence_chain(target_node, all_findings, upstream_context)

        # Step 11: Calculate risk
        risk = self._calculate_risk(
            target_node, change_type, all_findings, affected_pipelines, external_systems
        )

        # Step 12: Generate recommendation
        recommendation = self._generate_recommendation(
            target_node, change_type, risk, all_findings, affected_pipelines
        )

        # Step 13: Build impact chain and summary
        impact_chain = self._build_impact_chain(target_node, all_findings)
        potential_consequences = self._build_consequences(target_node, change_type, all_findings)
        summary_md = self._build_summary_md(
            target_node, request, risk, all_findings, affected_pipelines, external_systems, recommendation
        )

        return ImpactAnalysis(
            target={"id": target_node.id, "name": target_node.name, "objectType": target_node.type.value},
            requested_change=request,
            risk=risk,
            direct_impacts=direct_impacts + object_specific_impacts,
            indirect_impacts=downstream_impacts,
            affected_pipelines=sorted(affected_pipelines),
            affected_assets=sorted({f.asset for f in all_findings}),
            external_systems=external_systems,
            evidence=evidence,
            confidence=self._overall_confidence(all_findings),
            potential_consequences=potential_consequences,
            recommendation=recommendation,
            impact_chain=impact_chain,
            summary_md=summary_md,
            disambiguation=disambiguation.to_clarification_message() if disambiguation.needs_disambiguation else None,
        )

    # ------------------------------------------------------------------
    # Step 4: Direct Dependencies
    # ------------------------------------------------------------------

    def _find_direct_impacts(self, target: GraphNode, change_type: ChangeType) -> list[ImpactFinding]:
        """Find all assets directly connected to the target via graph edges."""
        findings: list[ImpactFinding] = []

        # Incoming edges: who depends on / uses / reads from this target
        for edge in self.graph.get_incoming_edges(target.id):
            src = self.graph.get_node(edge.source_id)
            if not src:
                continue

            classification = self._classify_edge(edge.type, direction="incoming")
            finding = self._make_finding(
                asset=src.name,
                asset_type=src.type,
                edge_type=edge.type,
                classification=classification,
                direction="incoming",
                target=target,
                evidence_items=[f"{edge.type.value}: {src.name} → {target.name}"],
            )
            findings.append(finding)

        # Outgoing edges: what this target depends on / reads / writes
        for edge in self.graph.get_outgoing_edges(target.id):
            tgt = self.graph.get_node(edge.target_id)
            if not tgt:
                continue

            if change_type in (ChangeType.DELETE, ChangeType.REMOVE, ChangeType.DECOMMISSION):
                # Removing this target breaks things downstream that depend on it
                # But outgoing edges mean this target USES the target — less impact
                classification = self._classify_edge(edge.type, direction="outgoing")
                finding = self._make_finding(
                    asset=tgt.name,
                    asset_type=tgt.type,
                    edge_type=edge.type,
                    classification=classification,
                    direction="outgoing_target",
                    target=target,
                    evidence_items=[f"{edge.type.value}: {target.name} → {tgt.name}"],
                )
                findings.append(finding)

        return findings

    # ------------------------------------------------------------------
    # Step 5: Expression References
    # ------------------------------------------------------------------

    def _find_expression_impacts(self, target: GraphNode, request: ChangeRequest) -> list[ImpactFinding]:
        """Find assets that reference the target in ADF expressions."""
        findings: list[ImpactFinding] = []

        # For activity targets, find expression references to them
        if target.type == NodeType.ACTIVITY:
            refs_to = self.expr_analyzer.get_references_to(target.name)
            for ref in refs_to:
                # Parameter-level references are inferred (contextual evidence)
                is_inferred = ref.reference_type in ("PARAMETER_REFERENCE", "VARIABLE_REFERENCE")
                findings.append(ImpactFinding(
                    asset=ref.target_name,
                    asset_type=NodeType.ACTIVITY,
                    impact_type="EXPRESSION_DEPENDENCY",
                    relationship=DependencyClassification.INFERRED if is_inferred else DependencyClassification.DATA_REFERENCE,
                    reason=f"Activity '{ref.target_name}' references {target.name} in expression: {ref.expression}",
                    evidence=[ref.expression],
                    confidence=ConfidenceLevel.MEDIUM if is_inferred else ConfidenceLevel.HIGH,
                    severity="HIGH" if not is_inferred else "MEDIUM",
                ))

        # For dataset targets, find expression references
        if target.type == NodeType.DATASET:
            refs_to = self.expr_analyzer.get_references_to(target.name)
            for ref in refs_to:
                is_inferred = ref.reference_type in ("PARAMETER_REFERENCE", "VARIABLE_REFERENCE")
                findings.append(ImpactFinding(
                    asset=ref.target_name,
                    asset_type=NodeType.ACTIVITY,
                    impact_type="EXPRESSION_DEPENDENCY",
                    relationship=DependencyClassification.INFERRED if is_inferred else DependencyClassification.DATA_REFERENCE,
                    reason=f"Activity '{ref.target_name}' references dataset {target.name} in expression: {ref.expression}",
                    evidence=[ref.expression],
                    confidence=ConfidenceLevel.MEDIUM if is_inferred else ConfidenceLevel.HIGH,
                    severity="HIGH" if not is_inferred else "MEDIUM",
                ))

        return findings

    # ------------------------------------------------------------------
    # Step 5b: Object-Specific Impact Interpretation
    # ------------------------------------------------------------------

    def _interpret_pipeline_impact(self, target: GraphNode, findings: list[ImpactFinding]) -> list[ImpactFinding]:
        """Pipeline-specific: ExecutePipeline chains, trigger schedules, activity chains."""
        extra: list[ImpactFinding] = []

        # Find parent pipelines that call this pipeline (ExecutePipeline)
        for edge in self.graph.get_incoming_edges(target.id, EdgeType.CALLS):
            src = self.graph.get_node(edge.source_id)
            if src:
                extra.append(ImpactFinding(
                    asset=src.name,
                    asset_type=src.type,
                    impact_type="PARENT_PIPELINE",
                    relationship=DependencyClassification.STRUCTURAL,
                    reason=f"Parent pipeline '{src.name}' calls this pipeline via ExecutePipeline",
                    evidence=[f"CALLS edge: {src.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        # Find child pipelines called by activities in this pipeline
        for edge in self.graph.get_outgoing_edges(target.id, EdgeType.CALLS):
            child = self.graph.get_node(edge.target_id)
            if child:
                extra.append(ImpactFinding(
                    asset=child.name,
                    asset_type=child.type,
                    impact_type="CHILD_PIPELINE",
                    relationship=DependencyClassification.STRUCTURAL,
                    reason=f"This pipeline calls child pipeline '{child.name}'",
                    evidence=[f"CALLS edge: {target.name} → {child.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="MEDIUM",
                ))

        # Find triggers that execute this pipeline
        for edge in self.graph.get_incoming_edges(target.id, EdgeType.EXECUTES):
            trigger = self.graph.get_node(edge.source_id)
            if trigger:
                extra.append(ImpactFinding(
                    asset=trigger.name,
                    asset_type=trigger.type,
                    impact_type="TRIGGER_SCHEDULE",
                    relationship=DependencyClassification.DIRECT,
                    reason=f"Trigger '{trigger.name}' automatically executes this pipeline",
                    evidence=[f"EXECUTES edge: {trigger.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        return extra

    def _interpret_dataset_impact(self, target: GraphNode, findings: list[ImpactFinding]) -> list[ImpactFinding]:
        """Dataset-specific: identify read/write patterns, data flow usage."""
        extra: list[ImpactFinding] = []

        # Find activities that read from this dataset
        for edge in self.graph.get_incoming_edges(target.id, EdgeType.READS):
            src = self.graph.get_node(edge.source_id)
            if src:
                extra.append(ImpactFinding(
                    asset=src.name,
                    asset_type=src.type,
                    impact_type="DATASET_READER",
                    relationship=DependencyClassification.DATA_REFERENCE,
                    reason=f"'{src.name}' reads from dataset '{target.name}'",
                    evidence=[f"READS edge: {src.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        # Find activities that write to this dataset
        for edge in self.graph.get_incoming_edges(target.id, EdgeType.WRITES):
            src = self.graph.get_node(edge.source_id)
            if src:
                extra.append(ImpactFinding(
                    asset=src.name,
                    asset_type=src.type,
                    impact_type="DATASET_WRITER",
                    relationship=DependencyClassification.DATA_REFERENCE,
                    reason=f"'{src.name}' writes to dataset '{target.name}'",
                    evidence=[f"WRITES edge: {src.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="MEDIUM",
                ))

        # Find data flows that use this dataset as source or sink
        for edge in self.graph.get_incoming_edges(target.id, EdgeType.READS):
            src = self.graph.get_node(edge.source_id)
            if src and src.type == NodeType.DATA_FLOW:
                extra.append(ImpactFinding(
                    asset=src.name,
                    asset_type=src.type,
                    impact_type="DATA_FLOW_SOURCE",
                    relationship=DependencyClassification.DATA_REFERENCE,
                    reason=f"Data flow '{src.name}' uses dataset '{target.name}' as source",
                    evidence=[f"READS edge: {src.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        for edge in self.graph.get_incoming_edges(target.id, EdgeType.WRITES):
            src = self.graph.get_node(edge.source_id)
            if src and src.type == NodeType.DATA_FLOW:
                extra.append(ImpactFinding(
                    asset=src.name,
                    asset_type=src.type,
                    impact_type="DATA_FLOW_SINK",
                    relationship=DependencyClassification.DATA_REFERENCE,
                    reason=f"Data flow '{src.name}' uses dataset '{target.name}' as sink",
                    evidence=[f"WRITES edge: {src.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        return extra

    def _interpret_linked_service_impact(self, target: GraphNode, findings: list[ImpactFinding]) -> list[ImpactFinding]:
        """LinkedService-specific: datasets using it, activities using it directly, pipelines."""
        extra: list[ImpactFinding] = []

        # Find datasets that use this linked service
        for edge in self.graph.get_incoming_edges(target.id, EdgeType.USES):
            src = self.graph.get_node(edge.source_id)
            if src and src.type == NodeType.DATASET:
                extra.append(ImpactFinding(
                    asset=src.name,
                    asset_type=src.type,
                    impact_type="LINKED_SERVICE_DATASET",
                    relationship=DependencyClassification.DIRECT,
                    reason=f"Dataset '{src.name}' uses linked service '{target.name}'",
                    evidence=[f"USES edge: {src.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        # Find activities that use this linked service directly (Web, AzureFunction, etc.)
        for edge in self.graph.get_incoming_edges(target.id, EdgeType.USES):
            src = self.graph.get_node(edge.source_id)
            if src and src.type == NodeType.ACTIVITY:
                extra.append(ImpactFinding(
                    asset=src.name,
                    asset_type=src.type,
                    impact_type="LINKED_SERVICE_ACTIVITY",
                    relationship=DependencyClassification.DIRECT,
                    reason=f"Activity '{src.name}' uses linked service '{target.name}' directly",
                    evidence=[f"USES edge: {src.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        # Find integration runtime used by this linked service
        for edge in self.graph.get_outgoing_edges(target.id, EdgeType.USES_INTEGRATION_RUNTIME):
            ir = self.graph.get_node(edge.target_id)
            if ir:
                extra.append(ImpactFinding(
                    asset=ir.name,
                    asset_type=ir.type,
                    impact_type="LINKED_SERVICE_IR",
                    relationship=DependencyClassification.DIRECT,
                    reason=f"Linked service '{target.name}' uses integration runtime '{ir.name}'",
                    evidence=[f"USES_INTEGRATION_RUNTIME edge: {target.name} → {ir.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="INFO",
                ))

        return extra

    def _interpret_trigger_impact(self, target: GraphNode, findings: list[ImpactFinding]) -> list[ImpactFinding]:
        """Trigger-specific: pipeline associations, schedule, execution implications."""
        extra: list[ImpactFinding] = []

        # Find pipelines executed by this trigger
        for edge in self.graph.get_outgoing_edges(target.id, EdgeType.EXECUTES):
            pipe = self.graph.get_node(edge.target_id)
            if pipe:
                extra.append(ImpactFinding(
                    asset=pipe.name,
                    asset_type=pipe.type,
                    impact_type="TRIGGERED_PIPELINE",
                    relationship=DependencyClassification.DIRECT,
                    reason=f"Trigger '{target.name}' executes pipeline '{pipe.name}'",
                    evidence=[f"EXECUTES edge: {target.name} → {pipe.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        # Get trigger schedule from properties
        schedule = target.properties.get("recurrence_schedule", "")
        if schedule:
            extra.append(ImpactFinding(
                asset=target.name,
                asset_type=target.type,
                impact_type="TRIGGER_SCHEDULE",
                relationship=DependencyClassification.DIRECT,
                reason=f"Trigger schedule: {schedule}. Disabling stops automated execution.",
                evidence=[f"Schedule: {schedule}"],
                confidence=ConfidenceLevel.HIGH,
                severity="MEDIUM",
            ))

        return extra

    def _interpret_data_flow_impact(self, target: GraphNode, findings: list[ImpactFinding]) -> list[ImpactFinding]:
        """DataFlow-specific: invoking pipelines, source/sink datasets, linked services."""
        extra: list[ImpactFinding] = []

        # Find source datasets
        for edge in self.graph.get_outgoing_edges(target.id, EdgeType.READS):
            ds = self.graph.get_node(edge.target_id)
            if ds and ds.type == NodeType.DATASET:
                extra.append(ImpactFinding(
                    asset=ds.name,
                    asset_type=ds.type,
                    impact_type="DATA_FLOW_SOURCE",
                    relationship=DependencyClassification.DATA_REFERENCE,
                    reason=f"Data flow '{target.name}' reads from dataset '{ds.name}'",
                    evidence=[f"READS edge: {target.name} → {ds.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="MEDIUM",
                ))

        # Find sink datasets
        for edge in self.graph.get_outgoing_edges(target.id, EdgeType.WRITES):
            ds = self.graph.get_node(edge.target_id)
            if ds and ds.type == NodeType.DATASET:
                extra.append(ImpactFinding(
                    asset=ds.name,
                    asset_type=ds.type,
                    impact_type="DATA_FLOW_SINK",
                    relationship=DependencyClassification.DATA_REFERENCE,
                    reason=f"Data flow '{target.name}' writes to dataset '{ds.name}'",
                    evidence=[f"WRITES edge: {target.name} → {ds.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="MEDIUM",
                ))

        # Find activities that contain this data flow
        for edge in self.graph.get_incoming_edges(target.id):
            src = self.graph.get_node(edge.source_id)
            if src and src.type == NodeType.ACTIVITY:
                extra.append(ImpactFinding(
                    asset=src.name,
                    asset_type=src.type,
                    impact_type="DATA_FLOW_INVOKED_BY",
                    relationship=DependencyClassification.STRUCTURAL,
                    reason=f"Activity '{src.name}' invokes data flow '{target.name}'",
                    evidence=[f"{edge.type.value} edge: {src.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

        return extra

    def _interpret_integration_runtime_impact(self, target: GraphNode, findings: list[ImpactFinding]) -> list[ImpactFinding]:
        """IntegrationRuntime-specific: linked services using it, cascade to datasets/activities/pipelines."""
        extra: list[ImpactFinding] = []

        # Find linked services that use this integration runtime
        for edge in self.graph.get_incoming_edges(target.id, EdgeType.USES_INTEGRATION_RUNTIME):
            ls = self.graph.get_node(edge.source_id)
            if ls:
                extra.append(ImpactFinding(
                    asset=ls.name,
                    asset_type=ls.type,
                    impact_type="IR_LINKED_SERVICE",
                    relationship=DependencyClassification.DIRECT,
                    reason=f"Linked service '{ls.name}' uses integration runtime '{target.name}'",
                    evidence=[f"USES_INTEGRATION_RUNTIME edge: {ls.name} → {target.name}"],
                    confidence=ConfidenceLevel.HIGH,
                    severity="HIGH",
                ))

                # Cascade: find datasets using this linked service
                for ds_edge in self.graph.get_incoming_edges(ls.id, EdgeType.USES):
                    ds = self.graph.get_node(ds_edge.source_id)
                    if ds and ds.type == NodeType.DATASET:
                        extra.append(ImpactFinding(
                            asset=ds.name,
                            asset_type=ds.type,
                            impact_type="IR_CASCADE_DATASET",
                            relationship=DependencyClassification.INDIRECT,
                            reason=f"Dataset '{ds.name}' uses linked service '{ls.name}' which depends on IR '{target.name}'",
                            evidence=[f"Chain: {ds.name} → {ls.name} → {target.name}"],
                            confidence=ConfidenceLevel.HIGH,
                            severity="HIGH",
                        ))

        return extra

    def _get_object_specific_impacts(self, target: GraphNode, direct_impacts: list[ImpactFinding]) -> list[ImpactFinding]:
        """Route to the appropriate object-specific interpretation method."""
        interpreters = {
            NodeType.PIPELINE: self._interpret_pipeline_impact,
            NodeType.DATASET: self._interpret_dataset_impact,
            NodeType.LINKED_SERVICE: self._interpret_linked_service_impact,
            NodeType.TRIGGER: self._interpret_trigger_impact,
            NodeType.DATA_FLOW: self._interpret_data_flow_impact,
            NodeType.INTEGRATION_RUNTIME: self._interpret_integration_runtime_impact,
        }
        interpreter = interpreters.get(target.type)
        if interpreter:
            return interpreter(target, direct_impacts)
        return []

    def _find_downstream_impacts(self, target: GraphNode, change_type: ChangeType) -> list[ImpactFinding]:
        """Traverse downstream blast radius."""
        findings: list[ImpactFinding] = []

        downstream = self.traversal.get_downstream_impact(target.id, max_hops=5)
        for item in downstream:
            node_id = item.get("node_id", "")
            node = self.graph.get_node(node_id)
            if not node or node.id == target.id:
                continue

            hop = item.get("hop", 0)
            relationship_str = item.get("relationship", "")

            # Determine severity based on hop distance
            if hop <= 1:
                severity = "HIGH"
                classification = DependencyClassification.DIRECT
            elif hop <= 3:
                severity = "MEDIUM"
                classification = DependencyClassification.INDIRECT
            else:
                severity = "LOW"
                classification = DependencyClassification.INFERRED

            findings.append(ImpactFinding(
                asset=node.name,
                asset_type=node.type,
                impact_type=f"DOWNSTREAM_HOP_{hop}",
                relationship=classification,
                reason=f"Downstream dependency at hop {hop}: {relationship_str}",
                evidence=[f"Path: {' → '.join(item.get('path', []))}"],
                confidence=ConfidenceLevel.HIGH if hop <= 2 else ConfidenceLevel.MEDIUM,
                severity=severity,
            ))

        return findings

    # ------------------------------------------------------------------
    # Step 7: Upstream Context
    # ------------------------------------------------------------------

    def _find_upstream_context(self, target: GraphNode) -> list[dict]:
        """Find upstream dependencies for context (not impact findings)."""
        return self.traversal.get_upstream_lineage(target.id, max_hops=3)

    # ------------------------------------------------------------------
    # Step 8: External Systems
    # ------------------------------------------------------------------

    def _identify_external_systems(self, target: GraphNode) -> list[str]:
        """Identify external systems connected to or through the target."""
        external: list[str] = []

        # Check linked services connected to this target
        for edge in self.graph.get_outgoing_edges(target.id):
            node = self.graph.get_node(edge.target_id)
            if not node:
                continue
            if node.type == NodeType.LINKED_SERVICE:
                ls_type = node.properties.get("type", "").lower()
                ls_name = node.name.lower()
                for vendor, patterns in _EXTERNAL_SYSTEM_PATTERNS.items():
                    if any(p in ls_type or p in ls_name for p in patterns):
                        if vendor not in external:
                            external.append(vendor)

        # Also check through dataset → linked service chain
        for edge in self.graph.get_outgoing_edges(target.id):
            node = self.graph.get_node(edge.target_id)
            if not node:
                continue
            if node.type == NodeType.DATASET:
                for ds_edge in self.graph.get_outgoing_edges(node.id):
                    ls_node = self.graph.get_node(ds_edge.target_id)
                    if ls_node and ls_node.type == NodeType.LINKED_SERVICE:
                        ls_type = ls_node.properties.get("type", "").lower()
                        ls_name = ls_node.name.lower()
                        for vendor, patterns in _EXTERNAL_SYSTEM_PATTERNS.items():
                            if any(p in ls_type or p in ls_name for p in patterns):
                                if vendor not in external:
                                    external.append(vendor)

        return external

    # ------------------------------------------------------------------
    # Step 9: Affected Workflows
    # ------------------------------------------------------------------

    def _collect_affected_pipelines(self, findings: list[ImpactFinding]) -> set[str]:
        """Collect all unique pipeline names from impact findings."""
        pipelines: set[str] = set()
        for f in findings:
            if f.asset_type == NodeType.PIPELINE:
                pipelines.add(f.asset)
            elif f.asset_type == NodeType.ACTIVITY:
                # Activity format is "PipelineName.ActivityName"
                if "." in f.asset:
                    pipelines.add(f.asset.rsplit(".", 1)[0])
            # Check properties for pipeline_name
        return pipelines

    # ------------------------------------------------------------------
    # Step 10: Evidence Builder
    # ------------------------------------------------------------------

    def _build_evidence_chain(
        self,
        target: GraphNode,
        findings: list[ImpactFinding],
        upstream: list[dict],
    ) -> list[ImpactFinding]:
        """Compile the full evidence chain for the analysis."""
        evidence: list[ImpactFinding] = []

        # Add the target itself as context
        evidence.append(ImpactFinding(
            asset=target.name,
            asset_type=target.type,
            impact_type="TARGET",
            relationship=DependencyClassification.DIRECT,
            reason=f"Target of proposed change ({target.type.value})",
            evidence=[f"Node ID: {target.id}"],
            confidence=ConfidenceLevel.HIGH,
            severity="INFO",
        ))

        # Add all findings as evidence
        evidence.extend(findings)

        return evidence

    # ------------------------------------------------------------------
    # Step 11: Risk Calculator
    # ------------------------------------------------------------------

    def _calculate_risk(
        self,
        target: GraphNode,
        change_type: ChangeType,
        findings: list[ImpactFinding],
        affected_pipelines: set[str],
        external_systems: list[str],
    ) -> RiskAssessment:
        """Calculate explainable risk level and score."""
        base_score = _OBJECT_TYPE_BASE_SCORE.get(target.type, 10)
        severity_mult = _CHANGE_TYPE_SEVERITY.get(change_type, 0.5)

        pipe_weight = len(affected_pipelines) * 12
        finding_weight = len(findings) * 3
        external_weight = len(external_systems) * 15

        raw_score = base_score * severity_mult + pipe_weight + finding_weight + external_weight
        score = min(100, int(raw_score))
        level = _risk_level_from_score(score)

        # Build explainable reasons
        reasons: list[str] = []
        if affected_pipelines:
            reasons.append(f"{len(affected_pipelines)} pipeline(s) would be affected")
        if external_systems:
            reasons.append(f"{len(external_systems)} external system(s) connected: {', '.join(external_systems)}")
        high_sev = [f for f in findings if f.severity == "HIGH"]
        if high_sev:
            reasons.append(f"{len(high_sev)} high-severity direct dependencies found")
        if not reasons:
            reasons.append("No significant downstream dependencies detected")

        # Determine scopes
        scopes: list[ImpactScope] = [ImpactScope.IMMEDIATE]
        if len(affected_pipelines) > 0:
            scopes.append(ImpactScope.PIPELINE)
        if len(affected_pipelines) > 1:
            scopes.append(ImpactScope.WORKFLOW)
        if len(findings) > 5:
            scopes.append(ImpactScope.PLATFORM)
        if external_systems:
            scopes.append(ImpactScope.EXTERNAL_SYSTEM)

        return RiskAssessment(level=level, score=score, reasons=reasons, scopes=scopes)

    # ------------------------------------------------------------------
    # Step 12: Recommendation Generator
    # ------------------------------------------------------------------

    def _generate_recommendation(
        self,
        target: GraphNode,
        change_type: ChangeType,
        risk: RiskAssessment,
        findings: list[ImpactFinding],
        affected_pipelines: set[str],
    ) -> str:
        """Generate a human-readable recommendation."""
        lines: list[str] = []

        if risk.level == "CRITICAL":
            lines.append(f"**Do not {change_type.value.lower()} `{target.name}` without a comprehensive migration plan.**")
            lines.append(f"This action would impact {len(affected_pipelines)} pipeline(s) and carries critical risk.")
        elif risk.level == "HIGH":
            lines.append(f"**Exercise caution before {change_type.value.lower()}ing `{target.name}`.**")
            lines.append(f"This action would impact {len(affected_pipelines)} pipeline(s).")
        elif risk.level == "MEDIUM":
            lines.append(f"**Proceed with caution when {change_type.value.lower()}ing `{target.name}`.**")
            lines.append(f"Some downstream dependencies will be affected.")
        else:
            lines.append(f"**Safe to {change_type.value.lower()} `{target.name}`.**")
            lines.append("No significant downstream dependencies were found.")

        # Change-type-specific advice
        if change_type in (ChangeType.DELETE, ChangeType.REMOVE):
            if affected_pipelines:
                lines.append(f"\n**Affected pipelines:** {', '.join(sorted(affected_pipelines)[:5])}")
            lines.append("\n**Before proceeding:**")
            lines.append(f"1. Verify no active pipelines depend on `{target.name}`")
            lines.append(f"2. Check for scheduled triggers that reference affected pipelines")
            lines.append(f"3. Notify dependent pipeline owners")
        elif change_type == ChangeType.DISABLE:
            lines.append("\nDisabling will stop automated execution but preserve the configuration.")
            lines.append("Verify no critical schedules depend solely on this trigger.")
        elif change_type == ChangeType.REPLACE:
            lines.append("\nBefore replacing, ensure the new configuration is compatible with all consumers.")
        elif change_type == ChangeType.RENAME:
            lines.append("\nRenaming will break all expression references to this object.")
            lines.append("Update all references in dependent pipelines before renaming.")
        elif change_type == ChangeType.DECOMMISSION:
            lines.append("\nBefore decommissioning:")
            lines.append(f"1. Confirm no active pipelines read from or write to `{target.name}`")
            lines.append(f"2. Archive the configuration for audit purposes")
        elif change_type == ChangeType.MODIFY:
            lines.append("\nBefore modifying, review which aspects may affect downstream consumers.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Step 13: Impact Chain & Summary
    # ------------------------------------------------------------------

    def _build_impact_chain(self, target: GraphNode, findings: list[ImpactFinding]) -> list[str]:
        """Build an ordered impact chain for visualization."""
        chain = [f"{target.name} ({target.type.value})"]
        # Sort findings by severity: HIGH → MEDIUM → LOW
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
        sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 9))
        for f in sorted_findings[:15]:  # Cap at 15 for readability
            chain.append(f"→ {f.asset} ({f.asset_type.value}) [{f.severity}]")
        return chain

    def _build_consequences(
        self, target: GraphNode, change_type: ChangeType, findings: list[ImpactFinding]
    ) -> list[str]:
        """Build a list of potential consequences."""
        consequences: list[str] = []
        high_findings = [f for f in findings if f.severity == "HIGH"]
        if high_findings:
            consequences.append(
                f"{len(high_findings)} high-severity dependency(ies) would be immediately impacted"
            )
        med_findings = [f for f in findings if f.severity == "MEDIUM"]
        if med_findings:
            consequences.append(
                f"{len(med_findings)} medium-severity dependency(ies) would be indirectly affected"
            )
        expr_findings = [f for f in findings if f.relationship == DependencyClassification.DATA_REFERENCE]
        if expr_findings:
            consequences.append(
                f"{len(expr_findings)} expression-level data reference(s) would break"
            )
        return consequences

    def _build_summary_md(
        self,
        target: GraphNode,
        request: ChangeRequest,
        risk: RiskAssessment,
        findings: list[ImpactFinding],
        affected_pipelines: set[str],
        external_systems: list[str],
        recommendation: str,
    ) -> str:
        """Build a complete human-readable markdown summary."""
        lines: list[str] = []

        # Header
        risk_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk.level, "⚪")
        lines.append(f"## Change Impact Analysis")
        lines.append(f"")
        lines.append(f"**Target:** `{target.name}` ({target.type.value})")
        lines.append(f"**Proposed Change:** {request.change_type.value}")
        if request.parent_context:
            lines.append(f"**Parent Context:** `{request.parent_context}`")
        lines.append(f"")
        lines.append(f"### {risk_emoji} Risk Level: {risk.level} (Score: {risk.score}/100)")
        lines.append(f"")

        # Risk reasons
        lines.append("**Why?**")
        for reason in risk.reasons:
            lines.append(f"- {reason}")
        lines.append(f"")

        # Impact summary
        lines.append(f"### Impact Summary")
        lines.append(f"- **Direct impacts:** {len([f for f in findings if f.relationship == DependencyClassification.DIRECT])}")
        lines.append(f"- **Indirect impacts:** {len([f for f in findings if f.relationship == DependencyClassification.INDIRECT])}")
        lines.append(f"- **Expression dependencies:** {len([f for f in findings if f.relationship == DependencyClassification.DATA_REFERENCE])}")
        lines.append(f"- **Affected pipelines:** {len(affected_pipelines)}")
        if external_systems:
            lines.append(f"- **External systems:** {', '.join(external_systems)}")
        lines.append(f"")

        # Affected pipelines
        if affected_pipelines:
            lines.append(f"### Affected Pipelines")
            for p in sorted(affected_pipelines):
                lines.append(f"- `{p}`")
            lines.append(f"")

        # Recommendation
        lines.append(f"### Recommendation")
        lines.append(recommendation)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _classify_edge(self, edge_type: EdgeType, direction: str) -> DependencyClassification:
        """Classify a graph edge into a dependency classification."""
        if edge_type in (EdgeType.CONTAINS, EdgeType.CALLS, EdgeType.EXECUTES):
            return DependencyClassification.STRUCTURAL
        if edge_type in (EdgeType.READS, EdgeType.WRITES, EdgeType.REFERENCES):
            return DependencyClassification.DATA_REFERENCE
        if edge_type == EdgeType.REFERENCES_OUTPUT_OF:
            return DependencyClassification.DATA_REFERENCE
        if edge_type in (EdgeType.USES, EdgeType.USES_INTEGRATION_RUNTIME):
            return DependencyClassification.DIRECT
        if edge_type == EdgeType.DEPENDS_ON:
            return DependencyClassification.DIRECT
        if edge_type in (EdgeType.TRIGGERED_BY, EdgeType.CALLS_API):
            return DependencyClassification.DIRECT
        return DependencyClassification.INDIRECT

    def _make_finding(
        self,
        asset: str,
        asset_type: NodeType,
        edge_type: EdgeType,
        classification: DependencyClassification,
        direction: str,
        target: GraphNode,
        evidence_items: list[str],
    ) -> ImpactFinding:
        """Create an ImpactFinding from a graph edge."""
        # Determine severity based on edge type and direction
        if direction == "incoming" and edge_type in (EdgeType.READS, EdgeType.WRITES, EdgeType.REFERENCES_OUTPUT_OF):
            severity = "HIGH"
        elif direction == "incoming" and edge_type in (EdgeType.CALLS, EdgeType.EXECUTES, EdgeType.TRIGGERED_BY):
            severity = "HIGH"
        elif direction == "incoming":
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Build human-readable reason
        if edge_type == EdgeType.READS:
            reason = f"{asset} reads from {target.name}"
        elif edge_type == EdgeType.WRITES:
            reason = f"{asset} writes to {target.name}"
        elif edge_type == EdgeType.CALLS:
            reason = f"{asset} calls {target.name}"
        elif edge_type == EdgeType.EXECUTES:
            reason = f"{asset} executes {target.name}"
        elif edge_type == EdgeType.TRIGGERED_BY:
            reason = f"{target.name} is triggered by {asset}"
        elif edge_type == EdgeType.USES:
            reason = f"{asset} uses {target.name}"
        elif edge_type == EdgeType.REFERENCES:
            reason = f"{asset} references {target.name}"
        elif edge_type == EdgeType.REFERENCES_OUTPUT_OF:
            reason = f"{asset} references output of {target.name}"
        elif edge_type == EdgeType.DEPENDS_ON:
            reason = f"{asset} depends on {target.name}"
        else:
            reason = f"{edge_type.value} relationship: {asset} ↔ {target.name}"

        return ImpactFinding(
            asset=asset,
            asset_type=asset_type,
            impact_type=f"EDGE_{edge_type.value}_{direction.upper()}",
            relationship=classification,
            reason=reason,
            evidence=evidence_items,
            confidence=ConfidenceLevel.HIGH,
            severity=severity,
        )

    def _overall_confidence(self, findings: list[ImpactFinding]) -> ConfidenceLevel:
        """Determine overall confidence based on all findings."""
        if not findings:
            return ConfidenceLevel.HIGH
        confidences = [f.confidence for f in findings]
        if all(c == ConfidenceLevel.HIGH for c in confidences):
            return ConfidenceLevel.HIGH
        if any(c == ConfidenceLevel.LOW for c in confidences):
            return ConfidenceLevel.LOW
        return ConfidenceLevel.MEDIUM

    def _not_found(self, request: ChangeRequest) -> ImpactAnalysis:
        """Return a not-found analysis result."""
        return ImpactAnalysis(
            target={"id": "", "name": request.target_object, "objectType": "Unknown"},
            requested_change=request,
            risk=RiskAssessment(level="LOW", score=0, reasons=["Target asset not found in Knowledge Graph"]),
            recommendation=f"Asset '{request.target_object}' was not found. Ensure the factory has been synced and the name is correct.",
        )

    def analyze_parameter_impact(self, param_name: str, change_type: ChangeType, query: str = "") -> ImpactAnalysis:
        """Analyze the impact of changing/removing a pipeline parameter or variable.

        Uses the ExpressionAnalyzer's compiled references to find all activities
        and pipelines that reference this parameter/variable name, then builds
        a full ImpactAnalysis result.
        """
        refs_to = self.expr_analyzer.get_references_to(param_name)

        affected_activities: set[str] = set()
        affected_pipelines: set[str] = set()
        ref_details: list[dict] = []

        for ref in refs_to:
            # target_name is like "PL_PipelineName.ActivityName" or just "ActivityName"
            target = ref.target_name
            affected_activities.add(target)

            # Extract parent pipeline name from "PL_PipelineName.ActivityName"
            parts = target.split(".")
            if len(parts) >= 2:
                pipeline_name = parts[0]
                affected_pipelines.add(pipeline_name)

            ref_details.append({
                "activity": target,
                "expression": ref.expression,
                "reference_type": ref.reference_type,
            })

        # Also scan for pipelines that declare this parameter in their metadata
        for node in self.graph.nodes.values():
            if node.type == NodeType.PIPELINE:
                params = node.properties.get("parameters", {})
                variables = node.properties.get("variables", {})
                if param_name in params or param_name in variables:
                    affected_pipelines.add(node.name)

        # Build direct impacts
        direct_impacts: list[ImpactFinding] = []
        for detail in ref_details:
            act_name = detail["activity"]
            # Try to find the activity node to get its type
            act_node = self.graph.get_node_by_name(act_name, NodeType.ACTIVITY)
            act_type = act_node.properties.get("type", "Unknown") if act_node else "Unknown"
            direct_impacts.append(ImpactFinding(
                asset=act_name,
                asset_type=NodeType.ACTIVITY,
                impact_type="EXPRESSION_DEPENDENCY",
                relationship=DependencyClassification.DATA_REFERENCE,
                reason=f"Activity '{act_name}' ({act_type}) references parameter/variable '{param_name}' in expression: {detail['expression']}",
                evidence=[detail["expression"]],
                confidence=ConfidenceLevel.MEDIUM,
                severity="HIGH",
            ))

        # Score: based on how many pipelines are affected
        num_pipelines = len(affected_pipelines)
        num_activities = len(affected_activities)
        if num_pipelines >= 10:
            score = 95
        elif num_pipelines >= 5:
            score = 80
        elif num_pipelines >= 2:
            score = 60
        elif num_pipelines == 1:
            score = 40
        else:
            score = 20

        # Adjust by change type
        multiplier = _CHANGE_TYPE_SEVERITY.get(change_type, 0.5)
        score = min(100, int(score * multiplier))

        risk = RiskAssessment(
            level=_risk_level_from_score(score),
            score=score,
            reasons=[
                f"Parameter/variable '{param_name}' is referenced by {num_activities} activity(ies) across {num_pipelines} pipeline(s)",
            ],
            scopes=[ImpactScope.PIPELINE] if num_pipelines > 0 else [],
        )

        # Build affected pipeline list
        affected_list = sorted(affected_pipelines)

        # Build impact chain
        impact_chain = [f"{param_name} (Parameter/Variable)"]
        for p in affected_list[:10]:
            impact_chain.append(p)
        if len(affected_list) > 10:
            impact_chain.append(f"... and {len(affected_list) - 10} more pipelines")

        # Build recommendation
        if num_pipelines == 0:
            recommendation = (
                f"Parameter/variable '{param_name}' was not found in any expression references "
                f"or pipeline definitions. Verify the name is correct."
            )
        elif num_pipelines <= 2:
            recommendation = (
                f"Before {change_type.value.lower()} parameter/variable '{param_name}', "
                f"notify owners of {', '.join(affected_list)}. "
                f"Verify no downstream processes depend on the current value."
            )
        else:
            recommendation = (
                f"CRITICAL: Parameter/variable '{param_name}' is used across {num_pipelines} pipelines. "
                f"Before {change_type.value.lower()}, coordinate with all pipeline owners: "
                f"{', '.join(affected_list[:5])}"
                f"{' and others' if num_pipelines > 5 else ''}. "
                f"Arrange an alternative execution method and test in non-production first."
            )

        # Build external systems list (from linked services in affected pipelines)
        external_systems: list[str] = []
        for p_name in affected_list:
            p_node = self.graph.get_node_by_name(p_name, NodeType.PIPELINE)
            if p_node:
                for edge in self.graph.get_outgoing_edges(p_node.id):
                    child = self.graph.nodes.get(edge.target_id)
                    if child and child.type == NodeType.ACTIVITY:
                        for act_edge in self.graph.get_outgoing_edges(child.id):
                            ds = self.graph.nodes.get(act_edge.target_id)
                            if ds and ds.type == NodeType.DATASET:
                                for ds_edge in self.graph.get_outgoing_edges(ds.id):
                                    ls = self.graph.nodes.get(ds_edge.target_id)
                                    if ls and ls.type == NodeType.LINKED_SERVICE:
                                        ls_name = ls.name
                                        if ls_name not in external_systems:
                                            external_systems.append(ls_name)

        # Build summary markdown
        summary_lines = [
            f"## Parameter/Variable Impact Analysis",
            f"",
            f"**Target:** `{param_name}` (Parameter/Variable)",
            f"**Change:** {change_type.value}",
            f"**Risk Level:** {risk.level} ({risk.score}/100)",
            f"",
            f"### Impact Summary",
            f"- **Affected Activities:** {num_activities}",
            f"- **Affected Pipelines:** {num_pipelines}",
            f"- **Expression References:** {len(ref_details)}",
            f"",
        ]

        if affected_list:
            summary_lines.append("### Affected Pipelines")
            for p in affected_list:
                summary_lines.append(f"- `{p}`")
            summary_lines.append("")

        if ref_details:
            summary_lines.append("### Expression References")
            for detail in ref_details[:10]:
                summary_lines.append(
                    f"- `{detail['activity']}`: `{detail['expression']}`"
                )
            if len(ref_details) > 10:
                summary_lines.append(f"- ... and {len(ref_details) - 10} more")
            summary_lines.append("")

        if external_systems:
            summary_lines.append("### External Systems")
            for sys_name in external_systems[:5]:
                summary_lines.append(f"- `{sys_name}`")
            summary_lines.append("")

        summary_lines.append(f"### Recommendation")
        summary_lines.append(recommendation)

        return ImpactAnalysis(
            target={"id": f"parameter:{param_name}", "name": param_name, "objectType": "Parameter/Variable"},
            requested_change=ChangeRequest(
                target_object=param_name,
                object_type=NodeType.PARAMETER,
                change_type=change_type,
                requested_action=query or f"Change parameter {param_name}",
            ),
            risk=risk,
            direct_impacts=direct_impacts,
            affected_pipelines=affected_list,
            affected_assets=affected_activities | affected_pipelines,
            external_systems=external_systems,
            confidence=ConfidenceLevel.MEDIUM,
            potential_consequences=[
                f"Changing parameter '{param_name}' would affect {num_pipelines} pipeline(s) and {num_activities} activity(ies)",
            ],
            recommendation=recommendation,
            impact_chain=impact_chain,
            summary_md="\n".join(summary_lines),
        )
