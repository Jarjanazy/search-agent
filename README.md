
docker build -t research-agent .


docker run --env-file .env \
  -v "C:\Users\celil\work\search-agent\search-topics\syrian-exports-topic.txt:/app/topic.txt" \
  -v "C:\Users\celil\work\search-agent\search-topics\syria-exports-angles.txt:/app/angles.txt" \
  -v "C:\Users\celil\work\search-agent\runs:/app/runs" \
  research-agent



To deploy on Hetzner:
  1. Create GitHub repo, push: git remote add origin <url> && git push -u origin master
  2. Copy repo to server, fill .env, run docker build -t research-agent .
  3. Add to crontab:
  CRON_TZ=Europe/Amsterdam
  0 14 * * * docker run --rm --env-file /path/to/.env research-agent:latest >> /var/log/research-agent.log 2>&1



## Workflow

Two input files drive each run:

  - Topic file (`RESEARCH_TOPIC_FILE`) — what to research and what sections to cover.
  - Angles file (`SEARCH_ANGLES_FILE`) — the raw search queries the researcher executes.


### Topic file

Defines the report subject and its required sections. Sent to all three phases — the
planner uses it to build a search strategy, the researcher uses it to stay on-scope,
the synthesizer uses it to structure the final report.

Format: plain text. First line is the report title. Remaining lines describe the
sections and data points to cover.

Example (saudi-oil-production.txt):

  Saudi Arabia oil production — weekly business intelligence report. Cover all of the
  following with current data:

  PRODUCTION
  - Latest crude oil output (million barrels per day)
  - OPEC+ quota compliance and Saudi actual vs. target production
  - Year-on-year and month-on-month production changes

  PRICES & TRADE
  - Saudi Official Selling Price (OSP) for Arab Light, Medium, Heavy to Asia, Europe, US
  - Active export volumes by destination (Asia, Europe, US, India, China)

  OPEC+ & POLICY
  - Latest OPEC+ meeting outcomes and Saudi position
  - Voluntary cut announcements or rollbacks

The more specific the section list, the tighter the planner's search strategy and the
more structured the synthesizer's output.


### Angles file

One search query per line. These are the raw inputs the planner builds its strategy
around, and the researcher uses them when calling web_search, search_x, and search_reddit.

Keep angles specific and keyword-dense — they go straight to Brave.
Broad angles waste search calls; narrow angles surface targeted results.

Example (saudi-oil-angles.txt):

  Saudi Arabia oil production 2025 2026 barrels
  Saudi Aramco output OPEC quota 2026
  Saudi official selling price OSP 2026
  Saudi Arabia crude oil exports China India 2026
  OPEC+ production cut Saudi Arabia 2026
  Saudi Aramco revenue earnings 2026
  Strait of Hormuz oil shipping disruption 2026
  Saudi Arabia spare oil capacity 2026

Rule of thumb: one angle per major topic area in the topic file. More angles = broader
coverage but more search calls consumed. The researcher is capped at 10 web_search,
5 search_x, and 5 search_reddit calls total across all angles.


Each run executes three phases, each handled by a separate model:

  Phase 1 — Planning (default: Sonnet)
      Opus analyzes the topic and search angles, produces a structured
      markdown search plan: priority queries, source types, what to avoid.
      Single API call, no tools.
      Output saved to: runs/<uuid>/thinking path/01_plan.md

  Phase 2 — Research (default: Sonnet)
      Sonnet receives the search plan and executes it using tools.
      Capped at 10 web_search calls, 5 search_x calls, 5 search_reddit calls,
      and 20 total iterations.
      Output saved to: runs/<uuid>/thinking path/02_research_messages.json

  Phase 3 — Synthesis (default: Sonnet)
      Opus receives the full research conversation and writes the final report.
      Single API call, no tools.
      Output saved to: runs/<uuid>/thinking path/03_synthesis_output.md


  Angles file + Topic file
      │
      ▼
  ┌─────────────────────────────────────────────────────┐
  │  Phase 1: Planner (Opus)                            │
  │  Produces structured search plan (markdown)         │
  └──────────────────────┬──────────────────────────────┘
                         │ search plan
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │  Phase 2: Researcher (Sonnet)                       │
  │                                                     │
  │  web_search ──► Brave ──► stripped results          │
  │  search_x   ──► Brave (site:x.com)                  │
  │  search_reddit ► Brave (site:reddit.com)            │
  │  fetch_url  ──► full page text (first 8 000 chars)  │
  │                                                     │
  │  Loops until plan executed (max 20 iterations)      │
  └──────────────────────┬──────────────────────────────┘
                         │ full conversation history
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │  Phase 3: Synthesizer (Opus)                        │
  │  Reads all gathered content, writes final report    │
  └──────────────────────┬──────────────────────────────┘
                         │ markdown report
                         ▼
                   GitHub commit

  Claude never touches Brave or the web directly — agent code mediates every call.

  X and Reddit search:

    search_x and search_reddit use the same Brave API key — no extra credentials needed.
    Both tools accept a plain query; the site: restriction is added automatically.
    Results are in English only (X and Reddit content is predominantly English).


Model configuration (optional):

  PLANNING_MODEL=claude-sonnet-4-6   (default)
  RESEARCH_MODEL=claude-sonnet-4-6   (default)
  SYNTHESIS_MODEL=claude-sonnet-4-6  (default)

  Override any phase independently. Use cheaper models to reduce cost,
  more capable models to improve quality.

  THINKING_OUTPUT_DIR=/app/runs   (default: runs)

  Directory where per-run thinking path files are written. Mount this path
  as a Docker volume to access the files on the host.


Language distribution:

  SEARCH_LANGUAGES="en:0.6,ar:0.3,de:0.1"

  Weights are normalized automatically. The researcher distributes its searches
  across languages proportionally and writes each query in the target language.


Date filter (optional):

  SEARCH_START_DATE="2025-01-01"
  SEARCH_END_DATE="2025-04-01"

  Dates are ISO 8601 (YYYY-MM-DD). Both must be set together or both omitted.
  End date must not be before start date.

  Two-layer filter:
    1. Brave receives a freshness param — drops pages published outside the window before results reach Claude.
    2. The researcher is instructed to focus on events within the window. Facts from outside are allowed only
       when they provide context that makes in-window findings more meaningful. Sources whose content
       is primarily off-window are skipped entirely.


Debug output:

  Each run creates runs/<uuid>/thinking path/ with three files:
    01_plan.md                — search plan produced by the planner
    02_research_messages.json — full tool-call conversation from the researcher
    03_synthesis_output.md    — final report text before YAML frontmatter

  The runs/ directory is gitignored.


Output:

  Report is committed to GitHub (GITHUB_REPO / GITHUB_OUTPUT_PATH, branch GITHUB_BRANCH)
  with a YAML frontmatter header (topic + date).

  If the commit fails, the report is saved to data/fallback_report.md.
  The next run detects the fallback, retries the commit, then proceeds with a fresh research run.
