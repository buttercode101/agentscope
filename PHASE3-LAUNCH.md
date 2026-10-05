# Phase 3 preview brief

## Release boundary
Developer preview. Local generator is the product core. The current Vercel project has a Git-provider linkage failure (`incorrect_git_source_info`), so hosted deployment provenance remains unverified until that external integration is repaired.

## Positioning
Your agents worked all night. AgentScope gives you one read-only screen for what ran, what broke, what needs attention, and what is unknown.

## ICP
Solo builders/operators with scheduled AI jobs or small agent crews who are too small for a full observability stack and currently inspect logs manually.

## Activation
Generate dashboard from real local sources -> one actionable anomaly or truthful UNKNOWN state appears.

## North star
Operator scans that surface a supported actionable issue or correctly preserve UNKNOWN when evidence is missing.

## Monetization
Free local/single-user first. Validate repeat daily/weekly scanning before hosted history, alerts, teams or multi-project plans.

## Experiments
1. 5-minute local install with agent operators. Success: time-to-first-useful-insight <5 min for 3/5 users. 21 days.
2. Missing-source demo: prove UNKNOWN rather than green. Success: users correctly understand state without explanation. 14 days.
3. Compare against trace-heavy tools for the morning-supervision job. Success: repeat use after 7 days.

## Launch copy
**One line:** One read-only screen for what your AI agent crew ran, broke, and still cannot prove.

## Evidence log
Do not claim hosted monitoring until deployment/source provenance is reconciled. Users/revenue: 0 verified here.

## Deployment blocker evidence

Vercel can read the existing project but rejects a fresh Git deployment for `buttercode101/agentscope` with `incorrect_git_source_info`. The previous failed deployment also exposed a stale output-directory configuration; the project output directory has been corrected to `site`, but the provider-link failure still prevents a provenance-backed current deployment. Do not describe the hosted surface as current until a deployment records the repository SHA.
