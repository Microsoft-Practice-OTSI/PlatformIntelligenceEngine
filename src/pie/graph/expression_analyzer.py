"""ADF Expression Reference Analyzer: Detects explicit references in ADF expressions
such as @activity('Name').output.value, dataset('Name'), and @pipeline().parameters.X.

These references represent high-confidence data dependencies that may not be captured
by structural graph edges alone.
"""

import re
from pie.graph.models import ConfidenceLevel, ExpressionReference
from pie.discovery.models import ActivityMetadata, FactoryMetadata


# --- Regex patterns for ADF expression references ---

_ACTIVITY_OUTPUT_REF = re.compile(
    r"activity\(\s*['\"]([^'\"]+)['\"]\s*\)\.output",
    re.IGNORECASE,
)

_ACTIVITY_INPUT_REF = re.compile(
    r"activity\(\s*['\"]([^'\"]+)['\"]\s*\)\.input",
    re.IGNORECASE,
)

_ACTIVITY_RESULT_REF = re.compile(
    r"activity\(\s*['\"]([^'\"]+)['\"]\s*\)\.result",
    re.IGNORECASE,
)

_ACTIVITY_NAME_REF = re.compile(
    r"activity\(\s*['\"]([^'\"]+)['\"]\s*\)",
    re.IGNORECASE,
)

_DATASET_REF = re.compile(
    r"dataset\(\s*['\"]([^'\"]+)['\"]\s*\)",
    re.IGNORECASE,
)

_PIPELINE_PARAM_REF = re.compile(
    r"@pipeline\(\)\.parameters\.([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

_GLOBAL_PARAM_REF = re.compile(
    r"@pipeline\(\)\.globalParameters\.([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

_VARIABLE_REF = re.compile(
    r"@variables\(\s*['\"]([^'\"]+)['\"]\s*\)",
    re.IGNORECASE,
)

_FOR_EACH_ITEM = re.compile(
    r"@items\(\s*['\"]([^'\"]+)['\"]\s*\)",
    re.IGNORECASE,
)

_IF_CONDITION = re.compile(
    r"@if\(\s*(.+?)\s*,",
    re.IGNORECASE,
)


def _extract_string_values(obj: any) -> list[str]:
    """Recursively extract all string values from a nested dict/list structure."""
    values: list[str] = []
    if isinstance(obj, str):
        values.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            values.extend(_extract_string_values(v))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(_extract_string_values(item))
    return values


def _extract_inner_activities(type_props: dict) -> list[dict]:
    """Extract inner activity definitions from ForEach, IfCondition, Until, Switch, etc.

    Returns a flat list of activity-like dicts with 'name', 'type', and 'typeProperties'.
    """
    activities: list[dict] = []

    # ForEach: typeProperties.activities[]
    for_each_acts = type_props.get("activities", [])
    if isinstance(for_each_acts, list):
        for act in for_each_acts:
            if isinstance(act, dict):
                activities.append(act)

    # IfCondition: typeProperties.ifTrueActivities[] and ifFalseActivities[]
    for branch_key in ("ifTrueActivities", "ifFalseActivities"):
        branch_acts = type_props.get(branch_key, [])
        if isinstance(branch_acts, list):
            for act in branch_acts:
                if isinstance(act, dict):
                    activities.append(act)

    # Until: typeProperties.activities[]
    until_acts = type_props.get("activities", [])
    if isinstance(until_acts, list) and until_acts != for_each_acts:
        for act in until_acts:
            if isinstance(act, dict):
                activities.append(act)

    # Switch: typeProps.cases[].activities[]
    cases = type_props.get("cases", [])
    if isinstance(cases, list):
        for case in cases:
            if isinstance(case, dict):
                case_acts = case.get("activities", [])
                if isinstance(case_acts, list):
                    for act in case_acts:
                        if isinstance(act, dict):
                            activities.append(act)

    return activities


def find_activity_references(expression: str) -> list[str]:
    """Find all activity() references in an ADF expression.

    Returns a list of referenced activity names.
    """
    return list({_m.group(1) for _m in _ACTIVITY_NAME_REF.finditer(expression)})


def find_activity_output_references(expression: str) -> list[str]:
    """Find activity output references (activity('X').output.*) — high-confidence data deps."""
    return list({_m.group(1) for _m in _ACTIVITY_OUTPUT_REF.finditer(expression)})


def find_dataset_references(expression: str) -> list[str]:
    """Find dataset() references in an ADF expression."""
    return list({_m.group(1) for _m in _DATASET_REF.finditer(expression)})


def find_parameter_references(expression: str) -> list[str]:
    """Find @pipeline().parameters.X references."""
    return list({_m.group(1) for _m in _PIPELINE_PARAM_REF.finditer(expression)})


def find_variable_references(expression: str) -> list[str]:
    """Find @variables('X') references."""
    return list({_m.group(1) for _m in _VARIABLE_REF.finditer(expression)})


class ExpressionAnalyzer:
    """Analyzes ADF metadata to discover expression-level references between assets.

    These references represent high-confidence DATA_REFERENCE dependencies that go
    beyond the structural CONTAINS/READS/WRITES edges built from ADF configuration.
    """

    def __init__(self):
        self._compiled_refs: dict[str, list[ExpressionReference]] = {}

    def analyze_activity(self, activity: ActivityMetadata, pipeline_name: str) -> list[ExpressionReference]:
        """Analyze a single activity's metadata for expression references.

        Scans type_properties, inputs, outputs, and linked_service fields for
        references to other activities, datasets, and parameters.
        """
        refs: list[ExpressionReference] = []
        activity_full_name = f"{pipeline_name}.{activity.name}"

        # Collect all string values from type_properties for scanning
        all_strings = _extract_string_values(activity.type_properties)
        if activity.linked_service:
            all_strings.append(activity.linked_service)
        for inp in activity.inputs:
            all_strings.append(inp)
        for out in activity.outputs:
            all_strings.append(out)

        combined_text = " ".join(all_strings)

        # 1. Activity output references — DATA_REFERENCE (HIGH confidence)
        for ref_name in find_activity_output_references(combined_text):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=activity_full_name,
                expression=f"activity('{ref_name}').output.*",
                reference_type="OUTPUT_REFERENCE",
                confidence=ConfidenceLevel.HIGH,
            ))

        # 2. Activity input references
        for ref_name in find_activity_references(combined_text):
            if ref_name != activity.name:  # skip self-references
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=activity_full_name,
                    expression=f"activity('{ref_name}')",
                    reference_type="ACTIVITY_REFERENCE",
                    confidence=ConfidenceLevel.HIGH,
                ))

        # 3. Dataset references
        for ref_name in find_dataset_references(combined_text):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=activity_full_name,
                expression=f"dataset('{ref_name}')",
                reference_type="DATASET_REFERENCE",
                confidence=ConfidenceLevel.HIGH,
            ))

        # 4. Parameter references (lower confidence — structural, not data)
        for ref_name in find_parameter_references(combined_text):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=activity_full_name,
                expression=f"@pipeline().parameters.{ref_name}",
                reference_type="PARAMETER_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        # 5. Variable references
        for ref_name in find_variable_references(combined_text):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=activity_full_name,
                expression=f"@variables('{ref_name}')",
                reference_type="VARIABLE_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        return refs

    def analyze_dataset(self, dataset) -> list[ExpressionReference]:
        """Analyze dataset parameters for expression references.

        Scans parameter default values for activity(), dataset(), pipeline().parameters
        references that may create hidden dependencies.
        """
        refs: list[ExpressionReference] = []
        param_strs = _extract_string_values(dataset.parameters)
        combined = " ".join(param_strs)

        for ref_name in find_activity_output_references(combined):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=dataset.name,
                expression=f"activity('{ref_name}').output.*",
                reference_type="OUTPUT_REFERENCE",
                confidence=ConfidenceLevel.HIGH,
            ))

        for ref_name in find_dataset_references(combined):
            if ref_name != dataset.name:
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=dataset.name,
                    expression=f"dataset('{ref_name}')",
                    reference_type="DATASET_REFERENCE",
                    confidence=ConfidenceLevel.HIGH,
                ))

        for ref_name in find_parameter_references(combined):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=dataset.name,
                expression=f"@pipeline().parameters.{ref_name}",
                reference_type="PARAMETER_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        for ref_name in find_variable_references(combined):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=dataset.name,
                expression=f"@variables('{ref_name}')",
                reference_type="VARIABLE_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        return refs

    def analyze_pipeline_parameters(self, pipeline) -> list[ExpressionReference]:
        """Analyze pipeline-level parameters and variables for expression references.

        Scans parameter default values and variable initial values for references
        to activities, datasets, and other pipelines that may create hidden dependencies.
        """
        refs: list[ExpressionReference] = []
        pipe_full_name = pipeline.name

        # Scan parameter default values
        param_strs = _extract_string_values(pipeline.parameters)
        combined_params = " ".join(param_strs)

        for ref_name in find_activity_output_references(combined_params):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=pipe_full_name,
                expression=f"activity('{ref_name}').output.*",
                reference_type="OUTPUT_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        for ref_name in find_dataset_references(combined_params):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=pipe_full_name,
                expression=f"dataset('{ref_name}')",
                reference_type="DATASET_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        # Scan variable default values
        var_strs = _extract_string_values(pipeline.variables)
        combined_vars = " ".join(var_strs)

        for ref_name in find_activity_output_references(combined_vars):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=pipe_full_name,
                expression=f"activity('{ref_name}').output.*",
                reference_type="OUTPUT_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        for ref_name in find_dataset_references(combined_vars):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=pipe_full_name,
                expression=f"dataset('{ref_name}')",
                reference_type="DATASET_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        for ref_name in find_variable_references(combined_vars):
            refs.append(ExpressionReference(
                source_name=ref_name,
                target_name=pipe_full_name,
                expression=f"@variables('{ref_name}')",
                reference_type="VARIABLE_REFERENCE",
                confidence=ConfidenceLevel.MEDIUM,
            ))

        return refs

    def analyze_foreach_condition(self, activity, pipeline_name: str) -> list[ExpressionReference]:
        """Analyze ForEach/IfCondition/Until/Switch inner activities for expression references.

        Recursively scans nested activity type_properties for expression references
        and returns them with the parent pipeline context.
        """
        refs: list[ExpressionReference] = []
        type_props = activity.type_properties or {}

        # Extract the expression that drives the ForEach/IfCondition
        items_expr = ""
        if "items" in type_props:
            items_val = type_props["items"]
            if isinstance(items_val, dict):
                items_expr = items_val.get("value", "")
            elif isinstance(items_val, str):
                items_expr = items_val

        condition_expr = ""
        if "expression" in type_props:
            expr_val = type_props["expression"]
            if isinstance(expr_val, dict):
                condition_expr = expr_val.get("value", "")
            elif isinstance(expr_val, str):
                condition_expr = expr_val

        parent_full_name = f"{pipeline_name}.{activity.name}"

        # Scan ForEach items expression for activity references
        if items_expr:
            for ref_name in find_activity_output_references(items_expr):
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=parent_full_name,
                    expression=f"activity('{ref_name}').output.* (ForEach items)",
                    reference_type="OUTPUT_REFERENCE",
                    confidence=ConfidenceLevel.HIGH,
                ))
            for ref_name in find_dataset_references(items_expr):
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=parent_full_name,
                    expression=f"dataset('{ref_name}') (ForEach items)",
                    reference_type="DATASET_REFERENCE",
                    confidence=ConfidenceLevel.HIGH,
                ))

        # Scan IfCondition expression for activity references
        if condition_expr:
            for ref_name in find_activity_output_references(condition_expr):
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=parent_full_name,
                    expression=f"activity('{ref_name}').output.* (IfCondition expression)",
                    reference_type="OUTPUT_REFERENCE",
                    confidence=ConfidenceLevel.HIGH,
                ))

        # Recursively scan inner activities
        inner_activities = _extract_inner_activities(type_props)
        for inner_act_dict in inner_activities:
            inner_name = inner_act_dict.get("name", "unknown")
            inner_type = inner_act_dict.get("type", "Unknown")
            inner_type_props = inner_act_dict.get("typeProperties", {})

            inner_strs = _extract_string_values(inner_type_props)
            combined_inner = " ".join(inner_strs)

            for ref_name in find_activity_output_references(combined_inner):
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=f"{pipeline_name}.{inner_name}",
                    expression=f"activity('{ref_name}').output.*",
                    reference_type="OUTPUT_REFERENCE",
                    confidence=ConfidenceLevel.HIGH,
                ))

            for ref_name in find_dataset_references(combined_inner):
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=f"{pipeline_name}.{inner_name}",
                    expression=f"dataset('{ref_name}')",
                    reference_type="DATASET_REFERENCE",
                    confidence=ConfidenceLevel.HIGH,
                ))

            for ref_name in find_parameter_references(combined_inner):
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=f"{pipeline_name}.{inner_name}",
                    expression=f"@pipeline().parameters.{ref_name}",
                    reference_type="PARAMETER_REFERENCE",
                    confidence=ConfidenceLevel.MEDIUM,
                ))

            for ref_name in find_variable_references(combined_inner):
                refs.append(ExpressionReference(
                    source_name=ref_name,
                    target_name=f"{pipeline_name}.{inner_name}",
                    expression=f"@variables('{ref_name}')",
                    reference_type="VARIABLE_REFERENCE",
                    confidence=ConfidenceLevel.MEDIUM,
                ))

        return refs

    def analyze_factory(self, factory_meta: FactoryMetadata) -> list[ExpressionReference]:
        """Scan the entire factory metadata for expression-level references.

        Iterates all pipelines, their activities, datasets, and pipeline-level
        parameters/variables, collecting every expression reference found.
        """
        all_refs: list[ExpressionReference] = []

        for pipeline in factory_meta.pipelines:
            # Scan each activity in the pipeline
            for activity in pipeline.activities:
                activity_refs = self.analyze_activity(activity, pipeline.name)
                all_refs.extend(activity_refs)

                # Scan ForEach / IfCondition / Until / Switch inner activities
                activity_type = activity.type.lower() if activity.type else ""
                if activity_type in ("foreach", "ifcondition", "until", "switch"):
                    inner_refs = self.analyze_foreach_condition(activity, pipeline.name)
                    all_refs.extend(inner_refs)

            # Scan pipeline-level parameters and variables for expression references
            pipe_param_refs = self.analyze_pipeline_parameters(pipeline)
            all_refs.extend(pipe_param_refs)

        # Scan dataset parameters for expression references
        for dataset in factory_meta.datasets:
            ds_refs = self.analyze_dataset(dataset)
            all_refs.extend(ds_refs)

        # Deduplicate by (source, target, reference_type) tuple
        seen: set[tuple[str, str, str]] = set()
        unique_refs: list[ExpressionReference] = []
        for ref in all_refs:
            key = (ref.source_name, ref.target_name, ref.reference_type)
            if key not in seen:
                seen.add(key)
                unique_refs.append(ref)

        self._compiled_refs = {}
        for ref in unique_refs:
            self._compiled_refs.setdefault(ref.target_name, []).append(ref)

        return unique_refs

    def get_references_to(self, asset_name: str) -> list[ExpressionReference]:
        """Get all expression references that point TO a given asset (as source).

        Returns references where other assets reference this asset in their expressions.
        Only works after analyze_factory() has been called.
        """
        refs: list[ExpressionReference] = []
        for target, ref_list in self._compiled_refs.items():
            for ref in ref_list:
                if ref.source_name == asset_name:
                    refs.append(ref)
        return refs

    def get_references_from(self, asset_name: str) -> list[ExpressionReference]:
        """Get all expression references FROM a given asset (as target).

        Returns references that this asset makes to other assets.
        Only works after analyze_factory() has been called.
        """
        return self._compiled_refs.get(asset_name, [])
