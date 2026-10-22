import pulp


class DistributionNetwork:
    def __init__(self):
        self.facilities = ["F1", "F2", "F3", "F4", "F5"]
        self.service_areas = ["S1", "S2", "S3", "S4", "S5", "S6"]
        self.periods = [t for t in range(0, 10, 1)]
        self.crews = ["K1", "K2"]
        self.budget = 7500

        # capacity that a facility can ship in a single period
        self.capacity = {
            "F1": 120,
            "F2": 60,
            "F3": 150,
            "F4": 90,
            "F5": 50,
        }

        self.opening_costs = {
            "F1": 400,
            "F2": 150,
            "F3": 600,
            "F4": 300,
            "F5": 120,
        }

        # number of periods it takes to construct a facility
        self.build_time = {
            "F1": 3,
            "F2": 1,
            "F3": 4,
            "F4": 2,
            "F5": 1,
        }

        # demand of a service area in a single period
        self.demand = {
            "S1": 60,
            "S2": 80,
            "S3": 50,
            "S4": 70,
            "S5": 90,
            "S6": 40,
        }

        self.unit_selling_price = {
            "S1": 15,
            "S2": 10,
            "S3": 12,
            "S4": 18,
            "S5": 8,
            "S6": 20,
        }

        self.unit_shipping_cost = {
            "F1": {"S1": 3, "S2": 4, "S3": 2, "S4": 7, "S5": 5, "S6": 9},
            "F2": {"S1": 6, "S2": 3, "S3": 5, "S4": 4, "S5": 7, "S6": 6},
            "F3": {"S1": 8, "S2": 6, "S3": 7, "S4": 5, "S5": 3, "S6": 4},
            "F4": {"S1": 2, "S2": 7, "S3": 4, "S4": 9, "S5": 6, "S6": 8},
            "F5": {"S1": 7, "S2": 5, "S3": 6, "S4": 3, "S5": 8, "S6": 5},
        }

    def solve(self):
        # All slide references below are to the Module 7 lecture
        # "Business Process Optimization" (slide numbers as printed on the slides).
        F = self.facilities
        S = self.service_areas
        T = self.periods
        K = self.crews
        P = self.build_time

        # Problem definition with a maximization objective
        # Pattern: slide 16 (pulp.LpProblem(..., pulp.LpMaximize))
        self._problem = pulp.LpProblem("CFLP_construction", pulp.LpMaximize)

        # DECISION VARIABLE Z[(f,k,t)] in {0,1}: 1 if crew k starts building facility f in period t.
        # Pattern: slide 33 (X_r,a,t = resource r starts activity a at time t), with the crew as the
        # resource and the facility as the activity; created with pulp.LpVariable.dicts(..., 0, 1,
        # cat=pulp.LpInteger) as on slide 20.
        Z = pulp.LpVariable.dicts("Z", ((f, k, t) for f in F for k in K for t in T), 0, 1, cat=pulp.LpInteger)

        # DECISION VARIABLE X[(f,s,t)] >= 0: number of units shipped from facility f to service area s in period t.
        # Pattern: slide 16 (pulp.LpVariable(name, 0)) written compactly with
        # pulp.LpVariable.dicts over all (f,s,t) combinations as on slide 20.
        X = pulp.LpVariable.dicts("X", ((f, s, t) for f in F for s in S for t in T), 0)

        # Helper expression: facility f is opened (= its construction is started once).
        # Pattern: slide 36 (sum over t in T, r in R of X_r,a,t: activity a is started).
        opened = {f: pulp.lpSum([Z[(f, k, t)] for k in K for t in T]) for f in F}

        # OBJECTIVE: maximize profit =
        #   sum over f,s,t of (price_s - shipping_cost_f,s) * X_f,s,t  -  sum over f of opening_cost_f * opened_f
        # Pattern: slide 21 (problem += pulp.lpSum([P[(r,a)] * X[(r,a)] for r in R for a in A])),
        # with Maximize as on slide 16.
        self._problem += (
            pulp.lpSum([(self.unit_selling_price[s] - self.unit_shipping_cost[f][s]) * X[(f, s, t)]
                        for f in F for s in S for t in T])
            - pulp.lpSum([self.opening_costs[f] * opened[f] for f in F])
        )

        # CONSTRAINT 1 (build at most once): the construction of a facility is started at most once,
        # by at most one crew.
        #   sum over k in K, t in T of Z_f,k,t <= 1, for all f in F
        # Pattern: slide 36 (sum over t in T, r in R of X_r,a,t = 1, for all a in A: every activity is
        # started at exactly one time by exactly one resource), with "<= 1" because opening is optional.
        for f in F:
            self._problem += opened[f] <= 1

        # CONSTRAINT 2 (completed within the horizon): start period + build time <= number of periods.
        #   sum over k in K, t in T of Z_f,k,t * (t + P_f) <= |T|, for all f in F
        # Pattern: slide 36 (sum over t in T, r in R of X_r,a,t * (t + P_r,a) <= 15, for all a in A:
        # all activities must complete before the maximum time).
        for f in F:
            self._problem += pulp.lpSum([Z[(f, k, t)] * (t + P[f]) for k in K for t in T]) <= len(T)

        # CONSTRAINT 3 (one facility per crew at a time): a crew that starts facility f in period t is
        # busy in periods t .. t + P_f - 1, so in every period l it can be busy with at most one facility.
        #   sum over f in F of sum over t = l - P_f + 1 .. l of Z_f,k,t <= 1, for all k in K, l in T
        # Pattern: slide 35 (sum over a in A of sum over t = l - P_r,a + 1 .. l of X_r,a,t <= 1,
        # for all r in R, l in T: at most one activity is performed by a resource at a time).
        for k in K:
            for l in T:
                self._problem += pulp.lpSum([Z[(f, k, t)] for f in F
                                             for t in range(l - P[f] + 1, l + 1) if t in T]) <= 1

        # CONSTRAINT 4 (demand): a service area cannot receive more than its demand in each period.
        #   sum over f of X_f,s,t <= demand_s, for all s in S, t in T
        # Pattern: slide 22 (for a in A: problem += pulp.lpSum([X[(r,a)] for r in R]) == 1),
        # with "<= upper bound" instead of "== 1" as on slide 30.
        for s in S:
            for t in T:
                self._problem += pulp.lpSum([X[(f, s, t)] for f in F]) <= self.demand[s]

        # CONSTRAINT 5 (capacity once completed): in period l a facility can ship at most its capacity,
        # and only if its construction has been completed, i.e. it was started in a period t with t + P_f <= l.
        #   sum over s of X_f,s,l <= capacity_f * (sum over k in K, t = 0 .. l - P_f of Z_f,k,t), for all f in F, l in T
        # Pattern: slide 30 (sum over a in A of P_r,a * X_r,a <= 15, for all r in R: a resource can be
        # used up to its maximum availability), combined with a sum of start variables over a range of
        # periods as on slide 34 (Xl_r,a,l = sum over t = l - P_r,a + 1 .. l of X_r,a,t).
        for f in F:
            for l in T:
                completed = pulp.lpSum([Z[(f, k, t)] for k in K for t in T if t + P[f] <= l])
                self._problem += pulp.lpSum([X[(f, s, l)] for s in S]) <= self.capacity[f] * completed

        # CONSTRAINT 6 (budget): opening costs plus shipping costs over the whole horizon may not exceed the budget.
        #   sum over f of opening_cost_f * opened_f + sum over f,s,t of shipping_cost_f,s * X_f,s,t <= budget
        # Pattern: slide 13/16 (linear constraint a1*X1 + ... + an*Xn <= b, e.g. 2*X1 + 3*X2 <= 15),
        # written compactly with pulp.lpSum as on slide 21.
        self._problem += (
            pulp.lpSum([self.opening_costs[f] * opened[f] for f in F])
            + pulp.lpSum([self.unit_shipping_cost[f][s] * X[(f, s, t)] for f in F for s in S for t in T])
            <= self.budget
        )

        # Solve and read the status. Pattern: slide 16 (problem.solve(), pulp.LpStatus[problem.status]).
        self._problem.solve(pulp.PULP_CBC_CMD(msg=False))
        self.status = pulp.LpStatus[self._problem.status]

        # Allocation plan: (facility, service area, period, amount) for every non-zero shipment.
        # Pattern: slide 16 (reading v.varValue after solving).
        solution = []
        for f in F:
            for s in S:
                for t in T:
                    amount = X[(f, s, t)].varValue
                    if amount is not None and amount > 1e-6:
                        solution.append((f, s, t, float(amount)))

        # Construction schedule: (facility, crew, start period, completion period) for every opened facility.
        schedule = []
        for f in F:
            for k in K:
                for t in T:
                    if Z[(f, k, t)].varValue is not None and Z[(f, k, t)].varValue > 0.5:
                        schedule.append((f, k, t, t + P[f]))

        self._compute_statistics(solution, schedule)
        return solution, schedule

    def _compute_statistics(self, solution, schedule):
        # Helper that fills in the attributes printed by the solution check.
        self.facilities_opened = [f for f, k, start, end in schedule]

        # crew_usage[(k, t)] = number of facilities crew k is building in period t
        self.crew_usage = {(k, t): 0 for k in self.crews for t in self.periods}
        for f, k, start, end in schedule:
            for t in range(start, end):
                self.crew_usage[(k, t)] += 1

        self.demand_met = {s: 0.0 for s in self.service_areas}
        for f, s, t, amount in solution:
            self.demand_met[s] += amount
        self.demand_unmet = {s: self.demand[s] * len(self.periods) - self.demand_met[s]
                             for s in self.service_areas}

        self.total_revenue = sum(self.unit_selling_price[s] * amount for f, s, t, amount in solution)
        self.total_opening_cost = sum(self.opening_costs[f] for f in self.facilities_opened)
        self.total_shipping_cost = sum(self.unit_shipping_cost[f][s] * amount for f, s, t, amount in solution)
        self.total_profit = self.total_revenue - self.total_opening_cost - self.total_shipping_cost
        self.budget_used = self.total_opening_cost + self.total_shipping_cost


##########################
##### SOLUTION CHECK #####
##########################

print(
    "\n\nDISCLAIMER\nNote that if you pass the solution check that does not mean that you will get full points. "
    + "We will test more and different things. Also note that you should see DONE at the end of the tests. "
    + "If you do not see DONE, this means that the program got stuck somewhere and consequently does not work properly. "
    + "Finally, note that you must use all attributes and functions that are defined in the template and give them correct values according to the assignment description. "
    + "You must not change names or signatures of predefined classes, attributes or functions. Doing so may lead to severe deduction of points. "
    + "\n\nSOLUTION CHECK\n"
    + "All of the following should be True:"
)

problem = DistributionNetwork()
solution, schedule = problem.solve()
print("- Solver status:", problem.status)
print("- An optimal solution was found:", problem._problem.status == 1)
print(f"- The total profit found is: {problem.total_profit}.")
print(
    f"*  revenue {problem.total_revenue}"
    f" - opening {problem.total_opening_cost}"
    f" - shipping {problem.total_shipping_cost}"
)
print("- The solution contains an assignment:", len(solution) > 0)
print(f"- Budget used: {problem.budget_used} / {problem.budget}")
print(
    "- The allocation plan is a list of 4-tuples:",
    (
        type(solution) == list
        and all([type(sol) == tuple and len(sol) == 4 for sol in solution])
        if len(solution) > 0
        else False
    ),
)
print(
    "- The construction schedule is a list of 4-tuples:",
    (
        type(schedule) == list
        and all([type(sch) == tuple and len(sch) == 4 for sch in schedule])
        if len(schedule) > 0
        else False
    ),
)
print("- Construction schedule:")
for f, crew, start, end in schedule:
    print(f"*  {f}: built by {crew}, starts in period {start}, completed in period {end}")
print("- Facilities not opened:", [
    f for f in problem.facilities if f not in problem.facilities_opened
])

print("- Crew occupancy per period (each crew builds at most one facility at a time):")
for k in problem.crews:
    timeline = "".join(
        str(problem.crew_usage[(k, t)]) for t in problem.periods
    )
    busy = max(problem.crew_usage[(k, t)] for t in problem.periods)
    print(f"*  {k}: {timeline}  (max {busy} of 1)")

print(f"- Total demand met: {sum(problem.demand_met.values())} / "
      f"{sum(problem.demand.values()) * len(problem.periods)}")

print("- Demand fulfillment over the planning horizon:")
for s in problem.service_areas:
    met = problem.demand_met[s]
    total = problem.demand[s] * len(problem.periods)
    unmet = problem.demand_unmet[s]
    print(f"*  {s}: met {met} of {total} (unmet {unmet})")

print("- Allocation plan:")
print(solution)

print("DONE\n")