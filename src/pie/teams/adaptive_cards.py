"""Adaptive Card builders and Teams webhook payloads for Microsoft Teams Bot integration."""

from typing import Any, Optional


class TeamsAdaptiveCardBuilder:
    """Generates strictly schema-compliant Adaptive Cards (Version 1.4) for Microsoft Teams."""

    @staticmethod
    def build_subscription_selection_card(subscriptions: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate interactive Adaptive Card for choosing Azure subscriptions."""
        choices = [
            {
                "title": f"{sub.get('subscription_name', 'Subscription')} ({sub.get('subscription_id', '')[:8]}...)",
                "value": sub.get("subscription_id", ""),
            }
            for sub in subscriptions
        ]

        return {
            "type": "AdaptiveCard",
            "version": "1.4",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "🔐 Select Azure Subscriptions for PIE Discovery",
                    "weight": "Bolder",
                    "size": "Medium",
                    "color": "Accent",
                },
                {
                    "type": "TextBlock",
                    "text": "Choose one or more subscriptions to discover Data Factory instances:",
                    "wrap": True,
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "selected_subscriptions",
                    "isMultiSelect": True,
                    "style": "expanded",
                    "choices": choices,
                },
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "🔍 Discover Data Factories",
                    "data": {"action": "select_subscriptions"},
                }
            ],
        }

    @staticmethod
    def build_factory_selection_card(factories: list[dict[str, Any]], subscription_id: str) -> dict[str, Any]:
        """Generate interactive Adaptive Card for choosing Data Factories to sync."""
        choices = [
            {
                "title": f"{f.get('factory_name', 'Factory')} [{f.get('resource_group', 'RG')}]",
                "value": f.get("factory_name", ""),
            }
            for f in factories
        ]

        return {
            "type": "AdaptiveCard",
            "version": "1.4",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "🏭 Select Data Factories to Sync & Cache",
                    "weight": "Bolder",
                    "size": "Medium",
                    "color": "Accent",
                },
                {
                    "type": "TextBlock",
                    "text": f"Discovered factories in Subscription `{subscription_id[:8]}...`. Select instances to ingest:",
                    "wrap": True,
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "selected_factories",
                    "isMultiSelect": True,
                    "style": "expanded",
                    "choices": choices,
                },
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "⚡ Start Scoped Sync",
                    "data": {"action": "sync_factories", "subscription_id": subscription_id},
                }
            ],
        }

    @staticmethod
    def build_deletion_risk_card(
        target_asset: str,
        risk_rating: str,
        risk_score: int,
        broken_readers: list[str],
        broken_writers: list[str],
        affected_pipelines: list[str],
        portal_url: Optional[str] = None,
        last_refreshed_at: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate rich interactive deletion blast-radius assessment card."""
        color = "Attention" if risk_score >= 70 else ("Warning" if risk_score >= 30 else "Good")
        url = portal_url or f"https://pie.company.local/lineage/{target_asset}"

        facts = [
            {"title": "Target Entity", "value": target_asset},
            {"title": "Risk Rating", "value": f"{risk_rating.upper()} ({risk_score}/100)"},
            {"title": "Direct Broken Readers", "value": str(len(broken_readers))},
            {"title": "Direct Broken Writers", "value": str(len(broken_writers))},
            {"title": "Impacted Pipelines", "value": f"{len(affected_pipelines)} active pipeline(s)"},
        ]
        if last_refreshed_at:
            facts.append({"title": "Metadata Snapshot", "value": last_refreshed_at})

        body: list[dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": "⚠️ PIE Asset Deletion Risk Assessment",
                "weight": "Bolder",
                "size": "Medium",
                "color": color,
            },
            {
                "type": "FactSet",
                "facts": facts,
            },
        ]

        if affected_pipelines:
            sample_pipes = ", ".join([f"`{p}`" for p in affected_pipelines[:4]])
            body.append(
                {
                    "type": "TextBlock",
                    "text": f"**Affected Pipelines:** {sample_pipes}",
                    "wrap": True,
                    "spacing": "Small",
                }
            )

        return {
            "type": "AdaptiveCard",
            "version": "1.4",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "body": body,
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "🌐 Open Visual Lineage in PIE Portal",
                    "url": url,
                }
            ],
        }

    @staticmethod
    def build_architecture_summary_card(
        pipeline_name: str,
        activity_count: int,
        saas_vendors: list[str],
        schedule: str,
        portal_url: Optional[str] = None,
        last_refreshed_at: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate architectural summary Adaptive Card for a pipeline."""
        url = portal_url or f"https://pie.company.local/pipelines/{pipeline_name}"
        saas_str = ", ".join(saas_vendors) if saas_vendors else "Internal Azure Stores"

        facts = [
            {"title": "Pipeline", "value": pipeline_name},
            {"title": "Activity Count", "value": f"{activity_count} activities"},
            {"title": "Integration Targets", "value": saas_str},
            {"title": "Recurrence Schedule", "value": schedule or "Manual / Event"},
        ]
        if last_refreshed_at:
            facts.append({"title": "Last Refreshed", "value": last_refreshed_at})

        return {
            "type": "AdaptiveCard",
            "version": "1.4",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"📋 PIE Architecture Overview: {pipeline_name}",
                    "weight": "Bolder",
                    "size": "Medium",
                    "color": "Accent",
                },
                {
                    "type": "FactSet",
                    "facts": facts,
                },
            ],
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "🔍 Deep Inspect in Portal",
                    "url": url,
                }
            ],
        }
