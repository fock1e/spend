#!/usr/bin/env python3
"""spend — CLI spending tracker backed by SQLite."""

import argparse
import calendar
import csv
import sqlite3
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

DB_PATH = Path(os.environ.get("SPEND_DB") or Path(__file__).parent / "spend.db").expanduser()
CURRENCY = os.environ.get("SPEND_CURRENCY") or "֏"


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            note TEXT DEFAULT '',
            date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            category TEXT PRIMARY KEY,
            monthly_limit REAL NOT NULL
        )
    """)
    db.commit()
    return db


def prev_month_str(month):
    """Given 'YYYY-MM', return the previous month string."""
    y, m = map(int, month.split("-"))
    if m == 1:
        return f"{y - 1}-12"
    return f"{y}-{m - 1:02d}"


def cmd_add(args):
    db = get_db()
    d = args.date or date.today().isoformat()
    note = args.note or ""
    db.execute(
        "INSERT INTO expenses (amount, category, note, date) VALUES (?, ?, ?, ?)",
        (args.amount, args.category.lower(), note, d),
    )
    db.commit()
    print(f"  + {args.amount:.0f}{CURRENCY} {args.category.lower()}" + (f" ({note})" if note else "") + f"  [{d}]")


def cmd_list(args):
    db = get_db()
    where = " WHERE 1=1"
    params = []

    if args.month:
        where += " AND date LIKE ?"
        params.append(f"{args.month}%")
    if args.category:
        where += " AND category = ?"
        params.append(args.category.lower())
    if args.today:
        where += " AND date = ?"
        params.append(date.today().isoformat())

    # Totals across ALL matching rows, independent of display limit
    total_row = db.execute(
        f"SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM expenses{where}", params
    ).fetchone()
    total_count, total_sum = total_row

    if total_count == 0:
        print("  No expenses found.")
        return

    query = f"SELECT id, amount, category, note, date FROM expenses{where} ORDER BY date DESC, id DESC"
    list_params = list(params)
    if args.limit and args.limit > 0:
        query += " LIMIT ?"
        list_params.append(args.limit)

    rows = db.execute(query, list_params).fetchall()

    for row_id, amount, cat, note, d in rows:
        line = f"  #{row_id:<4} {d}  {amount:>8.0f}{CURRENCY}  {cat}"
        if note:
            line += f"  — {note}"
        print(line)

    shown = len(rows)
    if shown < total_count:
        print(f"\n  Showing {shown} of {total_count} entries (use --limit 0 for all)")
    print(f"\n  Total: {total_sum:,.0f}{CURRENCY}  ({total_count} entries)")


def cmd_summary(args):
    db = get_db()
    month = args.month or date.today().strftime("%Y-%m")

    rows = db.execute(
        """SELECT category, SUM(amount) as total, COUNT(*) as cnt
           FROM expenses WHERE date LIKE ?
           GROUP BY category ORDER BY total DESC""",
        (f"{month}%",),
    ).fetchall()

    if not rows:
        print(f"  No expenses for {month}.")
        return

    budgets = dict(db.execute("SELECT category, monthly_limit FROM budgets").fetchall())

    grand = sum(r[1] for r in rows)
    print(f"\n  === {month} ===\n")
    for cat, total, cnt in rows:
        pct = (total / grand) * 100
        bar = "█" * int(pct / 3)
        line = f"  {cat:<16} {total:>8,.0f}{CURRENCY}  ({cnt:>2}x)  {bar} {pct:.0f}%"
        if cat in budgets:
            limit = budgets[cat]
            bpct = (total / limit) * 100 if limit > 0 else 0
            tag = f"  [budget {bpct:.0f}%]"
            if bpct > 100:
                tag += " ⚠"
            line += tag
        print(line)
    print(f"\n  {'TOTAL':<16} {grand:>8,.0f}{CURRENCY}")


def cmd_delete(args):
    db = get_db()
    row = db.execute("SELECT amount, category, date FROM expenses WHERE id = ?", (args.id,)).fetchone()
    if not row:
        print(f"  Expense #{args.id} not found.")
        sys.exit(1)
    db.execute("DELETE FROM expenses WHERE id = ?", (args.id,))
    db.commit()
    print(f"  Deleted #{args.id}: {row[0]:.0f}{CURRENCY} {row[1]} [{row[2]}]")


def cmd_edit(args):
    db = get_db()
    row = db.execute("SELECT amount, category, note, date FROM expenses WHERE id = ?", (args.id,)).fetchone()
    if not row:
        print(f"  Expense #{args.id} not found.")
        sys.exit(1)

    amount = args.amount if args.amount is not None else row[0]
    category = args.category.lower() if args.category else row[1]
    note = args.note if args.note is not None else row[2]
    d = args.date or row[3]

    db.execute(
        "UPDATE expenses SET amount=?, category=?, note=?, date=? WHERE id=?",
        (amount, category, note, d, args.id),
    )
    db.commit()
    print(f"  Updated #{args.id}: {amount:.0f}{CURRENCY} {category}" + (f" ({note})" if note else "") + f" [{d}]")


def cmd_categories(args):
    db = get_db()
    rows = db.execute(
        "SELECT category, COUNT(*), SUM(amount) FROM expenses GROUP BY category ORDER BY SUM(amount) DESC"
    ).fetchall()
    if not rows:
        print("  No categories yet.")
        return
    for cat, cnt, total in rows:
        print(f"  {cat:<16} {cnt:>3} entries  {total:>10,.0f}{CURRENCY} total")


def cmd_days(args):
    db = get_db()
    month = args.month or date.today().strftime("%Y-%m")
    rows = db.execute(
        """SELECT date, SUM(amount), COUNT(*) FROM expenses
           WHERE date LIKE ? GROUP BY date ORDER BY date""",
        (f"{month}%",),
    ).fetchall()
    if not rows:
        print(f"  No expenses for {month}.")
        return

    max_amt = max(r[1] for r in rows)
    grand = sum(r[1] for r in rows)
    print(f"\n  === {month} daily ===\n")
    for d, total, cnt in rows:
        bar_len = int((total / max_amt) * 30)
        bar = "█" * bar_len
        print(f"  {d}  {total:>9,.0f}{CURRENCY}  ({cnt:>2}x)  {bar}")
    avg = grand / len(rows)
    print(f"\n  TOTAL       {grand:>9,.0f}{CURRENCY}  ({len(rows)} active days, avg {avg:,.0f}{CURRENCY}/day)")


def cmd_rate(args):
    db = get_db()
    today = date.today()
    month = today.strftime("%Y-%m")
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day
    days_left = days_in_month - days_elapsed

    spent, cnt = db.execute(
        "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE date LIKE ?",
        (f"{month}%",),
    ).fetchone()

    daily_avg = spent / days_elapsed if days_elapsed > 0 else 0
    projected = daily_avg * days_in_month

    print(f"\n  === {month} burn rate ===\n")
    print(f"  Day {days_elapsed} of {days_in_month}  ({days_left} days remaining)")
    print(f"  Spent so far:    {spent:>10,.0f}{CURRENCY}  ({cnt} entries)")
    print(f"  Daily average:   {daily_avg:>10,.0f}{CURRENCY}")
    print(f"  Projected month: {projected:>10,.0f}{CURRENCY}")

    budgets = db.execute("SELECT category, monthly_limit FROM budgets").fetchall()
    if budgets:
        total_budget = sum(b[1] for b in budgets)
        print(f"  Total budget:    {total_budget:>10,.0f}{CURRENCY}")
        if projected > total_budget:
            over = projected - total_budget
            print(f"  ⚠ Projected OVER budget by {over:,.0f}{CURRENCY}")
        else:
            under = total_budget - projected
            print(f"  ✓ On track ({under:,.0f}{CURRENCY} headroom)")


def cmd_compare(args):
    db = get_db()
    cur_month = args.month or date.today().strftime("%Y-%m")
    prev_month = prev_month_str(cur_month)

    def fetch(month):
        return dict(db.execute(
            "SELECT category, SUM(amount) FROM expenses WHERE date LIKE ? GROUP BY category",
            (f"{month}%",),
        ).fetchall())

    cur = fetch(cur_month)
    prev = fetch(prev_month)
    cats = sorted(set(cur) | set(prev), key=lambda c: -(cur.get(c, 0) + prev.get(c, 0)))

    if not cats:
        print(f"  No expenses for {prev_month} or {cur_month}.")
        return

    print(f"\n  === {prev_month} vs {cur_month} ===\n")
    print(f"  {'category':<14} {prev_month:>11} {cur_month:>11}    Δ")
    for cat in cats:
        p = prev.get(cat, 0)
        c = cur.get(cat, 0)
        if p == 0:
            delta = "NEW"
        elif c == 0:
            delta = "GONE"
        else:
            pct = ((c - p) / p) * 100
            delta = f"{pct:+.0f}%"
        print(f"  {cat:<14} {p:>10,.0f}{CURRENCY} {c:>10,.0f}{CURRENCY}  {delta:>6}")
    pt = sum(prev.values())
    ct = sum(cur.values())
    if pt > 0:
        tdelta = f"{((ct - pt) / pt) * 100:+.0f}%"
    else:
        tdelta = "NEW"
    print(f"  {'TOTAL':<14} {pt:>10,.0f}{CURRENCY} {ct:>10,.0f}{CURRENCY}  {tdelta:>6}")


def cmd_top(args):
    db = get_db()
    where = " WHERE 1=1"
    params = []
    if args.month:
        where += " AND date LIKE ?"
        params.append(f"{args.month}%")
    if args.category:
        where += " AND category = ?"
        params.append(args.category.lower())

    rows = db.execute(
        f"SELECT id, amount, category, note, date FROM expenses{where} ORDER BY amount DESC LIMIT ?",
        params + [args.n],
    ).fetchall()

    if not rows:
        print("  No expenses found.")
        return

    label = f" in {args.month}" if args.month else ""
    print(f"\n  === Top {len(rows)} expenses{label} ===\n")
    for i, (rid, amt, cat, note, d) in enumerate(rows, 1):
        line = f"  {i:>2}. {amt:>9,.0f}{CURRENCY}  {cat:<12} {d}  #{rid}"
        if note:
            line += f"  — {note}"
        print(line)


def cmd_find(args):
    db = get_db()
    q = f"%{args.query.lower()}%"
    rows = db.execute(
        """SELECT id, amount, category, note, date FROM expenses
           WHERE LOWER(note) LIKE ? OR LOWER(category) LIKE ?
           ORDER BY date DESC, id DESC""",
        (q, q),
    ).fetchall()
    if not rows:
        print(f"  No matches for '{args.query}'.")
        return
    total = 0
    for rid, amt, cat, note, d in rows:
        total += amt
        line = f"  #{rid:<4} {d}  {amt:>8,.0f}{CURRENCY}  {cat}"
        if note:
            line += f"  — {note}"
        print(line)
    print(f"\n  Total: {total:,.0f}{CURRENCY}  ({len(rows)} matches)")


def cmd_week(args):
    db = get_db()
    today = date.today()
    week_ago = (today - timedelta(days=6)).isoformat()

    rows = db.execute(
        """SELECT category, SUM(amount), COUNT(*) FROM expenses
           WHERE date >= ? GROUP BY category ORDER BY SUM(amount) DESC""",
        (week_ago,),
    ).fetchall()
    if not rows:
        print("  No expenses in the last 7 days.")
        return
    grand = sum(r[1] for r in rows)
    print(f"\n  === Last 7 days ({week_ago} → {today}) ===\n")
    for cat, total, cnt in rows:
        pct = (total / grand) * 100
        bar = "█" * int(pct / 3)
        print(f"  {cat:<16} {total:>8,.0f}{CURRENCY}  ({cnt:>2}x)  {bar} {pct:.0f}%")
    print(f"\n  {'TOTAL':<16} {grand:>8,.0f}{CURRENCY}  (avg {grand / 7:,.0f}{CURRENCY}/day)")


def cmd_export(args):
    db = get_db()
    rows = db.execute(
        "SELECT id, date, category, amount, note FROM expenses ORDER BY date, id"
    ).fetchall()

    if args.output:
        f = open(args.output, "w", newline="")
    else:
        f = sys.stdout
    writer = csv.writer(f)
    writer.writerow(["id", "date", "category", "amount", "note"])
    for row in rows:
        writer.writerow(row)
    if args.output:
        f.close()
        print(f"  Exported {len(rows)} entries to {args.output}")


def cmd_budget(args):
    db = get_db()
    if args.action == "set":
        if args.category is None or args.amount is None:
            print("  Usage: spend budget set <category> <amount>")
            sys.exit(1)
        db.execute(
            "INSERT INTO budgets (category, monthly_limit) VALUES (?, ?) "
            "ON CONFLICT(category) DO UPDATE SET monthly_limit = excluded.monthly_limit",
            (args.category.lower(), args.amount),
        )
        db.commit()
        print(f"  Set budget: {args.category.lower()} = {args.amount:,.0f}{CURRENCY}/month")
    elif args.action == "rm":
        if args.category is None:
            print("  Usage: spend budget rm <category>")
            sys.exit(1)
        db.execute("DELETE FROM budgets WHERE category = ?", (args.category.lower(),))
        db.commit()
        print(f"  Removed budget for {args.category.lower()}")
    else:  # list
        rows = db.execute(
            "SELECT category, monthly_limit FROM budgets ORDER BY monthly_limit DESC"
        ).fetchall()
        if not rows:
            print("  No budgets set. Try: spend budget set food 100000")
            return
        month = date.today().strftime("%Y-%m")
        print(f"\n  === Budgets ({month} usage) ===\n")
        for cat, limit in rows:
            (spent,) = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE category = ? AND date LIKE ?",
                (cat, f"{month}%"),
            ).fetchone()
            pct = (spent / limit) * 100 if limit > 0 else 0
            warn = " ⚠ OVER" if pct > 100 else ""
            bar_len = min(int(pct / 5), 20)
            bar = "█" * bar_len
            print(f"  {cat:<14} {spent:>9,.0f}{CURRENCY} / {limit:>9,.0f}{CURRENCY}  {bar} {pct:.0f}%{warn}")


def main():
    p = argparse.ArgumentParser(prog="spend", description="Track your spending")
    sub = p.add_subparsers(dest="command")

    # add
    add_p = sub.add_parser("add", aliases=["a"], help="Add an expense")
    add_p.add_argument("amount", type=float)
    add_p.add_argument("category", type=str)
    add_p.add_argument("--note", "-n", type=str)
    add_p.add_argument("--date", "-d", type=str, help="YYYY-MM-DD (default: today)")

    # list
    list_p = sub.add_parser("list", aliases=["ls"], help="List expenses")
    list_p.add_argument("--month", "-m", type=str, help="YYYY-MM")
    list_p.add_argument("--category", "-c", type=str)
    list_p.add_argument("--today", "-t", action="store_true")
    list_p.add_argument("--limit", "-l", type=int, default=20)

    # summary
    sum_p = sub.add_parser("summary", aliases=["s"], help="Monthly summary")
    sum_p.add_argument("--month", "-m", type=str, help="YYYY-MM (default: current)")

    # delete
    del_p = sub.add_parser("delete", aliases=["rm"], help="Delete an expense")
    del_p.add_argument("id", type=int)

    # edit
    edit_p = sub.add_parser("edit", aliases=["e"], help="Edit an expense")
    edit_p.add_argument("id", type=int)
    edit_p.add_argument("--amount", "-a", type=float)
    edit_p.add_argument("--category", "-c", type=str)
    edit_p.add_argument("--note", "-n", type=str)
    edit_p.add_argument("--date", "-d", type=str)

    # categories
    sub.add_parser("categories", aliases=["cat"], help="List all categories")

    # days — daily breakdown for a month
    days_p = sub.add_parser("days", aliases=["d"], help="Daily breakdown for a month")
    days_p.add_argument("--month", "-m", type=str, help="YYYY-MM (default: current)")

    # rate — burn rate / projection
    sub.add_parser("rate", aliases=["r"], help="Burn rate and month projection")

    # compare — month vs previous month
    cmp_p = sub.add_parser("compare", aliases=["cmp"], help="Compare a month to the previous one")
    cmp_p.add_argument("--month", "-m", type=str, help="YYYY-MM (default: current)")

    # top — biggest expenses
    top_p = sub.add_parser("top", help="Biggest single expenses")
    top_p.add_argument("-n", type=int, default=10, help="How many (default: 10)")
    top_p.add_argument("--month", "-m", type=str, help="YYYY-MM")
    top_p.add_argument("--category", "-c", type=str)

    # find — search notes/category
    find_p = sub.add_parser("find", aliases=["f"], help="Search expenses by note/category text")
    find_p.add_argument("query", type=str)

    # week — last 7 days
    sub.add_parser("week", aliases=["w"], help="Last 7 days summary")

    # export — CSV
    exp_p = sub.add_parser("export", help="Export all expenses to CSV")
    exp_p.add_argument("--output", "-o", type=str, help="Output file (default: stdout)")

    # budget — set/list/rm
    bud_p = sub.add_parser("budget", aliases=["b"], help="Manage monthly budgets per category")
    bud_p.add_argument("action", nargs="?", default="list", choices=["set", "rm", "list"])
    bud_p.add_argument("category", nargs="?", type=str)
    bud_p.add_argument("amount", nargs="?", type=float)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(0)

    cmd_map = {
        "add": cmd_add, "a": cmd_add,
        "list": cmd_list, "ls": cmd_list,
        "summary": cmd_summary, "s": cmd_summary,
        "delete": cmd_delete, "rm": cmd_delete,
        "edit": cmd_edit, "e": cmd_edit,
        "categories": cmd_categories, "cat": cmd_categories,
        "days": cmd_days, "d": cmd_days,
        "rate": cmd_rate, "r": cmd_rate,
        "compare": cmd_compare, "cmp": cmd_compare,
        "top": cmd_top,
        "find": cmd_find, "f": cmd_find,
        "week": cmd_week, "w": cmd_week,
        "export": cmd_export,
        "budget": cmd_budget, "b": cmd_budget,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
