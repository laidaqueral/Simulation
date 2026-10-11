# TOPIC [Functions, slide 13]: import random (library with pre-defined functions).
import random

# TOPIC [Simulation, slides 10-11]: the simpy library: Environment, Resource, env.process, env.timeout.
import simpy


# TOPIC [Variables, Expressions, Types, slides 2-5]: constants of exercise 4.
SECURITY_ALERT_PROBABILITY = 0.10
SECURITY_ALERT_AFTER_HOURS = 1.0
SECURITY_CHECK_HOURS = 2.0
REGULAR_SCAN_HOURS = 4.0
SECURITY_ALERT_CAUSE = "security alert"
# TOPIC [Tuples and Sets, slide 2]: range stored as a tuple (min, max).
PAPER_CHECK_RANGE = (1, 3)  # port inspector: uniform 1-3 hours (exercise 4)

# ------------------------------- Model parameters --------------------------------------
# Assumption: simulation time 0 is Monday 00:00; time is measured in hours.
# TOPIC [Variables, Expressions, Types, slides 2-5, 7]: model parameters kept in named variables (constants).
ARRIVAL_RATE = 8 / 168  # 8 ships per week, expressed per hour
P_FEEDER = 0.65

BOOKING_HOURS = 5 * 24  # Task 1 takes five days
# TOPIC [Dictionaries, slides 2-6]: values looked up by key ("F"/"D"); ranges are tuples (Tuples and Sets, slide 2).
FEE_RANGE = {"F": (4_000, 12_000), "D": (25_000, 60_000)}
FEE_LIMIT = {"F": 9_000, "D": 50_000}
P_DIVERT = {"F": 0.30, "D": 0.10}

P_FEEDER_NEEDS_TUG = 0.30
FEEDER_TOW_HOURS = 6
DEEPSEA_TOW_MEAN_HOURS = 18

# TOPIC [Lists, slides 2, 4]: list of the three crane team names.
TEAMS = ["alpha", "bravo", "charlie"]
TEAM_PROBABILITIES = [0.40, 0.35, 0.25]
# TOPIC [Dictionaries, slide 2]: unloading hours per team name (dictionary).
UNLOAD_HOURS = {"alpha": 8, "bravo": 11, "charlie": 16}
P_CHARLIE_RESTACK = 0.25
P_CHARLIE_FIXES_ITSELF = 0.20
RESTACK_HOURS = 2

SCAN_HOURS = 4
P_MINOR = 0.08
P_MAJOR = 0.02
MINOR_EXTRA_HOURS = 1
MAJOR_EXTRA_HOURS = 4

OPEN_HOUR, CLOSE_HOUR = 6, 22  # opening hours, Monday-Saturday
BARGE_HOUR = 18
BARGE_SAIL_RANGE = (5, 9)


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
        # TOPIC [Object orientation: constructors, slide 4]: new counters are initialised in the constructor.
        self.nr_container_scans = 0  # Count of finished container scans.
        self.nr_paper_checks = 0  # Count of finished paper checks.
        self.nr_interrupted_scans = 0  # Count of routine scans interrupted by an alert.
        self.nr_completed_security_checks = 0  # Count of finished security checks.

    # ---------------------------------- Processes ------------------------------------

    def _arrivals(self, env):
        """Process 0 - Ship announcements.
        PATTERN: arrival (generator) process with exponential inter-arrival times,
        (Simulation slides 8, 10): loop { timeout(expovariate(rate)); create ship; env.process(ship) }.
        Ship kind: random branching with probability 65% / 35%  (Simulation slides 24-25).
        """
        # TOPIC [Iteration, slides 4-5]: while loop; Simulation slides 8, 10: the generator creates ships forever.
        while True:
            # TOPIC [Simulation, slides 8, 10]: wait for the inter-arrival time (exponential); random: Functions, slide 13.
            yield env.timeout(random.expovariate(ARRIVAL_RATE))
            # TOPIC [Simulation, slides 24-25, 30]: Choice with a probability (65% / 35%); different case types.
            if random.random() < P_FEEDER:
                kind = "F"
            else:
                kind = "D"
            if kind == "F":
                self.nr_arrived_ships_F += 1
            else:
                self.nr_arrived_ships_D += 1
            # TOPIC [Simulation, slide 10]: start a new process for every ship that arrives.
            env.process(self._ship(env, kind))

    def _ship(self, env, kind):
        """One ship = a chain of tasks; the ship stops if the operator refuses.
        PATTERN: process composition / sequential tasks (Simulation slide 23) (yield from)."""
        # TOPIC [Simulation, slide 23]: Sequence: the tasks run one after the other.
        confirmed = yield from self._task1_book_and_quote(env, kind)
        # TOPIC [Conditional execution, slide 5]: if: stop this ship when the booking is not confirmed.
        if not confirmed:
            return
        yield from self._task2_tow(env, kind)
        yield from self._task3_unload(env, kind)
        yield from self._task4_customs(env, kind)
        yield from self._task5_barge(env, kind)

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
            # TOPIC [Dictionaries, slide 2]: unloading time looked up by team name.
            yield env.timeout(UNLOAD_HOURS[team])
            # TOPIC [Comparators, Boolean expressions, slides 11-12]: and: both conditions; Simulation slide 24: Choice.
            if team == "charlie" and random.random() < P_CHARLIE_RESTACK:
                self.nr_restacked_ships += 1
                if random.random() < P_CHARLIE_FIXES_ITSELF:
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
        """Task 4 - Customs: container scan and paper check run IN PARALLEL.
        PATTERNS: parallel processes (Simulation slide 26): the container scan (customs team) and
        the paper check (port inspector) are two separate SimPy processes started at the
        same moment; the ship waits for both with `&` (scan & papers), so it is cleared only
        when the slower one is finished (Simulation slide 26). Process interruption (SimPy documentation; Simulation slide 32 points to it): in
        10% of the scans a third process, the security alert, is started; it interrupts the
        scan process (see _raise_security_alert and _scan_containers). Event used to
        synchronise the alert with the real start of the scan: scan_started (Simulation slide 5)."""
        # TOPIC [Simulation, slide 5]: an event that another process can trigger (SimPy documentation: env.event).
        scan_started = env.event()
        # TOPIC [Simulation, slides 10, 26]: start the container scan as its own process.
        scan = env.process(
            self._scan_containers(env, self.customs, self.teams["alpha"], scan_started)
        )
        # TOPIC [Simulation, slide 26]: start the paper check as its own process, at the same moment.
        papers = env.process(self._check_papers(env, self.inspector))
        # TOPIC [Simulation, slide 24]: Choice with a probability (10% of the scans get a security alert).
        if random.random() < SECURITY_ALERT_PROBABILITY:
            env.process(self._raise_security_alert(env, scan, scan_started))
        # TOPIC [Simulation, slide 26]: Parallelism: wait until both processes are finished.
        yield scan & papers
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

    # ---------------------- Parallel and interrupted checks ---------------------------

    def _raise_security_alert(self, env, scan_process, scan_started):
        """Waits for a scan to start and then interrupts its SimPy process.
        PATTERNS: process interruption (SimPy documentation; Simulation slide 32): process.interrupt(cause) raises
        simpy.Interrupt inside the scan process. Waiting for an event (Simulation slides 5, 27): the alert
        first waits for scan_started, which the scan triggers when it has really started
        (customs obtained and terminal open), so time in the queue does not count; then it
        waits exactly SECURITY_ALERT_AFTER_HOURS (timeout) and interrupts."""
        # TOPIC [Simulation, slide 5]: wait for an event generated by another process.
        yield scan_started
        # TOPIC [Simulation, slide 27]: Events: waiting for time to pass.
        yield env.timeout(SECURITY_ALERT_AFTER_HOURS)
        # TOPIC [Conditional execution, slide 5]: only interrupt a scan that is still running.
        if scan_process.is_alive:
            # TOPIC [SimPy documentation, mentioned on Simulation slide 32]: interrupt() is not taught in the slides.
            scan_process.interrupt(SECURITY_ALERT_CAUSE)

    def _scan_containers(self, env, scanner, alpha, scan_started):
        """Runs the container scan and handles a possible security interruption.
        PATTERNS: shared resource, capacity 1 (queue) (Simulation slides 28-30); opening hours as in
        task 3 (Simulation slides 27, 30); event triggering: scan_started.succeed() when the scan really
        starts (Simulation slide 5); handling an interruption with try / except simpy.Interrupt
        (Exceptions slides 3-6 for try/except; SimPy documentation for Interrupt): the customs team keeps its resource, performs the secondary security
        check (2 h) and then the remaining part of the scan (4 h minus the time already
        scanned); probabilistic extra work (8% minor / 2% major) after the routine scan
        (Simulation slide 25); the major check uses the resource of team alpha while the scanner is
        still held (two resources at the same time) (Simulation slide 30)."""
        # TOPIC [Simulation, slides 28-30]: the customs team is a Resource with capacity 1.
        with scanner.request() as request:
            yield request
            yield env.timeout(time_until_open(env.now))
            # TOPIC [Simulation, slide 5]: trigger the event: the scan has really started (SimPy documentation).
            scan_started.succeed()  # the alert counts its hour from this moment
            scan_start = env.now
            # TOPIC [Exceptions, slides 3-6]: try / except: the code in except runs when the interruption happens (SimPy documentation: Interrupt).
            try:
                yield env.timeout(REGULAR_SCAN_HOURS)
            except simpy.Interrupt as interrupt:
                if interrupt.cause == SECURITY_ALERT_CAUSE:
                    # TOPIC [Variables, Expressions, Types, slides 7-8]: expression: time already scanned = now - start.
                    already_scanned = env.now - scan_start
                    self.nr_interrupted_scans += 1
                    yield env.timeout(SECURITY_CHECK_HOURS)
                    self.nr_completed_security_checks += 1
                    yield env.timeout(REGULAR_SCAN_HOURS - already_scanned)
            self.nr_container_scans += 1  # the routine scan is complete
            # TOPIC [Simulation, slide 25]: Choice: draw once, then if / elif (8% minor, 2% major).
            draw = random.random()
            if draw < P_MINOR:
                self.nr_minor_problem += 1
                yield env.timeout(MINOR_EXTRA_HOURS)
            elif draw < P_MINOR + P_MAJOR:
                self.nr_major_problem += 1
                # TOPIC [Simulation, slide 30]: two resources at the same time: customs is still held.
                with alpha.request() as alpha_request:
                    yield alpha_request
                    yield env.timeout(MAJOR_EXTRA_HOURS)

    def _check_papers(self, env, inspector):
        """Runs the cargo paper check in parallel with the container scan.
        PATTERNS: shared resource, capacity 1: there is one port inspector (queue)
        (Simulation slides 28-30); uniformly distributed duration between 1 and 3 hours (Functions slide 13). It is
        a separate process, so it runs at the same time as the scan (Simulation slide 26). The
        assignment only limits unloading and customs scanning to the opening hours, so
        the inspector is not limited."""
        # TOPIC [Simulation, slides 28-30]: the port inspector is a Resource with capacity 1.
        with inspector.request() as request:
            yield request
            # TOPIC [Functions, slide 13]: random.uniform: duration between 1 and 3 hours.
            yield env.timeout(random.uniform(PAPER_CHECK_RANGE[0], PAPER_CHECK_RANGE[1]))
        self.nr_paper_checks += 1

    # ---------------------------------- Simulation -----------------------------------

    def simulate(self, duration):
        """Simulation function without random seed."""
        # TOPIC [Simulation, slide 11]: create the simulation environment.
        env = simpy.Environment()
        # TOPIC [Dictionaries, slides 3-4]: a dictionary that gets one Resource per team name.
        self.teams = {}
        # TOPIC [Iteration, slides 9-10]: for loop over the list of team names.
        for name in TEAMS:
            self.teams[name] = simpy.Resource(env, capacity=1)
        # TOPIC [Simulation, slide 11]: Resource with capacity 1.
        self.customs = simpy.Resource(env, capacity=1)
        # EXERCISE 4 (added line): the single port inspector who checks the cargo papers.
        # TOPIC [Simulation, slides 11, 30]: second resource for the paper check.
        self.inspector = simpy.Resource(env, capacity=1)
        # TOPIC [Simulation, slide 11]: start the arrival process.
        env.process(self._arrivals(env))
        # TOPIC [Simulation, slide 11]: run the simulation.
        env.run(until=duration)
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
    Terminal = ContainerTerminalSimulator()
    simulation = Terminal.simulate(8760)  # 1 year = 8760 hours
    total_ships = Terminal.nr_arrived_ships_F + Terminal.nr_arrived_ships_D
    total_unloaded = (
        Terminal.nr_unloaded_ships_F + Terminal.nr_unloaded_ships_D
    )
    total_scanned = Terminal.nr_scanned_ships_F + Terminal.nr_scanned_ships_D
    total_confirmed_ships = (
        Terminal.nr_quoted_ships_F
        + Terminal.nr_quoted_ships_D
        - Terminal.nr_diverted_ships_F
        - Terminal.nr_diverted_ships_D
    )
    total_delivered = (
        Terminal.nr_delivered_loads_F + Terminal.nr_delivered_loads_D
    )
    weeks = 8760 / 168
    print("Simulation Duration:", simulation.peek())
    print("Total Feeder Ships Announced:", Terminal.nr_arrived_ships_F)
    print("Total Deep-Sea Ships Announced:", Terminal.nr_arrived_ships_D)
    print(
        f"Feeder Ships with a Fee Quote: {Terminal.nr_quoted_ships_F}, avg: EUR {Terminal.sum_fees_F / Terminal.nr_quoted_ships_F if Terminal.nr_quoted_ships_F else 0:.1f}"
    )
    print(
        f"Deep-Sea Ships with a Fee Quote: {Terminal.nr_quoted_ships_D}, avg: EUR {Terminal.sum_fees_D / Terminal.nr_quoted_ships_D if Terminal.nr_quoted_ships_D else 0:.1f}"
    )
    print("Diverted Feeder Ships:", Terminal.nr_diverted_ships_F)
    print("Diverted Deep-Sea Ships:", Terminal.nr_diverted_ships_D)
    print("Towed Feeder Ships:", Terminal.nr_towed_ships_F)
    print("Towed Deep-Sea Ships:", Terminal.nr_towed_ships_D)
    print("Docked Feeder Ships:", Terminal.nr_docked_ships_F)
    print("Docked Deep-Sea Ships:", Terminal.nr_docked_ships_D)
    print("Unloaded Feeder Ships:", Terminal.nr_unloaded_ships_F)
    print("Unloaded Deep-Sea Ships:", Terminal.nr_unloaded_ships_D)
    print(f"Ships Unloaded by Team Alpha: {Terminal.unloading_by_alpha}")
    print(f"Ships Unloaded by Team Bravo: {Terminal.unloading_by_bravo}")
    print(f"Ships Unloaded by Team Charlie: {Terminal.unloading_by_charlie}")
    print("Scanned Feeder Ships:", Terminal.nr_scanned_ships_F)
    print("Scanned Deep-Sea Ships:", Terminal.nr_scanned_ships_D)
    print("Feeder Loads Delivered Inland:", Terminal.nr_delivered_loads_F)
    print("Deep-Sea Loads Delivered Inland:", Terminal.nr_delivered_loads_D)
    print("Ships Needing Restacking:", Terminal.nr_restacked_ships)
    print(f"Restacking by Team Alpha: {Terminal.restacking_by_alpha}")
    print(f"Restacking by Team Bravo: {Terminal.restacking_by_bravo}")
    print(f"Restacking by Team Charlie: {Terminal.restacking_by_charlie}")
    print("Scans with a Minor Problem:", Terminal.nr_minor_problem)
    print("Scans with a Major Problem:", Terminal.nr_major_problem)
    print("Finished Container Scans:", Terminal.nr_container_scans)
    print("Finished Paper Checks:", Terminal.nr_paper_checks)
    print("Interrupted Container Scans:", Terminal.nr_interrupted_scans)
    print("Completed Security Checks:", Terminal.nr_completed_security_checks)
    print("\nArrival Rate Checks:")
    print(f"Average Total Ships per Week: {(total_ships / weeks):.1f} (Expected ~8)")
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
            f"Percentage of Charlie Unloadings Needing Restacking: {(Terminal.nr_restacked_ships / Terminal.unloading_by_charlie * 100):.1f}% (Expected ~25%)"
        )
        print(
            f"Percentage of Loads Delivered: {(total_delivered / total_confirmed_ships * 100):.1f}% (Expected >= 95%)"
        )
        print(
            f"Percentage of Scans with a Minor Problem: {(Terminal.nr_minor_problem / total_scanned * 100):.1f}% (Expected ~8%)"
        )
        print(
            f"Percentage of Scans with a Major Problem: {(Terminal.nr_major_problem / total_scanned * 100):.1f}% (Expected ~2%)"
        )
        print(
            f"Percentage of Container Scans Interrupted: {(Terminal.nr_interrupted_scans / Terminal.nr_container_scans * 100):.1f}% (Expected ~10%)"
        )
    else:
        print("Percentage of Feeder Ships (F): 0.00% (No ships announced)")
        print("Percentage of Deep-Sea Ships (D): 0.00% (No ships announced)")

    print("\nDONE\n")