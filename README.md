
docker build -t research-agent .                                                                                              


  docker run --env-file .env \
    -v "C:\Users\celil\work\research agent\saudi-oil-production.txt:/app/topic.txt" \
    research-agent



To deploy on Hetzner:
  1. Create GitHub repo, push: git remote add origin <url> && git push -u origin master
  2. Copy repo to server, fill .env, run docker build -t research-agent .
  3. Add to crontab:
  CRON_TZ=Europe/Amsterdam
  0 14 * * * docker run --rm --env-file /path/to/.env research-agent:latest >> /var/log/research-agent.log 2>&1