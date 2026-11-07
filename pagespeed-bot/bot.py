import os
import time
import requests
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

# Initialize Slack App
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

def fetch_psi_data(url):
    """Calls Google PageSpeed Insights API and safely extracts all category scores."""
    api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    
    api_key = os.environ.get("PSI_API_KEY")
    params = {
        "url": url,
        "strategy": "mobile",
        "category": ["performance", "accessibility", "best-practices", "seo"],
        "key": api_key
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        print(f"API Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            categories = data.get("lighthouseResult", {}).get("categories", {})
            
            # Print available categories to terminal for debugging
            print("Found categories:", list(categories.keys()))
            
            # Safely extract each category score (supporting both normal and hyphenated keys)
            perf_score = categories.get("performance", {}).get("score", 0)
            acc_score = categories.get("accessibility", {}).get("score", 0)

            # Best practices can sometimes be 'best-practices'
            bp_cat = categories.get("best-practices", {}) or categories.get("best_practices", {})
            bp_score = bp_cat.get("score", 0)

            seo_score = categories.get("seo", {}).get("score", 0)

            scores = {
                "performance": int((perf_score if perf_score is not None else 0) * 100),
                "accessibility": int((acc_score if acc_score is not None else 0) * 100),
                "best_practices": int((bp_score if bp_score is not None else 0) * 100),
                "seo": int((seo_score if seo_score is not None else 0) * 100),
            }
            return scores
        else:
            print(f"API Error Response: {response.text}")
            return None
    except Exception as e:
        print(f"Exception caught: {e}")
        return None

    
@app.command("/pagespeed")
def handle_pagespeed(ack, command, respond):
    """Handles the /pagespeed Slack slash command."""
    ack() # Acknowledge command immediately to avoid Slack timeout errors
    
    text = command.get("text", "").strip().split()
    if not text:
        respond("❌ Please provide a URL. Usage: `/pagespeed https://example.com [runs]`")
        return
        
    target_url = text[0]
    
    # Parse number of runs (default to 3, limit between 1 and 5)
    num_runs = 3
    if len(text) > 1 and text[1].isdigit():
        num_runs = min(max(int(text[1]), 1), 5) 

    respond(f"⏳ Running PageSpeed analysis for `{target_url}` across **{num_runs} run(s)**. Please wait...")

    total_scores = {"performance": 0, "accessibility": 0, "best_practices": 0, "seo": 0}
    successful_runs = 0

    for i in range(num_runs):
        scores = fetch_psi_data(target_url)
        if scores:
            for key in total_scores:
                total_scores[key] += scores[key]
            successful_runs += 1
        if i < num_runs - 1:
            time.sleep(2)

    if successful_runs == 0:
        respond("❌ Failed to retrieve PageSpeed insights. Please check if the URL is valid and publicly accessible.")
        return

    avg_scores = {key: round(val / successful_runs) for key, val in total_scores.items()}

    response_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📊 *PageSpeed Insights Average Report*\n*Target URL:* {target_url}\n*Successful Runs:* {successful_runs}/{num_runs}"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*🚀 Performance:*\n`{avg_scores['performance']}/100`"},
                {"type": "mrkdwn", "text": f"*♿ Accessibility:*\n`{avg_scores['accessibility']}/100`"},
                {"type": "mrkdwn", "text": f"*💡 Best Practices:*\n`{avg_scores['best_practices']}/100`"},
                {"type": "mrkdwn", "text": f"*🔍 SEO:*\n`{avg_scores['seo']}/100`"}
            ]
        }
    ]

    respond(blocks=response_blocks)

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("⚡️ Slack PageSpeed Bot is running via Socket Mode...")
    handler.start()