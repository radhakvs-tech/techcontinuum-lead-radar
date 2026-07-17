"""Synthetic demo companies covering the eight scenarios in spec §19.

No real company names are used. Dates are computed relative to import time
so the demo always exercises recency decay realistically instead of going
fully stale the day after it's written.
"""

from __future__ import annotations

from datetime import date, timedelta

from lead_radar.providers.base import CompanyEventRecord, ProviderCompanyRecord


def _d(days_ago: int) -> date:
    return date.today() - timedelta(days=days_ago)


DEMO_COMPANIES: list[tuple[ProviderCompanyRecord, list[CompanyEventRecord]]] = [
    # 1. Martech SaaS launching an action-taking AI agent + hiring platform engineers.
    (
        ProviderCompanyRecord(
            company_name="Brightloop Martech",
            domain="brightloop-martech.example",
            headquarters_country="US",
            employee_count=140,
            reported_revenue_usd=45_000_000,
            industry="Marketing automation",
            business_model="B2B SaaS",
            company_type="martech_saas",
            technologies=["AWS", "Kubernetes"],
        ),
        [
            CompanyEventRecord(
                account_domain="brightloop-martech.example",
                event_type="action_taking_agent",
                title="Brightloop launches autonomous campaign agent",
                description=(
                    "Brightloop announced an agent that can adjust live campaign "
                    "budgets and send follow-up sequences without human sign-off."
                ),
                event_date=_d(18),
                source_url="https://brightloop-martech.example/press/agent-launch",
            ),
            CompanyEventRecord(
                account_domain="brightloop-martech.example",
                event_type="customer_facing_ai_launch",
                title="Changelog: AI Campaign Copilot generally available",
                description="Campaign Copilot moved from beta to GA for all customers.",
                event_date=_d(25),
                source_url="https://brightloop-martech.example/changelog#copilot-ga",
            ),
            CompanyEventRecord(
                account_domain="brightloop-martech.example",
                event_type="platform_or_sre_hiring",
                title="Careers: Senior Platform Engineer, SRE",
                description="Open roles for platform and SRE engineers to scale the agent runtime.",
                event_date=_d(10),
                source_url="https://brightloop-martech.example/careers",
            ),
            CompanyEventRecord(
                account_domain="brightloop-martech.example",
                event_type="multiple_ai_roles",
                title="Careers: 3 open AI/ML engineering roles",
                description="Multiple AI engineering and MLOps roles posted simultaneously.",
                event_date=_d(10),
                source_url="https://brightloop-martech.example/careers",
            ),
            CompanyEventRecord(
                account_domain="brightloop-martech.example",
                event_type="martech_agent_added_to_workflow",
                title="Agent acts inside existing campaign workflow",
                description="The new agent operates inside the established campaign builder.",
                event_date=_d(18),
                source_url="https://brightloop-martech.example/press/agent-launch",
            ),
        ],
    ),
    # 2. General B2B SaaS using generic AI language with no real commitment.
    (
        ProviderCompanyRecord(
            company_name="CloudPilot Suite",
            domain="cloudpilot-suite.example",
            headquarters_country="US",
            employee_count=90,
            reported_revenue_usd=20_000_000,
            industry="Project management software",
            business_model="B2B SaaS",
            company_type="b2b_saas",
            technologies=["AWS"],
        ),
        [
            CompanyEventRecord(
                account_domain="cloudpilot-suite.example",
                event_type="generic_ai_marketing_only",
                title="Homepage banner: 'Now powered by AI'",
                description="Marketing homepage adds an 'AI-powered' badge with no product detail.",
                event_date=_d(15),
                source_url="https://cloudpilot-suite.example/",
            ),
        ],
    ),
    # 3. Voice AI company with real-time production and cost pressure.
    (
        ProviderCompanyRecord(
            company_name="VoxStream Audio",
            domain="voxstream-audio.example",
            headquarters_country="GB",
            employee_count=75,
            reported_revenue_usd=18_000_000,
            industry="Voice AI / real-time audio",
            business_model="B2B SaaS",
            company_type="b2b_saas",
            technologies=["AWS", "GPU inference"],
        ),
        [
            CompanyEventRecord(
                account_domain="voxstream-audio.example",
                event_type="customer_facing_ai_launch",
                title="Real-time voice agent launched for enterprise customers",
                description=(
                    "VoxStream shipped a real-time voice agent for enterprise support lines."
                ),
                event_date=_d(40),
                source_url="https://voxstream-audio.example/blog/voice-agent-launch",
            ),
            CompanyEventRecord(
                account_domain="voxstream-audio.example",
                event_type="explicit_cloud_cost_signal",
                title="Engineering blog: inference cost per minute is our top margin risk",
                description=(
                    "Public engineering post discusses GPU inference cost pressure at scale."
                ),
                event_date=_d(20),
                source_url="https://voxstream-audio.example/blog/inference-costs",
            ),
            CompanyEventRecord(
                account_domain="voxstream-audio.example",
                event_type="finops_hiring",
                title="Careers: FinOps / Cloud Cost Engineer",
                description="Open role focused on cloud cost optimisation for real-time inference.",
                event_date=_d(15),
                source_url="https://voxstream-audio.example/careers",
            ),
        ],
    ),
    # 4. Company modernising a monolith to support AI.
    (
        ProviderCompanyRecord(
            company_name="MonolithShift Data",
            domain="monolithshift-data.example",
            headquarters_country="DE",
            employee_count=160,
            reported_revenue_usd=60_000_000,
            industry="Enterprise data software",
            business_model="B2B SaaS",
            company_type="enterprise_software",
            technologies=["AWS", "on-prem VMs"],
        ),
        [
            CompanyEventRecord(
                account_domain="monolithshift-data.example",
                event_type="explicit_modernisation_program",
                title="Public roadmap: monolith decomposition programme",
                description=(
                    "Company announced a multi-quarter programme to decompose its core monolith."
                ),
                event_date=_d(30),
                source_url="https://monolithshift-data.example/blog/modernisation-roadmap",
            ),
            CompanyEventRecord(
                account_domain="monolithshift-data.example",
                event_type="platform_or_sre_hiring",
                title="Careers: Platform Engineering team build-out",
                description="Multiple platform engineering roles to support the new architecture.",
                event_date=_d(25),
                source_url="https://monolithshift-data.example/careers",
            ),
            CompanyEventRecord(
                account_domain="monolithshift-data.example",
                event_type="ai_beta_to_ga",
                title="AI insights module moves to general availability",
                description=(
                    "AI insights feature, blocked for a year by data architecture, reaches GA."
                ),
                event_date=_d(45),
                source_url="https://monolithshift-data.example/changelog#ai-insights-ga",
            ),
        ],
    ),
    # 5. Large company: high AI pressure but poor fit for a two-person adviser.
    (
        ProviderCompanyRecord(
            company_name="GlobalScale Systems",
            domain="globalscale-systems.example",
            headquarters_country="US",
            employee_count=5200,
            reported_revenue_usd=900_000_000,
            industry="Enterprise software",
            business_model="B2B SaaS",
            company_type="enterprise_software",
            technologies=["AWS", "Azure", "Kubernetes"],
        ),
        [
            CompanyEventRecord(
                account_domain="globalscale-systems.example",
                event_type="action_taking_agent",
                title="GlobalScale launches enterprise agent platform",
                description="Large-scale agent platform launched across the product suite.",
                event_date=_d(20),
                source_url="https://globalscale-systems.example/press/agent-platform",
            ),
            CompanyEventRecord(
                account_domain="globalscale-systems.example",
                event_type="customer_facing_ai_launch",
                title="AI copilot rolled out to all enterprise tiers",
                description="Copilot feature generally available to all enterprise customers.",
                event_date=_d(22),
                source_url="https://globalscale-systems.example/changelog#copilot",
            ),
        ],
    ),
    # 6. Small company with strong intent but no internal implementation capacity.
    (
        ProviderCompanyRecord(
            company_name="TinyAgent Labs",
            domain="tinyagent-labs.example",
            headquarters_country="SG",
            employee_count=15,
            reported_revenue_usd=3_000_000,
            industry="AI agents",
            business_model="B2B SaaS",
            company_type="b2b_saas",
            technologies=["AWS"],
        ),
        [
            CompanyEventRecord(
                account_domain="tinyagent-labs.example",
                event_type="action_taking_agent",
                title="TinyAgent launches autonomous ops agent",
                description=(
                    "Small team ships an ambitious autonomous agent with no dedicated platform "
                    "team."
                ),
                event_date=_d(12),
                source_url="https://tinyagent-labs.example/press/agent-launch",
            ),
            CompanyEventRecord(
                account_domain="tinyagent-labs.example",
                event_type="customer_facing_ai_launch",
                title="Public beta of the agent opens to all users",
                description="Public beta announcement for the autonomous ops agent.",
                event_date=_d(14),
                source_url="https://tinyagent-labs.example/blog/public-beta",
            ),
        ],
    ),
    # 7. Company with stale signals only.
    (
        ProviderCompanyRecord(
            company_name="StaleForge Analytics",
            domain="staleforge-analytics.example",
            headquarters_country="AU",
            employee_count=110,
            reported_revenue_usd=35_000_000,
            industry="Product analytics",
            business_model="B2B SaaS",
            company_type="product_analytics",
            technologies=["AWS"],
        ),
        [
            CompanyEventRecord(
                account_domain="staleforge-analytics.example",
                event_type="customer_facing_ai_launch",
                title="AI insights feature launched (over a year ago)",
                description="Customer-facing AI insights feature launched; no updates since.",
                event_date=_d(400),
                source_url="https://staleforge-analytics.example/changelog#ai-insights",
            ),
            CompanyEventRecord(
                account_domain="staleforge-analytics.example",
                event_type="platform_or_sre_hiring",
                title="Careers: Platform Engineer (posted over a year ago)",
                description="Old platform engineering job posting, no longer active.",
                event_date=_d(380),
                source_url="https://staleforge-analytics.example/careers-archive",
            ),
        ],
    ),
    # 8. Company with conflicting employee and revenue information.
    (
        ProviderCompanyRecord(
            company_name="DriftData Conflict",
            domain="driftdata-conflict.example",
            headquarters_country="US",
            employee_count=190,
            reported_revenue_usd=500_000_000,  # conflicts with estimated range below
            industry="Customer data platform",
            business_model="B2B SaaS",
            company_type="customer_data_platform",
            technologies=["AWS"],
            raw={"estimated_revenue_min_usd": 15_000_000, "estimated_revenue_max_usd": 40_000_000},
        ),
        [
            CompanyEventRecord(
                account_domain="driftdata-conflict.example",
                event_type="multiple_ai_roles",
                title="Careers: multiple AI engineering roles",
                description="Several AI engineering roles posted for the customer data platform.",
                event_date=_d(30),
                source_url="https://driftdata-conflict.example/careers",
            ),
            CompanyEventRecord(
                account_domain="driftdata-conflict.example",
                event_type="funding_round",
                title="Series C funding announced",
                description="Company announced a new funding round.",
                event_date=_d(60),
                source_url="https://driftdata-conflict.example/press/series-c",
            ),
        ],
    ),
]
