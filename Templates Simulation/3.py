import json
# TOPIC [Functions, slide 13]: import random (library with pre-defined functions).
import random

# TOPIC [Simulation, slides 10-11]: the simpy library: Environment, Resource, env.process, env.timeout.
import simpy


WARMUP_HOURS = 1440.0
# TOPIC [Dictionaries, slide 2]: agreed handling time per ship type.
AGREED_TIME_FEEDER = 104.0
AGREED_TIME_DEEPSEA = 130.0
ONTIME_TARGET = 90.0

# ------------------------------- Model parameters --------------------------------------
# Assumption: simulation time 0 is Monday 00:00; time is measured in hours.
AGREED_TIME = {"F": AGREED_TIME_FEEDER, "D": AGREED_TIME_DEEPSEA}

BOOKING_HOURS = 5 * 24  # Task 1 takes five days
# TOPIC [Dictionaries, slides 2-6]: values looked up by key ("F"/"D"); ranges are tuples (Tuples and Sets, slide 2).
FEE_RANGE = {"F": (4_000, 12_000), "D": (25_000, 60_000)}
FEE_LIMIT = {"F": 9_000, "D": 50_000}
P_DIVERT = {"F": 0.30, "D": 0.10}

P_FEEDER_NEEDS_TUG = 0.30
FEEDER_TOW_HOURS = 6
DEEPSEA_TOW_MEAN_HOURS = 18

# TOPIC [Lists, slides 2, 4]: list of the three crane team names.
TEAMS = ["alpha", "bravo", "charlie"]  # the three speed classes of the roster
TEAM_PROBABILITIES = [0.40, 0.35, 0.25]
# TOPIC [Dictionaries, slide 2]: unloading hours per team name (dictionary).
UNLOAD_HOURS = {"alpha": 8, "bravo": 11, "charlie": 16}
P_CHARLIE_RESTACK = 0.25
P_CHARLIE_FIXES_ITSELF = 0.20
RESTACK_HOURS = 2
AUTOMATION_SAVING_HOURS = 3  # automated cranes: every unloading is 3 hours shorter

SCAN_HOURS = 4
P_MINOR = 0.08
P_MAJOR = 0.02
MINOR_EXTRA_HOURS = 1
MAJOR_EXTRA_HOURS = 4

OPEN_HOUR, CLOSE_HOUR = 6, 22  # opening hours, Monday-Saturday
BARGE_HOUR = 18
BARGE_SAIL_RANGE = (5, 9)

# Investment options: (label, value, cost in euro over the simulation horizon)
# TOPIC [Lists, slide 2]: list of tuples: label, number of extra teams, cost.
EXTRA_TEAM_OPTIONS = [
    ("No extra team", 0, 0),
    ("One extra team", 1, 55_000),
    ("Two extra teams", 2, 77_000),
]
# (label, automated_cranes, second_scanning_crew, cost in euro)
# TOPIC [Lists, slide 2]: list of tuples describing each process alternative.
PROCESS_OPTIONS = [
    ("No process investment", False, False, 0),
    ("Automated cranes", True, False, 35_000),
    ("Second customs team", False, True, 28_000),
]


# ------------------------------- Calendar helpers --------------------------------------
def is_open_day(day_number):
    """Monday-Saturday are open (day 0 = Monday), Sunday (day 6) is closed."""
    # TOPIC [Variables, Expressions, Types, slide 9]: % (modulus) gives the weekday, != is a comparator (Comparators, slide 8).
    return day_number % 7 != 6


def time_until_open(now):
    """Hours to wait until the terminal is open (0 if it is open right now)."""
    # TOPIC [Variables, Expressions, Types, slide 21]: int(...) converts a number to an int; //, - and * are numerical operators (slides 7-8).
    day = int(now // 24)
    hour = now - day * 24
    # TOPIC [Conditional execution, slides 5, 8-9]: if / return: decide with comparators (Comparators, slides 3-5).
    if is_open_day(day):
        if hour < OPEN_HOUR:
            return OPEN_HOUR - hour
        if hour < CLOSE_HOUR:
            return 0.0
    next_day = day + 1
    # TOPIC [Iteration, slides 4-6]: while loop: skip days until an open day is found (not: Comparators, slide 16).
    while not is_open_day(next_day):
        next_day += 1
    return next_day * 24 + OPEN_HOUR - now


def time_until_barge(now):
    """Hours until the next barge departure (18:00 on an opening day)."""
    day = int(now // 24)
    hour = now - day * 24
    # TOPIC [Comparators, Boolean expressions, slides 11-12]: and: both conditions must be True.
    if is_open_day(day) and hour < BARGE_HOUR:
        return BARGE_HOUR - hour
    next_day = day + 1
    # TOPIC [Iteration, slides 4-6]: while loop: skip days until an open day is found.
    while not is_open_day(next_day):
        next_day += 1
    return next_day * 24 + BARGE_HOUR - now


# ------------------------------- Exercise 3: evaluation --------------------------------
def compute_ontime_percentage(sim):
    """KPI - percentage of the measured ships (announced from the warm-up end onwards)
    that were handled within the agreed handling time.
    PATTERN: statistics collected during the run and evaluated after it (data
    collection / monitoring) (Simulation slides 14-16): the simulator counts, per ship that reached the
    inland terminal, whether it was on time (ontime_F/D) and how many were measured
    (total_F/D); this function only combines those counters (parameter only, no
    globals). Returns 0.0 if no ship was measured."""
    measured = sim.total_F + sim.total_D
    # TOPIC [Exceptions, slide 2]: avoid division by zero (Conditional execution slide 5).
    if measured == 0:
        return 0.0
    return (sim.ontime_F + sim.ontime_D) / measured * 100


def evaluate_investments(arrival_info, runs=10):
    """Simulates the 3 x 3 investment alternatives, prints the table of average on-time
    percentages, the number of warm-up ships and the cheapest alternative reaching the
    target.
    PATTERN: replications (Simulation slides 18-19): the arrivals are fixed (json) but handling times
    and decisions are random, so every alternative is simulated `runs` times with a
    fresh simulator object (independent counters) and the on-time percentage is
    averaged. PATTERN: parameterised scenario (Functions slide 5): the alternatives only differ
    in the keyword arguments passed to simulate() (extra teams, automated cranes, second
    customs team). Costs are added per alternative and the cheapest one meeting the
    target is selected."""
    alternatives = []  # (cost, extra label, process label, average percentage)
    table = []
    warmup_ships = 0
    # TOPIC [Iteration, slides 9-10]: for loop over a list of tuples.
    for extra_label, extra_gangs, extra_cost in EXTRA_TEAM_OPTIONS:
        row = []
        for process_label, automated, second_crew, process_cost in PROCESS_OPTIONS:
            percentages = []
            # TOPIC [Simulation, slides 18-19]: replications: simulate the same alternative several times (Iteration slides 11-13: range).
            for run in range(runs):
                # TOPIC [Object orientation: constructors, slides 3-5]: a new object per run, so the counters start at 0.
                sim = ContainerTerminalSimulator()
                sim.simulate(
                    arrival_info,
                    extra_gangs=extra_gangs,
                    automated_cranes=automated,
                    second_scanning_crew=second_crew,
                )
                percentages.append(compute_ontime_percentage(sim))
                warmup_ships = sim.nr_warmup_ships
            # TOPIC [Lists, slides 3, 12]: average of a list with sum and len.
            average = sum(percentages) / len(percentages)
            row.append(average)
            alternatives.append(
                (extra_cost + process_cost, extra_label, process_label, average)
            )
        table.append((extra_label, row))

    print(f"\nAverage on-time handling percentage over {runs} runs "
          f"(target {ONTIME_TARGET:.0f}%):")
    print(f"Ships left out as warm-up (announced before hour {WARMUP_HOURS:.0f}): "
          f"{warmup_ships}\n")
    header = f"{'Scenario':<18}"
    for option in PROCESS_OPTIONS:
        header = header + f"{option[0]:>24}"
    print(header)
    print("-" * len(header))
    for extra_label, row in table:
        line = f"{extra_label:<18}"
        for value in row:
            line = line + f"{value:>23.1f}%"
        print(line)

    cheapest = None  # cheapest alternative reaching the target (ties: higher percentage)
    best = None  # alternative with the highest percentage, in case none reaches the target
    for alternative in alternatives:
        # TOPIC [Comparators, Boolean expressions, slides 3-5]: comparator against the target.
        if alternative[3] >= ONTIME_TARGET:
            # TOPIC [Comparators, Boolean expressions, slides 13-15]: or: either there is no cheapest yet or this one is cheaper.
            if (cheapest is None or alternative[0] < cheapest[0]
                    or (alternative[0] == cheapest[0] and alternative[3] > cheapest[3])):
                cheapest = alternative
        if best is None or alternative[3] > best[3]:
            best = alternative
    if cheapest is not None:
        print(f"\nCheapest alternative reaching {ONTIME_TARGET:.0f}%: {cheapest[1]} + "
              f"{cheapest[2]} (EUR {cheapest[0]:,}, on-time {cheapest[3]:.1f}%)")
    else:
        print(f"\nNo alternative reaches {ONTIME_TARGET:.0f}%. Best one: {best[1]} + "
              f"{best[2]} (EUR {best[0]:,}, on-time {best[3]:.1f}%)")


# TOPIC [Object orientation: introduction, slides 6-7]: class with attributes and methods (self); see also Object orientation: constructors.
class ContainerTerminalSimulator:
    """A SimPy simulation model for a container terminal handling ships."""

    def __init__(self):
        # TOPIC [Object orientation: constructors, slides 3-5]: the constructor initialises every attribute (counters start at 0).
        # Counters required by the checker
        self.nr_arrived_ships_F = 0  # Count of all announced feeder ships.
        self.nr_arrived_ships_D = 0  # Count of all announced deep-sea ships.
        self.nr_quoted_ships_F = 0  # Count of fee quotations sent for feeder ships.
        self.nr_quoted_ships_D = 0  # Count of fee quotations sent for deep-sea ships.
        self.sum_fees_F = 0.0  # Sum of all handling fees quoted for feeder ships.
        self.sum_fees_D = 0.0  # Sum of all handling fees quoted for deep-sea ships.
        self.nr_fees_F_above = 0  # Count of feeder fees above the limit.
        self.nr_fees_D_above = 0  # Count of deep-sea fees above the limit.
        self.nr_diverted_ships_F = 0  # Count of feeder ships sent to another terminal.
        self.nr_diverted_ships_D = 0  # Count of deep-sea ships sent to another terminal.
        self.nr_towed_ships_F = 0  # Count of feeder ships that needed a tugboat.
        self.nr_towed_ships_D = 0  # Count of deep-sea ships that needed a tugboat.
        self.nr_docked_ships_F = 0  # Count of feeder ships docked at the quay.
        self.nr_docked_ships_D = 0  # Count of deep-sea ships docked at the quay.
        self.nr_unloaded_ships_F = 0  # Count of feeder ships fully unloaded.
        self.nr_unloaded_ships_D = 0  # Count of deep-sea ships fully unloaded.
        self.unloading_by_alpha = 0  # Count of ships unloaded by team alpha.
        self.unloading_by_bravo = 0  # Count of ships unloaded by team bravo.
        self.unloading_by_charlie = 0  # Count of ships unloaded by team charlie.
        self.nr_restacked_ships = 0  # Count of unloadings that needed restacking.
        self.restacking_by_alpha = 0  # Count of restacking jobs done by team alpha.
        self.restacking_by_bravo = 0  # Count of restacking jobs done by team bravo.
        self.restacking_by_charlie = 0  # Count of restacking jobs done by team charlie.
        self.nr_scanned_ships_F = 0  # Count of feeder ships cleared by customs.
        self.nr_scanned_ships_D = 0  # Count of deep-sea ships cleared by customs.
        self.nr_minor_problem = 0  # Count of scans with a minor problem.
        self.nr_major_problem = 0  # Count of scans with a major problem.
        self.nr_delivered_loads_F = 0  # Count of feeder loads delivered inland by barge.
        self.nr_delivered_loads_D = 0  # Count of deep-sea loads delivered inland by barge.
        self.ontime_F = 0  # Count of feeder ships handled within the agreed handling time.
        self.ontime_D = 0  # Count of deep-sea ships handled within the agreed handling time.
        self.total_F = 0  # Count of feeder ships whose load reached the inland terminal.
        self.total_D = 0  # Count of deep-sea ships whose load reached the inland terminal.
        self.nr_warmup_ships = 0  # Count of ships announced during the warm-up period.

    # ---------------------------------- Processes ------------------------------------

    def _arrivals(self, env, arrival_info):
        """Process 0 - Ship announcements read from the json file (future scenario).
        PATTERN: arrival process driven by recorded data (Simulation slides 8, 10; Iteration slides 11-13): instead of random
        inter-arrival times (exercise 1), the process waits until the next listed
        announcement time (timeout of the difference with env.now) and takes the listed
        kind ("F"/"D"). Creating one ship process per arrival (env.process) is as in
        exercise 1.
        """
        # TOPIC [Dictionaries, slide 2]: the data read from the json file is a dictionary of lists.
        times = arrival_info["ship_arrival_times"]
        kinds = arrival_info["ship_types"]
        # TOPIC [Iteration, slides 11-13]: for loop with range; Lists slides 3-4: len and index.
        for i in range(len(times)):
            kind = kinds[i]
            # TOPIC [Simulation, slide 27]: Events: wait until the announcement time of the next ship.
            yield env.timeout(max(0.0, times[i] - env.now))
            if kind == "F":
                self.nr_arrived_ships_F += 1
            else:
                self.nr_arrived_ships_D += 1
            # TOPIC [Simulation, slide 10]: start a new process for every ship that arrives.
            env.process(self._ship(env, kind))

    def _ship(self, env, kind):
        """One ship = a chain of tasks; the ship stops if the operator refuses.
        PATTERN: process composition / sequential tasks (Simulation slide 23) (yield from)."""
        # EXERCISE 3 (added lines) - DATA COLLECTION / WARM-UP (Simulation slides 18-19): the ship process
        # starts at the announcement; ships announced before WARMUP_HOURS are simulated
        # (they fill the queues) but are counted as warm-up and not measured.
        announced_at = env.now
        # TOPIC [Simulation, slides 18-19]: warm-up: ships announced early are not measured.
        if announced_at < WARMUP_HOURS:
            self.nr_warmup_ships += 1
        # TOPIC [Simulation, slide 23]: Sequence: the tasks run one after the other.
        confirmed = yield from self._task1_book_and_quote(env, kind)
        # TOPIC [Conditional execution, slide 5]: if: stop this ship when the booking is not confirmed.
        if not confirmed:
            return
        # EXERCISE 3 (added line): remember the moment the booking is confirmed.
        confirmed_at = env.now
        yield from self._task2_tow(env, kind)
        yield from self._task3_unload(env, kind)
        yield from self._task4_customs(env, kind)
        yield from self._task5_barge(env, kind)
        # EXERCISE 3 (added lines): for measured ships (announced from the end of the
        # warm-up) count the ship and whether turnaround <= agreed handling time.
        if announced_at >= WARMUP_HOURS:
            if kind == "F":
                self.total_F += 1
            else:
                self.total_D += 1
            if env.now - confirmed_at <= AGREED_TIME[kind]:
                if kind == "F":
                    self.ontime_F += 1
                else:
                    self.ontime_D += 1

    def _task1_book_and_quote(self, env, kind):
        """Task 1 - Book a berth and quote the fee (5 days, no resource).
        PATTERNS: timeout for the fixed duration (Simulation slide 27); uniform random fee
        (Functions slide 13); conditional probabilistic branch (diversion if fee above the limit)
        (Simulation slide 24). Returns True if the booking is confirmed."""
        # TOPIC [Simulation, slide 27]: Events: only waiting for time passes (no resource).
        yield env.timeout(BOOKING_HOURS)
        # TOPIC [Functions, slide 13]: random.uniform; ranges come from a dictionary of tuples (Dictionaries slide 2, Tuples slide 2).
        fee = random.uniform(FEE_RANGE[kind][0], FEE_RANGE[kind][1])
        # TOPIC [Conditional execution, slide 5]: if / else on the ship type (Simulation slide 30: different case types; Comparators slide 6: ==).
        if kind == "F":
            self.nr_quoted_ships_F += 1
        else:
            self.nr_quoted_ships_D += 1
        if kind == "F":
            self.sum_fees_F += fee
        else:
            self.sum_fees_D += fee
        # TOPIC [Comparators, Boolean expressions, slides 3-5]: comparator on the fee; Simulation slide 24: Choice.
        if fee > FEE_LIMIT[kind]:
            if kind == "F":
                self.nr_fees_F_above += 1
            else:
                self.nr_fees_D_above += 1
            # TOPIC [Simulation, slide 24]: Choice: divert with a probability.
            if random.random() < P_DIVERT[kind]:
                if kind == "F":
                    self.nr_diverted_ships_F += 1
                else:
                    self.nr_diverted_ships_D += 1
                # TOPIC [Functions, slide 7]: return gives the result to the caller (False = diverted).
                return False
        return True

    def _task2_tow(self, env, kind):
        """Task 2 - Tow the ship to the quay (not limited to opening hours).
        PATTERNS: exponential duration for deep-sea (Simulation slide 10); optional step
        (probabilistic branch, task skipped in 70% of the feeder cases) (Simulation slide 24)."""
        # TOPIC [Simulation, slide 30]: different case types: deep-sea ships are always towed; Conditional execution slide 9 (elif).
        if kind == "D":
            if kind == "F":
                self.nr_towed_ships_F += 1
            else:
                self.nr_towed_ships_D += 1
            # TOPIC [Simulation, slide 10]: exponential duration.
            yield env.timeout(random.expovariate(1 / DEEPSEA_TOW_MEAN_HOURS))
        # TOPIC [Simulation, slide 24]: Choice: only some feeders need the tugboat.
        elif random.random() < P_FEEDER_NEEDS_TUG:
            if kind == "F":
                self.nr_towed_ships_F += 1
            else:
                self.nr_towed_ships_D += 1
            # TOPIC [Simulation, slide 27]: Events: waiting for time to pass.
            yield env.timeout(FEEDER_TOW_HOURS)
        if kind == "F":
            self.nr_docked_ships_F += 1
        else:
            self.nr_docked_ships_D += 1

    def _task3_unload(self, env, kind):
        """Task 3 - Unload the containers with crane team alpha / bravo / charlie.
        PATTERNS: shared resource with capacity 1 per team (request/release in a
        'with' block, queue) (Simulation slides 28-30); probabilistic choice of the team (40/35/25)
        (Simulation slide 25); opening hours: after the team is obtained, wait until the terminal
        is open, then work without pausing until done (Simulation slides 27, 30); resource held while
        working for restacking by team charlie itself; restacking by alpha/bravo is a
        second request on another resource (Simulation slide 30)."""
        # TOPIC [Simulation, slide 25]: Choice with three branches: draw once, then if / elif / else.
        draw = random.random()  # team: 40% alpha, 35% bravo, 25% charlie
        if draw < TEAM_PROBABILITIES[0]:
            team = "alpha"
        elif draw < TEAM_PROBABILITIES[0] + TEAM_PROBABILITIES[1]:
            team = "bravo"
        else:
            team = "charlie"
        helper = None  # alpha/bravo when they have to be called in for restacking
        # TOPIC [Simulation, slides 28-30]: request a crane team (Resource, queue); the team comes from a dictionary (Dictionaries slide 2).
        with self.teams[team].request() as request:
            # TOPIC [Simulation, slides 5, 7]: wait until the resource becomes available.
            yield request
            # TOPIC [Simulation, slides 27, 30]: resource with limited availability: wait for the opening hour.
            yield env.timeout(time_until_open(env.now))  # may start only when open
            if team == "alpha":
                self.unloading_by_alpha += 1
            elif team == "bravo":
                self.unloading_by_bravo += 1
            else:
                self.unloading_by_charlie += 1
            # EXERCISE 3 (changed line): unloading time per class; 3 h shorter with
            # automated cranes (self.unload_hours is prepared in simulate).
            # TOPIC [Dictionaries, slide 2]: unloading time looked up by team name.
            yield env.timeout(self.unload_hours[team])
            # TOPIC [Comparators, Boolean expressions, slides 11-12]: and: both conditions; Simulation slide 24: Choice.
            # TOPIC [Comparators, Boolean expressions, slides 11-12]: and: both conditions; Simulation slide 24: Choice.
            if team == "charlie" and random.random() < P_CHARLIE_RESTACK:
                self.nr_restacked_ships += 1
                # EXERCISE 3 (changed line): with automated cranes charlie repairs every stack.
                # TOPIC [Comparators, Boolean expressions, slides 13-15]: or: automated cranes always repair themselves, otherwise by chance.
                if self.automated_cranes or random.random() < P_CHARLIE_FIXES_ITSELF:
                    yield env.timeout(RESTACK_HOURS)  # charlie keeps its crane
                    self.restacking_by_charlie += 1
                else:
                    # alpha or bravo, in proportion 40 : 35
                    if random.random() * (TEAM_PROBABILITIES[0] + TEAM_PROBABILITIES[1]) < TEAM_PROBABILITIES[0]:
                        helper = "alpha"
                    else:
                        helper = "bravo"
        # TOPIC [Conditional execution, slide 5]: only call a second team when one is needed.
        if helper is not None:
            # TOPIC [Simulation, slide 30]: multiple resources: a request on another team.
            with self.teams[helper].request() as request:
                yield request
                yield env.timeout(time_until_open(env.now))  # new job: only when open
                yield env.timeout(RESTACK_HOURS)
                if helper == "alpha":
                    self.restacking_by_alpha += 1
                else:
                    self.restacking_by_bravo += 1
        if kind == "F":
            self.nr_unloaded_ships_F += 1
        else:
            self.nr_unloaded_ships_D += 1

    def _task4_customs(self, env, kind):
        """Task 4 - Customs scanning with the single customs team.
        PATTERNS: shared resource, capacity 1 (queue) (Simulation slides 28-30); opening hours as in
        task 3 (Simulation slides 27, 30); probabilistic extra work (8% minor / 2% major) (Simulation slide 25);
        simultaneous use of two resources: the customs team holds its resource and also
        requests team alpha for the major check (Simulation slide 30)."""
        # TOPIC [Simulation, slides 28-30]: the single customs team is a Resource with capacity 1.
        with self.customs.request() as request:
            yield request
            yield env.timeout(time_until_open(env.now))
            # TOPIC [Simulation, slide 27]: Events: waiting for time to pass.
            yield env.timeout(SCAN_HOURS)
            # TOPIC [Simulation, slide 25]: Choice: draw once, then if / elif (8% minor, 2% major).
            draw = random.random()
            if draw < P_MINOR:
                self.nr_minor_problem += 1
                yield env.timeout(MINOR_EXTRA_HOURS)
            elif draw < P_MINOR + P_MAJOR:
                self.nr_major_problem += 1
                # TOPIC [Simulation, slide 30]: two resources at the same time: customs is still held.
                with self.teams["alpha"].request() as alpha_request:
                    yield alpha_request
                    yield env.timeout(MAJOR_EXTRA_HOURS)
        if kind == "F":
            self.nr_scanned_ships_F += 1
        else:
            self.nr_scanned_ships_D += 1

    def _task5_barge(self, env, kind):
        """Task 5 - Inland transport by barge (unlimited capacity, not limited to
        opening hours). PATTERNS: wait for a scheduled time (departure every opening
        day at 18:00) (Simulation slide 27); uniform sailing time (Functions slide 13)."""
        # TOPIC [Simulation, slide 27]: Events: wait for the departure time.
        yield env.timeout(time_until_barge(env.now))
        # TOPIC [Functions, slide 13]: random.uniform: sailing time between 5 and 9 hours.
        yield env.timeout(random.uniform(BARGE_SAIL_RANGE[0], BARGE_SAIL_RANGE[1]))
        if kind == "F":
            self.nr_delivered_loads_F += 1
        else:
            self.nr_delivered_loads_D += 1

    # ---------------------------------- Simulation -----------------------------------

    def simulate(
        self,
        arrival_info,
        *,
        extra_gangs: int = 0,
        automated_cranes: bool = False,
        second_scanning_crew: bool = False,
    ):
        """Runs the scenario until every announced ship has been handled.
        PATTERN: parameterised resources (Simulation slides 11, 29-30): the capacity of each speed class
        and of the customs resource, and the unloading times, are set here from the
        investment arguments, so the same processes simulate all 9 alternatives."""
        # TOPIC [Simulation, slide 11]: create the simulation environment.
        env = simpy.Environment()
        self.automated_cranes = automated_cranes
        bravo_capacity = 1
        charlie_capacity = 1
        if extra_gangs >= 1:
            bravo_capacity = 2  # first extra team works at bravo speed, added to bravo
        if extra_gangs >= 2:
            charlie_capacity = 2  # second extra team works at charlie speed, added to charlie
        # TOPIC [Dictionaries, slides 3-4]: a dictionary that gets one Resource per team name.
        self.teams = {}
        self.teams["alpha"] = simpy.Resource(env, capacity=1)
        self.teams["bravo"] = simpy.Resource(env, capacity=bravo_capacity)
        self.teams["charlie"] = simpy.Resource(env, capacity=charlie_capacity)
        customs_capacity = 1
        if second_scanning_crew:
            customs_capacity = 2  # two ships can be scanned at the same time
        # TOPIC [Simulation, slide 11]: Resource with capacity 1.
        self.customs = simpy.Resource(env, capacity=customs_capacity)
        saving = 0
        if automated_cranes:
            saving = AUTOMATION_SAVING_HOURS
        self.unload_hours = {}
        # TOPIC [Iteration, slides 9-10]: for loop over the list of team names.
        for name in TEAMS:
            self.unload_hours[name] = UNLOAD_HOURS[name] - saving
        # TOPIC [Simulation, slide 11]: start the arrival process.
        env.process(self._arrivals(env, arrival_info))
        # TOPIC [Simulation, slide 11]: run the simulation.
        env.run()  # the arrivals are finite: runs until the last ship is delivered
        return env


# -------------------------------------------------------------------------------------
# --------------------------- SOLUTION CHECK (Don't change) ---------------------------
# -------------------------------------------------------------------------------------
if __name__ == "__main__":
    print(
        "\n\nDISCLAIMER\nIf you do not see DONE, this means that the program got stuck somewhere and consequently does not work properly. "
        + "Finally, note that you must use all attributes and functions that are defined in the template and give them correct values according to the assignment description. "
        + "You must not change names or signatures of predefined classes, attributes or functions. Doing so may lead to severe deduction of points. "
        + "\n\nRESULTS"
    )

    with open("ship_arrival_information.json") as data:
        arrival_information = json.load(data)

    evaluate_investments(arrival_information, runs=10)

    Terminal = ContainerTerminalSimulator()
    simulation = Terminal.simulate(arrival_information)
    total_ships = Terminal.nr_arrived_ships_F + Terminal.nr_arrived_ships_D
    total_unloaded = Terminal.nr_unloaded_ships_F + Terminal.nr_unloaded_ships_D
    total_scanned = Terminal.nr_scanned_ships_F + Terminal.nr_scanned_ships_D
    total_confirmed_ships = (
        Terminal.nr_quoted_ships_F
        + Terminal.nr_quoted_ships_D
        - Terminal.nr_diverted_ships_F
        - Terminal.nr_diverted_ships_D
    )
    total_delivered = Terminal.nr_delivered_loads_F + Terminal.nr_delivered_loads_D
    weeks = 8760 / 168
    print("\nBase scenario without any investment")
    print("Simulation End Time:", round(simulation.now, 1))
    print("Total Feeder Ships Announced:", Terminal.nr_arrived_ships_F)
    print("Total Deep-Sea Ships Announced:", Terminal.nr_arrived_ships_D)
    print("Diverted Feeder Ships:", Terminal.nr_diverted_ships_F)
    print("Diverted Deep-Sea Ships:", Terminal.nr_diverted_ships_D)
    print("Unloaded Feeder Ships:", Terminal.nr_unloaded_ships_F)
    print("Unloaded Deep-Sea Ships:", Terminal.nr_unloaded_ships_D)
    print(f"Ships Unloaded by Team Alpha: {Terminal.unloading_by_alpha}")
    print(f"Ships Unloaded by Team Bravo: {Terminal.unloading_by_bravo}")
    print(f"Ships Unloaded by Team Charlie: {Terminal.unloading_by_charlie}")
    print("Feeder Loads Delivered Inland:", Terminal.nr_delivered_loads_F)
    print("Deep-Sea Loads Delivered Inland:", Terminal.nr_delivered_loads_D)
    print(
        f"On-Time Feeder Ships: {Terminal.ontime_F} of {Terminal.total_F}"
        f" (agreed handling time {AGREED_TIME_FEEDER:.0f} h)"
    )
    print(
        f"On-Time Deep-Sea Ships: {Terminal.ontime_D} of {Terminal.total_D}"
        f" (agreed handling time {AGREED_TIME_DEEPSEA:.0f} h)"
    )
    print("Ships Left Out as Warm-Up:", Terminal.nr_warmup_ships)
    print(f"On-Time Percentage: {compute_ontime_percentage(Terminal):.1f}%")
    print("\nArrival Rate Checks:")
    print(f"Average Total Ships per Week: {(total_ships / weeks):.1f}")
    if total_ships > 0:
        print(
            f"Percentage of Feeder Ships: {(Terminal.nr_arrived_ships_F / total_ships * 100):.1f}% (Expected ~65%)"
        )
        print(
            f"Percentage of Deep-Sea Ships: {(Terminal.nr_arrived_ships_D / total_ships * 100):.1f}% (Expected ~35%)"
        )
        print(
            f"Percentage of Feeder Ships That Needed Towing: {(Terminal.nr_towed_ships_F / Terminal.nr_docked_ships_F * 100):.1f}% (Expected ~30%)"
        )
        print(
            f"Percentage of Ships Unloaded by Team Alpha: {(Terminal.unloading_by_alpha / total_unloaded * 100):.1f}% (Expected ~40%)"
        )
        print(
            f"Percentage of Ships Unloaded by Team Bravo: {(Terminal.unloading_by_bravo / total_unloaded * 100):.1f}% (Expected ~35%)"
        )
        print(
            f"Percentage of Ships Unloaded by Team Charlie: {(Terminal.unloading_by_charlie / total_unloaded * 100):.1f}% (Expected ~25%)"
        )
        print(
            f"Percentage of Loads Delivered: {(total_delivered / total_confirmed_ships * 100):.1f}% (Expected 100%)"
        )
        print(
            f"Percentage of Scans with a Minor Problem: {(Terminal.nr_minor_problem / total_scanned * 100):.1f}% (Expected ~8%)"
        )
        print(
            f"Percentage of Scans with a Major Problem: {(Terminal.nr_major_problem / total_scanned * 100):.1f}% (Expected ~2%)"
        )
    else:
        print("Percentage of Feeder Ships (F): 0.00% (No ships announced)")
        print("Percentage of Deep-Sea Ships (D): 0.00% (No ships announced)")

    print("\nDONE\n")