#!/usr/bin/env python3
import json
from datetime import datetime
import subprocess

def generate_dashboard():
    try:
        with open('/data/data/com.termux/files/home/agentscope/commission.json', 'r') as file:
            commission_data = json.load(file)
    
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        source_tiers = {
            's1': 'Tier 1',
            's2': 'Tier 1',
            's3': 'Tier 1',
            's4': 'Tier 1',
            's5': 'Tier 2'
        }

        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Madlanga Commission Evidence Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; }
                h1 { color: #2c3e50; }
                .claim { margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .status-pass { color: #27ae60; font-weight: bold; }
                .status-fail { color: #e74c3c; font-weight: bold; }
                .source { font-size: 0.9em; color: #7f8c8d; }
                .claim-header { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee; }
            </style>
        </head>
        <body>
            <h1>Madlanga Commission Evidence Dashboard</h1>
            <p>Last updated: {now}</p>
            <h2>Claims Summary</h2>
        """

        for claim in commission_data['claims']:
            status = 'PASS' if len(claim['sourceIds']) >= 2 else 'FAIL'
            html_content += f"""
            <div class="claim">
                <div class="claim-header"><strong>{claim['id']}</strong> - {claim['statement']}</div>
                <div class="source">Sources: {', '.join(claim['sourceIds'])}</div>
                <div class="source">Source Tiers: {', '.join([source_tiers.get(source_id, 'Unknown') for source_id in claim['sourceIds']])}</div>
                <div class="source">Verification Status: <span class="status-{status.lower()}">{status}</span></div>
            </div>
            """

        html_content += """
        </body>
        </html>
        """

        with open('/data/data/com.termux/files/home/agentscope/dashboard.html', 'w') as file:
            file.write(html_content)

if __name__ == "__main__":
    generate_dashboard()
    
    # Ingestion logic outside the function
    sources = ['s1', 's2', 's3', 's4']
    for source in sources:
        try:
            result = subprocess.run(['python3', '/data/data/com.termux/files/home/agentscope/api/ingest.py', source], capture_output=True, text=True)
            print(f"Ingestion of {source}:")
            if result.returncode == 0:
                print(f"Success")
                if result.stdout:
                    print(f"Output: {result.stdout}")
            else:
                print(f"Failed with error: {result.stderr}")
        except Exception as e:
            print(f"Failed to ingest {source} due to exception: {str(e)}")

print("Dashboard generated successfully at /data/data/com.termux/files/home/agentscope/dashboard.html")