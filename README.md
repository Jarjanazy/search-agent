
docker build -t research-agent .                                                                                              


docker run --env-file .env -v "C:\Users\celil\work\search-agent\saudi-oil-production.txt:/app/topic.txt" -v "C:\Users\celil\work\search-agent\syrian-olive-oil-angles.txt:/app/angles.txt" research-agent



To deploy on Hetzner:
  1. Create GitHub repo, push: git remote add origin <url> && git push -u origin master
  2. Copy repo to server, fill .env, run docker build -t research-agent .
  3. Add to crontab:
  CRON_TZ=Europe/Amsterdam
  0 14 * * * docker run --rm --env-file /path/to/.env research-agent:latest >> /var/log/research-agent.log 2>&1







 RESEARCH_TOPIC is only used once — at the very start, as the first message to Claude:

  "Research this topic and write a Markdown report: <RESEARCH_TOPIC>"

  After that, Claude generates its own search queries based on what it thinks will help research the topic. Those queries are not the topic itself — they're
  angles Claude invents (e.g. topic is "quantum computing", Claude might search "quantum computing 2024 breakthroughs", then "quantum vs classical speed
  comparison", etc.)


  Claude thinks: "I need to search for X"
      │
      ▼
  Claude sends search words to the agent code
      │
      ▼
  Agent code sends those words to Brave
      │
      ▼
  Brave sends back a big blob of data about many web pages
      │
      ▼
  Agent code strips it down — keeps only:
      • page title
      • page URL
      • one-sentence description
      (everything else thrown away)
      │
      ▼
  That stripped text gets handed back to Claude
      │
      ▼
  Claude reads it, decides: search again? or fetch a full page? or write report?
      │
      └─► if search again → loop repeats
          if write report → done

  Brave sends hundreds of fields. Claude only ever sees three per result. Claude never touches Brave directly — agent code sits in between every time.


Search input:

  - Angles file — what to search (web_search queries)
  - Topic file — what to write (sections, data points, report structure)

  Without topic file, Claude only has the search queries + generic system prompt. Report would be unstructured — no
  "PRODUCTION / PRICES & TRADE / RISKS" sections, no specific data points to cover.