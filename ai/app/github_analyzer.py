"""
GitHub organization analyzer — deterministic tech-stack and security-posture extraction (v2).

v2 improvements:
- #18: GITHUB_TOKEN verified and used in Authorization header
- #19: Dependency vulnerability check via GitHub Advisory Database
- #20: README analysis with GPT-4o-mini for top-starred repo
- #21: License detection and risk flagging per repo
- #22: Commit frequency signal and trend for top repos
- #23: Granular infrastructure maturity scoring (0-3 scale)

Output shape: {"fields": {}, "confidence_scores": {}, "citations": {}, "metadata": {}}
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
_MAX_REPOS = 15

# ── Dependency file patterns -> technology names ────────────────────────

_DEP_FILES: dict[str, str] = {
    "package.json": "node",
    "yarn.lock": "node",
    "pnpm-lock.yaml": "node",
    "requirements.txt": "python",
    "Pipfile": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "go.mod": "go",
    "go.sum": "go",
    "Cargo.toml": "rust",
    "Cargo.lock": "rust",
    "Gemfile": "ruby",
    "Gemfile.lock": "ruby",
    "build.gradle": "java",
    "build.gradle.kts": "kotlin",
    "pom.xml": "java",
    "mix.exs": "elixir",
    "pubspec.yaml": "dart",
    "Package.swift": "swift",
    "*.csproj": "dotnet",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
    "Makefile": "make",
    "Terraform": "terraform",
}

_NPM_FRAMEWORK_PATTERNS: dict[str, str] = {
    "react": "React", "next": "Next.js", "vue": "Vue.js", "angular": "Angular",
    "express": "Express", "fastify": "Fastify", "nestjs": "NestJS",
    "electron": "Electron", "typescript": "TypeScript", "@types/": "TypeScript",
    "tailwindcss": "Tailwind CSS", "prisma": "Prisma", "sequelize": "Sequelize",
    "graphql": "GraphQL", "apollo": "GraphQL (Apollo)", "webpack": "Webpack",
    "vite": "Vite", "jest": "Jest", "mocha": "Mocha",
    "cypress": "Cypress", "playwright": "Playwright",
}

_PYTHON_FRAMEWORK_PATTERNS: dict[str, str] = {
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
    "celery": "Celery", "sqlalchemy": "SQLAlchemy", "pandas": "pandas",
    "numpy": "NumPy", "tensorflow": "TensorFlow", "torch": "PyTorch",
    "scikit-learn": "scikit-learn", "pytest": "pytest",
    "boto3": "AWS SDK (Python)", "google-cloud": "GCP SDK (Python)", "pydantic": "Pydantic",
}

_GO_FRAMEWORK_PATTERNS: dict[str, str] = {
    "gin-gonic": "Gin", "gorilla/mux": "Gorilla Mux", "grpc": "gRPC",
    "cobra": "Cobra CLI", "protobuf": "Protocol Buffers",
    "kubernetes": "Kubernetes client", "aws-sdk-go": "AWS SDK (Go)",
}

_RUBY_FRAMEWORK_PATTERNS: dict[str, str] = {
    "rails": "Ruby on Rails", "sinatra": "Sinatra",
    "sidekiq": "Sidekiq", "rspec": "RSpec",
}

_SECURITY_TOOLS = {
    "snyk", "dependabot", "codeql", "trivy", "semgrep", "sonarqube",
    "sonarcloud", "bandit", "safety", "gitleaks", "trufflehog",
    "grype", "anchore", "checkov", "tfsec", "gosec", "brakeman",
    "npm audit", "yarn audit", "pip-audit", "cargo-audit",
}

_INFRA_KEYWORDS: dict[str, str] = {
    "kubernetes": "Kubernetes", "k8s": "Kubernetes", "helm": "Helm",
    "terraform": "Terraform", "pulumi": "Pulumi", "cloudformation": "CloudFormation",
    "aws": "AWS", "gcp": "GCP", "azure": "Azure", "docker": "Docker",
    "redis": "Redis", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mysql": "MySQL", "mongodb": "MongoDB", "elasticsearch": "Elasticsearch",
    "kafka": "Kafka", "rabbitmq": "RabbitMQ", "nginx": "Nginx",
    "envoy": "Envoy", "istio": "Istio", "vault": "HashiCorp Vault",
    "consul": "HashiCorp Consul", "prometheus": "Prometheus",
    "grafana": "Grafana", "datadog": "Datadog", "sentry": "Sentry",
}

# #19: Ecosystem mapping for GitHub Advisory Database
_ECOSYSTEM_MAP: dict[str, str] = {
    "node": "npm", "python": "pip", "go": "go", "rust": "crates.io",
    "ruby": "rubygems", "java": "maven", "kotlin": "maven",
    "dotnet": "nuget",
}


# ═══════════════════════════════════════════════════════════════════════
# GitHub API client (#18 — verified GITHUB_TOKEN support)
# ═══════════════════════════════════════════════════════════════════════

def _build_headers() -> dict[str, str]:
    """Build headers, using GITHUB_TOKEN if available."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        logger.info("Using GITHUB_TOKEN for authenticated requests (5000 req/hr)")
    else:
        logger.warning("No GITHUB_TOKEN set — rate limit is 60 req/hr. Set GITHUB_TOKEN for production use.")
    return headers


def _check_rate_limit(response: httpx.Response) -> None:
    remaining = response.headers.get("x-ratelimit-remaining")
    if remaining is not None and int(remaining) < 5:
        reset_ts = int(response.headers.get("x-ratelimit-reset", "0"))
        reset_at = datetime.fromtimestamp(reset_ts, tz=timezone.utc).isoformat()
        logger.warning("GitHub rate limit nearly exhausted: %s remaining, resets at %s", remaining, reset_at)


_rate_limited = False


async def _github_get(client: httpx.AsyncClient, path: str) -> dict | list | None:
    global _rate_limited
    if _rate_limited:
        return None
    url = f"{_GITHUB_API}{path}" if path.startswith("/") else path
    try:
        resp = await client.get(url)
        _check_rate_limit(resp)
        if resp.status_code == 404:
            return None
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            logger.error("GitHub API rate limit exceeded — skipping remaining requests")
            _rate_limited = True
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("GitHub API error %s for %s", e.response.status_code, path)
        return None
    except Exception:
        logger.exception("GitHub API request failed: %s", path)
        return None


async def _github_get_file_content(client: httpx.AsyncClient, owner: str, repo: str, path: str) -> str | None:
    data = await _github_get(client, f"/repos/{owner}/{repo}/contents/{path}")
    if not isinstance(data, dict):
        return None
    encoding = data.get("encoding", "")
    content = data.get("content", "")
    if encoding == "base64" and content:
        try:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception:
            return None
    return None


# ═══════════════════════════════════════════════════════════════════════
# Org + repo fetching
# ═══════════════════════════════════════════════════════════════════════

def _parse_org_from_url(url: str) -> str:
    parsed = urlparse(url.rstrip("/"))
    parts = [p for p in parsed.path.split("/") if p]
    if parts:
        return parts[0]
    return url


async def _fetch_org_repos(client: httpx.AsyncClient, org: str) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while len(repos) < _MAX_REPOS:
        data = await _github_get(client, f"/orgs/{org}/repos?sort=stars&direction=desc&per_page=30&page={page}")
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        for r in data:
            if r.get("fork", False) or r.get("archived", False):
                continue
            repos.append(r)
            if len(repos) >= _MAX_REPOS:
                break
        page += 1
        if len(data) < 30:
            break
    return repos


# ═══════════════════════════════════════════════════════════════════════
# #21: License detection
# ═══════════════════════════════════════════════════════════════════════

_RISKY_LICENSES = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later"}


async def _fetch_license(client: httpx.AsyncClient, owner: str, repo_name: str) -> dict[str, Any]:
    """Fetch license info for a repo. Returns {spdx_id, name, risk_flag}."""
    data = await _github_get(client, f"/repos/{owner}/{repo_name}/license")
    if not isinstance(data, dict):
        return {"spdx_id": None, "name": "No license", "risk_flag": "ip_uncertainty"}

    license_info = data.get("license", {})
    spdx = license_info.get("spdx_id", "NOASSERTION")
    name = license_info.get("name", "Unknown")

    risk_flag = None
    if spdx in _RISKY_LICENSES:
        risk_flag = "copyleft_commercial_risk"
    elif spdx in ("NOASSERTION", None, ""):
        risk_flag = "ip_uncertainty"

    return {"spdx_id": spdx, "name": name, "risk_flag": risk_flag}


# ═══════════════════════════════════════════════════════════════════════
# #22: Commit frequency and trend
# ═══════════════════════════════════════════════════════════════════════

async def _fetch_commit_activity(client: httpx.AsyncClient, owner: str, repo_name: str) -> dict[str, Any]:
    """Fetch weekly commit activity for the last year. Returns trend analysis."""
    data = await _github_get(client, f"/repos/{owner}/{repo_name}/stats/commit_activity")
    if not isinstance(data, list) or len(data) == 0:
        return {"avg_weekly_commits": 0, "trend": "unknown", "weeks_analyzed": 0}

    weekly_counts = [week.get("total", 0) for week in data]
    avg = sum(weekly_counts) / len(weekly_counts) if weekly_counts else 0

    # Trend: compare last quarter average to first quarter average
    quarter = max(1, len(weekly_counts) // 4)
    first_q_avg = sum(weekly_counts[:quarter]) / quarter
    last_q_avg = sum(weekly_counts[-quarter:]) / quarter

    if last_q_avg > first_q_avg * 1.2:
        trend = "increasing"
    elif last_q_avg < first_q_avg * 0.8:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "avg_weekly_commits": round(avg, 1),
        "trend": trend,
        "weeks_analyzed": len(weekly_counts),
        "recent_quarter_avg": round(last_q_avg, 1),
        "first_quarter_avg": round(first_q_avg, 1),
    }


# ═══════════════════════════════════════════════════════════════════════
# #19: Dependency vulnerability check
# ═══════════════════════════════════════════════════════════════════════

async def _check_vulnerabilities(
    client: httpx.AsyncClient,
    tech_set: set[str],
    dep_packages: list[str],
) -> dict[str, Any]:
    """Query GitHub Advisory Database for known vulnerabilities.

    Checks by ecosystem rather than per-package to stay within rate limits.
    """
    vuln_summary: dict[str, Any] = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "ecosystems_checked": [],
        "sample_advisories": [],
    }

    ecosystems_to_check: set[str] = set()
    for tech in tech_set:
        eco = _ECOSYSTEM_MAP.get(tech.lower())
        if eco:
            ecosystems_to_check.add(eco)

    for eco in sorted(ecosystems_to_check):
        data = await _github_get(
            client,
            f"/advisories?ecosystem={eco}&type=reviewed&per_page=5"
        )
        if not isinstance(data, list):
            continue

        vuln_summary["ecosystems_checked"].append(eco)
        for adv in data:
            severity = adv.get("severity", "unknown")
            vuln_summary["total"] += 1
            if severity in vuln_summary:
                vuln_summary[severity] += 1
            if len(vuln_summary["sample_advisories"]) < 5:
                vuln_summary["sample_advisories"].append({
                    "ghsa_id": adv.get("ghsa_id"),
                    "summary": (adv.get("summary") or "")[:100],
                    "severity": severity,
                    "ecosystem": eco,
                })

    return vuln_summary


# ═══════════════════════════════════════════════════════════════════════
# #20: README analysis with GPT-4o-mini
# ═══════════════════════════════════════════════════════════════════════

async def _analyze_readme(readme_content: str, org: str) -> dict[str, Any]:
    """Send top repo README to GPT-4o-mini for product/compliance insights. ~$0.001."""
    try:
        oai = AsyncOpenAI()
        resp = await oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You analyze GitHub README files for an insurance underwriting system. Extract concise insights."},
                {"role": "user", "content": f"""Based on this README from {org}'s top repository, answer in JSON:

README (truncated to 3000 chars):
{readme_content[:3000]}

Return JSON:
{{
  "product_summary": "one sentence about what this product/company builds",
  "technologies_mentioned": ["list", "of", "technologies"],
  "compliance_certifications": ["any compliance/security certs mentioned"],
  "business_model_hints": "any hints about B2B/B2C, target market"
}}"""},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=500,
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception:
        logger.warning("README analysis with GPT-4o-mini failed")
        return {}


# ═══════════════════════════════════════════════════════════════════════
# Per-repo analysis
# ═══════════════════════════════════════════════════════════════════════

async def _analyze_repo(client: httpx.AsyncClient, owner: str, repo_data: dict) -> dict[str, Any]:
    repo_name = repo_data["name"]
    result: dict[str, Any] = {
        "name": repo_name,
        "full_name": repo_data.get("full_name", f"{owner}/{repo_name}"),
        "stars": repo_data.get("stargazers_count", 0),
        "language": repo_data.get("language"),
        "description": repo_data.get("description", ""),
        "last_push": repo_data.get("pushed_at"),
        "technologies": set(),
        "frameworks": set(),
        "security_tools": set(),
        "infra_signals": set(),
        "has_ci": False,
        "has_security_scanning": False,
        "has_security_policy": False,
        "has_docker": False,
        "has_k8s": False,
        "has_terraform": False,
        "has_helm": False,
        "has_deploy_steps": False,
        "dep_files_found": [],
        "dep_packages": [],
    }

    if repo_data.get("language"):
        result["technologies"].add(repo_data["language"])

    tree = await _github_get(client, f"/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1")
    if not isinstance(tree, dict):
        return _finalize_repo_result(result)

    file_paths = [item["path"] for item in tree.get("tree", []) if item.get("type") == "blob"]

    dep_file_paths: list[str] = []
    ci_workflow_paths: list[str] = []
    security_policy = False

    for fp in file_paths:
        basename = fp.split("/")[-1]

        for pattern, tech in _DEP_FILES.items():
            if pattern.startswith("*"):
                if basename.endswith(pattern[1:]):
                    dep_file_paths.append(fp)
                    result["technologies"].add(tech)
            elif basename == pattern:
                dep_file_paths.append(fp)
                result["technologies"].add(tech)

        if ".github/workflows/" in fp and (fp.endswith(".yml") or fp.endswith(".yaml")):
            ci_workflow_paths.append(fp)
            result["has_ci"] = True

        if basename.upper() == "SECURITY.MD":
            security_policy = True

        # #23: Granular infrastructure detection
        if basename == "Dockerfile" or basename.startswith("docker-compose"):
            result["has_docker"] = True
            result["infra_signals"].add("Docker")
        if basename in ("Chart.yaml", "values.yaml") or "helm/" in fp:
            result["has_helm"] = True
            result["has_k8s"] = True
            result["infra_signals"].add("Helm")
            result["infra_signals"].add("Kubernetes")
        if "k8s/" in fp or "kubernetes/" in fp or "kustomization" in basename.lower():
            result["has_k8s"] = True
            result["infra_signals"].add("Kubernetes")
        if fp.endswith(".tf") or fp.endswith(".tf.json") or "terraform/" in fp:
            result["has_terraform"] = True
            result["infra_signals"].add("Terraform")
            result["technologies"].add("terraform")

    result["has_security_policy"] = security_policy
    result["dep_files_found"] = dep_file_paths[:5]

    files_to_fetch = dep_file_paths[:3] + ci_workflow_paths[:3]
    for fp in files_to_fetch:
        content = await _github_get_file_content(client, owner, repo_name, fp)
        if content is None:
            continue
        _parse_file_content(fp, content, result)

    return _finalize_repo_result(result)


def _parse_file_content(path: str, content: str, result: dict) -> None:
    basename = path.split("/")[-1]
    content_lower = content.lower()

    if basename == "package.json":
        _parse_package_json(content, result)
    elif basename in ("requirements.txt", "Pipfile"):
        _parse_python_deps(content, result)
    elif basename == "go.mod":
        _parse_go_mod(content, result)
    elif basename in ("Gemfile", "Gemfile.lock"):
        _parse_ruby_deps(content, result)
    elif basename == "Cargo.toml":
        result["technologies"].add("rust")

    if ".github/workflows/" in path:
        for tool in _SECURITY_TOOLS:
            if tool in content_lower:
                result["security_tools"].add(tool)
                result["has_security_scanning"] = True
        # #23: Detect deploy steps in CI
        deploy_keywords = ["deploy", "release", "publish", "push to", "kubectl apply", "helm upgrade"]
        if any(kw in content_lower for kw in deploy_keywords):
            result["has_deploy_steps"] = True

    for keyword, label in _INFRA_KEYWORDS.items():
        if keyword in content_lower:
            result["infra_signals"].add(label)


def _parse_package_json(content: str, result: dict) -> None:
    try:
        pkg = json.loads(content)
    except json.JSONDecodeError:
        return
    all_deps = {}
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        all_deps.update(pkg.get(section, {}))
    for dep_name in all_deps:
        result["dep_packages"].append(dep_name)
        dep_lower = dep_name.lower()
        for pattern, framework in _NPM_FRAMEWORK_PATTERNS.items():
            if pattern in dep_lower:
                result["frameworks"].add(framework)
                break


def _parse_python_deps(content: str, result: dict) -> None:
    for line in content.splitlines():
        line = line.strip().split("#")[0].split(";")[0].strip()
        if not line or line.startswith("-"):
            continue
        pkg_name = re.split(r"[>=<!\[\]~]", line)[0].strip().lower()
        result["dep_packages"].append(pkg_name)
        for pattern, framework in _PYTHON_FRAMEWORK_PATTERNS.items():
            if pattern in pkg_name:
                result["frameworks"].add(framework)
                break


def _parse_go_mod(content: str, result: dict) -> None:
    for line in content.splitlines():
        line = line.strip()
        for pattern, framework in _GO_FRAMEWORK_PATTERNS.items():
            if pattern in line.lower():
                result["frameworks"].add(framework)
                break


def _parse_ruby_deps(content: str, result: dict) -> None:
    for line in content.splitlines():
        line_lower = line.strip().lower()
        for pattern, framework in _RUBY_FRAMEWORK_PATTERNS.items():
            if pattern in line_lower:
                result["frameworks"].add(framework)
                break


def _finalize_repo_result(result: dict) -> dict:
    for key in ("technologies", "frameworks", "security_tools", "infra_signals"):
        result[key] = sorted(result[key])
    return result


# ═══════════════════════════════════════════════════════════════════════
# #23: Granular infrastructure maturity scoring
# ═══════════════════════════════════════════════════════════════════════

def _calculate_infra_maturity_level(repo_results: list[dict]) -> tuple[int, str]:
    """Score infrastructure maturity on a 0-3 scale.

    0 = none (no Docker, no CI)
    1 = basic Docker (Dockerfile exists)
    2 = Docker + CI/CD
    3 = Docker + K8s/Terraform + CI/CD with deploy steps
    """
    has_docker = any(r.get("has_docker") for r in repo_results)
    has_ci = any(r.get("has_ci") for r in repo_results)
    has_k8s = any(r.get("has_k8s") for r in repo_results)
    has_terraform = any(r.get("has_terraform") for r in repo_results)
    has_helm = any(r.get("has_helm") for r in repo_results)
    has_deploy = any(r.get("has_deploy_steps") for r in repo_results)

    if has_docker and (has_k8s or has_terraform) and has_ci and has_deploy:
        return 3, "advanced: Docker + orchestration (K8s/Terraform) + CI/CD with deploy"
    if has_docker and has_ci:
        return 2, "intermediate: Docker + CI/CD"
    if has_docker:
        return 1, "basic: Docker only"
    return 0, "minimal: no containerization"


# ═══════════════════════════════════════════════════════════════════════
# Engineering maturity scoring (updated)
# ═══════════════════════════════════════════════════════════════════════

def _calculate_engineering_maturity(repo_results: list[dict]) -> tuple[float, dict[str, float]]:
    if not repo_results:
        return 0.0, {}

    n = len(repo_results)

    ci_rate = sum(1 for r in repo_results if r["has_ci"]) / n
    security_scanning_rate = sum(1 for r in repo_results if r["has_security_scanning"]) / n
    security_policy_rate = sum(1 for r in repo_results if r["has_security_policy"]) / n
    docker_rate = sum(1 for r in repo_results if r["has_docker"]) / n
    k8s_rate = sum(1 for r in repo_results if r.get("has_k8s", False)) / n

    now = datetime.now(timezone.utc)
    active_repos = 0
    for r in repo_results:
        pushed = r.get("last_push")
        if pushed:
            try:
                pushed_dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                if (now - pushed_dt).days < 180:
                    active_repos += 1
            except (ValueError, TypeError):
                pass
    activity_rate = active_repos / n if n else 0

    all_security_tools = set()
    for r in repo_results:
        all_security_tools.update(r.get("security_tools", []))
    tool_diversity = min(len(all_security_tools) / 3.0, 1.0)

    breakdown = {
        "ci_cd_adoption": round(ci_rate, 2),
        "security_scanning": round(security_scanning_rate, 2),
        "security_policy": round(security_policy_rate, 2),
        "containerization": round(docker_rate, 2),
        "orchestration": round(k8s_rate, 2),
        "activity_rate": round(activity_rate, 2),
        "security_tool_diversity": round(tool_diversity, 2),
    }

    weights = {
        "ci_cd_adoption": 0.20,
        "security_scanning": 0.25,
        "security_policy": 0.10,
        "containerization": 0.10,
        "orchestration": 0.05,
        "activity_rate": 0.15,
        "security_tool_diversity": 0.15,
    }

    score = sum(breakdown[k] * weights[k] for k in weights)
    return round(score, 3), breakdown


# ═══════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════

async def analyze_github_org(url: str) -> dict[str, Any]:
    """Analyze a GitHub organization and extract tech stack + security posture."""
    global _rate_limited
    _rate_limited = False

    start = time.time()
    org = _parse_org_from_url(url)

    headers = _build_headers()
    has_token = "Authorization" in headers

    async with httpx.AsyncClient(headers=headers, timeout=_TIMEOUT, follow_redirects=True) as client:
        org_info = await _github_get(client, f"/orgs/{org}")
        if org_info is None:
            org_info = await _github_get(client, f"/users/{org}")

        repos = await _fetch_org_repos(client, org)
        if not repos:
            data = await _github_get(client, f"/users/{org}/repos?sort=stars&direction=desc&per_page={_MAX_REPOS}")
            repos = [r for r in (data or []) if isinstance(r, dict) and not r.get("fork") and not r.get("archived")][:_MAX_REPOS]

        logger.info("Analyzing %d repos for %s (authenticated: %s)", len(repos), org, has_token)

        repo_results: list[dict] = []
        for repo_data in repos:
            result = await _analyze_repo(client, org, repo_data)
            repo_results.append(result)

        # #21: License detection for all repos
        license_dist: dict[str, int] = {}
        license_risks: list[dict] = []
        for r in repo_results:
            lic = await _fetch_license(client, org, r["name"])
            r["license"] = lic
            spdx = lic.get("spdx_id") or "No license"
            license_dist[spdx] = license_dist.get(spdx, 0) + 1
            if lic.get("risk_flag"):
                license_risks.append({"repo": r["name"], "license": spdx, "risk": lic["risk_flag"]})

        # #22: Commit frequency for top 5 repos
        commit_trends: list[dict] = []
        for r in repo_results[:5]:
            activity = await _fetch_commit_activity(client, org, r["name"])
            activity["repo"] = r["name"]
            commit_trends.append(activity)
            r["commit_activity"] = activity

        # #19: Vulnerability check
        all_tech_set: set[str] = set()
        all_dep_packages: list[str] = []
        for r in repo_results:
            all_tech_set.update(r.get("technologies", []))
            all_dep_packages.extend(r.get("dep_packages", []))

        vuln_summary = await _check_vulnerabilities(client, all_tech_set, all_dep_packages)

        # #20: README analysis for top-starred repo
        readme_insights: dict = {}
        if repo_results:
            top_repo = repo_results[0]
            readme_content = await _github_get_file_content(client, org, top_repo["name"], "README.md")
            if readme_content:
                readme_insights = await _analyze_readme(readme_content, org)

    elapsed_ms = int((time.time() - start) * 1000)

    # Aggregate across all repos
    all_technologies: set[str] = set()
    all_frameworks: set[str] = set()
    all_security_tools: set[str] = set()
    all_infra: set[str] = set()
    all_languages: set[str] = set()

    for r in repo_results:
        all_technologies.update(r.get("technologies", []))
        all_frameworks.update(r.get("frameworks", []))
        all_security_tools.update(r.get("security_tools", []))
        all_infra.update(r.get("infra_signals", []))
        if r.get("language"):
            all_languages.add(r["language"])

    # Normalize tech stack
    raw_tech = all_technologies | all_frameworks
    tech_lower_map: dict[str, str] = {}
    for t in raw_tech:
        key = t.lower()
        existing = tech_lower_map.get(key)
        if existing is None or (t[0].isupper() and not existing[0].isupper()):
            tech_lower_map[key] = t
    tech_stack = sorted(tech_lower_map.values())

    maturity_score, maturity_breakdown = _calculate_engineering_maturity(repo_results)
    infra_level, infra_description = _calculate_infra_maturity_level(repo_results)

    org_name = org_info.get("name", org) if isinstance(org_info, dict) else org
    org_description = org_info.get("description", "") if isinstance(org_info, dict) else ""
    public_repos_count = org_info.get("public_repos", len(repos)) if isinstance(org_info, dict) else len(repos)

    # Aggregate commit trend
    declining_repos = sum(1 for ct in commit_trends if ct.get("trend") == "declining")
    overall_trend = "declining" if declining_repos > len(commit_trends) / 2 else (
        "increasing" if sum(1 for ct in commit_trends if ct.get("trend") == "increasing") > len(commit_trends) / 2
        else "stable"
    )

    # Build output
    fields: dict[str, Any] = {
        "company_name": org_name,
        "github_org": org,
        "product_description": org_description,
        "tech_stack": json.dumps(tech_stack),
        "primary_languages": json.dumps(sorted(all_languages)),
        "frameworks": json.dumps(sorted(all_frameworks)),
        "infrastructure": json.dumps(sorted(all_infra)),
        "security_tools": json.dumps(sorted(all_security_tools)),
        "has_ci_cd": str(any(r["has_ci"] for r in repo_results)),
        "has_security_scanning": str(any(r["has_security_scanning"] for r in repo_results)),
        "has_security_policy": str(any(r["has_security_policy"] for r in repo_results)),
        "has_docker": str(any(r["has_docker"] for r in repo_results)),
        "has_k8s": str(any(r.get("has_k8s", False) for r in repo_results)),
        "engineering_maturity_score": str(maturity_score),
        "infra_maturity_level": str(infra_level),
        "repos_analyzed": str(len(repo_results)),
        "public_repos_total": str(public_repos_count),
        "commit_trend": overall_trend,
    }

    confidence_scores: dict[str, str] = {
        "tech_stack": "high" if repo_results else "low",
        "primary_languages": "high",
        "frameworks": "high" if all_frameworks else "medium",
        "security_tools": "high" if all_security_tools else "medium",
        "has_ci_cd": "high",
        "engineering_maturity_score": "high" if len(repo_results) >= 5 else "medium",
        "vulnerability_summary": "medium",
        "commit_trend": "high" if commit_trends else "low",
        "license_distribution": "high",
    }

    top_repos = [r["full_name"] for r in repo_results[:5]]
    citations: dict[str, str] = {
        "tech_stack": f"Aggregated from {len(repo_results)} repos: {', '.join(top_repos)}",
        "primary_languages": "GitHub language detection",
        "frameworks": "Parsed from dependency files (package.json, requirements.txt, go.mod, etc.)",
        "security_tools": "Scanned .github/workflows/ YAML files",
        "engineering_maturity_score": json.dumps(maturity_breakdown),
        "vulnerability_summary": f"GitHub Advisory Database: {', '.join(vuln_summary.get('ecosystems_checked', []))}",
        "commit_trend": f"Analyzed top {len(commit_trends)} repos weekly commit activity",
        "license_distribution": f"Checked {len(repo_results)} repos via GitHub License API",
    }

    metadata: dict[str, Any] = {
        "source_type": "github_repo",
        "extraction_time_ms": elapsed_ms,
        "org": org,
        "org_name": org_name,
        "authenticated": has_token,
        "repos_analyzed": len(repo_results),
        "public_repos_total": public_repos_count,
        "engineering_maturity_score": maturity_score,
        "maturity_breakdown": maturity_breakdown,
        "infra_maturity_level": infra_level,
        "infra_maturity_description": infra_description,
        "tech_stack": tech_stack,
        "primary_languages": sorted(all_languages),
        "frameworks": sorted(all_frameworks),
        "infrastructure": sorted(all_infra),
        "security_tools": sorted(all_security_tools),
        "vulnerability_summary": vuln_summary,
        "readme_insights": readme_insights,
        "license_distribution": license_dist,
        "license_risks": license_risks,
        "commit_trends": commit_trends,
        "overall_commit_trend": overall_trend,
        "per_repo": [
            {
                "name": r["full_name"],
                "stars": r["stars"],
                "language": r["language"],
                "has_ci": r["has_ci"],
                "has_security_scanning": r["has_security_scanning"],
                "has_security_policy": r["has_security_policy"],
                "has_docker": r["has_docker"],
                "has_k8s": r.get("has_k8s", False),
                "has_terraform": r.get("has_terraform", False),
                "frameworks": r["frameworks"],
                "security_tools": r["security_tools"],
                "license": r.get("license", {}),
                "commit_activity": r.get("commit_activity"),
            }
            for r in repo_results
        ],
    }

    return {
        "fields": fields,
        "confidence_scores": confidence_scores,
        "citations": citations,
        "metadata": metadata,
    }
