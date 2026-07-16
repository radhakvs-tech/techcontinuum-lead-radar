Build TechContinuum Lead Radar
Act as a principal software engineer, AI-agent architect and B2B market-intelligence specialist.
For this session, implement Phase 1 only (Section 20). Stop after make lint, make typecheck, and make test all pass and make demo produces sample output using the mock provider. Do not start Phase 2
Build a production-quality MVP called TechContinuum Lead Radar. It should discover, research, qualify and rank companies that are likely to need external advisory for moving AI-enabled SaaS products from experimentation to dependable production.
The system must be explainable, evidence-driven, credit-conscious and safe to operate.
Do not build a mass-emailing system. Do not send emails. Do not scrape personal LinkedIn profiles.
________________________________________
1. Business context
TechContinuum is a two-person senior advisory company with expertise across:
•	AWS and cloud-native architecture
•	Platform engineering
•	Kubernetes and infrastructure as code
•	CI/CD and developer experience
•	Cloud cost optimisation
•	Legacy-to-cloud modernisation
•	AI production readiness
•	AI-native product and platform architecture
The initial commercial positioning is:
TechContinuum helps established SaaS companies evolve from AI-assisted features to reliable, governed and economically viable agentic products—without cloud costs, platform complexity or legacy constraints spiralling out of control.
The strongest initial vertical is martech SaaS, but the agent must also support adjacent and non-martech SaaS categories.
________________________________________
2. Primary objectives
The agent must:
1.	Discover companies matching the target ICP.
2.	Collect recent public evidence about product, hiring, technology and business changes.
3.	Detect likely AI-production, cloud-cost and modernisation pain.
4.	Determine whether the company is likely to benefit from a small senior external advisory firm.
5.	Rank companies using deterministic, explainable scoring.
6.	Generate evidence-backed account dossiers.
7.	Minimise Vibe Prospecting credit consumption.
8.	Support human review and feedback.
9.	Persist all evidence, scores and review decisions.
10.	Never classify a company as high intent based only on generic AI marketing language.
The initial target is quality rather than volume:
•	20–40 genuinely qualified accounts per week
•	3–10 high-priority accounts
•	No more than two recommended contacts per approved account
•	No contact enrichment before human approval
________________________________________
3. Target ICP
Geography
Only include companies headquartered in:
•	United States
•	United Kingdom
•	Germany
•	Australia
•	Singapore
The system should make geography configurable.
Company size
Initial employee range:
minimum_employees: 30
maximum_employees: 200
Commercial size
Target:
minimum_revenue_usd: 10_000_000
maximum_revenue_usd: 300_000_000
ARR is preferred but often unavailable.
Store revenue and ARR separately:
reported_revenue
estimated_revenue_min
estimated_revenue_max
estimated_arr
arr_estimation_method
arr_confidence
Do not pretend that estimated revenue equals ARR.
Do not reject an otherwise strong company merely because ARR is unavailable. Mark the commercial-size confidence accurately.
Included company types
Prioritise:
•	B2B SaaS
•	Martech SaaS
•	Product analytics
•	Customer engagement
•	Marketing automation
•	Customer-data platforms
•	Conversational marketing
•	Research and customer-intelligence platforms
•	Enterprise software
•	Software-enabled product companies
•	Technology-led marketing companies
•	Agency–technology hybrids that are productising reusable AI capabilities
Exclusions
Reject or heavily penalise:
•	Recruitment and staffing firms
•	Training companies
•	Generic marketing agencies with no meaningful product or engineering function
•	Pure outsourced-development agencies
•	Thin AI wrappers with no proprietary workflow, data or integrations
•	Very early companies without an internal team capable of implementing recommendations
•	Companies primarily selling consulting services unless they are creating reusable software or AI platforms
________________________________________
4. Core pain tracks
Every qualified account must be scored independently across these pain tracks.
A. AI production readiness
Detect companies moving from:
AI experiment
→ AI feature
→ customer-facing AI
→ action-taking agent
→ production-scale agentic platform
Relevant signals include:
•	Customer-facing AI feature announcement
•	AI assistant, copilot or agent launch
•	AI feature moving from beta to general availability
•	Agent that performs actions rather than only generating text
•	AI/ML engineering hiring
•	MLOps, LLMOps or AI-platform hiring
•	Evaluation, guardrail or observability roles
•	AI security or governance activity
•	New AI leadership
•	Model-provider or AI-platform partnership
•	AI capabilities being added across multiple products
•	Product documentation referencing autonomous workflows
•	AI usage being opened to enterprise customers
•	AI feature tied to sensitive or tenant-specific data
B. Cloud and AI economics
Relevant signals include:
•	Explicit cloud-cost or margin concern
•	FinOps or cloud-cost hiring
•	Infrastructure efficiency mentioned in job descriptions
•	Rapid engineering or customer growth
•	Kubernetes or multi-region architecture
•	High-volume data processing
•	Real-time inference
•	Audio, video or document processing
•	Customer-facing AI with usage-dependent costs
•	GPU, token or inference-cost references
•	Pricing changes likely caused by compute economics
•	Expansion to additional regions
•	Migration between cloud providers
•	Heavy platform or SRE hiring after growth
•	Public engineering posts about reducing infrastructure cost
The system must distinguish between:
Uses AWS
and:
Has credible evidence of meaningful cloud-cost pressure
Merely using AWS must not qualify a company.
C. Legacy-to-cloud or AI-native modernisation
Interpret “legacy” broadly for SaaS companies.
Signals include:
•	Cloud migration
•	Application modernisation
•	Monolith decomposition
•	Replatforming or refactoring
•	Data-centre exit
•	Migration from virtual machines to containers
•	Older runtime or framework modernisation
•	Manual deployment processes
•	Shared or tightly coupled databases
•	Platform consolidation after acquisition
•	On-premises product moving to SaaS
•	New APIs or integration layer
•	Modernisation of data platforms
•	Product AI ambitions constrained by data or integration architecture
•	Simultaneous hiring for platform, data and AI roles
D. Martech agentisation pressure
This should be a separate configurable dimension.
Signals include:
•	Existing marketing or customer-engagement platform
•	AI assistant added to an established workflow
•	Movement from recommendations to autonomous actions
•	Customer-data or CRM access
•	Agent acting across external systems
•	AI campaign optimisation
•	AI lead qualification
•	AI customer-journey orchestration
•	AI content plus campaign execution
•	Shift from seat-based workflows to automated outcomes
•	Competitors releasing agents
•	Hyperscaler or major platform partnership
•	AI roadshows, regional events or market-education initiatives
•	Expansion into new geographies
•	Product and engineering hiring inside an agency or martech company
•	Public emphasis on AI-led operational efficiency
E. External-advisor likelihood
The company may have pain but still be a poor prospect for TechContinuum.
Positive signals:
•	50–200 employees
•	Existing engineering team capable of execution
•	AI and platform hiring occurring simultaneously
•	Relevant senior technical role vacant
•	New CTO, VP Engineering or Head of AI
•	Recently funded
•	Product deadline or public launch commitment
•	No visibly mature AI-platform, FinOps or architecture function
•	Complex transition crossing product, platform and cloud boundaries
•	Company is large enough to pay but small enough to engage a specialist firm
•	Internal team appears execution-oriented but may lack cross-domain production experience
Negative signals:
•	Large internal consulting or architecture function
•	Major hyperscaler already acting as the implementation partner
•	Very large procurement barriers
•	No internal engineering capacity
•	No evidence of budget or urgency
•	Purely experimental internal AI usage
•	AI capability unrelated to the company’s core product
________________________________________
5. Evidence hierarchy
Every material claim must be stored with:
source_url
source_title
source_type
published_date
observed_date
evidence_text
evidence_summary
signal_type
confidence
independence_group
Classify evidence as:
OBSERVED_FACT
REASONABLE_INFERENCE
GENERAL_INDUSTRY_CONSIDERATION
UNKNOWN_REQUIRING_VALIDATION
Preferred sources
Use:
•	Company website
•	Product pages
•	Product documentation
•	Changelog and release notes
•	Careers pages
•	Public job descriptions
•	Engineering blog
•	Public GitHub organisation or repositories
•	Trust centre and security documentation
•	Press releases
•	Funding announcements
•	Public conference talks
•	Company-authored social posts
•	Vibe Prospecting business and event data
•	Permitted technology-intelligence sources
LinkedIn restrictions
Do not automate scraping of personal LinkedIn profiles.
Do not store or publish:
•	Personal profile photographs
•	Personal biographies
•	Detailed career histories
•	Personal contact details gathered through scraping
•	Large lists of individual employee skills
Company-authored LinkedIn posts may be used only through a permitted provider or manually supplied URL.
Employee-level information should only be collected after an account passes human approval, and only to identify up to two relevant decision-makers.
Evidence quality rules
A company cannot be labelled high intent unless:
•	It has at least two independent intent signals.
•	At least one material signal occurred within the previous 90 days.
•	At least one signal directly indicates a product, engineering or business commitment.
•	The conclusion is not based only on marketing phrases such as “AI-powered.”
•	Evidence dates and URLs are available for the main conclusion.
________________________________________
6. Vibe Prospecting integration
Vibe Prospecting is available via the vpai CLI. Read its live tool schemas before first use of each tool — do not assume parameters. Create a provider interface so the application is not tightly coupled to Vibe:
class CompanyDataProvider(Protocol):
    def estimate_query_cost(...)
    def company_statistics(...)
    def search_companies(...)
    def enrich_company(...)
    def get_company_events(...)
    def find_contacts(...)
    def enrich_contact_email(...)
Implement:
1.	VibeProvider when a real interface is available.
2.	CsvProvider for exported Vibe files.
3.	MockProvider for tests and development.
Credit controls
Implement configuration such as:
credit_budget:
  maximum_per_run: 100
  maximum_per_week: 400
  require_cost_estimate: true
  retrieve_contacts_only_after_approval: true
  retrieve_email_only_after_approval: true
  retrieve_phone_numbers: false
User has 4 to 6 authentic email accounts that can be used to avail free-credit limits, so the agent must be able to take all these email accounts. Prioritize using the free credit limits.
Before every Vibe operation:
1.	When free credit limits of all accounts are exhausted, estimate cost where supported.
2.	Record expected cost.
3.	Set the default configured budget as 0, Refuse to proceed when the configured budget would be exceeded. When the free limits and the budget are exhausted, prompt and alert the user and ask how to proceed further. Provide an estimated cost per week.
4.	Display a clear dry-run summary.
5.	Require an explicit CLI flag for costly exports.
Account-first workflow
The workflow must be:
Query statistics
→ fetch businesses
→ apply hard gates
→ low-cost signal enrichment
→ score accounts
→ public-source verification for promising accounts
→ human approval
→ identify up to two contacts
→ optional email enrichment
Never fetch hundreds of people before qualifying their companies.
________________________________________
7. Public web research provider
Create a provider abstraction:
class WebResearchProvider(Protocol):
    def search(...)
    def fetch_page(...)
    def extract_public_evidence(...)
Support at least:
•	ManualUrlProvider
•	MockWebProvider
Optionally support one configurable external search API, but do not make the system unusable without it.
Do not use uncontrolled crawling.
Respect:
•	robots restrictions where applicable
•	rate limits
•	source terms
•	page-fetch timeouts
•	maximum pages per domain
•	content-size limits
Maintain a per-domain fetch cache.
The agent should search only accounts that have passed the preliminary score threshold.
Suggested source sequence:
company homepage
→ AI/product pages
→ changelog
→ careers page
→ current job descriptions
→ engineering blog
→ trust/security page
→ press releases
→ public GitHub presence
________________________________________
8. Deterministic scoring system
Do not let an LLM directly invent the final lead score.
LLMs may:
•	classify evidence
•	summarise evidence
•	identify probable pain
•	draft explanations
•	suggest missing validation questions
The final score must be computed by deterministic Python rules.
Score structure
Use the following initial 100-point model:
ICP and commercial fit                   20
AI/product-transition pressure           20
Cloud, platform and modernisation pain    20
Martech agentisation pressure             10
External-advisor likelihood               15
Evidence quality and recency               15
                                         ---
                                         100
For non-martech companies, reallocate the martech component proportionally across the other intent dimensions or set it to a configurable sector-transition score.
Suggested signal weights
Use configuration, not hard-coded values.
Examples:
signals:
  customer_facing_ai_launch:
    weight: 12
    half_life_days: 120

  ai_beta_to_ga:
    weight: 8
    half_life_days: 90

  multiple_ai_roles:
    weight: 8
    half_life_days: 60

  platform_or_sre_hiring:
    weight: 7
    half_life_days: 60

  simultaneous_ai_and_platform_hiring:
    weight: 10
    half_life_days: 75

  action_taking_agent:
    weight: 12
    half_life_days: 120

  explicit_cloud_cost_signal:
    weight: 10
    half_life_days: 90

  finops_hiring:
    weight: 8
    half_life_days: 60

  explicit_modernisation_program:
    weight: 10
    half_life_days: 120

  funding_round:
    weight: 5
    half_life_days: 180

  new_technical_leader:
    weight: 5
    half_life_days: 120

  ecosystem_expansion_event:
    weight: 5
    half_life_days: 90

  generic_ai_marketing_only:
    weight: -10
    half_life_days: 60

  engineering_headcount_decline:
    weight: -12
    half_life_days: 90
Recency decay
Use:
effective_weight = base_weight * confidence * (
    0.5 ** (age_days / half_life_days)
)
Handle signals with unknown dates conservatively.
Classification
classification:
  high_intent: 80
  high_priority_review: 65
  watchlist: 45
Suggested labels:
HIGH_INTENT
HIGH_PRIORITY_REVIEW
GOOD_FIT_LOW_SIGNAL
WATCHLIST
IGNORE_WRONG_ICP
IGNORE_WEAK_SIGNAL
INSUFFICIENT_INFORMATION
A company must not receive HIGH_INTENT unless the minimum evidence requirements are met, regardless of the raw numeric score.
Explainability
Every score must have a breakdown showing:
•	Signal
•	Source
•	Original weight
•	Recency-adjusted weight
•	Confidence
•	Positive or negative contribution
•	Reason for inclusion
•	Any scoring cap applied
________________________________________
9. Recommended offer matching
For every account scoring 65 or higher, select the most relevant TechContinuum offer.
Offer A: Agentic Product Readiness for Martech SaaS
Use when the company is:
•	an established martech or customer-engagement platform
•	adding AI assistants or agents
•	allowing AI to act on customer data
•	moving from deterministic workflows to autonomous actions
Offer B: AI Production Readiness Sprint
Use when the company:
•	has launched customer-facing AI
•	is moving from prototype or beta to production
•	is hiring AI and platform roles
•	has reliability, evaluation, governance or deployment complexity
Offer C: Cloud and AI Unit Economics Sprint
Use when:
•	cloud or AI spend is likely material
•	the workload is data- or inference-intensive
•	the company has scale, margin or cost pressure
•	architecture is likely driving costs
Offer D: AI-Native Modernisation Blueprint
Use when:
•	legacy architecture constrains AI plans
•	the company is modernising a monolith or data platform
•	AI capability depends on APIs, event architecture or data-access changes
•	migration decisions are complex and high-risk
The agent must explain why the selected offer fits the evidence.
________________________________________
10. Human-review workflow
No company should move directly from automated discovery to contact enrichment.
Implement statuses:
DISCOVERED
PRELIMINARY_QUALIFIED
RESEARCHED
SCORED
PENDING_HUMAN_REVIEW
APPROVED_FOR_CONTACT_DISCOVERY
REJECTED
WATCHLIST
CONTACTED
POSITIVE_REPLY
NEGATIVE_REPLY
MEETING_BOOKED
Support reviewer labels:
HIGH_PRIORITY
GOOD_FIT_LOW_SIGNAL
WRONG_ICP
WEAK_SIGNAL
INSUFFICIENT_INFORMATION
DUPLICATE
NOT_SUITABLE_FOR_SMALL_ADVISORY
Capture a free-text reviewer reason.
Persist:
•	reviewer
•	timestamp
•	old status
•	new status
•	reason
•	scoring version
________________________________________
11. Contact discovery
Contact discovery is outside the initial automated pipeline and must require account approval.
For each approved company, identify no more than two people:
Strategic buyer
Prefer:
•	CTO
•	Technical co-founder
•	CIO
•	VP Engineering
•	Chief Product and Technology Officer
Technical champion
Prefer:
•	Head of Platform
•	Head of Infrastructure
•	Head of SRE
•	Head of DevOps
•	Director of Engineering
•	Head of AI
•	Head of ML Platform
•	Head of Data Platform
Store:
name
exact_title
role_category
public_profile_url
reason_selected
role_change_date
email
email_verification_status
email_retrieved_at
Do not retrieve phone numbers.
Do not retrieve email addresses until a separate human approval step.
________________________________________
12. Data model
Use Python 3.12.
Preferred libraries:
•	Pydantic v2
•	SQLModel or SQLAlchemy
•	SQLite for MVP
•	Alembic if SQLAlchemy migrations are needed
•	Typer for CLI
•	Rich for terminal output
•	Jinja2 for reports
•	pytest
•	ruff
•	mypy
•	httpx
•	tenacity
•	PyYAML
Core entities:
Account
AccountAlias
CompanyMetric
Evidence
Signal
ScoreRun
ScoreContribution
HumanReview
Contact
ProviderUsage
ResearchRun
OfferRecommendation
Important account fields:
id
company_name
domain
headquarters_country
employee_count
revenue_min_usd
revenue_max_usd
estimated_arr_usd
arr_confidence
industry
business_model
company_type
technologies
created_at
updated_at
Deduplicate primarily by canonical domain.
________________________________________
13. Repository structure
Create a clean repository similar to:
techcontinuum-lead-radar/
├── README.md
├── pyproject.toml
├── .env.example
├── Makefile
├── config/
│   ├── icp.yaml
│   ├── scoring.yaml
│   ├── signal_taxonomy.yaml
│   ├── title_taxonomy.yaml
│   ├── exclusions.yaml
│   └── providers.yaml
├── src/lead_radar/
│   ├── __init__.py
│   ├── cli.py
│   ├── settings.py
│   ├── db.py
│   ├── models/
│   ├── providers/
│   │   ├── base.py
│   │   ├── vibe.py
│   │   ├── csv_provider.py
│   │   ├── web.py
│   │   └── mock.py
│   ├── discovery/
│   ├── research/
│   ├── evidence/
│   ├── scoring/
│   ├── contacts/
│   ├── review/
│   ├── reporting/
│   └── llm/
├── prompts/
│   ├── evidence_classifier.md
│   ├── pain_classifier.md
│   ├── account_summary.md
│   └── validation_questions.md
├── templates/
│   ├── account_dossier.md.j2
│   ├── run_summary.md.j2
│   └── outside_in_snapshot.md.j2
├── tests/
│   ├── fixtures/
│   ├── test_hard_gates.py
│   ├── test_scoring.py
│   ├── test_recency.py
│   ├── test_credit_limits.py
│   ├── test_deduplication.py
│   ├── test_evidence_requirements.py
│   └── test_contact_guardrails.py
├── data/
│   ├── imports/
│   └── exports/
└── scripts/
    └── seed_demo_data.py
________________________________________
14. CLI requirements
Implement commands such as:
lead-radar init-db

lead-radar estimate \
  --country US \
  --employees-min 30 \
  --employees-max 200

lead-radar discover \
  --countries US,GB,AU,SG \
  --dry-run

lead-radar import-vibe-csv data/imports/vibe-companies.csv

lead-radar enrich --account-id 123

lead-radar research --account-id 123

lead-radar score --account-id 123

lead-radar run \
  --countries US,GB,AU,SG \
  --maximum-credits 100 \
  --dry-run

lead-radar review list

lead-radar review approve 123 \
  --reason "Customer-facing AI launch plus simultaneous platform hiring"

lead-radar contacts discover --account-id 123

lead-radar export \
  --minimum-score 65 \
  --format csv

lead-radar dossier --account-id 123

lead-radar feedback import data/imports/review-feedback.csv
All costly commands should support --dry-run.
________________________________________
15. Outputs
Generate:
qualified_accounts.csv
Columns:
company
domain
country
employee_count
revenue_range
arr_confidence
industry
primary_pain_track
recommended_offer
icp_score
ai_transition_score
cloud_modernisation_score
sector_pressure_score
advisor_fit_score
evidence_score
total_score
classification
top_signal_1
top_signal_2
top_signal_3
signal_dates
evidence_urls
unknowns
review_status
scoring_version
review_queue.csv
Include accounts requiring human decision.
evidence.jsonl
Store machine-readable evidence with source metadata.
account_dossiers/<domain>.md
Each dossier should include:
Company
Why this account surfaced
Why now
Observed public evidence
AI-product transition
Cloud/platform complexity
Modernisation indicators
External-advisor fit
Strongest pain hypothesis
What remains unknown
Recommended TechContinuum offer
Suggested validation questions
Potential strategic buyer
Potential technical champion
Score breakdown
Sources
run_summary.md
Include:
•	Accounts discovered
•	Accounts rejected by hard gates
•	Accounts researched
•	Accounts by classification
•	Estimated and actual Vibe credits used
•	Data-provider errors
•	Top recurring signals
•	Top pain tracks
•	Research gaps
________________________________________
16. Optional outside-in snapshot generator
After the core lead agent works, add an optional command:
lead-radar snapshot --account-id 123
The snapshot must clearly separate:
•	Publicly observed
•	Reasonably inferred
•	Unknown
•	General production-readiness considerations
Do not state that the company lacks a control merely because no public evidence was found.
Use phrases such as:
Public evidence did not establish whether a formal evaluation framework is in place.
Do not use:
The company has no evaluation framework.
The generated snapshot must contain a disclaimer that it is based only on public information and is not an internal audit.
Do not include synthetic internal data in a named company report.
________________________________________
17. LLM integration
Anthropic API (Claude) as the only implemented provider for MVP, Create an abstraction supporting configurable providers for the future after MVP
The application must work in a deterministic reduced-function mode without an LLM.
The LLM may:
•	classify text into the signal taxonomy
•	summarise evidence
•	detect probable pain tracks
•	generate internal-validation questions
•	draft account dossiers
•	suggest offer matching
The LLM must return structured JSON validated with Pydantic.
Prompts must instruct the LLM:
•	Do not invent missing facts.
•	Do not infer absence from lack of public disclosure.
•	Cite the evidence IDs supporting each conclusion.
•	Return INSUFFICIENT_INFORMATION when evidence is weak.
•	Separate observations from inferences.
•	Avoid defamatory or accusatory wording.
•	Do not produce the final numeric score.
Persist:
•	model name
•	prompt version
•	input evidence IDs
•	raw response
•	parsed output
•	timestamp
________________________________________
18. Tests and acceptance criteria
Write comprehensive tests.
At minimum, verify:
1.	A company outside the geography is rejected.
2.	A company outside the employee band is rejected or flagged.
3.	Missing ARR does not automatically reject the company.
4.	Generic “AI-powered” language alone cannot produce high intent.
5.	Simultaneous AI and platform hiring increases the score materially.
6.	Old signals decay.
7.	Two signals from the same copied press release do not count as independent.
8.	High intent requires a recent direct signal.
9.	Vibe budget limits cannot be bypassed accidentally.
10.	Contact discovery cannot run before approval.
11.	Email enrichment cannot run before a second approval.
12.	Phone enrichment is disabled.
13.	Every major score contribution references evidence.
14.	Duplicate domains merge safely.
15.	Missing dates reduce confidence.
16.	An LLM failure does not corrupt the run.
17.	Provider retries do not duplicate records.
18.	A report distinguishes fact, inference and unknown.
19.	Negative wording is not generated from missing public evidence.
20.	The CLI produces a useful dry-run report.
MVP acceptance criteria
The MVP is complete when it can:
1.	Import a Vibe CSV or use the real Vibe connector.
2.	Apply the ICP hard gates.
3.	Enrich candidate companies with structured public evidence.
4.	Score accounts deterministically.
5.	Produce a ranked CSV.
6.	Produce an evidence-backed dossier.
7.	Track Vibe credit usage.
8.	Support human review.
9.	Prevent premature contact enrichment.
10.	Run successfully using synthetic fixtures.
________________________________________
19. Demo fixtures
Create synthetic test companies covering:
1.	Martech SaaS launching an action-taking AI agent and hiring platform engineers.
2.	General B2B SaaS using generic AI language with no real commitment.
3.	Voice AI company with real-time production and cost pressure.
4.	Company modernising a monolith to support AI.
5.	Large company that has high AI pressure but poor fit for a two-person adviser.
6.	Small company with strong intent but no internal implementation capacity.
7.	Company with stale signals only.
8.	Company with conflicting employee and revenue information.
Do not use real company names in test fixtures.
________________________________________
20. Implementation sequence
Work in this order:
Phase 1
•	Repository scaffold
•	Configuration
•	Database
•	Core models
•	Mock provider
•	CSV import
•	Hard gates
•	Deterministic scoring
•	Tests
•	CLI
•	Sample outputs
Phase 2
•	Inspect and implement the available Vibe interface
•	Cost estimation
•	Credit tracking
•	Company-event enrichment
•	Retry and caching behaviour
Phase 3
•	Public web research abstraction
•	Source collection
•	Evidence extraction
•	LLM-assisted classification
•	Dossier generation
Phase 4
•	Human-review workflow
•	Approved contact discovery
•	Optional email enrichment
•	Feedback import
Phase 5
•	Optional outside-in snapshot generator
•	Scheduling documentation
•	PostgreSQL migration guidance
•	Optional lightweight review dashboard
Do not begin Phase 2 until Phase 1 works with tests and synthetic fixtures.
________________________________________
21. Documentation
Create a README that includes:
•	Business purpose
•	Architecture diagram
•	Setup instructions
•	Environment variables
•	Vibe integration options
•	CSV import format
•	CLI examples
•	Scoring explanation
•	Evidence standards
•	Credit-control model
•	Privacy and compliance guardrails
•	Human-review process
•	How to add new signals
•	How to change ICP criteria
•	How to add a new data provider
•	How to run tests
•	Known limitations
Also create:
docs/architecture.md
docs/scoring-model.md
docs/evidence-policy.md
docs/vibe-credit-strategy.md
docs/human-review.md
docs/future-roadmap.md
________________________________________
22. Engineering quality requirements
Use:
•	Strict type checking
•	Small cohesive modules
•	Dependency injection for providers
•	Structured logging
•	Clear exception hierarchy
•	Timeouts and retries
•	Database transactions
•	Idempotent imports
•	Deterministic tests
•	No hidden global state
•	No credentials committed to Git
•	Safe .env.example
•	Reproducible development commands
Add:
make setup
make lint
make typecheck
make test
make demo
Do not over-engineer a distributed architecture. This is initially a single-user, CLI-first application.
SQLite is sufficient for the MVP.
________________________________________
23. Important constraints
•	Do not send emails.
•	Do not build sequences.
•	Do not scrape LinkedIn personal profiles.
•	Do not obtain phone numbers.
•	Do not bypass Vibe credit restrictions.
•	Do not invent private-company ARR.
•	Do not claim internal deficiencies from public-source absence.
•	Do not let the LLM determine the final score.
•	Do not fetch contacts before account approval.
•	Do not make the system dependent on one paid web-search provider.
•	Do not expose provider credentials in logs.
•	Do not silently discard conflicting data.
•	Do not describe an account as high intent without evidence.
________________________________________
24. First response and execution behaviour
Begin by:
1.	Restating the intended MVP in no more than ten lines.
2.	Inspecting the current repository and available tools.
3.	Identifying whether a usable Vibe interface is already present.
4.	Listing concrete assumptions.
5.	Presenting the implementation plan.
6.	Immediately implementing Phase 1.
Do not stop after producing an architecture proposal.
Create the files, tests and working CLI.
Where a real Vibe integration cannot yet be implemented because credentials or exact documentation are unavailable, create the provider interface and CSV/mock implementation, clearly document the missing integration information, and complete the rest of the MVP.
At the end, run:
make lint
make typecheck
make test
make demo
Fix failures before presenting the result.
The final response should include:
•	What was implemented
•	Repository structure
•	Commands to run it
•	Test results
•	Example output locations
•	Vibe integration status
•	Known limitations
•	Recommended next engineering step
