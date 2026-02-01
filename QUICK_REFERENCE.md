# Quick Reference Card

## Installation (One-Time Setup)

\`\`\`bash
cd "/Users/justinkobely/Library/Mobile Documents/iCloud~md~obsidian/Documents/My_Notes/0 - Programs/congressional-trading-bot"
pip install -r requirements.txt
python3 scripts/init_optimization.py
\`\`\`

## Daily Usage

### Morning Routine
\`\`\`bash
# Scrape new Senate filings (2-3 min)
python3 -m src.cli.cli scrape senate --days 2 --max-filings 10

# View recommendations
python3 -m src.cli.cli recommendations --days 7
\`\`\`

### Track Specific People
\`\`\`bash
# Nancy Pelosi (House)
python3 -m src.cli.cli politician-stats "Nancy Pelosi"

# Elizabeth Warren (Senate)
python3 -m src.cli.cli scrape senator Warren --days 90
python3 -m src.cli.cli politician-stats "Elizabeth Warren"
\`\`\`

### Check Performance
\`\`\`bash
# AI optimization status
python3 -m src.cli.cli optimize status

# Bot status
python3 -m src.cli.cli status
\`\`\`

## Common Commands

| Task | Command |
|------|---------|
| Scrape House | \`python3 -m src.cli.cli scrape house --start-year 2023\` |
| Scrape Senate | \`python3 -m src.cli.cli scrape senate --days 90\` |
| Scrape Senator | \`python3 -m src.cli.cli scrape senator <Name> --days 90\` |
| Recommendations | \`python3 -m src.cli.cli recommendations --days 30\` |
| Analyze Ticker | \`python3 -m src.cli.cli analyze NVDA --days 30\` |
| Politician Stats | \`python3 -m src.cli.cli politician-stats "Name"\` |
| Optimization | \`python3 -m src.cli.cli optimize status\` |
| Status | \`python3 -m src.cli.cli status\` |

## Full Documentation

- **README.md** - Project overview
- **SENATE_SCRAPING_GUIDE.md** - Senate scraping details
- **OPTIMIZATION_GUIDE.md** - AI optimization guide
- **COMPLETE_IMPLEMENTATION_SUMMARY.md** - Everything in one place

## Support

- Check logs: \`tail -f logs/app.log\`
- Run tests: \`pytest\`
- Review docs above
