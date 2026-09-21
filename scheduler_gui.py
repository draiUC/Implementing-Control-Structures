#!/usr/bin/env python3
"""
Assignment 4 - OPTIONAL GUI (Python / Tkinter)

Input : type an employee name, pick 1st / 2nd / 3rd shift choice for every day
        (leave the 1st choice blank = does not want to work that day), click
        "Add employee".  "Load demo data" fills in 12 sample employees.
Output: "Generate schedule" fills the Schedule tab (day x shift grid), the
        Employee summary tab and the Conflict log tab.

Uses the scheduling logic in scheduler.py (keep both files in one folder).
Run:  python scheduler_gui.py
"""

import random
import tkinter as tk
from tkinter import ttk, messagebox

from scheduler import (DAYS, SHIFTS, Employee, build_schedule, make_demo_employees)

BLANK = ""


class SchedulerApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.master.title("Employee Shift Scheduler")
        self.pack(fill="both", expand=True)
        self.employees = []
        self._build_widgets()

    # ------------------------------------------------------------------ UI
    def _build_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        self.notebook = notebook

        self._build_input_tab(notebook)
        self._build_schedule_tab(notebook)
        self._build_summary_tab(notebook)
        self._build_log_tab(notebook)

    def _build_input_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="1. Employees")

        # ---- entry form
        form = ttk.LabelFrame(tab, text="New employee (rank shifts per day)", padding=8)
        form.pack(fill="x")

        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=24).grid(row=0, column=1, columnspan=2, sticky="w")

        for col, text in enumerate(["Day", "1st choice", "2nd choice", "3rd choice"]):
            ttk.Label(form, text=text, font=("TkDefaultFont", 9, "bold")).grid(row=1, column=col, padx=4, pady=(8, 2))

        self.combos = {}        # day -> [combo1, combo2, combo3]
        for r, day in enumerate(DAYS, start=2):
            ttk.Label(form, text=day).grid(row=r, column=0, sticky="w", padx=4)
            row = []
            for c in range(3):
                cb = ttk.Combobox(form, values=[BLANK] + SHIFTS, width=11, state="readonly")
                cb.set(BLANK)
                cb.grid(row=r, column=c + 1, padx=4, pady=1)
                row.append(cb)
            self.combos[day] = row

        buttons = ttk.Frame(form)
        buttons.grid(row=9, column=0, columnspan=4, pady=(8, 0), sticky="w")
        ttk.Button(buttons, text="Add employee", command=self.add_employee).pack(side="left", padx=2)
        ttk.Button(buttons, text="Clear form", command=self.clear_form).pack(side="left", padx=2)

        # ---- employee list
        lst = ttk.LabelFrame(tab, text="Employees entered", padding=8)
        lst.pack(fill="both", expand=True, pady=(8, 0))

        self.emp_tree = ttk.Treeview(lst, columns=("name", "days"), show="headings", height=6)
        self.emp_tree.heading("name", text="Name")
        self.emp_tree.heading("days", text="Requested days (ranked shifts)")
        self.emp_tree.column("name", width=110, stretch=False)
        self.emp_tree.column("days", width=520)
        self.emp_tree.pack(fill="both", expand=True)

        bar = ttk.Frame(lst)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Remove selected", command=self.remove_selected).pack(side="left", padx=2)
        ttk.Button(bar, text="Load demo data", command=self.load_demo).pack(side="left", padx=2)
        ttk.Button(bar, text="Generate schedule  >", command=self.generate).pack(side="right", padx=2)

    def _build_schedule_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="2. Schedule")
        cols = ("day",) + tuple(SHIFTS)
        self.sched_tree = ttk.Treeview(tab, columns=cols, show="headings", height=7)
        self.sched_tree.heading("day", text="Day")
        self.sched_tree.column("day", width=90, stretch=False)
        for s in SHIFTS:
            self.sched_tree.heading(s, text=s)
            self.sched_tree.column(s, width=220)
        self.sched_tree.pack(fill="both", expand=True)

    def _build_summary_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="3. Employee summary")
        self.summary_text = tk.Text(tab, height=16, width=90, font=("Courier", 10), state="disabled")
        self.summary_text.pack(fill="both", expand=True)

    def _build_log_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="4. Conflict log")
        self.log_text = tk.Text(tab, height=16, width=90, font=("Courier", 10), state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------ handlers
    def clear_form(self):
        self.name_var.set("")
        for row in self.combos.values():
            for cb in row:
                cb.set(BLANK)

    def add_employee(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Please type the employee's name.")
            return
        if any(e.name.lower() == name.lower() for e in self.employees):
            messagebox.showwarning("Duplicate", f"'{name}' has already been added.")
            return

        emp = Employee(name)
        for day, row in self.combos.items():
            ranking = []
            for cb in row:
                value = cb.get()
                if value and value not in ranking:
                    ranking.append(value)
            if ranking:
                emp.preferences[day] = ranking
        self.employees.append(emp)
        self._refresh_employee_list()
        self.clear_form()

    def remove_selected(self):
        selected = self.emp_tree.selection()
        names = {self.emp_tree.item(i, "values")[0] for i in selected}
        self.employees = [e for e in self.employees if e.name not in names]
        self._refresh_employee_list()

    def load_demo(self):
        self.employees = make_demo_employees()
        self._refresh_employee_list()

    def _refresh_employee_list(self):
        self.emp_tree.delete(*self.emp_tree.get_children())
        for emp in self.employees:
            days = "   ".join(f"{d[:3]}:{'>'.join(s[0] for s in emp.preferences[d])}"
                              for d in DAYS if d in emp.preferences)
            self.emp_tree.insert("", "end", values=(emp.name, days or "(no days requested)"))

    def generate(self):
        if not self.employees:
            messagebox.showwarning("No employees", "Add at least one employee first.")
            return
        result = build_schedule(self.employees, random.Random())

        # schedule grid
        self.sched_tree.delete(*self.sched_tree.get_children())
        for day in DAYS:
            cells = [", ".join(result.schedule[day][s]) or "-" for s in SHIFTS]
            self.sched_tree.insert("", "end", values=(day, *cells))

        # employee summary
        lines = []
        for name in sorted(result.days_worked):
            parts = [f"{d[:3]}:{s[:3]}" for d in DAYS for s in SHIFTS if name in result.schedule[d][s]]
            lines.append(f"{name:<10} {result.days_worked[name]} day(s)   " + "  ".join(parts))
        self._set_text(self.summary_text, "\n".join(lines))

        # log
        self._set_text(self.log_text,
                       "\n".join("- " + m for m in result.log) or "(no conflicts)")

        if any(m.startswith("WARNING") for m in result.log):
            messagebox.showwarning("Understaffed",
                                   "Some shifts could not reach 2 employees - see the Conflict log tab.\n"
                                   "(You need about 9 or more employees to staff 42 shifts at 5 days each.)")
        self.notebook.select(1)

    @staticmethod
    def _set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    SchedulerApp(root)
    root.mainloop()
