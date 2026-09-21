/*
 * Assignment 4 - Implementing Control Structures
 * Employee Shift Scheduler (C# version, .NET 8 console app)
 *
 * Rules enforced
 *   - 7 days a week, 3 shifts a day (Morning / Afternoon / Evening)
 *   - An employee works at most ONE shift per day
 *   - An employee works at most 5 days per week
 *   - Every shift needs at least 2 employees (random top-up from employees
 *     who are still under 5 days)
 *   - A shift holds at most MaxPerShift employees. When an employee's preferred
 *     shift is full the conflict is resolved by moving them to another open
 *     shift the same day, or (if the whole day is full) to the next day.
 *   - BONUS: each employee ranks their shifts per day (1st, 2nd, 3rd choice).
 *
 * Usage
 *   dotnet run                    -> asks: demo data or type in your own
 *   dotnet run -- --demo          -> generated demo data
 *   dotnet run -- --demo --seed 7 -> repeatable output
 */

using System.Text;

namespace ShiftScheduler;

// ---------------------------------------------------------------------------
// Data structures
// ---------------------------------------------------------------------------
public enum Shift { Morning, Afternoon, Evening }

public class Employee
{
    public string Name { get; }

    // day index (0 = Monday) -> ranked shifts (index 0 = first choice).
    // A day that is missing / empty means "I do not ask to work that day".
    public Dictionary<int, List<Shift>> Preferences { get; } = new();

    public Employee(string name) => Name = name;
}

public class ScheduleResult
{
    // Schedule[day, shift] -> names of the employees on that shift
    public List<string>[,] Schedule { get; } = new List<string>[7, 3];
    public Dictionary<string, int> DaysWorked { get; } = new();
    public List<string> Log { get; } = new();

    public ScheduleResult()
    {
        for (int d = 0; d < 7; d++)
            for (int s = 0; s < 3; s++)
                Schedule[d, s] = new List<string>();
    }
}

// ---------------------------------------------------------------------------
// Scheduling logic
// ---------------------------------------------------------------------------
public static class Scheduler
{
    public static readonly string[] Days =
        { "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday" };

    public static readonly Shift[] AllShifts = Enum.GetValues<Shift>();

    public const int MinPerShift = 2;       // company minimum per shift per day
    public const int MaxPerShift = 3;       // capacity of a shift (conflict detection)
    public const int MaxDaysPerWeek = 5;    // max days one employee may work

    private record Deferred(Employee Emp, List<Shift> Ranking, string OriginDay);
    private record QueueItem(Employee Emp, List<Shift> Ranking, string? Origin);

    public static ScheduleResult Build(List<Employee> employees, Random rng)
    {
        var result = new ScheduleResult();
        var log = result.Log;
        var worksOn = Enumerable.Range(0, 7).Select(_ => new HashSet<string>()).ToArray();
        var daysWorked = employees.ToDictionary(e => e.Name, _ => 0);
        var deferred = new List<Deferred>();     // bumped employees waiting for the next day

        // ----- small helpers (local functions) -----------------------------
        bool CanWork(Employee e, int d) =>
            daysWorked[e.Name] < MaxDaysPerWeek && !worksOn[d].Contains(e.Name);

        void Assign(Employee e, int d, Shift s)
        {
            result.Schedule[d, (int)s].Add(e.Name);
            worksOn[d].Add(e.Name);
            daysWorked[e.Name]++;
        }

        void Unassign(Employee e, int d, Shift s)
        {
            result.Schedule[d, (int)s].Remove(e.Name);
            worksOn[d].Remove(e.Name);
            daysWorked[e.Name]--;
        }

        // Reserve check: after a tentative assignment, can every remaining shift
        // still reach its minimum of 2?  An employee covers at most one shift per
        // day and at most (5 - daysWorked) more days, so for the last j days
        // (j = 0 .. days remaining) we need enough employee-days.  This stops
        // early-week preferences from using up everybody's 5 days.
        bool CoverageOk(int d)
        {
            int futureDays = Days.Length - d - 1;
            int perDay = MinPerShift * AllShifts.Length;
            int shortfallToday = AllShifts.Sum(s => Math.Max(0, MinPerShift - result.Schedule[d, (int)s].Count));

            for (int j = 0; j <= futureDays; j++)
            {
                int haveWithToday = 0, haveFutureOnly = 0;
                foreach (var e in employees)
                {
                    int left = MaxDaysPerWeek - daysWorked[e.Name];
                    int freeToday = worksOn[d].Contains(e.Name) ? 0 : 1;
                    haveWithToday += Math.Min(left, j + freeToday);
                    haveFutureOnly += Math.Min(left, j);
                }
                if (haveWithToday < shortfallToday + perDay * j) return false;
                if (j > 0 && haveFutureOnly < perDay * j) return false;
            }
            return true;
        }

        // ----- main loop: one iteration per day ----------------------------
        for (int d = 0; d < Days.Length; d++)
        {
            string day = Days[d];

            // Step 1: build today's queue (bumped people first, then requesters)
            var carried = deferred;
            deferred = new List<Deferred>();
            var carriedNames = carried.Select(c => c.Emp.Name).ToHashSet();

            var requesters = employees
                .Where(e => e.Preferences.TryGetValue(d, out var r) && r.Count > 0
                            && !carriedNames.Contains(e.Name))
                .ToList();
            Shuffle(requesters, rng);                                        // random tie-break
            requesters = requesters.OrderBy(e => daysWorked[e.Name]).ToList(); // fewest days first (stable)

            var queue = new List<QueueItem>();
            foreach (var c in carried)
            {
                var todayRanking = c.Emp.Preferences.TryGetValue(d, out var r) && r.Count > 0 ? r : c.Ranking;
                queue.Add(new QueueItem(c.Emp, todayRanking, c.OriginDay));
            }
            foreach (var e in requesters)
                queue.Add(new QueueItem(e, e.Preferences[d], null));

            // Step 2: honour preferences and resolve conflicts
            foreach (var item in queue)
            {
                var emp = item.Emp;
                var ranking = item.Ranking;

                if (daysWorked[emp.Name] >= MaxDaysPerWeek)
                {
                    log.Add($"{day}: {emp.Name} already has {MaxDaysPerWeek} days - request dropped.");
                    continue;
                }

                // ranked shifts first, then any remaining shift as a fallback
                var tryOrder = ranking.Concat(AllShifts.Where(s => !ranking.Contains(s))).ToList();

                Shift? placed = null;
                foreach (var shift in tryOrder)
                {
                    if (result.Schedule[d, (int)shift].Count < MaxPerShift)
                    {
                        placed = shift;
                        break;
                    }
                }

                if (placed is null)
                {
                    // every shift today is full -> try again tomorrow
                    if (d < Days.Length - 1)
                    {
                        deferred.Add(new Deferred(emp, ranking, item.Origin ?? day));
                        log.Add($"{day}: all shifts full for {emp.Name} - moved to {Days[d + 1]}.");
                    }
                    else
                    {
                        log.Add($"{day}: all shifts full for {emp.Name} and there is no next day - request could not be met.");
                    }
                    continue;
                }

                Shift chosen = placed.Value;
                Assign(emp, d, chosen);

                if (!CoverageOk(d))
                {
                    Unassign(emp, d, chosen);
                    log.Add($"{day}: {emp.Name}'s request held back - those days are needed to keep every shift staffed later in the week.");
                    continue;
                }

                if (item.Origin != null)
                {
                    log.Add($"{day}: {emp.Name} (bumped from {item.Origin}) -> {chosen}.");
                }
                else if (chosen != ranking[0])
                {
                    string rankText = ranking.Contains(chosen)
                        ? $"choice #{ranking.IndexOf(chosen) + 1}"
                        : "not on their list";
                    log.Add($"{day}: {emp.Name}'s first choice ({ranking[0]}) is full -> assigned {chosen} ({rankText}).");
                }
            }

            // Step 3: enforce the minimum of 2 per shift
            foreach (var shift in AllShifts)
            {
                while (result.Schedule[d, (int)shift].Count < MinPerShift)
                {
                    var pool = employees.Where(e => CanWork(e, d)).ToList();
                    if (pool.Count == 0)
                    {
                        log.Add($"WARNING {day} {shift}: only {result.Schedule[d, (int)shift].Count} employee(s) - nobody left who is under {MaxDaysPerWeek} days.");
                        break;
                    }

                    // random choice, but only among people whose extra day still
                    // leaves enough staff for the rest of the week
                    var safe = new List<Employee>();
                    foreach (var e in pool)
                    {
                        Assign(e, d, shift);
                        if (CoverageOk(d)) safe.Add(e);
                        Unassign(e, d, shift);
                    }
                    var candidates = safe.Count > 0 ? safe : pool;
                    var pick = candidates[rng.Next(candidates.Count)];
                    Assign(pick, d, shift);
                    log.Add($"{day} {shift}: understaffed - randomly added {pick.Name}.");
                }
            }
        }

        foreach (var kv in daysWorked) result.DaysWorked[kv.Key] = kv.Value;
        return result;
    }

    // Fisher-Yates shuffle
    private static void Shuffle<T>(IList<T> list, Random rng)
    {
        for (int i = list.Count - 1; i > 0; i--)
        {
            int j = rng.Next(i + 1);
            (list[i], list[j]) = (list[j], list[i]);
        }
    }
}

// ---------------------------------------------------------------------------
// Output
// ---------------------------------------------------------------------------
public static class Report
{
    public static string FormatSchedule(ScheduleResult r)
    {
        string Cell(int d, int s) => r.Schedule[d, s].Count == 0 ? "-" : string.Join(", ", r.Schedule[d, s]);

        int w0 = Scheduler.Days.Max(x => x.Length);
        var widths = new int[3];
        for (int s = 0; s < 3; s++)
        {
            widths[s] = ((Shift)s).ToString().Length;
            for (int d = 0; d < 7; d++) widths[s] = Math.Max(widths[s], Cell(d, s).Length);
        }

        string line = "+-" + new string('-', w0) + "-+" +
                      string.Join("+", widths.Select(w => new string('-', w + 2))) + "+";

        var sb = new StringBuilder();
        sb.AppendLine(line);
        sb.AppendLine("| " + "Day".PadRight(w0) + " |" +
                      string.Join("|", Enumerable.Range(0, 3).Select(s => " " + ((Shift)s).ToString().PadRight(widths[s]) + " ")) + "|");
        sb.AppendLine(line);
        for (int d = 0; d < 7; d++)
        {
            sb.AppendLine("| " + Scheduler.Days[d].PadRight(w0) + " |" +
                          string.Join("|", Enumerable.Range(0, 3).Select(s => " " + Cell(d, s).PadRight(widths[s]) + " ")) + "|");
            sb.AppendLine(line);
        }
        return sb.ToString().TrimEnd();
    }

    public static string FormatEmployeeSummary(ScheduleResult r)
    {
        var sb = new StringBuilder();
        int nameW = r.DaysWorked.Keys.Max(n => n.Length);
        foreach (var name in r.DaysWorked.Keys.OrderBy(n => n, StringComparer.OrdinalIgnoreCase))
        {
            var parts = new List<string>();
            for (int d = 0; d < 7; d++)
                for (int s = 0; s < 3; s++)
                    if (r.Schedule[d, s].Contains(name))
                        parts.Add($"{Scheduler.Days[d][..3]}:{((Shift)s).ToString()[..3]}");
            sb.AppendLine($"  {name.PadRight(nameW)}  {r.DaysWorked[name]} day(s)  {string.Join("  ", parts)}");
        }
        return sb.ToString().TrimEnd();
    }

    public static void Print(ScheduleResult r)
    {
        Console.WriteLine("\n" + new string('=', 30) + " WEEKLY SCHEDULE " + new string('=', 30));
        Console.WriteLine(FormatSchedule(r));
        Console.WriteLine("\nEmployee summary (Mon..Sun, Mor/Aft/Eve):");
        Console.WriteLine(FormatEmployeeSummary(r));
        Console.WriteLine("\nConflict / scheduling log:");
        if (r.Log.Count == 0) Console.WriteLine("  (no conflicts)");
        foreach (var msg in r.Log) Console.WriteLine("  - " + msg);
    }

    public static void PrintPreferences(List<Employee> employees)
    {
        Console.WriteLine("\nEmployee preferences (ranked, first choice first):");
        foreach (var e in employees)
        {
            var parts = new List<string>();
            for (int d = 0; d < 7; d++)
                if (e.Preferences.TryGetValue(d, out var r) && r.Count > 0)
                    parts.Add($"{Scheduler.Days[d][..3]}:{string.Join(">", r.Select(s => s.ToString()[0]))}");
            Console.WriteLine($"  {e.Name,-8} {string.Join("  ", parts)}");
        }
    }
}

// ---------------------------------------------------------------------------
// Program entry point + console input
// ---------------------------------------------------------------------------
public static class Program
{
    public static void Main(string[] args)
    {
        bool demo = args.Contains("--demo");
        int? seed = null;
        int seedIdx = Array.IndexOf(args, "--seed");
        if (seedIdx >= 0 && seedIdx + 1 < args.Length && int.TryParse(args[seedIdx + 1], out int sv))
            seed = sv;

        if (!demo)
        {
            Console.Write("Use demo data? (y = demo, n = type my own): ");
            demo = (Console.ReadLine() ?? "").Trim().ToLower() == "y";
        }

        List<Employee> employees = demo ? MakeDemoEmployees() : ReadEmployeesFromConsole();
        Report.PrintPreferences(employees);

        var rng = seed.HasValue ? new Random(seed.Value) : new Random();
        ScheduleResult result = Scheduler.Build(employees, rng);
        Report.Print(result);
    }

    /// 'm a e' / 'morning, evening' / 'e' -> ranked list.  Blank / 'off' -> empty list.
    /// Returns null when the text is invalid.
    private static List<Shift>? ParseRanking(string text)
    {
        text = text.Trim().ToLower();
        if (text is "" or "off" or "-" or "none") return new List<Shift>();

        var ranking = new List<Shift>();
        foreach (var token in text.Replace(',', ' ').Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
            Shift? match = null;
            foreach (var s in Scheduler.AllShifts)
            {
                if (s.ToString().ToLower().StartsWith(token))
                {
                    match = s;
                    break;
                }
            }
            if (match is null) return null;
            if (!ranking.Contains(match.Value)) ranking.Add(match.Value);
        }
        return ranking;
    }

    private static List<Employee> ReadEmployeesFromConsole()
    {
        var employees = new List<Employee>();
        Console.WriteLine("\nEnter employees. Shifts: M = Morning, A = Afternoon, E = Evening.");
        Console.WriteLine("For each day list your shifts in order of preference (e.g. 'E M').");
        Console.WriteLine("Press Enter (or type 'off') if you do not want to work that day.\n");

        while (true)
        {
            Console.Write("Employee name (blank to finish): ");
            string name = (Console.ReadLine() ?? "").Trim();

            if (name.Length == 0)
            {
                if (employees.Count > 0) break;
                Console.WriteLine("  Please enter at least one employee.");
                continue;
            }
            if (employees.Any(e => e.Name.Equals(name, StringComparison.OrdinalIgnoreCase)))
            {
                Console.WriteLine("  That name is already entered.");
                continue;
            }

            var emp = new Employee(name);
            for (int d = 0; d < 7; d++)
            {
                List<Shift>? ranking;
                while (true)
                {
                    Console.Write($"  {Scheduler.Days[d],-9} preference for {name}: ");
                    ranking = ParseRanking(Console.ReadLine() ?? "");
                    if (ranking != null) break;
                    Console.WriteLine("    Invalid entry - use M, A, E (e.g. 'M E') or leave blank.");
                }
                if (ranking.Count > 0) emp.Preferences[d] = ranking;
            }
            employees.Add(emp);
            Console.WriteLine();
        }
        return employees;
    }

    /// 12 employees with random ranked preferences.
    private static List<Employee> MakeDemoEmployees(int seed = 1)
    {
        var rng = new Random(seed);
        string[] names = { "Alice", "Bob", "Carmen", "David", "Elena", "Frank",
                           "Grace", "Hector", "Irene", "Jamal", "Kira", "Liam" };
        int[] dayCounts = { 4, 5, 5, 6 };
        var employees = new List<Employee>();

        foreach (var name in names)
        {
            var emp = new Employee(name);
            int howMany = dayCounts[rng.Next(dayCounts.Length)];
            var chosenDays = Enumerable.Range(0, 7).OrderBy(_ => rng.Next()).Take(howMany);

            foreach (int d in chosenDays)
            {
                var ranking = Scheduler.AllShifts.OrderBy(_ => rng.Next()).ToList();
                emp.Preferences[d] = ranking.Take(rng.Next(1, 4)).ToList();
            }
            employees.Add(emp);
        }
        return employees;
    }
}
