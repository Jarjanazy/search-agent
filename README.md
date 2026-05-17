
docker build -t research-agent .                                                                                              


docker run --env-file .env -v "C:\Users\celil\work\search-agent\saudi-oil-production.txt:/app/topic.txt" -v "C:\Users\celil\work\search-agent\syrian-olive-oil-angles.txt:/app/angles.txt" research-agent



To deploy on Hetzner:
  1. Create GitHub repo, push: git remote add origin <url> && git push -u origin master
  2. Copy repo to server, fill .env, run docker build -t research-agent .
  3. Add to crontab:
  CRON_TZ=Europe/Amsterdam
  0 14 * * * docker run --rm --env-file /path/to/.env research-agent:latest >> /var/log/research-agent.log 2>&1



## Workflow

Two input files drive each run:

  - Angles file (`SEARCH_ANGLES_FILE`) — exact search queries, one per line. Claude uses these verbatim; it does not invent new queries.
  - Topic file (`RESEARCH_TOPIC_FILE`) — the report subject and structure (sections, data points to cover). Sent as the first user message.

  Claude is capped at 10 web_search calls, 5 search_x calls, 5 search_reddit calls,
  and 25 total agent loop iterations.


  Angles file supplies verbatim query list
      │
      ▼
  Claude picks a query from the list, calls web_search with it
  (optionally with a language code — see SEARCH_LANGUAGES below)
      │
      ▼
  Agent code sends query + language to Brave
      │
      ▼
  Brave returns raw results
      │
      ▼
  Agent code strips to three fields per result:
      • page title
      • page URL
      • one-sentence description
      (everything else thrown away)
      │
      ▼
  Claude reads stripped results
      │
      ▼
  Claude decides: search again (another angle)? fetch full article? write report?
      │
      ├─► fetch_url → agent fetches full page text (first 8 000 chars) → back to Claude
      │
      ├─► web_search again → loop repeats (up to 10 searches total)
      │
      ├─► search_x → searches X (Twitter) via Brave restricted to x.com (up to 5 calls total)
      │
      ├─► search_reddit → searches Reddit via Brave restricted to reddit.com (up to 5 calls total)
      │
      └─► write report → done

  Claude never touches Brave or the web directly — agent code mediates every call.

  X and Reddit search:

    search_x and search_reddit use the same Brave API key — no extra credentials needed.
    Both tools accept a plain query; the site: restriction is added automatically.
    Results are in English only (X and Reddit content is predominantly English).
    Claude may call each tool once per angle to surface social discussion alongside
    traditional web sources.


Language distribution:

  SEARCH_LANGUAGES="en:0.6,ar:0.3,de:0.1"

  Weights are normalized automatically. Claude distributes its searches across languages
  proportionally and writes each query in the target language.


Date filter (optional):

  SEARCH_START_DATE="2025-01-01"
  SEARCH_END_DATE="2025-04-01"

  Dates are ISO 8601 (YYYY-MM-DD). Both must be set together or both omitted.
  End date must not be before start date.

  Two-layer filter:
    1. Brave receives a freshness param — drops pages published outside the window before results reach Claude.
    2. Claude is instructed to focus on events within the window. Facts from outside are allowed only
       when they provide context that makes in-window findings more meaningful. Sources whose content
       is primarily off-window are skipped entirely.


Output:

  Report is committed to GitHub (GITHUB_REPO / GITHUB_OUTPUT_PATH, branch GITHUB_BRANCH)
  with a YAML frontmatter header (topic + date).

  If the commit fails, the report is saved to data/fallback_report.md.
  The next run detects the fallback, retries the commit, then proceeds with a fresh research run.