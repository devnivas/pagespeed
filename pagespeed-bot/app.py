import os
import time
import requests
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.oauth.oauth_flow import OAuthFlow

# 1. Configure OAuth Flow (Stores tokens dynamically per workspace)
oauth_flow = OAuthFlow.sqlite3(
    database="installations.db",
    client_id=os.environ["SLACK_CLIENT_ID"],
    client_secret=os.environ["SLACK_CLIENT_SECRET"],
    scopes=["commands", "chat:write"]
)

# 2. Initialize Bolt App with OAuth settings
app = App(
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    oauth_flow=oauth_flow
)

# 3. Define the instant acknowledgment function (prevents Slack timeout)
def acknowledge_command(ack):
    ack()

# 4. Define the background worker for your PageSpeed logic
def run_pagespeed_analysis(command, respond):
    text = command.get("text", "").strip().split()
    if not text:
        respond("❌ Please provide a URL. Usage: `/pagespeed https://example.com [runs]`")
        return
        
    target_url = text[0]
    num_runs = 3
    if len(text) > 1 and text[1].isdigit():
        num_runs = min(max(int(text[1]), 1), 5) 

    respond(f"⏳ Running PageSpeed analysis for `{target_url}` across **{num_runs} run(s)**...")

    total_scores = {"performance": 0, "accessibility": 0, "best_practices": 0, "seo": 0}
    successful_runs = 0
    api_key = os.environ.get("PSI_API_KEY")

    for i in range(num_runs):
        try:
            res = requests.get(
                "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params={"url": target_url, "strategy": "mobile", "key": api_key},
                timeout=30
            )
            if res.status_code == 200:
                cats = res.json().get("lighthouseResult", {}).get("categories", {})
                total_scores["performance"] += int((cats.get("performance", {}).get("score", 0) or 0) * 100)
                total_scores["accessibility"] += int((cats.get("accessibility", {}).get("score", 0) or 0) * 100)
                total_scores["best_practices"] += int((cats.get("best-practices", {}).get("score", 0) or 0) * 100)
                total_scores["seo"] += int((cats.get("seo", {}).get("score", 0) or 0) * 100)
                successful_runs += 1
        except Exception:
            pass
        if i < num_runs - 1:
            time.sleep(3)

    if successful_runs == 0:
        respond("❌ Failed to fetch PageSpeed metrics.")
        return

    avg = {k: round(v / successful_runs) for k, v in total_scores.items()}

    respond(blocks=[
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"📊 *PageSpeed Report*\n*URL:* {target_url} ({successful_runs}/{num_runs} runs)"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*🚀 Performance:*\n`{avg['performance']}/100`"},
                {"type": "mrkdwn", "text": f"*♿ Accessibility:*\n`{avg['accessibility']}/100`"},
                {"type": "mrkdwn", "text": f"*💡 Best Practices:*\n`{avg['best_practices']}/100`"},
                {"type": "mrkdwn", "text": f"*🔍 SEO:*\n`{avg['seo']}/100`"}
            ]
        }
    ])

# Register the command using ack + lazy listeners
app.command("/pagespeed")(
    ack=acknowledge_command,
    lazy=[run_pagespeed_analysis]
)

# 5. Wrap with FastAPI
api = FastAPI()
handler = AsyncSlackRequestHandler(app)

@api.post("/slack/events")
async def endpoint(req: Request):
    return await handler.handle(req)

@api.get("/slack/install")
async def install(req: Request):
    return await handler.handle(req)

@api.get("/slack/oauth_redirect")
async def oauth_redirect(req: Request):
    return await handler.handle(req)