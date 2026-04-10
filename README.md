# spend

A no-bullshit personal spending tracker that lives in your terminal. SQLite-backed, zero dependencies, one Python file.

Built because every spreadsheet I tried got abandoned in three weeks. The CLI is fast enough that logging an expense takes less time than opening an app.

```
  === 2026-04 ===

  food               83,371֏  (16x)  ██████████████ 43%  [budget 83%]
  flowers            42,000֏  ( 1x)  ███████ 22%
  phone              18,000֏  ( 1x)  ███ 9%
  gym                18,000֏  ( 1x)  ███ 9%
  taxi               16,150֏  ( 4x)  ██ 8%  [budget 54%]
  groceries          15,875֏  ( 4x)  ██ 8%
  household           1,070֏  ( 1x)   1%
  samokat               770֏  ( 2x)   0%

  TOTAL             195,236֏
```

## Why

- **Fast.** `spend add 5000 food` and you're done.
- **Local.** Your data lives in a SQLite file on your machine. No cloud, no telemetry, no account.
- **Zero deps.** Pure Python stdlib. No `pip install` dance.
- **Hackable.** One file, ~300 lines, easy to fork and tweak.
- **Pretty.** Bar charts in the terminal. Burn rate. Month-over-month comparison.

## Install

Clone the repo and add an alias to your shell:

```bash
git clone https://github.com/fock1e/spend ~/spend
chmod +x ~/spend/spend.py

# Add to ~/.zshrc or ~/.bashrc:
alias spend="python3 ~/spend/spend.py"
```

Reload your shell. That's it. The database is created automatically on first use.

## Quick start

```bash
spend add 5000 food                       # log an expense (today)
spend add 12000 groceries -n "Yerevan Market"   # with a note
spend add 150000 rent -d 2026-04-01      # with a custom date

spend summary                             # current month breakdown
spend rate                                # burn rate + projection
spend days                                # daily bar chart
```

## All commands

| Command | Alias | What it does |
|---|---|---|
| `spend add <amount> <category>` | `a` | Add an expense. Flags: `-n note`, `-d YYYY-MM-DD` |
| `spend list` | `ls` | Recent expenses. Flags: `-m month`, `-c category`, `-t` (today), `-l limit` |
| `spend summary` | `s` | Category breakdown for the current month |
| `spend days` | `d` | Per-day bar chart for a month |
| `spend rate` | `r` | Daily average + projected month total |
| `spend compare` | `cmp` | This month vs previous month |
| `spend top` | | Biggest single expenses. Flags: `-n N`, `-m month`, `-c category` |
| `spend find <query>` | `f` | Search notes and category names |
| `spend week` | `w` | Last 7 days summary |
| `spend categories` | `cat` | All categories with totals |
| `spend budget set <cat> <amount>` | `b` | Set a monthly budget for a category |
| `spend budget` | `b` | Show budget usage for the current month |
| `spend budget rm <cat>` | `b` | Remove a budget |
| `spend export -o file.csv` | | Dump everything to CSV |
| `spend edit <id>` | `e` | Edit an entry. Flags: `-a`, `-c`, `-n`, `-d` |
| `spend delete <id>` | `rm` | Delete an entry |

## Currency

The default currency symbol is `֏` (Armenian dram). To change it, edit the `CURRENCY` constant at the top of `spend.py`:

```python
CURRENCY = "$"   # or "€", "£", "₽", "¥", whatever
```

## Where the data lives

`~/spend/spend.db` (or wherever you cloned it). It's a single SQLite file. Back it up, sync it with Syncthing, copy it between machines, do whatever you want with it.

## Roadmap

Things that might happen:
- Recurring expenses (rent, subscriptions)
- Daily/weekly digest
- Telegram bot companion (for logging from your phone)
- Optional encryption for the SQLite file

## License

MIT. See [LICENSE](LICENSE).
