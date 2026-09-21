#!/usr/bin/env python3
"""
Assignment 4 - Implementing Control Structures
Employee Shift Scheduler (Python version)

Rules enforced
  * 7 days a week, 3 shifts a day (Morning / Afternoon / Evening)
  * An employee works at most ONE shift per day
  * An employee works at most 5 days per week
  * Every shift needs at least 2 employees (random top-up from employees
    who are still under 5 days)
  * A shift can hold at most MAX_PER_SHIFT employees. When an employee's
    preferred shift is full, the conflict is resolved by moving them to
    another open shift the same day, or (if the whole day is full) to the
    next day.
  * BONUS: each employee ranks their shifts per day (1st, 2nd, 3rd choice).

Usage
  python scheduler.py            # asks: demo data or type in your own
  python scheduler.py --demo     # run with generated demo data
  python scheduler.py --demo --seed 7
"""

import argparse
import random
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SHIFTS = ["Morning", "Afternoon", "Evening"]

MIN_PER_SHIFT = 2        # company minimum per shift per day
MAX_PER_SHIFT = 3        # capacity of a shift (used for conflict detection)
MAX_DAYS_PER_WEEK = 5    # max days one employee may work


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------
@dataclass
class Employee:
    name: str
    # day name -> ranked list of shifts (index 0 = first choice).
    # A day that is missing / empty means "I do not ask to work that day".
    preferences: dict = field(default_factory=dict)


@dataclass
class ScheduleResult:
    schedule: dict      # schedule[day][shift] -> list of employee names
    days_worked: dict   # employee name -> number of days worked
    log: list           # human readable conflict / warning messages


# --------------------------------------------------------------------------
# Scheduling logic
# --------------------------------------------------------------------------
def build_schedule(employees, rng=None):
    """Return a ScheduleResult for the given list of Employee objects."""
    rng = rng or random.Random()

    schedule = {d: {s: [] for s in SHIFTS} for d in DAYS}
    works_on = {d: {} for d in DAYS}                 # day -> {name: shift}
    days_worked = {e.name: 0 for e in employees}
    log = []
    deferred = []      # [(employee, ranking, original_day)] waiting for next day

    def can_work(emp, day):
        return days_worked[emp.name] < MAX_DAYS_PER_WEEK and emp.name not in works_on[day]

    def assign(emp, day, shift):
        schedule[day][shift].append(emp.name)
        works_on[day][emp.name] = shift
        days_worked[emp.name] += 1

    def unassign(emp, day, shift):
        schedule[day][shift].remove(emp.name)
        del works_on[day][emp.name]
        days_worked[emp.name] -= 1

    def coverage_ok(day_idx, day):
        """
        Reserve check: after a tentative assignment, can every remaining shift
        still reach its minimum of 2?  An employee can cover at most one shift
        per day and at most `days_left` more days, so for the last j days
        (j = 0 .. days remaining) we need enough employee-days to cover
        MIN_PER_SHIFT * 3 shifts per day.  This stops early-week preferences
        from using up everybody's 5 days before the weekend.
        """
        future_days = len(DAYS) - day_idx - 1
        per_day = MIN_PER_SHIFT * len(SHIFTS)
        shortfall_today = sum(max(0, MIN_PER_SHIFT - len(schedule[day][s])) for s in SHIFTS)
        left = {e.name: MAX_DAYS_PER_WEEK - days_worked[e.name] for e in employees}
        free_today = {e.name: 0 if e.name in works_on[day] else 1 for e in employees}

        for j in range(future_days + 1):
            # today's shortfall + the LAST j days
            have = sum(min(left[n], j + free_today[n]) for n in left)
            if have < shortfall_today + per_day * j:
                return False
            # the last j days on their own
            if j and sum(min(left[n], j) for n in left) < per_day * j:
                return False
        return True

    for day_idx, day in enumerate(DAYS):
        # ---- Step 1: build today's queue ---------------------------------
        carried = deferred                 # people bumped from yesterday go first
        deferred = []
        carried_names = {e.name for e, _, _ in carried}

        requesters = [e for e in employees
                      if e.preferences.get(day) and e.name not in carried_names]
        rng.shuffle(requesters)                                   # random tie-break
        requesters.sort(key=lambda e: days_worked[e.name])        # fewest days first

        queue = []
        for emp, old_ranking, origin in carried:
            queue.append((emp, emp.preferences.get(day) or old_ranking, origin))
        for emp in requesters:
            queue.append((emp, emp.preferences[day], None))

        # ---- Step 2: honour preferences, resolve conflicts ---------------
        for emp, ranking, origin in queue:
            if days_worked[emp.name] >= MAX_DAYS_PER_WEEK:
                log.append(f"{day}: {emp.name} already has {MAX_DAYS_PER_WEEK} days - "
                           f"request dropped.")
                continue

            # ranked shifts first, then any remaining shift as a fallback
            try_order = ranking + [s for s in SHIFTS if s not in ranking]

            placed = None
            for shift in try_order:
                if len(schedule[day][shift]) < MAX_PER_SHIFT:
                    placed = shift
                    break

            if placed is None:
                # every shift today is full -> try again tomorrow
                if day_idx < len(DAYS) - 1:
                    deferred.append((emp, ranking, origin or day))
                    log.append(f"{day}: all shifts full for {emp.name} - "
                               f"moved to {DAYS[day_idx + 1]}.")
                else:
                    log.append(f"{day}: all shifts full for {emp.name} and there is "
                               f"no next day - request could not be met.")
                continue

            assign(emp, day, placed)
            if not coverage_ok(day_idx, day):
                unassign(emp, day, placed)
                log.append(f"{day}: {emp.name}'s request held back - those days are "
                           f"needed to keep every shift staffed later in the week.")
                continue

            if origin:
                log.append(f"{day}: {emp.name} (bumped from {origin}) -> {placed}.")
            elif placed != ranking[0]:
                rank_txt = (f"choice #{ranking.index(placed) + 1}"
                            if placed in ranking else "not on their list")
                log.append(f"{day}: {emp.name}'s first choice ({ranking[0]}) is full "
                           f"-> assigned {placed} ({rank_txt}).")

        # ---- Step 3: enforce the minimum of 2 per shift -----------------
        for shift in SHIFTS:
            while len(schedule[day][shift]) < MIN_PER_SHIFT:
                pool = [e for e in employees if can_work(e, day)]
                if not pool:
                    log.append(f"WARNING {day} {shift}: only "
                               f"{len(schedule[day][shift])} employee(s) - nobody "
                               f"left who is under {MAX_DAYS_PER_WEEK} days.")
                    break
                # random choice, but only among people whose extra day still
                # leaves enough staff for the rest of the week
                safe = []
                for e in pool:
                    assign(e, day, shift)
                    if coverage_ok(day_idx, day):
                        safe.append(e)
                    unassign(e, day, shift)
                pick = rng.choice(safe or pool)
                assign(pick, day, shift)
                log.append(f"{day} {shift}: understaffed - randomly added {pick.name}.")

    return ScheduleResult(schedule, days_worked, log)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def format_schedule(result):
    """Return the weekly schedule as a text grid."""
    cell = lambda d, s: ", ".join(result.schedule[d][s]) or "-"
    w0 = max(len(d) for d in DAYS)
    widths = [max(len(s), max(len(cell(d, s)) for d in DAYS)) for s in SHIFTS]

    line = "+-" + "-" * w0 + "-+" + "+".join("-" + "-" * w + "-" for w in widths) + "+"
    out = [line,
           "| " + "Day".ljust(w0) + " |" +
           "|".join(" " + s.ljust(w) + " " for s, w in zip(SHIFTS, widths)) + "|",
           line]
    for d in DAYS:
        out.append("| " + d.ljust(w0) + " |" +
                   "|".join(" " + cell(d, s).ljust(w) + " " for s, w in zip(SHIFTS, widths)) + "|")
        out.append(line)
    return "\n".join(out)


def format_employee_summary(result):
    """One line per employee: days worked and where."""
    lines = []
    name_w = max((len(n) for n in result.days_worked), default=4)
    for name in sorted(result.days_worked):
        parts = []
        for d in DAYS:
            for s in SHIFTS:
                if name in result.schedule[d][s]:
                    parts.append(f"{d[:3]}:{s[:3]}")
        lines.append(f"  {name.ljust(name_w)}  {result.days_worked[name]} day(s)  "
                     + "  ".join(parts))
    return "\n".join(lines)


def print_report(result):
    print("\n" + "=" * 30 + " WEEKLY SCHEDULE " + "=" * 30)
    print(format_schedule(result))
    print("\nEmployee summary (Mon..Sun, Mor/Aft/Eve):")
    print(format_employee_summary(result))
    print("\nConflict / scheduling log:")
    if result.log:
        for msg in result.log:
            print("  - " + msg)
    else:
        print("  (no conflicts)")


# --------------------------------------------------------------------------
# Input (console)
# --------------------------------------------------------------------------
def parse_ranking(text):
    """
    'm a e' / 'morning, evening' / 'e' -> ['Evening', ...]
    Blank or 'off' -> [] (day off).  Returns None if the text is invalid.
    """
    text = text.strip().lower()
    if text in ("", "off", "-", "none"):
        return []
    ranking = []
    for token in text.replace(",", " ").split():
        match = next((s for s in SHIFTS if s.lower().startswith(token[0])), None)
        if match is None or (len(token) > 1 and not match.lower().startswith(token)):
            return None
        if match not in ranking:
            ranking.append(match)
    return ranking


def read_employees_from_console():
    employees = []
    print("\nEnter employees. Shifts: M = Morning, A = Afternoon, E = Evening.")
    print("For each day list your shifts in order of preference (e.g. 'E M').")
    print("Press Enter (or type 'off') if you do not want to work that day.\n")

    while True:
        name = input("Employee name (blank to finish): ").strip()
        if not name:
            if employees:
                break
            print("  Please enter at least one employee.")
            continue
        if any(e.name.lower() == name.lower() for e in employees):
            print("  That name is already entered.")
            continue

        emp = Employee(name)
        for day in DAYS:
            while True:
                ranking = parse_ranking(input(f"  {day:<9} preference for {name}: "))
                if ranking is not None:
                    break
                print("    Invalid entry - use M, A, E (e.g. 'M E') or leave blank.")
            if ranking:
                emp.preferences[day] = ranking
        employees.append(emp)
        print()
    return employees


def make_demo_employees(seed=1):
    """Generate 12 employees with random ranked preferences."""
    rng = random.Random(seed)
    names = ["Alice", "Bob", "Carmen", "David", "Elena", "Frank",
             "Grace", "Hector", "Irene", "Jamal", "Kira", "Liam"]
    employees = []
    for name in names:
        emp = Employee(name)
        for day in rng.sample(DAYS, k=rng.choice([4, 5, 5, 6])):
            ranking = SHIFTS[:]
            rng.shuffle(ranking)
            emp.preferences[day] = ranking[:rng.choice([1, 2, 3])]
        employees.append(emp)
    return employees


def print_preferences(employees):
    print("\nEmployee preferences (ranked, first choice first):")
    for emp in employees:
        parts = [f"{d[:3]}:{'>'.join(s[0] for s in emp.preferences[d])}"
                 for d in DAYS if d in emp.preferences]
        print(f"  {emp.name:<8} " + "  ".join(parts))


# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Employee shift scheduler")
    parser.add_argument("--demo", action="store_true", help="use generated demo data")
    parser.add_argument("--seed", type=int, default=None,
                        help="random seed (repeatable output)")
    args = parser.parse_args()

    use_demo = args.demo
    if not use_demo:
        use_demo = input("Use demo data? (y = demo, n = type my own): ").strip().lower() == "y"

    employees = make_demo_employees() if use_demo else read_employees_from_console()
    print_preferences(employees)

    result = build_schedule(employees, random.Random(args.seed))
    print_report(result)


if __name__ == "__main__":
    main()
