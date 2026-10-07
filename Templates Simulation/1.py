import random

import simpy

# ------------------------------- Model parameters --------------------------------------
# Assumption: simulation time 0 is Monday 00:00; time is measured in hours.
ARRIVAL_RATE = 8 / 168  # 8 ships per week, expressed per hour
P_FEEDER = 0.65

BOOKING_HOURS = 5 * 24  # Task 1 takes five days
FEE_RANGE = {"F": (4_000, 12_000), "D": (25_000, 60_000)}
FEE_LIMIT = {"F": 9_000, "D": 50_000}
P_DIVERT = {"F": 0.30, "D": 0.10}

P_FEEDER_NEEDS_TUG = 0.30
FEEDER_TOW_HOURS = 6
DEEPSEA_TOW_MEAN_HOURS = 18

TEAMS = ["alpha", "bravo", "charlie"]
TEAM_PROBABILITIES = [0.40, 0.35, 0.25]
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
    return day_number % 7 != 6


def time_until_open(now):
    """Hours to wait until the terminal is open (0 if it is open right now)."""
    day = int(now // 24)
    hour = now - day * 24
    if is_open_day(day):
        if hour < OPEN_HOUR: # Closed
            return OPEN_HOUR - hour
        if hour < CLOSE_HOUR: 
            return 0.0
    next_day = day + 1
    while not is_open_day(next_day):
        next_day += 1
    return next_day * 24 + OPEN_HOUR - now


def time_until_barge(now):
    """Hours until the next barge departure (18:00 on an opening day)."""
    day = int(now // 24)
    hour = now - day * 24
    if is_open_day(day) and hour < BARGE_HOUR:
        return BARGE_HOUR - hour
    next_day = day + 1
    while not is_open_day(next_day):
        next_day += 1
    return next_day * 24 + BARGE_HOUR - now


class ContainerTerminalSimulator:
    """A SimPy simulation model for a container terminal handling ships."""

    def __init__(self):
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

    # ---------------------------------- Simulation -----------------------------------

    def _count(self, base, kind, amount=1):
        """Increase the counter."""
        name = f"{base}_{kind}"
        setattr(self, name, getattr(self, name) + amount)

    # ---------------------------------- Processes ------------------------------------

    def _arrivals(self, env):
        """Process 0 - Ship announcements.
        PATTERN: arrival (generator) process with exponential inter-arrival times,
        [Slide ??]: loop { timeout(expovariate(rate)); create ship; env.process(ship) }.
        Ship kind: random branching with probability 65% / 35%  [Slide ??].
        """
        while True:
            yield env.timeout(random.expovariate(ARRIVAL_RATE))
            kind = "F" if random.random() < P_FEEDER else "D"
            self._count("nr_arrived_ships", kind)
            env.process(self._ship(env, kind))

    def _ship(self, env, kind):
        """One ship = a chain of tasks; the ship stops if the operator refuses.
        PATTERN: process composition / sequential tasks [Slide ??] (yield from)."""
        confirmed = yield from self._task1_book_and_quote(env, kind)
        if not confirmed:
            return
        yield from self._task2_tow(env, kind)
        yield from self._task3_unload(env, kind)
        yield from self._task4_customs(env, kind)
        yield from self._task5_barge(env, kind)

    def _task1_book_and_quote(self, env, kind):
        """Task 1 - Book a berth and quote the fee (5 days, no resource).
        PATTERNS: timeout for the fixed duration [Slide ??]; uniform random fee
        [Slide ??]; conditional probabilistic branch (diversion if fee above the limit)
        [Slide ??]. Returns True if the booking is confirmed."""
        yield env.timeout(BOOKING_HOURS)
        fee = random.uniform(*FEE_RANGE[kind])
        self._count("nr_quoted_ships", kind)
        self._count("sum_fees", kind, fee)
        if fee > FEE_LIMIT[kind]:
            if kind == "F":
                self.nr_fees_F_above += 1
            else:
                self.nr_fees_D_above += 1
            if random.random() < P_DIVERT[kind]:
                self._count("nr_diverted_ships", kind)
                return False
        return True

    def _task2_tow(self, env, kind):
        """Task 2 - Tow the ship to the quay (not limited to opening hours).
        PATTERNS: exponential duration for deep-sea [Slide ??]; optional step
        (probabilistic branch, task skipped in 70% of the feeder cases) [Slide ??]."""
        if kind == "D":
            self._count("nr_towed_ships", kind)
            yield env.timeout(random.expovariate(1 / DEEPSEA_TOW_MEAN_HOURS))
        elif random.random() < P_FEEDER_NEEDS_TUG:
            self._count("nr_towed_ships", kind)
            yield env.timeout(FEEDER_TOW_HOURS)
        self._count("nr_docked_ships", kind)

    def _task3_unload(self, env, kind):
        """Task 3 - Unload the containers with crane team alpha / bravo / charlie.
        PATTERNS: shared resource with capacity 1 per team (request/release in a
        'with' block, queue) [Slide ??]; probabilistic choice of the team (40/35/25)
        [Slide ??]; opening hours: after the team is obtained, wait until the terminal
        is open, then work without pausing until done [Slide ??]; resource held while
        working for restacking by team charlie itself; restacking by alpha/bravo is a
        second request on another resource [Slide ??]."""
        team = random.choices(TEAMS, weights=TEAM_PROBABILITIES)[0]
        helper = None  # alpha/bravo when they have to be called in for restacking
        with self.teams[team].request() as request:
            yield request
            yield env.timeout(time_until_open(env.now))  # may start only when open
            setattr(self, f"unloading_by_{team}", getattr(self, f"unloading_by_{team}") + 1)
            yield env.timeout(UNLOAD_HOURS[team])
            if team == "charlie" and random.random() < P_CHARLIE_RESTACK:
                self.nr_restacked_ships += 1
                if random.random() < P_CHARLIE_FIXES_ITSELF:
                    yield env.timeout(RESTACK_HOURS)  # charlie keeps its crane
                    self.restacking_by_charlie += 1
                else:
                    helper = random.choices(
                        ["alpha", "bravo"], weights=[TEAM_PROBABILITIES[0], TEAM_PROBABILITIES[1]]
                    )[0]
        if helper is not None:
            with self.teams[helper].request() as request:
                yield request
                yield env.timeout(time_until_open(env.now))  # new job: only when open
                yield env.timeout(RESTACK_HOURS)
                setattr(self, f"restacking_by_{helper}", getattr(self, f"restacking_by_{helper}") + 1)
        self._count("nr_unloaded_ships", kind)

    def _task4_customs(self, env, kind):
        """Task 4 - Customs scanning with the single customs team.
        PATTERNS: shared resource, capacity 1 (queue) [Slide ??]; opening hours as in
        task 3 [Slide ??]; probabilistic extra work (8% minor / 2% major) [Slide ??];
        simultaneous use of two resources: the customs team holds its resource and also
        requests team alpha for the major check [Slide ??]."""
        with self.customs.request() as request:
            yield request
            yield env.timeout(time_until_open(env.now))
            yield env.timeout(SCAN_HOURS)
            draw = random.random()
            if draw < P_MINOR:
                self.nr_minor_problem += 1
                yield env.timeout(MINOR_EXTRA_HOURS)
            elif draw < P_MINOR + P_MAJOR:
                self.nr_major_problem += 1
                with self.teams["alpha"].request() as alpha_request:
                    yield alpha_request
                    yield env.timeout(MAJOR_EXTRA_HOURS)
        self._count("nr_scanned_ships", kind)

    def _task5_barge(self, env, kind):
        """Task 5 - Inland transport by barge (unlimited capacity, not limited to
        opening hours). PATTERNS: wait for a scheduled time (departure every opening
        day at 18:00) [Slide ??]; uniform sailing time [Slide ??]."""
        yield env.timeout(time_until_barge(env.now))
        yield env.timeout(random.uniform(*BARGE_SAIL_RANGE))
        self._count("nr_delivered_loads", kind)

    # ---------------------------------- Simulation -----------------------------------

    def simulate(self, duration):
        """Simulation function without random seed."""
        env = simpy.Environment()
        self.teams = {name: simpy.Resource(env, capacity=1) for name in TEAMS}
        self.customs = simpy.Resource(env, capacity=1)
        env.process(self._arrivals(env))
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
    else:
        print("Percentage of Feeder Ships (F): 0.00% (No ships announced)")
        print("Percentage of Deep-Sea Ships (D): 0.00% (No ships announced)")

    print("\nDONE\n")